"""Asocia retroactivamente Tickets a su DolibarrTransaction de origen
para boletos generados ANTES de v1.2.0, cuando todavía no existía el FK
Ticket.dolibarr_transaction.

Heurística: cuando el webhook procesaba una factura, creaba la
DolibarrTransaction y luego los N Tickets en la MISMA transacción atómica
de DB. Eso significa que el `sold_at` de esos N tickets queda a unos
segundos del `created_at` de la transaction, y comparten el mismo customer.

El comando agrupa Tickets sin transaction asignada por (raffle, customer,
ventana temporal corta) y los matchea contra DolibarrTransactions cuya
tickets_count coincide.

Uso:
    python manage.py backfill_legacy_tickets --dry-run
    python manage.py backfill_legacy_tickets               # aplica
    python manage.py backfill_legacy_tickets --raffle 5    # acotado
    python manage.py backfill_legacy_tickets --window 120  # +/-120s
"""
import datetime as dt

from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.utils import timezone

from raffles.models import DolibarrTransaction, Ticket


class Command(BaseCommand):
    help = "Asocia Tickets pre-v1.2.0 con su DolibarrTransaction de origen por heurística temporal."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo reporta qué se haría, sin escribir.',
        )
        parser.add_argument(
            '--raffle',
            type=int,
            default=None,
            help='Limitar a una rifa específica por ID.',
        )
        parser.add_argument(
            '--window',
            type=int,
            default=60,
            help='Ventana de tolerancia temporal en segundos (default 60).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        raffle_id = options['raffle']
        window_seconds = options['window']

        window = dt.timedelta(seconds=window_seconds)

        orphan_qs = Ticket.objects.filter(dolibarr_transaction__isnull=True)
        if raffle_id is not None:
            orphan_qs = orphan_qs.filter(raffle_id=raffle_id)

        total_orphans = orphan_qs.count()
        self.stdout.write(f"Tickets sin transaction: {total_orphans}")
        if total_orphans == 0:
            self.stdout.write(self.style.SUCCESS("Nada para backfillear."))
            return

        # Solo transacciones que todavía no tengan tickets asignados.
        tx_qs = DolibarrTransaction.objects.filter(tickets__isnull=True).order_by('created_at')
        total_txs = tx_qs.count()
        self.stdout.write(f"DolibarrTransactions sin tickets asignados: {total_txs}")

        matched_tx = 0
        matched_tickets = 0
        skipped_no_tickets = 0
        skipped_mismatch = 0

        for tx in tx_qs.iterator():
            wanted = tx.tickets_count
            if wanted <= 0:
                skipped_no_tickets += 1
                continue

            # Buscar `wanted` tickets en la misma rifa cuyo sold_at quede dentro de la ventana
            # y que todavía estén huérfanos. Filtramos por raffle activa al momento del webhook,
            # pero como no la conocemos, usamos cualquier rifa.
            t_qs = (
                Ticket.objects
                .filter(dolibarr_transaction__isnull=True)
                .filter(sold_at__gte=tx.created_at - window, sold_at__lte=tx.created_at + window)
                .order_by('sold_at', 'ticket_number')
            )
            if raffle_id is not None:
                t_qs = t_qs.filter(raffle_id=raffle_id)

            candidates = list(t_qs[: wanted * 3])  # margen para descartar customer mismatch

            # Agrupar por customer y elegir el grupo del tamaño exacto wanted.
            by_customer = {}
            for t in candidates:
                by_customer.setdefault(t.customer_id, []).append(t)

            picked = None
            for cust_id, tickets_list in by_customer.items():
                if len(tickets_list) >= wanted:
                    picked = tickets_list[:wanted]
                    break

            if picked is None:
                skipped_mismatch += 1
                if total_txs <= 30:
                    self.stdout.write(self.style.WARNING(
                        f"  ↯ tx id={tx.id} ref={tx.ref} customers en ventana={list(by_customer.keys())} wanted={wanted} → no match"
                    ))
                continue

            ids = [t.id for t in picked]
            if dry_run:
                self.stdout.write(
                    f"  ✓ tx id={tx.id} ref={tx.ref} customer={picked[0].customer_id} → tickets {ids}"
                )
            else:
                with db_transaction.atomic():
                    Ticket.objects.filter(id__in=ids).update(dolibarr_transaction=tx)

            matched_tx += 1
            matched_tickets += len(ids)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Resultado: matchearon {matched_tx}/{total_txs} transactions → {matched_tickets} tickets vinculados."
        ))
        if skipped_no_tickets:
            self.stdout.write(self.style.WARNING(
                f"  (saltadas {skipped_no_tickets} transactions con tickets_count<=0)"
            ))
        if skipped_mismatch:
            self.stdout.write(self.style.WARNING(
                f"  ({skipped_mismatch} transactions sin grupo del tamaño exacto en la ventana — revisar manualmente)"
            ))

        remaining = Ticket.objects.filter(dolibarr_transaction__isnull=True)
        if raffle_id is not None:
            remaining = remaining.filter(raffle_id=raffle_id)
        self.stdout.write(f"Tickets que quedan sin transaction: {remaining.count()}")

        if dry_run:
            self.stdout.write(self.style.NOTICE("DRY-RUN: nada fue persistido. Quite --dry-run para aplicar."))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Aplicado a las {timezone.now().isoformat()}."
            ))
