from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView
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

def verify_ticket(request, qr_code):
    """
    Verifica si un boleto es válido mediante su código QR.
    """
    ticket = get_object_or_404(Ticket, qr_code=qr_code)

    context = {
        'ticket': ticket,
    }
    return render(request, 'raffles/ticket_verification.html', context)

class HomeView(TemplateView):
    template_name = 'raffles/home.html'
