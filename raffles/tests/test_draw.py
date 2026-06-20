"""Tests for the new staff-only draw panel: aleatoriedad, exclusiones,
descarte/resorteo, y comportamiento ante caída del API Dolibarr."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from raffles.models import (
    Customer,
    DolibarrInstance,
    DolibarrTransaction,
    Prize,
    Raffle,
    Ticket,
    WinnerDiscard,
)


def make_ticket(raffle, instance, ticket_number, facture_id, customer=None):
    """Helper: create one ticket linked to a DolibarrTransaction for a given instance."""
    if customer is None:
        customer = Customer.objects.create(
            first_name=f"Cliente {ticket_number}",
            identification=f"id-{ticket_number}",
        )
    tx = DolibarrTransaction.objects.create(
        instance=instance,
        ref=f"REF-{ticket_number}",
        facture_id=facture_id,
        amount=100,
        tickets_count=1,
    )
    return Ticket.objects.create(
        raffle=raffle,
        customer=customer,
        ticket_number=ticket_number,
        price=0,
        dolibarr_transaction=tx,
    )


class DrawPanelTest(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.staff = User.objects.create_user(
            username='staffer', password='pwd1234', is_staff=True,
        )
        self.non_staff = User.objects.create_user(
            username='lurker', password='pwd1234', is_staff=False,
        )
        self.raffle = Raffle.objects.create(name="Rifa Test", year=2024, is_active=True)
        self.instance = DolibarrInstance.objects.create(
            name="Hellbam",
            slug="hellbam",
            inbound_api_key="hellbam-key",
            outbound_api_url="https://erp.hellbam.test/api/index.php",
            outbound_api_key="DOLAPIKEY-X",
        )
        self.prize1 = Prize.objects.create(raffle=self.raffle, position=1, name="Premio 1")
        self.prize2 = Prize.objects.create(raffle=self.raffle, position=2, name="Premio 2")
        self.prize3 = Prize.objects.create(raffle=self.raffle, position=3, name="Premio 3")
        self.tickets = [make_ticket(self.raffle, self.instance, i, facture_id=100 + i) for i in range(1, 11)]

    def _draw_url(self, prize):
        return reverse('raffles:execute_prize_draw', args=[self.raffle.id, prize.id])

    def _discard_url(self, prize):
        return reverse('raffles:discard_winner', args=[self.raffle.id, prize.id])

    @patch('raffles.views.is_invoice_paid', return_value=True)
    def test_only_staff_can_draw(self, _mock_paid):
        self.client.login(username='lurker', password='pwd1234')
        r = self.client.post(self._draw_url(self.prize1))
        self.assertIn(r.status_code, (302, 403))  # @staff_member_required → redirect to login

    @patch('raffles.views.is_invoice_paid', return_value=True)
    def test_draw_excludes_other_prize_winners(self, _mock_paid):
        self.client.login(username='staffer', password='pwd1234')

        r1 = self.client.post(self._draw_url(self.prize1))
        self.assertEqual(r1.status_code, 200)
        winner1_id = r1.json()['ticket_id']

        r2 = self.client.post(self._draw_url(self.prize2))
        self.assertEqual(r2.status_code, 200)
        winner2_id = r2.json()['ticket_id']

        r3 = self.client.post(self._draw_url(self.prize3))
        self.assertEqual(r3.status_code, 200)
        winner3_id = r3.json()['ticket_id']

        self.assertEqual(len({winner1_id, winner2_id, winner3_id}), 3)

    @patch('raffles.views.is_invoice_paid', return_value=True)
    def test_draw_excludes_discarded(self, _mock_paid):
        self.client.login(username='staffer', password='pwd1234')

        r1 = self.client.post(self._draw_url(self.prize1))
        first_winner_id = r1.json()['ticket_id']

        # Descartar al primer ganador
        r_discard = self.client.post(self._discard_url(self.prize1), {'reason': 'no_contact', 'notes': 'No atiende'})
        self.assertEqual(r_discard.status_code, 302)
        self.assertEqual(WinnerDiscard.objects.count(), 1)
        self.prize1.refresh_from_db()
        self.assertIsNone(self.prize1.winning_ticket_id)

        # Re-sortear el premio 1 varias veces: nunca debe salir el descartado.
        for _ in range(5):
            self.prize1.winning_ticket = None
            self.prize1.save(update_fields=['winning_ticket'])
            r = self.client.post(self._draw_url(self.prize1))
            self.assertEqual(r.status_code, 200)
            self.assertNotEqual(r.json()['ticket_id'], first_winner_id)

    @patch('raffles.views.is_invoice_paid')
    def test_draw_excludes_unpaid_when_flag_on(self, mock_paid):
        """Two of ten tickets are flagged unpaid → never selected."""
        self.client.login(username='staffer', password='pwd1234')

        unpaid_ids = {self.tickets[0].id, self.tickets[1].id}

        def side_effect(ticket, force_refresh=False):
            return False if ticket.id in unpaid_ids else True

        mock_paid.side_effect = side_effect

        for _ in range(10):
            self.prize1.winning_ticket = None
            self.prize1.save(update_fields=['winning_ticket'])
            r = self.client.post(self._draw_url(self.prize1), {'exclude_unpaid': '1'})
            self.assertEqual(r.status_code, 200)
            self.assertNotIn(r.json()['ticket_id'], unpaid_ids)

    @patch('raffles.views.is_invoice_paid', return_value=None)
    def test_unverified_payment_is_treated_as_excluded_when_flag_on(self, _mock_paid):
        """If Dolibarr is down (all None), excluding unpaid drains the pool."""
        self.client.login(username='staffer', password='pwd1234')
        r = self.client.post(self._draw_url(self.prize1), {'exclude_unpaid': '1'})
        self.assertEqual(r.status_code, 409)
        self.assertIn('elegibles', r.json()['error'])

    @patch('raffles.views.is_invoice_paid', return_value=None)
    def test_can_still_draw_when_unpaid_flag_off(self, _mock_paid):
        """Operator can override and draw even with API down by clearing the flag."""
        self.client.login(username='staffer', password='pwd1234')
        r = self.client.post(self._draw_url(self.prize1), {'exclude_unpaid': '0'})
        self.assertEqual(r.status_code, 200)

    @patch('raffles.views.is_invoice_paid', return_value=True)
    def test_cannot_redraw_without_discarding_first(self, _mock_paid):
        self.client.login(username='staffer', password='pwd1234')
        self.client.post(self._draw_url(self.prize1))
        r2 = self.client.post(self._draw_url(self.prize1))
        self.assertEqual(r2.status_code, 409)
        self.assertIn('ya tiene un ganador', r2.json()['error'])


class DolibarrClientTest(TestCase):
    def setUp(self):
        self.raffle = Raffle.objects.create(name="X", year=2024)
        self.instance = DolibarrInstance.objects.create(
            name="Hellbam",
            slug="hellbam",
            inbound_api_key="hellbam-key",
            outbound_api_url="https://erp.hellbam.test/api/index.php",
            outbound_api_key="DOLAPIKEY-X",
        )

    def test_returns_none_when_no_transaction(self):
        from raffles.dolibarr_client import is_invoice_paid
        customer = Customer.objects.create(first_name="X")
        ticket = Ticket.objects.create(raffle=self.raffle, customer=customer, ticket_number=1, price=0)
        self.assertIsNone(is_invoice_paid(ticket))

    def test_returns_none_when_instance_has_no_outbound_url(self):
        from raffles.dolibarr_client import is_invoice_paid
        self.instance.outbound_api_url = ""
        self.instance.save()
        customer = Customer.objects.create(first_name="X")
        tx = DolibarrTransaction.objects.create(
            instance=self.instance, ref='R', facture_id=1, amount=100, tickets_count=1,
        )
        ticket = Ticket.objects.create(
            raffle=self.raffle, customer=customer, ticket_number=1, price=0, dolibarr_transaction=tx,
        )
        self.assertIsNone(is_invoice_paid(ticket))

    @patch('raffles.dolibarr_client._session.get')
    def test_returns_none_when_api_raises(self, mock_get):
        import requests
        from raffles.dolibarr_client import is_invoice_paid
        mock_get.side_effect = requests.ConnectionError("Dolibarr down")

        customer = Customer.objects.create(first_name="X")
        tx = DolibarrTransaction.objects.create(
            instance=self.instance, ref='R', facture_id=1, amount=100, tickets_count=1,
        )
        ticket = Ticket.objects.create(
            raffle=self.raffle, customer=customer, ticket_number=1, price=0, dolibarr_transaction=tx,
        )
        self.assertIsNone(is_invoice_paid(ticket, force_refresh=True))

    @patch('raffles.dolibarr_client._session.get')
    def test_returns_true_when_dolibarr_says_paid(self, mock_get):
        from raffles.dolibarr_client import is_invoice_paid
        mock_get.return_value.ok = True
        mock_get.return_value.json.return_value = {'paye': '1'}

        customer = Customer.objects.create(first_name="X")
        tx = DolibarrTransaction.objects.create(
            instance=self.instance, ref='R', facture_id=99, amount=100, tickets_count=1,
        )
        ticket = Ticket.objects.create(
            raffle=self.raffle, customer=customer, ticket_number=1, price=0, dolibarr_transaction=tx,
        )
        self.assertTrue(is_invoice_paid(ticket, force_refresh=True))

    @patch('raffles.dolibarr_client._session.get')
    def test_returns_false_when_dolibarr_says_unpaid(self, mock_get):
        from raffles.dolibarr_client import is_invoice_paid
        mock_get.return_value.ok = True
        mock_get.return_value.json.return_value = {'paye': '0'}

        customer = Customer.objects.create(first_name="X")
        tx = DolibarrTransaction.objects.create(
            instance=self.instance, ref='R', facture_id=99, amount=100, tickets_count=1,
        )
        ticket = Ticket.objects.create(
            raffle=self.raffle, customer=customer, ticket_number=1, price=0, dolibarr_transaction=tx,
        )
        self.assertFalse(is_invoice_paid(ticket, force_refresh=True))
