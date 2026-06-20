"""Multi-instance coexistence: two Dolibarr installs sharing one Django.

The legacy schema treated `DolibarrTransaction.ref` as a global unique key,
which would have caused false 409s as soon as both companies started emitting
invoices in parallel (each Dolibarr numbers facture_id/ref independently).
"""
from django.test import Client, TestCase
from django.urls import reverse

from raffles.models import (
    DolibarrInstance,
    DolibarrTransaction,
    Raffle,
    Ticket,
)


class MultiInstanceWebhookTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('raffles:dolibarr_webhook')
        self.raffle = Raffle.objects.create(name="Rifa Conjunta", year=2024, is_active=True)
        self.instance_a = DolibarrInstance.objects.create(
            name="Hellbam ERP",
            slug="hellbam",
            inbound_api_key="key-hellbam",
            tickets_per_amount=1,
            amount_step=100.00,
            is_active=True,
        )
        self.instance_b = DolibarrInstance.objects.create(
            name="Kama ERP",
            slug="kama",
            inbound_api_key="key-kama",
            tickets_per_amount=1,
            amount_step=100.00,
            is_active=True,
        )

    def _hdrs(self, key):
        return {'HTTP_AUTHORIZATION': f'Bearer {key}'}

    def test_two_instances_same_ref_no_collision(self):
        """Hellbam and Kama both emit ref=INV-001 — both must succeed."""
        payload = {
            'customer_identification': '0912345678',
            'customer_name': 'Cliente Compartido',
            'total_amount': 100.00,
            'ref': 'INV-001',
        }
        r_a = self.client.post(self.url, payload, content_type='application/json', **self._hdrs('key-hellbam'))
        self.assertEqual(r_a.status_code, 201)
        self.assertEqual(r_a.json()['instance'], 'hellbam')

        r_b = self.client.post(self.url, payload, content_type='application/json', **self._hdrs('key-kama'))
        self.assertEqual(r_b.status_code, 201)
        self.assertEqual(r_b.json()['instance'], 'kama')

        self.assertEqual(DolibarrTransaction.objects.count(), 2)
        self.assertEqual(Ticket.objects.count(), 2)
        self.assertEqual(DolibarrTransaction.objects.filter(instance=self.instance_a).count(), 1)
        self.assertEqual(DolibarrTransaction.objects.filter(instance=self.instance_b).count(), 1)

    def test_two_instances_same_facture_id_no_collision(self):
        """Both Dolibarr instances internally number facture_id=42 — no collision."""
        common_facture = 42
        r_a = self.client.post(
            self.url,
            {
                'customer_identification': '0912345678',
                'customer_name': 'Cliente A',
                'total_amount': 100.00,
                'ref': 'A-001',
                'facture_id': common_facture,
            },
            content_type='application/json',
            **self._hdrs('key-hellbam'),
        )
        self.assertEqual(r_a.status_code, 201)

        r_b = self.client.post(
            self.url,
            {
                'customer_identification': '0922222222',
                'customer_name': 'Cliente B',
                'total_amount': 100.00,
                'ref': 'B-001',
                'facture_id': common_facture,
            },
            content_type='application/json',
            **self._hdrs('key-kama'),
        )
        self.assertEqual(r_b.status_code, 201)

        self.assertEqual(DolibarrTransaction.objects.filter(facture_id=common_facture).count(), 2)

    def test_same_instance_duplicate_ref_returns_409(self):
        """Within ONE instance, the existing idempotency contract still holds."""
        payload = {
            'customer_identification': '0912345678',
            'customer_name': 'X',
            'total_amount': 100.00,
            'ref': 'DUP-001',
        }
        r1 = self.client.post(self.url, payload, content_type='application/json', **self._hdrs('key-hellbam'))
        self.assertEqual(r1.status_code, 201)
        r2 = self.client.post(self.url, payload, content_type='application/json', **self._hdrs('key-hellbam'))
        self.assertEqual(r2.status_code, 409)

    def test_unknown_inbound_key_returns_401(self):
        r = self.client.post(self.url, {}, content_type='application/json', **self._hdrs('not-a-real-key'))
        self.assertEqual(r.status_code, 401)

    def test_inactive_instance_returns_401(self):
        self.instance_b.is_active = False
        self.instance_b.save()
        r = self.client.post(self.url, {}, content_type='application/json', **self._hdrs('key-kama'))
        self.assertEqual(r.status_code, 401)

    def test_no_active_raffle_returns_500(self):
        self.raffle.is_active = False
        self.raffle.save()
        r = self.client.post(
            self.url,
            {'customer_identification': '0912345678', 'total_amount': 100.00, 'ref': 'X'},
            content_type='application/json',
            **self._hdrs('key-hellbam'),
        )
        self.assertEqual(r.status_code, 500)
        self.assertIn('No active raffle', r.json()['error'])

    def test_ticket_links_back_to_instance_via_transaction(self):
        """Draw panel needs ticket → transaction → instance traceability."""
        self.client.post(
            self.url,
            {
                'customer_identification': '0912345678',
                'customer_name': 'Cliente Origen',
                'total_amount': 200.00,
                'ref': 'TRACE-001',
                'facture_id': 7,
            },
            content_type='application/json',
            **self._hdrs('key-hellbam'),
        )
        tickets = Ticket.objects.all()
        self.assertEqual(tickets.count(), 2)
        for ticket in tickets:
            self.assertIsNotNone(ticket.dolibarr_transaction)
            self.assertEqual(ticket.dolibarr_transaction.instance, self.instance_a)
            self.assertEqual(ticket.dolibarr_transaction.facture_id, 7)
