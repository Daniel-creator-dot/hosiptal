"""
Backfill pharmacy stock for dispensed sales that never created a deduction log.

Safe to re-run: uses PharmacyStockDeductionLog + reduce_pharmacy_stock_once.

Default (no args): **yesterday** in the active Django timezone.

Usage:
  python manage.py migrate
  python manage.py backfill_pharmacy_stock_from_dispensings
  python manage.py backfill_pharmacy_stock_from_dispensings --yesterday
  python manage.py backfill_pharmacy_stock_from_dispensings --since 2026-03-20 --until 2026-03-24
  python manage.py backfill_pharmacy_stock_from_dispensings --dry-run
"""
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Apply missed stock deductions for dispensed prescriptions / walk-in lines (default: yesterday)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--yesterday',
            action='store_true',
            help='Same as default: only calendar yesterday (local timezone)',
        )
        parser.add_argument(
            '--since',
            type=str,
            default=None,
            help='Start date inclusive (YYYY-MM-DD). Default: yesterday if --until omitted.',
        )
        parser.add_argument(
            '--until',
            type=str,
            default=None,
            help='End date inclusive (YYYY-MM-DD). Default: same as --since.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List rows only; do not change stock',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        tz = timezone.get_current_timezone()
        today = timezone.localdate()

        if options['since'] or options['until']:
            try:
                since_date = (
                    datetime.strptime(options['since'], '%Y-%m-%d').date()
                    if options['since']
                    else today - timedelta(days=1)
                )
                until_date = (
                    datetime.strptime(options['until'], '%Y-%m-%d').date()
                    if options['until']
                    else since_date
                )
            except ValueError as e:
                self.stderr.write(self.style.ERROR(f"Invalid date: {e}"))
                return
        else:
            # Default: yesterday
            since_date = until_date = today - timedelta(days=1)

        if until_date < since_date:
            self.stderr.write(self.style.ERROR('--until must be on or after --since'))
            return

        start_dt = timezone.make_aware(datetime.combine(since_date, time.min), tz)
        end_dt = timezone.make_aware(datetime.combine(until_date + timedelta(days=1), time.min), tz)

        self.stdout.write(
            self.style.NOTICE(
                f"Window (local TZ): {since_date} 00:00 up to (not incl.) {(until_date + timedelta(days=1))} 00:00"
            )
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no stock changes"))

        from hospital.models_payment_verification import (
            PharmacyDispensing,
            PharmacyDispenseHistory,
            PharmacyStockDeductionLog,
        )
        from hospital.models_pharmacy_walkin import WalkInPharmacySale
        from hospital.pharmacy_stock_utils import reduce_pharmacy_stock_once

        applied = 0
        skipped_logged = 0
        skipped_insurer = 0
        shortfalls = []

        # --- 1. Dispense history rows (one ledger line per dispense action) ---
        history_qs = (
            PharmacyDispenseHistory.objects.filter(
                dispensed_at__gte=start_dt,
                dispensed_at__lt=end_dt,
                is_deleted=False,
            )
            .select_related('drug', 'dispensing_record', 'prescription')
        )

        h_count = history_qs.count()
        self.stdout.write(f"PharmacyDispenseHistory in window: {h_count}")

        for h in history_qs.iterator():
            drug = h.drug or (
                getattr(h.prescription, 'drug', None) if h.prescription_id else None
            )
            if not drug and h.dispensing_record_id:
                drug = h.dispensing_record.drug_to_dispense if h.dispensing_record else None
            if not drug:
                self.stdout.write(self.style.WARNING(f"  Skip history {h.id}: no drug"))
                continue

            qty = int(h.quantity_dispensed or 0)
            if qty <= 0:
                continue

            disp_rec = h.dispensing_record
            if disp_rec and getattr(disp_rec, 'stock_reduced_at', None):
                skipped_insurer += 1
                self.stdout.write(
                    f"  Skip history {h.id}: insurer/corporate already deducted at billing"
                )
                continue

            if PharmacyStockDeductionLog.objects.filter(
                source_type=PharmacyStockDeductionLog.SOURCE_DISPENSE_HISTORY,
                source_id=h.id,
            ).exists():
                skipped_logged += 1
                self.stdout.write(f"  Skip history {h.id}: already in deduction log")
                continue

            if dry_run:
                self.stdout.write(self.style.SUCCESS(f"  [dry-run] would deduct {drug.name} x{qty} (history {h.id})"))
                applied += 1
                continue

            shortfall = reduce_pharmacy_stock_once(
                drug,
                qty,
                PharmacyStockDeductionLog.SOURCE_DISPENSE_HISTORY,
                h.id,
            )
            if shortfall > 0:
                shortfalls.append((drug.name, qty, shortfall))
            applied += 1
            self.stdout.write(f"  Deducted {drug.name} x{qty} (history {h.id})")

        # --- 2. Dispensing API / dashboard (no history row for this window) ---
        dispensings_with_history = set(
            PharmacyDispenseHistory.objects.filter(
                dispensed_at__gte=start_dt,
                dispensed_at__lt=end_dt,
                is_deleted=False,
                dispensing_record_id__isnull=False,
            ).values_list('dispensing_record_id', flat=True).distinct()
        )

        api_dispensings = (
            PharmacyDispensing.objects.filter(
                dispensed_at__gte=start_dt,
                dispensed_at__lt=end_dt,
                is_deleted=False,
                dispensing_status__in=['partially_dispensed', 'fully_dispensed', 'dispensed'],
                quantity_dispensed__gt=0,
            )
            .exclude(id__in=dispensings_with_history)
            .select_related('prescription', 'prescription__drug')
        )

        api_count = api_dispensings.count()
        self.stdout.write(f"PharmacyDispensing (no history in window): {api_count}")

        for d in api_dispensings.iterator():
            if getattr(d, 'stock_reduced_at', None):
                skipped_insurer += 1
                self.stdout.write(
                    f"  Skip dispensing {d.id}: stock_reduced_at (billing pre-deduct)"
                )
                continue

            drug = d.drug_to_dispense or (
                d.prescription.drug if d.prescription_id else None
            )
            if not drug:
                self.stdout.write(self.style.WARNING(f"  Skip dispensing {d.id}: no drug"))
                continue

            qty = int(d.quantity_dispensed or 0)
            if qty <= 0:
                continue

            if PharmacyStockDeductionLog.objects.filter(
                source_type=PharmacyStockDeductionLog.SOURCE_PHARMACY_DISPENSING,
                source_id=d.id,
            ).exists():
                skipped_logged += 1
                self.stdout.write(f"  Skip dispensing {d.id}: already in deduction log")
                continue

            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(f"  [dry-run] would deduct {drug.name} x{qty} (dispensing {d.id})")
                )
                applied += 1
                continue

            shortfall = reduce_pharmacy_stock_once(
                drug,
                qty,
                PharmacyStockDeductionLog.SOURCE_PHARMACY_DISPENSING,
                d.id,
            )
            if shortfall > 0:
                shortfalls.append((drug.name, qty, shortfall))
            applied += 1
            self.stdout.write(f"  Deducted {drug.name} x{qty} (dispensing {d.id})")

        # --- 3. Walk-in / prescribe sales ---
        walkin_qs = WalkInPharmacySale.objects.filter(
            is_dispensed=True,
            dispensed_at__gte=start_dt,
            dispensed_at__lt=end_dt,
            is_deleted=False,
        )

        w_count = walkin_qs.count()
        self.stdout.write(f"Walk-in sales dispensed in window: {w_count}")

        for sale in walkin_qs.iterator():
            for item in sale.items.filter(is_deleted=False).select_related('drug'):
                if not item.drug or item.quantity <= 0:
                    continue

                if PharmacyStockDeductionLog.objects.filter(
                    source_type=PharmacyStockDeductionLog.SOURCE_WALKIN_SALE_ITEM,
                    source_id=item.id,
                ).exists():
                    skipped_logged += 1
                    self.stdout.write(
                        f"  Skip walk-in line {item.id}: already in deduction log"
                    )
                    continue

                if dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  [dry-run] would deduct {item.drug.name} x{item.quantity} (sale {sale.sale_number})"
                        )
                    )
                    applied += 1
                    continue

                shortfall = reduce_pharmacy_stock_once(
                    item.drug,
                    item.quantity,
                    PharmacyStockDeductionLog.SOURCE_WALKIN_SALE_ITEM,
                    item.id,
                )
                if shortfall > 0:
                    shortfalls.append((item.drug.name, item.quantity, shortfall))
                applied += 1
                self.stdout.write(
                    f"  Deducted {item.drug.name} x{item.quantity} (sale {sale.sale_number})"
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Operations completed this run: {applied}"))
        self.stdout.write(f"Skipped (already logged): {skipped_logged}")
        self.stdout.write(f"Skipped (insurer pre-deduct): {skipped_insurer}")

        if shortfalls:
            self.stdout.write(self.style.WARNING("Insufficient positive stock (shortfall rows):"))
            for name, requested, short in shortfalls:
                self.stdout.write(f"  - {name}: requested {requested}, short by {short}")
