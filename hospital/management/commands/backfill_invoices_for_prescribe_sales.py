"""
Backfill Invoice records for existing prescribe (walk-in pharmacy) sales
so they appear on the Invoices page (/hms/invoices/).

Run once after deploying the fix that creates invoices when new prescribe sales
are created: python manage.py backfill_invoices_for_prescribe_sales
"""
from django.core.management.base import BaseCommand

from hospital.models import Invoice
from hospital.models_pharmacy_walkin import WalkInPharmacySale
from hospital.services.pharmacy_walkin_service import WalkInPharmacyService


class Command(BaseCommand):
    help = 'Create Invoice records for prescribe sales that do not yet have one (so they show on /hms/invoices/)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only report which sales would get an invoice',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        # Sales that have at least one (non-deleted) item
        sales = WalkInPharmacySale.objects.filter(
            is_deleted=False,
            items__is_deleted=False,
        ).distinct()

        created = 0
        skipped = 0
        errors = 0
        for sale in sales:
            if not sale.items.filter(is_deleted=False).exists():
                skipped += 1
                continue
            try:
                patient = WalkInPharmacyService.ensure_sale_patient(sale)
                # Check if an invoice already exists for this sale
                has_invoice = Invoice.all_objects.filter(
                    patient=patient,
                    is_deleted=False,
                    lines__description__icontains=sale.sale_number,
                ).exclude(status__in=['cancelled', 'paid']).exists()
                if has_invoice:
                    skipped += 1
                    continue
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Would create invoice for sale {sale.sale_number} (patient {patient.full_name})'
                        )
                    )
                    created += 1
                    continue
                WalkInPharmacyService.ensure_sale_invoice(sale, patient)
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created invoice for sale {sale.sale_number} ({patient.full_name})')
                )
            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(f'Error for sale {sale.sale_number}: {e}')
                )
        self.stdout.write(
            self.style.SUCCESS(
                f'Done. Invoices created: {created}, skipped (already had invoice): {skipped}, errors: {errors}'
            )
        )
