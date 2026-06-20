from django.test import Client, TestCase
from django.urls import reverse

from raffles.models import (
    Customer,
    DolibarrInstance,
    DolibarrTransaction,
    Raffle,
    Ticket,
)


class DolibarrWebhookTest(TestCase):
    """Single-instance happy paths (was test_dolibarr.py before multi-instance).
    Recreates the legacy DolibarrIntegration scenario by registering a single
    DolibarrInstance and one active Raffle."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('raffles:dolibarr_webhook')

        self.raffle = Raffle.objects.create(name="Rifa 2024", year=2024, is_active=True)
        self.instance = DolibarrInstance.objects.create(
            name="Default",
            slug="default",
            inbound_api_key="secret-key-123",
            tickets_per_amount=1,
            amount_step=100.00,
            is_active=True,
        )

    def _hdrs(self, key="secret-key-123"):
        return {'HTTP_AUTHORIZATION': f'Bearer {key}'}

    def test_unauthorized_missing_token(self):
        response = self.client.post(self.url, {}, content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_unauthorized_wrong_token(self):
        response = self.client.post(self.url, {}, content_type='application/json', HTTP_AUTHORIZATION='Bearer wrong-key')
        self.assertEqual(response.status_code, 401)

    def test_inactive_instance_returns_401(self):
        self.instance.is_active = False
        self.instance.save()
        response = self.client.post(self.url, {}, content_type='application/json', **self._hdrs())
        self.assertEqual(response.status_code, 401)

    def test_valid_ticket_creation(self):
        data = {
            'customer_identification': '0912345678',
            'customer_name': 'Juan Perez',
            'total_amount': 250.00,
            'ref': 'INV-001',
        }
        response = self.client.post(self.url, data, content_type='application/json', **self._hdrs())
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body['tickets_generated'], 2)
        self.assertEqual(body['instance'], 'default')

        customer = Customer.objects.get(identification='0912345678')
        self.assertEqual(customer.first_name, 'Juan Perez')
        self.assertEqual(Ticket.objects.count(), 2)
        # Every created ticket points back to its source transaction.
        for ticket in Ticket.objects.all():
            self.assertIsNotNone(ticket.dolibarr_transaction)
            self.assertEqual(ticket.dolibarr_transaction.instance, self.instance)

    def test_insufficient_amount(self):
        data = {
            'customer_identification': '0912345678',
            'customer_name': 'Juan Perez',
            'total_amount': 50.00,
        }
        response = self.client.post(self.url, data, content_type='application/json', **self._hdrs())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['tickets_generated'], 0)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_customer_update_logic(self):
        Customer.objects.create(identification='0999999999', first_name='Old Name')
        data = {
            'customer_identification': '0999999999',
            'customer_name': 'New Name',
            'total_amount': 100.00,
            'ref': 'INV-UP',
        }
        response = self.client.post(self.url, data, content_type='application/json', **self._hdrs())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Customer.objects.get(identification='0999999999').first_name, 'New Name')

    def test_duplicate_transaction(self):
        data = {
            'customer_identification': '0912345678',
            'total_amount': 250.00,
            'ref': 'INV-DUPLICATE-TEST',
        }
        response = self.client.post(self.url, data, content_type='application/json', **self._hdrs())
        self.assertEqual(response.status_code, 201)
        response = self.client.post(self.url, data, content_type='application/json', **self._hdrs())
        self.assertEqual(response.status_code, 409)

    def test_duplicate_by_facture_id_different_ref(self):
        data = {
            'customer_identification': '0912345678',
            'customer_name': 'Juan Perez',
            'total_amount': 200.00,
            'ref': 'FA-001',
            'facture_id': 42,
        }
        response = self.client.post(self.url, data, content_type='application/json', **self._hdrs())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['tickets_generated'], 2)
        self.assertEqual(Ticket.objects.count(), 2)

        txn = DolibarrTransaction.objects.get(ref='FA-001')
        self.assertEqual(txn.facture_id, 42)
        self.assertEqual(txn.instance, self.instance)

        data2 = {
            'customer_identification': '0912345678',
            'customer_name': 'Juan Perez',
            'total_amount': 300.00,
            'ref': 'FA-002',
            'facture_id': 42,
        }
        response = self.client.post(self.url, data2, content_type='application/json', **self._hdrs())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['tickets_previously_generated'], 2)
        self.assertEqual(Ticket.objects.count(), 2)

    def test_duplicate_by_ref_without_facture_id(self):
        data = {
            'customer_identification': '0912345678',
            'total_amount': 100.00,
            'ref': 'FA-NODUP',
        }
        response = self.client.post(self.url, data, content_type='application/json', **self._hdrs())
        self.assertEqual(response.status_code, 201)
        response = self.client.post(self.url, data, content_type='application/json', **self._hdrs())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Ticket.objects.count(), 1)

    def test_different_invoices_same_customer(self):
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
        response = self.client.post(self.url, data1, content_type='application/json', **self._hdrs())
        self.assertEqual(response.status_code, 201)
        response = self.client.post(self.url, data2, content_type='application/json', **self._hdrs())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Ticket.objects.count(), 2)

    def test_no_active_raffle_returns_500(self):
        self.raffle.is_active = False
        self.raffle.save()
        data = {
            'customer_identification': '0912345678',
            'total_amount': 100.00,
            'ref': 'NORAFFLE-001',
        }
        response = self.client.post(self.url, data, content_type='application/json', **self._hdrs())
        self.assertEqual(response.status_code, 500)
        self.assertIn('No active raffle', response.json()['error'])
