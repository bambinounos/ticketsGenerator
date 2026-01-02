from django.test import TestCase, Client
from django.urls import reverse
from raffles.models import Ticket, Raffle, Customer, TicketTemplate
import uuid

class TicketVerificationTest(TestCase):
    def setUp(self):
        self.template = TicketTemplate.objects.create(name="Test Template")
        self.raffle = Raffle.objects.create(name="Test Raffle", ticket_template=self.template)
        self.customer = Customer.objects.create(first_name="John Doe", phone="123456")
        self.ticket = Ticket.objects.create(
            raffle=self.raffle,
            customer=self.customer,
            ticket_number=1,
            price=10.0
        )

    def test_verify_valid_ticket(self):
        client = Client()
        url = reverse('raffles:verify_ticket', args=[self.ticket.qr_code])
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'raffles/ticket_verification.html')
        self.assertContains(response, "¡Boleto Válido!")
        self.assertContains(response, str(self.ticket.ticket_number))

    def test_verify_invalid_ticket_uuid(self):
        client = Client()
        random_uuid = uuid.uuid4()
        url = reverse('raffles:verify_ticket', args=[random_uuid])
        response = client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_qr_code_link_in_ticket(self):
        client = Client()
        url = reverse('raffles:generate_ticket', args=[self.ticket.id])
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        # Check if the QR code data parameter contains the verify URL
        verify_url = reverse('raffles:verify_ticket', args=[self.ticket.qr_code])
        # Note: request.get_host() in tests usually returns 'testserver'
        expected_part = f"data=http://testserver{verify_url}"
        self.assertContains(response, expected_part)
