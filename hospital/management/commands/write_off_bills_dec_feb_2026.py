"""
Write off all bills from December 1, 2025 through February 28, 2026.
Soft-deletes Invoices, Bills, related lines, receipts, transactions, and ambulance bills
in that date range so they no longer appear in lists (system starting fresh in March 2026).

Run: python manage.py write_off_bills_dec_feb_2026
     python manage.py write_off_bills_dec_feb_2026 --dry-run   # preview only
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from hospital.models import Invoice, InvoiceLine
from hospital.models_accounting import Transaction, PaymentReceipt, PaymentAllocation, AccountsReceivable
from hospital.models_workflow import Bill
from hospital.models_ambulance import AmbulanceBilling


# Date range: December 1, 2025 through February 28, 2026 (inclusive)
START_DATE = date(2025, 12, 1)
END_DATE = date(2026, 2, 28)


class Command(BaseCommand):
    help = (
        'Write off (soft-delete) all bills from December 1, 2025 to February 28, 2026 '
        'so they do not appear in lists (fresh start in March).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show counts and what would be written off without saving.',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        self.stdout.write(
            f'Date range: {START_DATE} through {END_DATE} (inclusive)\n'
        )

        # Invoices by issued_at date (use all_objects to include write-off period; default manager hides them)
        invoices_qs = Invoice.all_objects.filter(
            is_deleted=False,
            issued_at__date__gte=START_DATE,
            issued_at__date__lte=END_DATE,
        )
        invoice_count = invoices_qs.count()
        invoice_ids = list(invoices_qs.values_list('id', flat=True))

        # Bills by issued_at date (include those not linked to our invoices, e.g. standalone)
        bills_qs = Bill.objects.filter(
            is_deleted=False,
            issued_at__date__gte=START_DATE,
            issued_at__date__lte=END_DATE,
        )
        bill_count = bills_qs.count()

        # Ambulance billing: by invoice_date or created in range
        ambulance_qs = AmbulanceBilling.objects.filter(
            is_deleted=False,
        ).filter(
            Q(invoice_date__date__gte=START_DATE, invoice_date__date__lte=END_DATE)
            | Q(created__date__gte=START_DATE, created__date__lte=END_DATE)
        )
        ambulance_count = ambulance_qs.count()

        if not invoice_ids:
            line_count = 0
            receipt_count = 0
            txn_count = 0
            allocation_count = 0
            ar_count = 0
        else:
            line_count = InvoiceLine.objects.filter(
                is_deleted=False,
                invoice_id__in=invoice_ids,
            ).count()
            receipt_count = PaymentReceipt.objects.filter(
                is_deleted=False,
                invoice_id__in=invoice_ids,
            ).count()
            txn_count = Transaction.objects.filter(
                is_deleted=False,
                invoice_id__in=invoice_ids,
            ).count()
            allocation_count = PaymentAllocation.objects.filter(
                is_deleted=False,
                invoice_id__in=invoice_ids,
            ).count()
            ar_count = AccountsReceivable.objects.filter(
                is_deleted=False,
                invoice_id__in=invoice_ids,
            ).count()

        self.stdout.write(
            f'Would write off:\n'
            f'  Invoices:         {invoice_count}\n'
            f'  Invoice lines:    {line_count}\n'
            f'  Bills:            {bill_count}\n'
            f'  Payment receipts: {receipt_count}\n'
            f'  Transactions:     {txn_count}\n'
            f'  Payment allocs:   {allocation_count}\n'
            f'  AR entries:       {ar_count}\n'
            f'  Ambulance bills:  {ambulance_count}\n'
        )

        if invoice_count == 0 and bill_count == 0 and ambulance_count == 0:
            self.stdout.write(self.style.SUCCESS('Nothing in range to write off.'))
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '\nDry run: no changes made. Run without --dry-run to write off these records.'
                )
            )
            return

        with transaction.atomic():
            # 1. Accounts receivable entries for these invoices
            if invoice_ids:
                updated = AccountsReceivable.objects.filter(
                    is_deleted=False,
                    invoice_id__in=invoice_ids,
                ).update(is_deleted=True)
                if updated:
                    self.stdout.write(f'  AR entries: {updated}')

            # 2. Payment allocations (reference invoice)
            updated = PaymentAllocation.objects.filter(
                is_deleted=False,
                invoice_id__in=invoice_ids,
            ).update(is_deleted=True)
            if updated:
                self.stdout.write(f'  Payment allocations: {updated}')

            # 3. Transactions
            updated = Transaction.objects.filter(
                is_deleted=False,
                invoice_id__in=invoice_ids,
            ).update(is_deleted=True)
            if updated:
                self.stdout.write(f'  Transactions: {updated}')

            # 4. Payment receipts
            updated = PaymentReceipt.objects.filter(
                is_deleted=False,
                invoice_id__in=invoice_ids,
            ).update(is_deleted=True)
            if updated:
                self.stdout.write(f'  Payment receipts: {updated}')

            # 5. Invoice lines for those invoices
            updated = InvoiceLine.objects.filter(
                is_deleted=False,
                invoice_id__in=invoice_ids,
            ).update(is_deleted=True)
            if updated:
                self.stdout.write(f'  Invoice lines: {updated}')

            # 6. Invoices in date range (use all_objects so we can see and soft-delete them)
            updated = Invoice.all_objects.filter(
                is_deleted=False,
                issued_at__date__gte=START_DATE,
                issued_at__date__lte=END_DATE,
            ).update(is_deleted=True)
            if updated:
                self.stdout.write(f'  Invoices: {updated}')

            # 7. Bills in date range
            updated = Bill.objects.filter(
                is_deleted=False,
                issued_at__date__gte=START_DATE,
                issued_at__date__lte=END_DATE,
            ).update(is_deleted=True)
            if updated:
                self.stdout.write(f'  Bills: {updated}')

            # 8. Ambulance billing in date range
            updated = AmbulanceBilling.objects.filter(
                is_deleted=False,
            ).filter(
                Q(invoice_date__date__gte=START_DATE, invoice_date__date__lte=END_DATE)
                | Q(created__date__gte=START_DATE, created__date__lte=END_DATE)
            ).update(is_deleted=True)
            if updated:
                self.stdout.write(f'  Ambulance bills: {updated}')

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone. All bills from {START_DATE} to {END_DATE} have been written off '
                'and will no longer appear in lists.'
            )
        )
