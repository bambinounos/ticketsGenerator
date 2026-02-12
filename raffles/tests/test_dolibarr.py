
from django.test import TestCase, Client
from django.urls import reverse
from raffles.models import DolibarrIntegration, DolibarrTransaction, Raffle, Customer, Ticket
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

        # Verify Customer was updated with new data from Dolibarr
        c = Customer.objects.get(identification='0999999999')
        self.assertEqual(c.first_name, 'New Name')

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

    def test_duplicate_by_facture_id_different_ref(self):
        """
        Simulates: invoice validated (ref=FA-001), then edited in Dolibarr,
        then re-validated with a new ref (FA-002) but same facture_id.
        Should detect the duplicate via facture_id and return 409.
        """
        headers = {'HTTP_AUTHORIZATION': 'Bearer secret-key-123'}

        # First validation: ref=FA-001, facture_id=42
        data = {
            'customer_identification': '0912345678',
            'customer_name': 'Juan Perez',
            'total_amount': 200.00,
            'ref': 'FA-001',
            'facture_id': 42,
        }
        response = self.client.post(self.url, data, content_type='application/json', **headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['tickets_generated'], 2)
        self.assertEqual(Ticket.objects.count(), 2)

        # Verify facture_id was stored
        txn = DolibarrTransaction.objects.get(ref='FA-001')
        self.assertEqual(txn.facture_id, 42)

        # Re-validation after edit: NEW ref (FA-002) but SAME facture_id (42)
        data2 = {
            'customer_identification': '0912345678',
            'customer_name': 'Juan Perez',
            'total_amount': 300.00,
            'ref': 'FA-002',
            'facture_id': 42,
        }
        response = self.client.post(self.url, data2, content_type='application/json', **headers)
        self.assertEqual(response.status_code, 409)
        json_resp = response.json()
        self.assertEqual(json_resp['tickets_previously_generated'], 2)

        # Verify no extra tickets were created
        self.assertEqual(Ticket.objects.count(), 2)

    def test_duplicate_by_ref_without_facture_id(self):
        """Backward compatibility: duplicate detection still works with ref only."""
        headers = {'HTTP_AUTHORIZATION': 'Bearer secret-key-123'}
        data = {
            'customer_identification': '0912345678',
            'total_amount': 100.00,
            'ref': 'FA-NODUP',
        }

        response = self.client.post(self.url, data, content_type='application/json', **headers)
        self.assertEqual(response.status_code, 201)

        response = self.client.post(self.url, data, content_type='application/json', **headers)
        self.assertEqual(response.status_code, 409)

        self.assertEqual(Ticket.objects.count(), 1)

    def test_different_invoices_same_customer(self):
        """Different invoices from the same customer should each generate tickets."""
        headers = {'HTTP_AUTHORIZATION': 'Bearer secret-key-123'}

        data1 = {
            'customer_identification': '0912345678',
            'customer_name': 'Juan Perez',
            'total_amount': 100.00,
            'ref': 'FA-100',
            'facture_id': 100,
        }
        data2 = {
            'customer_identification': '0912345678',
            'customer_name': 'Juan Perez',
            'total_amount': 100.00,
            'ref': 'FA-101',
            'facture_id': 101,
        }

        response = self.client.post(self.url, data1, content_type='application/json', **headers)
        self.assertEqual(response.status_code, 201)

        response = self.client.post(self.url, data2, content_type='application/json', **headers)
        self.assertEqual(response.status_code, 201)

        self.assertEqual(Ticket.objects.count(), 2)
