import json
import logging
import secrets

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from .dolibarr_client import is_invoice_paid
from .models import (
    Customer,
    DolibarrInstance,
    DolibarrTransaction,
    Prize,
    Raffle,
    Ticket,
    WinnerDiscard,
)

logger = logging.getLogger(__name__)


def generate_ticket(request, ticket_id):
    """Genera una vista previa en HTML de un boleto específico."""
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
    """Verifica si un boleto es válido mediante su código QR."""
    ticket = get_object_or_404(Ticket, qr_code=qr_code)
    raffle = ticket.raffle

    is_winner = bool(
        raffle.prizes.filter(winning_ticket=ticket).exists()
        or (raffle.winning_ticket_id and raffle.winning_ticket_id == ticket.id)
    )
    winning_ticket = raffle.winning_ticket
    winning_prize = raffle.prizes.filter(winning_ticket=ticket).first()

    context = {
        'ticket': ticket,
        'raffle': raffle,
        'is_winner': is_winner,
        'winning_ticket': winning_ticket,
        'winning_prize': winning_prize,
        'now': timezone.now(),
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
                num = int(ticket_number)
                tickets = Ticket.objects.filter(ticket_number=num).select_related('raffle', 'customer')

                for ticket in tickets:
                    raffle = ticket.raffle
                    winning_ticket = raffle.winning_ticket
                    is_winner = bool(
                        raffle.prizes.filter(winning_ticket=ticket).exists()
                        or (winning_ticket and winning_ticket.id == ticket.id)
                    )
                    search_results.append({
                        'ticket': ticket,
                        'raffle': raffle,
                        'is_winner': is_winner,
                        'winning_ticket': winning_ticket,
                        'draw_passed': raffle.draw_datetime and raffle.draw_datetime < timezone.now(),
                    })
            except ValueError:
                context['error'] = "El número de boleto debe ser un valor numérico."

        context['ticket_number'] = ticket_number
        context['search_results'] = search_results
        return context


# -----------------------------------------------------------------------------
# Dolibarr inbound webhook (multi-instance)
# -----------------------------------------------------------------------------

def _parse_bearer(request):
    auth_header = request.headers.get('Authorization', '')
    if not auth_header:
        return None
    parts = auth_header.split(' ')
    if len(parts) == 2 and parts[0].lower() == 'bearer':
        return parts[1].strip()
    if len(parts) == 1:
        return parts[0].strip()
    return None


@method_decorator(csrf_exempt, name='dispatch')
class DolibarrWebhookView(View):
    def post(self, request, *args, **kwargs):
        logger.info("DolibarrWebhook: Received request")

        token = _parse_bearer(request)
        if not token:
            logger.warning("DolibarrWebhook: No authorization token provided")
            return JsonResponse({'error': 'Unauthorized - No token provided'}, status=401)

        try:
            instance = DolibarrInstance.objects.get(inbound_api_key=token, is_active=True)
        except DolibarrInstance.DoesNotExist:
            logger.warning(
                "DolibarrWebhook: Unknown or inactive inbound_api_key (received length=%s)",
                len(token),
            )
            return JsonResponse({'error': 'Unauthorized - Invalid API key'}, status=401)

        logger.info("DolibarrWebhook: Authentication successful - instance=%s", instance.slug)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            logger.error(f"DolibarrWebhook: Invalid JSON - {str(e)}")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        identification = data.get('customer_identification') or data.get('customer_id')
        name = data.get('customer_name', 'Unknown')
        amount_raw = data.get('total_amount', 0)
        external_id = data.get('customer_id', '')
        ref = data.get('ref', '')
        facture_id = data.get('facture_id')

        try:
            facture_id = int(facture_id) if facture_id else None
        except (ValueError, TypeError):
            facture_id = None

        logger.info(
            "DolibarrWebhook: Processing request - instance=%s ref=%s facture_id=%s customer=%s amount=%s",
            instance.slug, ref, facture_id, name, amount_raw,
        )

        if not identification:
            logger.warning("DolibarrWebhook: Missing customer identification")
            return JsonResponse({'error': 'Missing customer identification'}, status=400)

        # Idempotency: per-instance match on ref or facture_id
        existing_transaction = None
        if ref or facture_id is not None:
            qs = DolibarrTransaction.objects.filter(instance=instance)
            if ref and facture_id is not None:
                existing_transaction = qs.filter(ref=ref).first() or qs.filter(facture_id=facture_id).first()
            elif ref:
                existing_transaction = qs.filter(ref=ref).first()
            else:
                existing_transaction = qs.filter(facture_id=facture_id).first()

        if existing_transaction:
            logger.info(
                "DolibarrWebhook: Transaction already processed - instance=%s ref=%s facture_id=%s existing_ref=%s tickets_count=%s",
                instance.slug, ref, facture_id, existing_transaction.ref, existing_transaction.tickets_count,
            )
            return JsonResponse({
                'error': 'Transaction already processed',
                'ref': existing_transaction.ref,
                'tickets_previously_generated': existing_transaction.tickets_count,
            }, status=409)

        try:
            amount = float(amount_raw)
        except (ValueError, TypeError):
            logger.error(f"DolibarrWebhook: Invalid amount value - {amount_raw}")
            return JsonResponse({'error': 'Invalid amount'}, status=400)

        active_raffle = Raffle.objects.filter(is_active=True).first()
        if not active_raffle:
            logger.error("DolibarrWebhook: No active raffle configured (set Raffle.is_active=True on one row)")
            return JsonResponse({'error': 'No active raffle configured'}, status=500)

        amount_step = float(instance.amount_step)
        if amount_step <= 0:
            logger.error(f"DolibarrWebhook: Invalid amount_step configuration on instance={instance.slug} - {amount_step}")
            return JsonResponse({'error': 'Invalid configuration (amount_step)'}, status=500)

        tickets_to_generate = int(amount / amount_step) * instance.tickets_per_amount

        logger.info(
            "DolibarrWebhook: Calculated tickets - instance=%s amount=%s amount_step=%s tickets_per_amount=%s tickets_to_generate=%s",
            instance.slug, amount, amount_step, instance.tickets_per_amount, tickets_to_generate,
        )

        if tickets_to_generate <= 0:
            logger.info(
                "DolibarrWebhook: No tickets to generate (amount insufficient) - instance=%s amount=%s required=%s",
                instance.slug, amount, amount_step,
            )
            return JsonResponse({
                'message': 'No tickets generated (amount insufficient)',
                'tickets_generated': 0,
                'amount_received': amount,
                'amount_required': amount_step,
            }, status=200)

        try:
            with transaction.atomic():
                tx = None
                if ref or facture_id is not None:
                    tx = DolibarrTransaction.objects.create(
                        instance=instance,
                        ref=ref or '',
                        facture_id=facture_id,
                        amount=amount,
                        tickets_count=tickets_to_generate,
                    )
                    logger.info(
                        "DolibarrWebhook: Created transaction record - instance=%s ref=%s facture_id=%s",
                        instance.slug, ref, facture_id,
                    )

                customer_defaults = {
                    'first_name': name,
                    'email': data.get('customer_email', ''),
                    'phone': data.get('customer_phone', ''),
                    'address': data.get('customer_address', ''),
                    'additional_info': f"Imported from Dolibarr (instance={instance.slug}, ID: {external_id})",
                }

                customer, created = Customer.objects.get_or_create(
                    identification=identification,
                    defaults=customer_defaults,
                )

                if created:
                    logger.info(f"DolibarrWebhook: Created new customer - identification={identification}")
                else:
                    customer.first_name = name
                    customer.email = data.get('customer_email', customer.email)
                    customer.phone = data.get('customer_phone', customer.phone)
                    customer.address = data.get('customer_address', customer.address)
                    customer.save()
                    logger.info(f"DolibarrWebhook: Updated existing customer - identification={identification}")

                raffle = Raffle.objects.select_for_update().get(pk=active_raffle.pk)

                max_ticket = Ticket.objects.filter(raffle=raffle).aggregate(Max('ticket_number'))['ticket_number__max']
                current_number = (max_ticket or 0) + 1

                logger.info(
                    "DolibarrWebhook: Starting ticket creation - instance=%s raffle=%s starting_number=%s",
                    instance.slug, raffle.name, current_number,
                )

                created_tickets = []
                for _ in range(tickets_to_generate):
                    ticket = Ticket.objects.create(
                        raffle=raffle,
                        customer=customer,
                        ticket_number=current_number,
                        price=instance.default_ticket_price,
                        dolibarr_transaction=tx,
                    )
                    created_tickets.append(ticket.ticket_number)
                    current_number += 1

                logger.info(
                    "DolibarrWebhook: Successfully created %s tickets - instance=%s numbers=%s",
                    len(created_tickets), instance.slug, created_tickets,
                )

            return JsonResponse({
                'message': 'Tickets generated successfully',
                'customer': customer.first_name,
                'tickets_generated': len(created_tickets),
                'ticket_numbers': created_tickets,
                'raffle': raffle.name,
                'instance': instance.slug,
                'ref': ref,
            }, status=201)

        except IntegrityError as e:
            # Race: another concurrent webhook for the same (instance, ref/facture_id) won
            logger.warning(
                "DolibarrWebhook: IntegrityError (race or duplicate) - instance=%s ref=%s facture_id=%s - %s",
                instance.slug, ref, facture_id, e,
            )
            return JsonResponse({'error': 'Transaction already processed (race)'}, status=409)

        except Exception as e:
            logger.error(f"DolibarrWebhook: Error creating tickets - {str(e)}", exc_info=True)
            return JsonResponse({'error': f'Error creating tickets: {str(e)}'}, status=500)


# -----------------------------------------------------------------------------
# Draw panel (staff only)
# -----------------------------------------------------------------------------

def _eligible_pool(raffle, exclude_unpaid=True, force_refresh=False):
    """Build the queryset of tickets eligible for the next draw and a parallel
    list of unverified-payment tickets so the UI can show counters.

    Exclusions:
    - already winners in another Prize of the same raffle,
    - any ticket present in a WinnerDiscard for prizes of this raffle,
    - optionally, tickets whose source invoice is not paid in Dolibarr.
    """
    locked_winner_ids = list(
        raffle.prizes.exclude(winning_ticket__isnull=True).values_list('winning_ticket_id', flat=True)
    )
    discarded_ids = list(
        WinnerDiscard.objects.filter(prize__raffle=raffle).values_list('ticket_id', flat=True)
    )

    qs = (
        Ticket.objects
        .filter(raffle=raffle)
        .exclude(id__in=locked_winner_ids)
        .exclude(id__in=discarded_ids)
        .select_related('customer', 'dolibarr_transaction__instance')
    )

    if not exclude_unpaid:
        return list(qs), []

    eligible = []
    unverified = []
    for ticket in qs:
        status = is_invoice_paid(ticket, force_refresh=force_refresh)
        if status is True:
            eligible.append(ticket)
        elif status is None:
            unverified.append(ticket)
        # status is False -> dropped
    return eligible, unverified


@staff_member_required
def raffle_draw_dashboard(request, raffle_id):
    raffle = get_object_or_404(Raffle, pk=raffle_id)
    force = request.GET.get('refresh') == '1'

    prizes = list(raffle.prizes.select_related('winning_ticket__customer', 'winning_ticket__dolibarr_transaction__instance').order_by('position'))

    eligible, unverified = _eligible_pool(raffle, exclude_unpaid=True, force_refresh=force)
    all_pool, _ = _eligible_pool(raffle, exclude_unpaid=False, force_refresh=False)

    instances_summary = {}
    for ticket in all_pool:
        slug = ticket.dolibarr_transaction.instance.slug if ticket.dolibarr_transaction_id and ticket.dolibarr_transaction.instance_id else 'manual'
        instances_summary[slug] = instances_summary.get(slug, 0) + 1

    prize_states = []
    for prize in prizes:
        payment_status = None
        if prize.winning_ticket_id:
            payment_status = is_invoice_paid(prize.winning_ticket, force_refresh=force)
        prize_states.append({
            'prize': prize,
            'payment_status': payment_status,
            'discard_reasons': WinnerDiscard.Reason.choices,
            'discard_history': list(prize.discards.select_related('ticket', 'discarded_by').order_by('-created_at')),
        })

    context = {
        'raffle': raffle,
        'prize_states': prize_states,
        'eligible_count': len(eligible),
        'unverified_count': len(unverified),
        'total_pool_count': len(all_pool),
        'instances_summary': sorted(instances_summary.items()),
        'force_refresh_url': f"{reverse('raffles:raffle_draw_dashboard', args=[raffle.id])}?refresh=1",
        'all_drawn': all(p.winning_ticket_id for p in prizes) and bool(prizes),
        'no_prizes_yet': not prizes,
    }
    return render(request, 'raffles/draw_dashboard.html', context)


@staff_member_required
@require_POST
def execute_prize_draw(request, raffle_id, prize_id):
    raffle = get_object_or_404(Raffle, pk=raffle_id)
    exclude_unpaid = request.POST.get('exclude_unpaid', '1') == '1'

    with transaction.atomic():
        prize = (
            Prize.objects
            .select_for_update()
            .select_related('raffle')
            .get(pk=prize_id, raffle=raffle)
        )
        if prize.winning_ticket_id is not None:
            return JsonResponse({
                'error': 'Este premio ya tiene un ganador. Descártalo antes de re-sortear.',
            }, status=409)

        eligible, _ = _eligible_pool(raffle, exclude_unpaid=exclude_unpaid, force_refresh=False)
        if not eligible:
            return JsonResponse({
                'error': 'No quedan boletos elegibles en el pool (¿factura impaga, descartes previos?).',
            }, status=409)

        winner = secrets.choice(eligible)  # CSPRNG, not Mersenne Twister
        prize.winning_ticket = winner
        prize.drawn_at = timezone.now()
        prize.save(update_fields=['winning_ticket', 'drawn_at'])

    tx = winner.dolibarr_transaction
    instance_slug = tx.instance.slug if tx and tx.instance_id else None

    return JsonResponse({
        'prize_id': prize.id,
        'prize_name': prize.name,
        'prize_position': prize.position,
        'ticket_id': winner.id,
        'ticket_number': winner.ticket_number,
        'customer_name': winner.customer.first_name,
        'customer_phone': winner.customer.phone or '',
        'customer_email': winner.customer.email or '',
        'customer_identification': winner.customer.identification or '',
        'instance_slug': instance_slug,
        'drawn_at': prize.drawn_at.isoformat(),
    })


@staff_member_required
@require_POST
def discard_winner(request, raffle_id, prize_id):
    raffle = get_object_or_404(Raffle, pk=raffle_id)
    reason = request.POST.get('reason', '')
    notes = request.POST.get('notes', '').strip()

    valid_reasons = {choice for choice, _ in WinnerDiscard.Reason.choices}
    if reason not in valid_reasons:
        messages.error(request, "Motivo de descarte inválido.")
        return redirect('raffles:raffle_draw_dashboard', raffle_id=raffle.id)

    with transaction.atomic():
        prize = Prize.objects.select_for_update().get(pk=prize_id, raffle=raffle)
        if prize.winning_ticket_id is None:
            messages.warning(request, f"Premio #{prize.position} no tiene ganador para descartar.")
            return redirect('raffles:raffle_draw_dashboard', raffle_id=raffle.id)

        WinnerDiscard.objects.create(
            prize=prize,
            ticket_id=prize.winning_ticket_id,
            reason=reason,
            notes=notes,
            discarded_by=request.user,
        )
        prize.winning_ticket = None
        prize.drawn_at = None
        prize.save(update_fields=['winning_ticket', 'drawn_at'])

    messages.success(
        request,
        f"Ganador del premio #{prize.position} descartado ({WinnerDiscard.Reason(reason).label}). Podés volver a sortear.",
    )
    return redirect('raffles:raffle_draw_dashboard', raffle_id=raffle.id)


@staff_member_required
def winners_list(request, raffle_id):
    raffle = get_object_or_404(Raffle, pk=raffle_id)
    rows = []
    for prize in raffle.prizes.select_related(
        'winning_ticket__customer',
        'winning_ticket__dolibarr_transaction__instance',
    ).order_by('position'):
        ticket = prize.winning_ticket
        if ticket is None:
            continue
        tx = ticket.dolibarr_transaction
        rows.append({
            'prize': prize,
            'ticket': ticket,
            'customer': ticket.customer,
            'instance_name': tx.instance.name if tx and tx.instance_id else 'Manual',
            'payment_status': is_invoice_paid(ticket),
        })
    context = {
        'raffle': raffle,
        'rows': rows,
    }
    return render(request, 'raffles/winners_list.html', context)
