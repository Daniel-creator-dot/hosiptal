"""
Fix waived invoice lines where discount_amount is insufficient (e.g. from merge).
Run: python manage.py fix_waived_lines_discount
Sets discount_amount = subtotal + tax for waived lines so line_total = 0
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from hospital.models import InvoiceLine


class Command(BaseCommand):
    help = 'Fix waived invoice lines with wrong discount_amount (e.g. 960 waived but column shows -240)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without saving',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        lines = InvoiceLine.objects.filter(
            is_deleted=False,
            waived_at__isnull=False
        ).select_related('invoice', 'service_code')
        fixed = 0
        for line in lines:
            subtotal = Decimal(str(line.quantity)) * Decimal(str(line.unit_price))
            tax = Decimal(str(line.tax_amount or 0))
            full_waive = subtotal + tax
            if Decimal(str(line.discount_amount or 0)) < full_waive:
                fixed += 1
                self.stdout.write(
                    f"  {line.invoice.invoice_number} line {line.id} {line.description[:40]}: "
                    f"discount {line.discount_amount} -> {full_waive}"
                )
                if not dry_run:
                    line.discount_amount = full_waive
                    line.save()
                    line.invoice.update_totals()
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\nDry run: {fixed} line(s) would be fixed'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\nFixed {fixed} waived line(s)'))
