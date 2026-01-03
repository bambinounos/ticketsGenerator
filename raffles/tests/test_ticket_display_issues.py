from django.test import TestCase, RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from raffles.models import Raffle, Ticket, Customer
import uuid

class IssueReproTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        # Create a dummy image
        self.image_name = 'test_product.png'
        image = SimpleUploadedFile(name=self.image_name, content=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82', content_type='image/png')

        self.raffle = Raffle.objects.create(name="Rifa Test", product_images=image)
        self.customer = Customer.objects.create(first_name="Juan", phone="123")
        self.ticket = Ticket.objects.create(raffle=self.raffle, customer=self.customer, ticket_number=1, price=10)

    def test_ticket_generation_content(self):
        url = reverse('raffles:generate_ticket', args=[self.ticket.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Check for full QR code (UUID)
        self.assertIn(str(self.ticket.qr_code), content, "Full QR code UUID should be present")

        # Check for product image
        self.assertIn(self.raffle.product_images.url, content, "Product image URL should be present")
