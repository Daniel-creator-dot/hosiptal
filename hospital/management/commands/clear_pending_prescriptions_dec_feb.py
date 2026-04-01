"""
Clear pending prescriptions from Dec 2025 to Feb 6 2026.
Removes them from pharmacy/cashier pending by cancelling PharmacyDispensing
and waiving InvoiceLines. Quantity returns to stock (never dispensed).

Run: python manage.py clear_pending_prescriptions_dec_feb
     python manage.py clear_pending_prescriptions_dec_feb --dry-run  # preview only
"""
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from hospital.models import Prescription, InvoiceLine, Order
from hospital.models_payment_verification import PharmacyDispensing


class Command(BaseCommand):
    help = 'Clear pending prescriptions from Dec 2025 to Feb 6 2026 (cancel dispensing, waive invoice lines)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without saving',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Clear ALL pending prescriptions (any date)',
        )
        parser.add_argument(
            '--weeks',
            type=int,
            metavar='N',
            help='Clear prescriptions from the last N weeks (e.g. --weeks 4)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        clear_all = options.get('all', False)
        weeks = options.get('weeks')

        if clear_all:
            start_date = None
            end_date = None
            prescriptions = Prescription.objects.filter(
                is_deleted=False
            ).select_related('drug', 'order__encounter__patient')
            self.stdout.write('Finding ALL prescriptions (--all mode)...')
        elif weeks:
            today = timezone.now().date()
            start_date = today - timedelta(weeks=weeks)
            end_date = today
            prescriptions = Prescription.objects.filter(
                is_deleted=False,
                created__date__gte=start_date,
                created__date__lte=end_date
            ).select_related('drug', 'order__encounter__patient')
            self.stdout.write(
                f'Finding prescriptions from last {weeks} week(s) ({start_date} to {end_date})...'
            )
        else:
            start_date = datetime(2025, 12, 1).date()
            end_date = datetime(2026, 2, 7).date()
            prescriptions = Prescription.objects.filter(
                is_deleted=False,
                created__date__gte=start_date,
                created__date__lte=end_date
            ).select_related('drug', 'order__encounter__patient')
            self.stdout.write(
                f'Finding prescriptions created between {start_date} and {end_date}...'
            )

        count = prescriptions.count()
        self.stdout.write(f'Found {count} prescription(s) in date range.')

        if count == 0:
            self.stdout.write(self.style.SUCCESS('Nothing to do.'))
            return

        disp_cancelled = 0
        lines_waived = 0
        orders_completed = 0
        affected_order_ids = set()

        with transaction.atomic():
            for rx in prescriptions:
                if rx.order_id:
                    affected_order_ids.add(rx.order_id)
                # Cancel PharmacyDispensing if exists and still pending
                try:
                    disp = rx.dispensing_record
                    if disp and disp.dispensing_status in ('pending_payment', 'ready_to_dispense'):
                        if not dry_run:
                            disp.dispensing_status = 'cancelled'
                            disp.quantity_ordered = 0
                            disp.save()
                        disp_cancelled += 1
                        self.stdout.write(
                            f'  Cancel dispensing: RX {rx.id} {rx.drug.name} x{rx.quantity} '
                            f'({rx.order.encounter.patient.full_name})'
                        )
                except PharmacyDispensing.DoesNotExist:
                    pass

                # Waive InvoiceLine if exists and not already waived
                invoice_lines = InvoiceLine.objects.filter(
                    prescription=rx,
                    is_deleted=False,
                    waived_at__isnull=True
                ).select_related('invoice')
                for line in invoice_lines:
                    if not dry_run:
                        subtotal = Decimal(str(line.quantity)) * Decimal(str(line.unit_price))
                        tax = Decimal(str(line.tax_amount or 0))
                        full_waive = subtotal + tax
                        line.discount_amount = full_waive
                        line.waived_at = timezone.now()
                        reason = f'Bulk clear: pending prescriptions' + (
                            f' (last {weeks} weeks)' if weeks else
                            f' (--all)' if clear_all else
                            ' (Dec 2025 - Feb 7 2026)'
                        )
                        line.waiver_reason = reason[:255]
                        line.save()
                        line.invoice.update_totals()
                    lines_waived += 1
                    self.stdout.write(
                        f'  Waive line: Invoice {line.invoice.invoice_number} '
                        f'{line.description[:50]}...'
                    )

            # Mark orders as completed when all prescriptions are waived/cancelled
            waived_rx_ids = set(InvoiceLine.objects.filter(
                prescription__isnull=False, is_deleted=False, waived_at__isnull=False
            ).values_list('prescription_id', flat=True))
            for order_id in affected_order_ids:
                try:
                    order = Order.objects.select_related('encounter__patient').get(
                        pk=order_id, order_type='medication', status='pending'
                    )
                    rxs = list(order.prescriptions.filter(is_deleted=False).values_list('id', flat=True))
                    if not rxs:
                        continue
                    done_count = 0
                    for rx_id in rxs:
                        if rx_id in waived_rx_ids:
                            done_count += 1
                        else:
                            try:
                                d = PharmacyDispensing.objects.get(prescription_id=rx_id)
                                if d.dispensing_status == 'cancelled' or (d.quantity_ordered or 0) <= 0:
                                    done_count += 1
                            except PharmacyDispensing.DoesNotExist:
                                pass
                    if done_count >= len(rxs) and not dry_run:
                        order.status = 'completed'
                        order.save()
                        orders_completed += 1
                        self.stdout.write(f'  Complete order: {order.id} ({order.encounter.patient.full_name})')
                except Order.DoesNotExist:
                    pass

        if dry_run:
            msg = (
                f'\nDry run: Would cancel {disp_cancelled} dispensing(s), '
                f'waive {lines_waived} invoice line(s), complete orders. Run without --dry-run to apply.'
            )
            self.stdout.write(self.style.WARNING(msg))
        else:
            msg = (
                f'\nDone. Cancelled {disp_cancelled} dispensing(s), '
                f'waived {lines_waived} invoice line(s), completed {orders_completed} order(s).'
            )
            self.stdout.write(self.style.SUCCESS(msg))
