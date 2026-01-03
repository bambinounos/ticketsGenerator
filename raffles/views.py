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
