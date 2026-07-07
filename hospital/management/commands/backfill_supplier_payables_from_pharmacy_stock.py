"""
Idempotent backfill: create stock_receipt SupplierPayableLine for PharmacyStock rows
that have a supplier and positive qty * unit_cost, when no linked line exists yet.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from hospital.models import PharmacyStock
from hospital.models_supplier_payables import SupplierPayableLine, post_pharmacy_stock_supplier_payable


class Command(BaseCommand):
    help = 'Backfill supplier payable lines from existing pharmacy stock batches (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print counts only; do not write.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        qs = (
            PharmacyStock.objects.filter(is_deleted=False, supplier__isnull=False)
            .exclude(supplier_payable_line__isnull=False)
        )
        created = 0
        skipped = 0
        for stock in qs.select_related('supplier', 'created_by'):
            qty = int(stock.quantity_on_hand or 0)
            unit = Decimal(str(stock.unit_cost or 0))
            if qty <= 0 or unit <= 0:
                skipped += 1
                continue
            if dry:
                created += 1
                continue
            with transaction.atomic():
                post_pharmacy_stock_supplier_payable(
                    stock=stock,
                    quantity_added=qty,
                    unit_cost=unit,
                    supplier=stock.supplier,
                    user=stock.created_by,
                )
            created += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Would create' if dry else 'Created'} {created} line(s); skipped (zero cost/qty) {skipped}."
            )
        )
