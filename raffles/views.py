from django.shortcuts import render, get_object_or_404
from .models import Ticket

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
