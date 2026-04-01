"""
Reverse all pharmacy prescription bills that were sent to insurance today.
Use this when you want to bill insurance via Prescribe Sales (walk-in pharmacy
sales with payer = Insurance/Corporate) instead of consultation prescriptions.

- Waives today's InvoiceLines that are prescription-based and on an insurance/corporate invoice.
- Resets the corresponding PharmacyDispensing back to pending_payment so pharmacy can
  re-handle (e.g. via prescribe sales for insurance).

Run: python manage.py reverse_pharmacy_bills_to_insurance_today [--dry-run] [--date YYYY-MM-DD]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from hospital.models import Invoice, InvoiceLine
from hospital.models_payment_verification import PharmacyDispensing


class Command(BaseCommand):
    help = (
        "Reverse all drugs (prescription-based invoice lines) pushed to insurance today. "
        "Use prescribe sales for insurance billing instead."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only list what would be reversed; do not waive or update.',
        )
        parser.add_argument(
            '--date',
            type=str,
            default=None,
            help='Date to target (YYYY-MM-DD). Default: today.',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        date_str = options.get('date')
        if date_str:
            try:
                from datetime import datetime
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid --date; use YYYY-MM-DD'))
                return
        else:
            target_date = timezone.now().date()

        # Invoice lines: prescription-based, not waived, on an invoice whose payer is insurance/corporate, created on target date
        lines = list(
            InvoiceLine.objects.filter(
                prescription__isnull=False,
                is_deleted=False,
                waived_at__isnull=True,
                invoice__is_deleted=False,
                invoice__payer__payer_type__in=('insurance', 'private', 'nhis', 'corporate'),
                created__date=target_date,
            ).select_related('prescription', 'invoice', 'invoice__payer')
        )

        if not lines:
            self.stdout.write(
                self.style.WARNING(
                    f'No prescription-based insurance/corporate invoice lines found for date {target_date}.'
                )
            )
            return

        self.stdout.write(
            f'Found {len(lines)} prescription line(s) on insurance/corporate invoices for {target_date}:'
        )
        for line in lines:
            rx = line.prescription
            inv = line.invoice
            self.stdout.write(
                f'  - {line.description} (inv #{inv.invoice_number}, payer {getattr(inv.payer, "name", "")}) '
                f'prescription_id={rx.id if rx else "?"}'
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN: No changes made. Run without --dry-run to reverse.')
            )
            return

        waived = 0
        disp_reset = 0
        errors = []

        with transaction.atomic():
            for line in lines:
                try:
                    line.waived_at = timezone.now()
                    line.waiver_reason = 'Reversed: use prescribe sales for insurance billing'
                    line.save()
                    waived += 1
                except Exception as e:
                    errors.append(f"Line {line.id}: {e}")
                    continue

                # Reset PharmacyDispensing so prescription is back to "not sent to insurance"
                if line.prescription_id:
                    disp = PharmacyDispensing.objects.filter(
                        prescription_id=line.prescription_id,
                        is_deleted=False,
                    ).first()
                    if disp and disp.dispensing_status in ('ready_to_dispense', 'fully_dispensed', 'partially_dispensed', 'dispensed'):
                        disp.dispensing_status = 'pending_payment'
                        disp.payment_verified_at = None
                        disp.save(update_fields=['dispensing_status', 'payment_verified_at', 'modified'])
                        disp_reset += 1

            # Recalculate totals for affected invoices
            invoice_ids = set(line.invoice_id for line in lines)
            for inv_id in invoice_ids:
                try:
                    inv = Invoice.objects.get(pk=inv_id)
                    if hasattr(inv, 'update_totals'):
                        inv.update_totals()
                    elif hasattr(inv, 'calculate_totals'):
                        inv.calculate_totals()
                        inv.save(update_fields=['total_amount', 'balance', 'status'])
                except Exception as e:
                    errors.append(f"Invoice {inv_id} update_totals: {e}")

        for err in errors:
            self.stdout.write(self.style.ERROR(err))
        self.stdout.write(
            self.style.SUCCESS(
                f'Reversed {waived} line(s), reset {disp_reset} dispensing record(s) to pending_payment.'
            )
        )
        self.stdout.write(
            'Use Prescribe Sales (Pharmacy → payer = Insurance/Corporate) for insurance billing.'
        )
