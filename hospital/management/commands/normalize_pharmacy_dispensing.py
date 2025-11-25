from django.core.management.base import BaseCommand
from django.db import transaction

from hospital.models_payment_verification import PharmacyDispensing


class Command(BaseCommand):
    help = "Normalize pharmacy dispensing records so statuses match dispensed quantities and payments."

    def handle(self, *args, **options):
        updated = 0

        qs = PharmacyDispensing.objects.filter(is_deleted=False).order_by('created').select_related('prescription', 'patient')
        total = qs.count()

        self.stdout.write(f"Normalizing {total} dispensing record(s)...")

        for record in qs.iterator():
            old_status = record.dispensing_status
            old_dispensed = record.quantity_dispensed

            record._sync_status_from_numbers()

            if record.dispensing_status != old_status:
                with transaction.atomic():
                    record.save(update_fields=['dispensing_status'])
                updated += 1
                self.stdout.write(
                    f"- {record.prescription_id}: {old_status} -> {record.dispensing_status} "
                    f"(dispensed {old_dispensed}/{record.quantity_ordered})"
                )

        self.stdout.write(self.style.SUCCESS(f"Normalization complete. Updated {updated} record(s)."))










