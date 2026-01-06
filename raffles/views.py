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
        logger.info("DolibarrWebhook: Received request")

        # 1. Load Configuration
        try:
            config = DolibarrIntegration.objects.first()
        except Exception as e:
            logger.error(f"DolibarrWebhook: Failed to load configuration - {str(e)}")
            return JsonResponse({'error': 'Integration not configured'}, status=500)

        if not config:
            logger.warning("DolibarrWebhook: No configuration found")
            return JsonResponse({'error': 'Integration not configured'}, status=500)

        if not config.is_active:
            logger.info("DolibarrWebhook: Integration is disabled")
            return JsonResponse({'error': 'Integration disabled'}, status=503)

        # 2. Authenticate
        auth_header = request.headers.get('Authorization', '')
        token = None

        if auth_header:
            # Expecting "Bearer <api_key>" or just "<api_key>"
            parts = auth_header.split(' ')
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1].strip()
            elif len(parts) == 1:
                token = parts[0].strip()

        if not token:
            logger.warning("DolibarrWebhook: No authorization token provided")
            return JsonResponse({'error': 'Unauthorized - No token provided'}, status=401)

        # Normalize both API keys to string for comparison (handles UUID vs string)
        stored_api_key = str(config.api_key).strip()
        received_token = str(token).strip()

        if received_token != stored_api_key:
            logger.warning(f"DolibarrWebhook: Invalid API key (received length: {len(received_token)}, stored length: {len(stored_api_key)})")
            return JsonResponse({'error': 'Unauthorized - Invalid API key'}, status=401)

        logger.info("DolibarrWebhook: Authentication successful")

        # 3. Parse Data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            logger.error(f"DolibarrWebhook: Invalid JSON - {str(e)}")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        # Expected fields:
        # - customer_id (Dolibarr ID or Identification)
        # - customer_identification (Tax ID / CI / RUC) -> Preferred for mapping
        # - customer_name
        # - customer_email (Optional, for info)
        # - total_amount
        # - ref (Invoice/Order reference for idempotency)

        # Use 'customer_identification' if present, fallback to 'customer_id'
        identification = data.get('customer_identification') or data.get('customer_id')
        name = data.get('customer_name', 'Unknown')
        amount = data.get('total_amount', 0)

        # Determine additional info
        external_id = data.get('customer_id', '')
        ref = data.get('ref', '')  # Invoice/Order ref for idempotency

        logger.info(f"DolibarrWebhook: Processing request - ref={ref}, customer={name}, amount={amount}")

        if not identification:
            logger.warning("DolibarrWebhook: Missing customer identification")
            return JsonResponse({'error': 'Missing customer identification'}, status=400)

        # Check idempotency - prevent duplicate ticket generation for same invoice
        if ref:
            existing_transaction = DolibarrTransaction.objects.filter(ref=ref).first()
            if existing_transaction:
                logger.info(f"DolibarrWebhook: Transaction already processed - ref={ref}, tickets_count={existing_transaction.tickets_count}")
                return JsonResponse({
                    'error': 'Transaction already processed',
                    'ref': ref,
                    'tickets_previously_generated': existing_transaction.tickets_count
                }, status=409)

        try:
            amount = float(amount)
        except (ValueError, TypeError):
            logger.error(f"DolibarrWebhook: Invalid amount value - {amount}")
            return JsonResponse({'error': 'Invalid amount'}, status=400)

        # 4. Logic
        if not config.active_raffle:
            logger.error("DolibarrWebhook: No active raffle configured")
            return JsonResponse({'error': 'No active raffle configured'}, status=500)

        # Calculate tickets
        amount_step = float(config.amount_step)
        if amount_step <= 0:
            logger.error(f"DolibarrWebhook: Invalid amount_step configuration - {amount_step}")
            return JsonResponse({'error': 'Invalid configuration (amount_step)'}, status=500)

        tickets_to_generate = int(amount / amount_step) * config.tickets_per_amount

        logger.info(f"DolibarrWebhook: Calculated tickets - amount={amount}, amount_step={amount_step}, tickets_per_amount={config.tickets_per_amount}, tickets_to_generate={tickets_to_generate}")

        if tickets_to_generate <= 0:
            logger.info(f"DolibarrWebhook: No tickets to generate (amount insufficient) - amount={amount}, required={amount_step}")
            return JsonResponse({
                'message': 'No tickets generated (amount insufficient)',
                'tickets_generated': 0,
                'amount_received': amount,
                'amount_required': amount_step
            }, status=200)

        try:
            with transaction.atomic():
                # Log Transaction first to ensure idempotency inside the lock
                if ref:
                    DolibarrTransaction.objects.create(
                        ref=ref,
                        amount=amount,
                        tickets_count=tickets_to_generate
                    )
                    logger.info(f"DolibarrWebhook: Created transaction record - ref={ref}")

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

                if created:
                    logger.info(f"DolibarrWebhook: Created new customer - identification={identification}")
                else:
                    # Update existing customer information
                    customer.first_name = name
                    customer.email = data.get('customer_email', customer.email)
                    customer.phone = data.get('customer_phone', customer.phone)
                    customer.address = data.get('customer_address', customer.address)
                    customer.save()
                    logger.info(f"DolibarrWebhook: Updated existing customer - identification={identification}")

                # Generate Tickets
                created_tickets = []

                # Lock the raffle to serialize ticket numbering
                # select_for_update() ensures no other transaction can read/write to this raffle row until we finish
                raffle = Raffle.objects.select_for_update().get(pk=config.active_raffle.pk)

                max_ticket = Ticket.objects.filter(raffle=raffle).aggregate(Max('ticket_number'))['ticket_number__max']
                current_number = (max_ticket or 0) + 1

                logger.info(f"DolibarrWebhook: Starting ticket creation - raffle={raffle.name}, starting_number={current_number}")

                for _ in range(tickets_to_generate):
                    ticket = Ticket.objects.create(
                        raffle=raffle,
                        customer=customer,
                        ticket_number=current_number,
                        price=config.default_ticket_price
                    )
                    created_tickets.append(ticket.ticket_number)
                    current_number += 1

                logger.info(f"DolibarrWebhook: Successfully created {len(created_tickets)} tickets - numbers={created_tickets}")

            return JsonResponse({
                'message': 'Tickets generated successfully',
                'customer': customer.first_name,
                'tickets_generated': len(created_tickets),
                'ticket_numbers': created_tickets,
                'raffle': raffle.name,
                'ref': ref
            }, status=201)

        except Exception as e:
            logger.error(f"DolibarrWebhook: Error creating tickets - {str(e)}", exc_info=True)
            return JsonResponse({'error': f'Error creating tickets: {str(e)}'}, status=500)
