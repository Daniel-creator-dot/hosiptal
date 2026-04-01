from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Report dispensed rows missing PharmacyStockDeductionLog records."

    def handle(self, *args, **options):
        from hospital.models_payment_verification import (
            PharmacyDispenseHistory,
            PharmacyStockDeductionLog,
        )
        from hospital.models_pharmacy_walkin import WalkInPharmacySaleItem

        hist_total = 0
        hist_missing = 0
        walkin_total = 0
        walkin_missing = 0

        history_qs = PharmacyDispenseHistory.objects.filter(is_deleted=False)
        hist_total = history_qs.count()
        missing_hist_qs = history_qs.exclude(
            id__in=PharmacyStockDeductionLog.objects.filter(
                source_type=PharmacyStockDeductionLog.SOURCE_DISPENSE_HISTORY,
            ).values_list('source_id', flat=True)
        )
        hist_missing = missing_hist_qs.count()

        walkin_qs = WalkInPharmacySaleItem.objects.filter(
            is_deleted=False,
            sale__is_deleted=False,
            sale__is_dispensed=True,
        )
        walkin_total = walkin_qs.count()
        missing_walkin_qs = walkin_qs.exclude(
            id__in=PharmacyStockDeductionLog.objects.filter(
                source_type=PharmacyStockDeductionLog.SOURCE_WALKIN_SALE_ITEM,
            ).values_list('source_id', flat=True)
        )
        walkin_missing = missing_walkin_qs.count()

        self.stdout.write(self.style.NOTICE("Pharmacy Stock Deduction Mismatch Check"))
        self.stdout.write(f"DispenseHistory rows: {hist_total}")
        self.stdout.write(f"DispenseHistory missing log: {hist_missing}")
        self.stdout.write(f"Dispensed walk-in sale items: {walkin_total}")
        self.stdout.write(f"Dispensed walk-in items missing log: {walkin_missing}")

        if hist_missing:
            self.stdout.write(self.style.WARNING("Sample missing DispenseHistory IDs:"))
            for row in missing_hist_qs.order_by('-created')[:20]:
                self.stdout.write(f"  - {row.id}")

        if walkin_missing:
            self.stdout.write(self.style.WARNING("Sample missing walk-in sale item IDs:"))
            for row in missing_walkin_qs.order_by('-created')[:20]:
                self.stdout.write(f"  - {row.id} (sale {row.sale_id})")

        if hist_missing == 0 and walkin_missing == 0:
            self.stdout.write(self.style.SUCCESS("No deduction mismatches found."))
        else:
            self.stdout.write(self.style.WARNING("Mismatches found. Run stock backfill where appropriate."))
