from django.test import TestCase
from django.urls import reverse
from raffles.models import Customer, Raffle, Ticket, TicketTemplate

class TicketGenerationTests(TestCase):

    def setUp(self):
        """Set up the necessary objects for testing."""
        self.customer = Customer.objects.create(
            first_name="John Doe",
            address="123 Main St",
            phone="555-1234"
        )
        self.template = TicketTemplate.objects.create(
            name="Test Template",
            background_color="#DDDDDD",
            font_color="#111111"
        )
        self.raffle = Raffle.objects.create(
            name="Test Raffle",
            year=2024,
            description="A test raffle.",
            ticket_template=self.template
        )
        self.ticket = Ticket.objects.create(
            raffle=self.raffle,
            customer=self.customer,
            ticket_number=1,
            price=10.00
        )

    def test_generate_ticket_view(self):
        """Test that the generate_ticket view returns a 200 OK response and uses the correct template."""
        url = reverse('raffles:generate_ticket', args=[self.ticket.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'raffles/ticket.html')

    def test_ticket_content(self):
        """Test that the rendered ticket contains the correct information."""
        url = reverse('raffles:generate_ticket', args=[self.ticket.id])
        response = self.client.get(url)
        self.assertContains(response, self.raffle.name)
        self.assertContains(response, self.ticket.ticket_number)
        self.assertContains(response, self.customer.first_name)
        self.assertContains(response, self.template.background_color)
        self.assertContains(response, self.template.font_color)

    def test_raffle_can_have_no_template(self):
        """Test that a raffle can exist without a template and the ticket still renders."""
        raffle_no_template = Raffle.objects.create(
            name="No Template Raffle",
            year=2024
        )
        ticket_no_template = Ticket.objects.create(
            raffle=raffle_no_template,
            customer=self.customer,
            ticket_number=2,
            price=5.00
        )
        url = reverse('raffles:generate_ticket', args=[ticket_no_template.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Check for default colors in the template
        self.assertContains(response, '#FFFFFF') # default background
        self.assertContains(response, '#000000') # default font color

    def test_qr_code_generation(self):
        """Test that the QR code URL is correctly generated in the template."""
        url = reverse('raffles:generate_ticket', args=[self.ticket.id])
        response = self.client.get(url)
        verify_url = reverse('raffles:verify_ticket', args=[self.ticket.qr_code])
        # We expect the template to contain the API URL that embeds our verify URL
        expected_qr_api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=100x100&data=http://testserver{verify_url}"
        self.assertContains(response, expected_qr_api_url)