"""
Backfill Dr Inventories (1400) / Cr Trade Payables (2100) for pharmacy stock
batches missing receipt journals, and create supplier payable sub-ledger lines.
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from hospital.models import PharmacyStock
from hospital.models_supplier_payables import (
    SupplierPayableLine,
    post_pharmacy_stock_supplier_payable,
)
from hospital.services.inventory_gl_service import (
    _existing_posted_entry,
    post_pharmacy_stock_receipt_gl,
)


def _receipt_qty(stock):
    """Prefer initial receipt qty so dispensed batches are not under-valued."""
    initial = int(stock.initial_quantity or 0)
    on_hand = int(stock.quantity_on_hand or 0)
    return max(initial, on_hand, 0)


class Command(BaseCommand):
    help = (
        'Backfill pharmacy stock receipt GL (1400/2100) and supplier payables '
        'for batches missing Trade Payables / supplier account capture'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--since',
            default='2026-03-01',
            help='Only batches created on/after this date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--until',
            default=None,
            help='Only batches created on/before this date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report only; do not post journals',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=5000,
            help='Max batches to process (default 5000)',
        )

    def handle(self, *args, **options):
        since = date.fromisoformat(options['since'])
        until = date.fromisoformat(options['until']) if options['until'] else None
        dry_run = options['dry_run']
        limit = options['limit']

        qs = PharmacyStock.objects.filter(
            is_deleted=False, created__date__gte=since
        )
        if until:
            qs = qs.filter(created__date__lte=until)
        qs = qs.select_related('drug', 'supplier', 'created_by').order_by('created')[:limit]

        gl_posted = 0
        gl_skipped = 0
        payable_posted = 0
        value_gl = Decimal('0.00')
        value_pay = Decimal('0.00')

        for stock in qs:
            qty = _receipt_qty(stock)
            unit = Decimal(str(stock.unit_cost or 0))
            total = (Decimal(qty) * unit).quantize(Decimal('0.01'))
            if total <= 0:
                gl_skipped += 1
                continue

            ref = f'STOCK-RCV-{stock.pk}'
            has_gl = bool(_existing_posted_entry(ref))
            has_payable = SupplierPayableLine.objects.filter(
                pharmacy_stock=stock, is_deleted=False
            ).exists()

            if dry_run:
                if not has_gl or (stock.supplier_id and not has_payable):
                    self.stdout.write(
                        f'Would fix {stock.created.date()} '
                        f'{stock.drug.name if stock.drug_id else "?"} '
                        f'GHS {total} GL={has_gl} payable={has_payable} '
                        f'supplier={getattr(stock.supplier, "name", None)}'
                    )
                if not has_gl:
                    gl_posted += 1
                    value_gl += total
                if stock.supplier_id and not has_payable:
                    payable_posted += 1
                    value_pay += total
                continue

            if not has_gl:
                # Temporarily align on-hand for helper that multiplies qty * unit_cost
                # by posting with explicit qty via wrapper that uses quantity_added.
                result = post_pharmacy_stock_receipt_gl(
                    stock, qty, unit, user=getattr(stock, 'created_by', None)
                )
                if result.get('posted') or result.get('already_posted'):
                    gl_posted += 1
                    value_gl += total
                else:
                    gl_skipped += 1
                    self.stdout.write(
                        self.style.WARNING(f'GL skip {stock.pk}: {result.get("message")}')
                    )
            else:
                gl_skipped += 1

            if stock.supplier_id and not has_payable:
                line = post_pharmacy_stock_supplier_payable(
                    stock=stock,
                    quantity_added=qty,
                    unit_cost=unit,
                    supplier=stock.supplier,
                    user=getattr(stock, 'created_by', None),
                )
                if line:
                    payable_posted += 1
                    value_pay += total

        mode = 'DRY RUN' if dry_run else 'LIVE'
        self.stdout.write(
            self.style.SUCCESS(
                f'{mode}: GL posted/fixed={gl_posted} (GHS {value_gl}), '
                f'GL skipped={gl_skipped}, payables added={payable_posted} (GHS {value_pay})'
            )
        )
