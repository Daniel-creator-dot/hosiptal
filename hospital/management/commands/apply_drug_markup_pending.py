"""
Apply 50% drug markup to all pending insurance and corporate bills.

Drug prices for insurance and corporate were increased from 15% to 50% markup.
This command updates existing pending (unpaid/partially paid) invoices and
prescribe sales so they use the new 50% markup.

Run: python manage.py apply_drug_markup_pending [--dry-run]
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Q

from hospital.models import Invoice, InvoiceLine
from hospital.models_pharmacy_walkin import WalkInPharmacySale, WalkInPharmacySaleItem
from hospital.services.pharmacy_walkin_service import WalkInPharmacyService
from hospital.utils_billing import DRUG_INSURANCE_CORPORATE_MARKUP


# When upgrading from 15% to 50%: new_price = old_price * (1.5 / 1.15)
UPGRADE_MARKUP_MULTIPLIER = (Decimal('1') + DRUG_INSURANCE_CORPORATE_MARKUP) / Decimal('1.15')


class Command(BaseCommand):
    help = 'Apply 50%% drug markup to all pending insurance and corporate invoices and prescribe sales'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only report what would be updated',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN – no changes will be saved'))

        insurance_corporate_types = ('insurance', 'private', 'nhis', 'corporate')

        # 1. Pending prescribe sales (insurance/corporate): update sale items then sync to invoice
        pending_sales = WalkInPharmacySale.objects.filter(
            is_deleted=False,
            payment_status__in=('pending', 'partial'),
            amount_due__gt=0,
            waived_at__isnull=True,
        ).filter(
            Q(payer__payer_type__in=insurance_corporate_types)
        ).select_related('payer').prefetch_related('items')

        sale_items_updated = 0
        sales_updated = 0
        for sale in pending_sales:
            if not sale.payer or getattr(sale.payer, 'payer_type', None) not in insurance_corporate_types:
                continue
            updated_this_sale = 0
            for item in sale.items.filter(is_deleted=False, waived_at__isnull=True):
                old_price = item.unit_price
                new_price = (old_price * UPGRADE_MARKUP_MULTIPLIER).quantize(Decimal('0.01'))
                if new_price == old_price:
                    continue
                sale_items_updated += 1
                updated_this_sale += 1
                if not dry_run:
                    item.unit_price = new_price
                    item.line_total = Decimal(str(item.quantity)) * new_price
                    item.save(update_fields=['unit_price', 'line_total', 'modified'])
            if updated_this_sale > 0:
                if not dry_run:
                    sale.calculate_totals()
                    try:
                        patient = WalkInPharmacyService.ensure_sale_patient(sale)
                        WalkInPharmacyService.ensure_sale_invoice(sale, patient)
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'ensure_sale_invoice for {sale.sale_number}: {e}')
                        )
                sales_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Prescribe sales: {sale_items_updated} item(s) updated on {sales_updated} sale(s)'
            )
        )

        # 2. Pending invoices (insurance/corporate, balance > 0): update drug lines
        pending_invoices = Invoice.objects.filter(
            is_deleted=False,
            status__in=('issued', 'draft', 'partially_paid'),
        ).exclude(balance__lte=0).filter(
            payer__payer_type__in=insurance_corporate_types,
        ).select_related('payer').prefetch_related('lines__service_code')

        inv_lines_updated = 0
        invoices_updated = 0
        for invoice in pending_invoices:
            if not invoice.payer or getattr(invoice.payer, 'payer_type', None) not in insurance_corporate_types:
                continue
            lines = invoice.lines.filter(
                is_deleted=False,
                waived_at__isnull=True,
            ).select_related('service_code')
            updated_this_inv = 0
            for line in lines:
                if not line.service_code:
                    continue
                code = (line.service_code.code or '').strip()
                category = (getattr(line.service_code, 'category', None) or '').lower()
                is_drug_line = (
                    code.startswith('WALKIN-') or
                    'pharmacy' in category or
                    'drug' in category
                )
                if not is_drug_line:
                    continue
                old_unit = line.unit_price
                new_unit = (old_unit * UPGRADE_MARKUP_MULTIPLIER).quantize(Decimal('0.01'))
                if new_unit == old_unit:
                    continue
                updated_this_inv += 1
                if not dry_run:
                    line.unit_price = new_unit
                    line.save(update_fields=['unit_price', 'modified'])
            if updated_this_inv:
                inv_lines_updated += updated_this_inv
                if not dry_run:
                    invoice.update_totals()
                invoices_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Invoices: {inv_lines_updated} drug line(s) updated on {invoices_updated} invoice(s)'
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING('Dry run complete. Run without --dry-run to apply changes.')
            )
        else:
            self.stdout.write(self.style.SUCCESS('Done. 50% drug markup applied to all pending insurance/corporate.'))
