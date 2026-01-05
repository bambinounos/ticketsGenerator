from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView
from django.utils import timezone
from .models import Ticket, Raffle

def generate_ticket(request, ticket_id):
    """
    Genera una vista previa en HTML de un boleto específico.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id)
    raffle = ticket.raffle
    template = raffle.ticket_template

    context = {
        'ticket': ticket,
        'raffle': raffle,
        'template': template,
    }
    return render(request, 'raffles/ticket.html', context)

def verify_ticket(request, qr_code):
    """
    Verifica si un boleto es válido mediante su código QR.
    """
    ticket = get_object_or_404(Ticket, qr_code=qr_code)
    raffle = ticket.raffle

    # Check if raffle is completed (has a winning ticket)
    is_winner = False
    winning_ticket = raffle.winning_ticket
    if winning_ticket and winning_ticket.id == ticket.id:
        is_winner = True

    context = {
        'ticket': ticket,
        'raffle': raffle,
        'is_winner': is_winner,
        'winning_ticket': winning_ticket,
        'now': timezone.now()
    }
    return render(request, 'raffles/ticket_verification.html', context)

class HomeView(TemplateView):
    template_name = 'raffles/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ticket_number = self.request.GET.get('ticket_number')

        search_results = []
        if ticket_number:
            try:
                # Assuming ticket_number is an integer
                num = int(ticket_number)
                tickets = Ticket.objects.filter(ticket_number=num).select_related('raffle', 'customer')

                for ticket in tickets:
                    raffle = ticket.raffle
                    winning_ticket = raffle.winning_ticket
                    is_winner = False
                    if winning_ticket and winning_ticket.id == ticket.id:
                        is_winner = True

                    search_results.append({
                        'ticket': ticket,
                        'raffle': raffle,
                        'is_winner': is_winner,
                        'winning_ticket': winning_ticket,
                        'draw_passed': raffle.draw_datetime and raffle.draw_datetime < timezone.now()
                    })
            except ValueError:
                context['error'] = "El número de boleto debe ser un valor numérico."

        context['ticket_number'] = ticket_number
        context['search_results'] = search_results
        return context

import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.db import transaction
from django.db.models import Max
from .models import DolibarrIntegration, Customer, Ticket, DolibarrTransaction, Raffle

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class DolibarrWebhookView(View):
    def post(self, request, *args, **kwargs):
        # 1. Load Configuration
        try:
            config = DolibarrIntegration.objects.first()
        except Exception:
            return JsonResponse({'error': 'Integration not configured'}, status=500)

        if not config or not config.is_active:
            return JsonResponse({'error': 'Integration disabled'}, status=503)

        # 2. Authenticate
        auth_header = request.headers.get('Authorization')
        # Expecting "Bearer <api_key>" or just "<api_key>"
        token = auth_header.split(' ')[1] if auth_header and ' ' in auth_header else auth_header

        if token != config.api_key:
            return JsonResponse({'error': 'Unauthorized'}, status=401)

        # 3. Parse Data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        # Expected fields:
        # - customer_id (Dolibarr ID or Identification)
        # - customer_identification (Tax ID / CI / RUC) -> Preferred for mapping
        # - customer_name
        # - customer_email (Optional, for info)
        # - total_amount

        # Use 'customer_identification' if present, fallback to 'customer_id'
        identification = data.get('customer_identification') or data.get('customer_id')
        name = data.get('customer_name', 'Unknown')
        amount = data.get('total_amount', 0)

        # Determine additional info
        external_id = data.get('customer_id', '')
        ref = data.get('ref', '') # Invoice/Order ref

        if not identification:
             return JsonResponse({'error': 'Missing customer identification'}, status=400)

        if ref and DolibarrTransaction.objects.filter(ref=ref).exists():
             return JsonResponse({'error': 'Transaction already processed'}, status=409)

        try:
            amount = float(amount)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid amount'}, status=400)

        # 4. Logic
        if not config.active_raffle:
             return JsonResponse({'error': 'No active raffle configured'}, status=500)

        # Calculate tickets
        tickets_to_generate = int(amount / float(config.amount_step)) * config.tickets_per_amount

        if tickets_to_generate <= 0:
            return JsonResponse({
                'message': 'No tickets generated (amount insufficient)',
                'tickets_generated': 0
            }, status=200)

        with transaction.atomic():
            # Log Transaction first to ensure idempotency inside the lock
            if ref:
                DolibarrTransaction.objects.create(
                    ref=ref,
                    amount=amount,
                    tickets_count=tickets_to_generate
                )

            # Find or Create Customer
            customer_defaults = {
                'first_name': name,
                'email': data.get('customer_email', ''),
                'phone': data.get('customer_phone', ''),
                'address': data.get('customer_address', ''),
                'additional_info': f"Imported from Dolibarr (ID: {external_id})"
            }

            customer, created = Customer.objects.get_or_create(
                identification=identification,
                defaults=customer_defaults
            )

            if not created:
                # Update existing customer information
                customer.first_name = name
                customer.email = data.get('customer_email', customer.email)
                customer.phone = data.get('customer_phone', customer.phone)
                customer.address = data.get('customer_address', customer.address)
                customer.save()

            # Generate Tickets
            created_tickets = []

            # Lock the raffle to serialize ticket numbering
            # select_for_update() ensures no other transaction can read/write to this raffle row until we finish
            _ = Raffle.objects.select_for_update().get(pk=config.active_raffle.pk)

            max_ticket = Ticket.objects.filter(raffle=config.active_raffle).aggregate(Max('ticket_number'))['ticket_number__max']
            current_number = (max_ticket or 0) + 1

            for _ in range(tickets_to_generate):
                ticket = Ticket.objects.create(
                    raffle=config.active_raffle,
                    customer=customer,
                    ticket_number=current_number,
                    price=config.default_ticket_price
                )
                created_tickets.append(ticket.ticket_number)
                current_number += 1

        return JsonResponse({
            'message': 'Tickets generated successfully',
            'customer': customer.first_name,
            'tickets_generated': len(created_tickets),
            'ticket_numbers': created_tickets,
            'raffle': config.active_raffle.name
        }, status=201)
