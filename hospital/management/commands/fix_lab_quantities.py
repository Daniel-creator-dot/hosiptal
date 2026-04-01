"""
Reset inflated lab line quantities to 1. Run after deploying the lab-quantity fix.
Run: python manage.py fix_lab_quantities [--dry-run]
Use when lab quantities were incorrectly increased (e.g. 12 instead of 1) from repeated create_lab_bill calls.
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from hospital.models import InvoiceLine, ServiceCode


class Command(BaseCommand):
    help = 'Reset lab invoice line quantities to 1 (fixes inflation from repeated billing calls)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would change without saving')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        lab_codes = ServiceCode.objects.filter(code__startswith='LAB-', is_deleted=False).values_list('pk', flat=True)
        lines = InvoiceLine.objects.filter(
            service_code_id__in=lab_codes,
            quantity__gt=1,
            is_deleted=False
        ).select_related('invoice', 'service_code')
        fixed = 0
        for line in lines:
            fixed += 1
            self.stdout.write(
                f"  {line.invoice.invoice_number} {line.service_code.code}: "
                f"qty {line.quantity} -> 1"
            )
            if not dry_run:
                line.quantity = Decimal('1.00')
                line.line_total = line.unit_price * Decimal('1.00')
                line.save()
                line.invoice.update_totals()
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\nDry run: {fixed} line(s) would be reset to qty 1'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\nFixed {fixed} lab line(s)'))
