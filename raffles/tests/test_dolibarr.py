
from django.test import TestCase, Client
from django.urls import reverse
from raffles.models import DolibarrIntegration, Raffle, Customer, Ticket
import json

class DolibarrIntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('raffles:dolibarr_webhook')

        # Setup Data
        self.raffle = Raffle.objects.create(name="Rifa 2024", year=2024)
        self.config = DolibarrIntegration.objects.create(
            api_key="secret-key-123",
            active_raffle=self.raffle,
            tickets_per_amount=1,
            amount_step=100.00,
            is_active=True
        )

    def test_unauthorized(self):
        response = self.client.post(self.url, {}, content_type='application/json')
        self.assertEqual(response.status_code, 401)

        response = self.client.post(self.url, {}, content_type='application/json', HTTP_AUTHORIZATION='Bearer wrong-key')
        self.assertEqual(response.status_code, 401)

    def test_disabled_integration(self):
        self.config.is_active = False
        self.config.save()

        headers = {'HTTP_AUTHORIZATION': 'Bearer secret-key-123'}
        response = self.client.post(self.url, {}, content_type='application/json', **headers)
        self.assertEqual(response.status_code, 503)

    def test_valid_ticket_creation(self):
        headers = {'HTTP_AUTHORIZATION': 'Bearer secret-key-123'}
        data = {
            'customer_identification': '0912345678',
            'customer_name': 'Juan Perez',
            'total_amount': 250.00, # Should generate 2 tickets (250 // 100 * 1)
            'ref': 'INV-001'
        }

        response = self.client.post(self.url, data, content_type='application/json', **headers)

        self.assertEqual(response.status_code, 201)
        json_resp = response.json()
        self.assertEqual(json_resp['tickets_generated'], 2)

        # Verify DB
        customer = Customer.objects.get(identification='0912345678')
        self.assertEqual(customer.first_name, 'Juan Perez')
        self.assertEqual(Ticket.objects.count(), 2)
        self.assertEqual(Ticket.objects.first().customer, customer)

    def test_insufficient_amount(self):
        headers = {'HTTP_AUTHORIZATION': 'Bearer secret-key-123'}
        data = {
            'customer_identification': '0912345678',
            'customer_name': 'Juan Perez',
            'total_amount': 50.00, # < 100
        }

        response = self.client.post(self.url, data, content_type='application/json', **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['tickets_generated'], 0)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_customer_update_logic(self):
        # Create customer first
        Customer.objects.create(identification='0999999999', first_name='Old Name')

        headers = {'HTTP_AUTHORIZATION': 'Bearer secret-key-123'}
        data = {
            'customer_identification': '0999999999',
            'customer_name': 'New Name',
            'total_amount': 100.00,
        }

        response = self.client.post(self.url, data, content_type='application/json', **headers)
        self.assertEqual(response.status_code, 201)

        # Verify Customer was NOT overwritten (based on current logic to preserve manual edits)
        # Note: If we change logic to update, update this test.
        c = Customer.objects.get(identification='0999999999')
        self.assertEqual(c.first_name, 'Old Name')

    def test_duplicate_transaction(self):
        headers = {'HTTP_AUTHORIZATION': 'Bearer secret-key-123'}
        data = {
            'customer_identification': '0912345678',
            'total_amount': 250.00,
            'ref': 'INV-DUPLICATE-TEST'
        }

        # First request: Success
        response = self.client.post(self.url, data, content_type='application/json', **headers)
        self.assertEqual(response.status_code, 201)

        # Second request: Conflict
        response = self.client.post(self.url, data, content_type='application/json', **headers)
        self.assertEqual(response.status_code, 409)
