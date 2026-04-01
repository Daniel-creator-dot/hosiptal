"""
Reverse a payment receipt (e.g. mistaken / duplicate / no cash received).

  python manage.py reverse_payment_receipt RCP2026031410411543172826
  python manage.py reverse_payment_receipt RCP2026031410411543172826 --dry-run
"""
from django.core.management.base import BaseCommand

from hospital.services.reverse_payment_receipt_service import reverse_payment_receipt_by_number


class Command(BaseCommand):
    help = 'Soft-delete a PaymentReceipt and unwind linked billing/accounting (administrative reversal).'

    def add_arguments(self, parser):
        parser.add_argument('receipt_number', type=str, help='Public receipt number, e.g. RCP...')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would happen without writing to the database.',
        )
        parser.add_argument('--reason', type=str, default='', help='Optional note for logs (not stored yet).')

    def handle(self, *args, **options):
        rn = options['receipt_number'].strip()
        dry = options['dry_run']
        reason = (options.get('reason') or '').strip()

        try:
            result = reverse_payment_receipt_by_number(rn, dry_run=dry, reason=reason)
        except ValueError as e:
            self.stderr.write(self.style.ERROR(str(e)))
            return

        if result.get('dry_run'):
            self.stdout.write(self.style.WARNING(result['message']))
        else:
            self.stdout.write(self.style.SUCCESS(result['message']))

        for line in result.get('steps') or []:
            self.stdout.write(f'  • {line}')

        self.stdout.write(
            f"\nReceipt: {rn} | Amount: GHS {result.get('amount')} | "
            f"Invoice: {result.get('invoice_id') or '—'} | Patient: {result.get('patient_id') or '—'}"
        )

        if not dry:
            self.stdout.write(
                self.style.WARNING(
                    '\nIf this was insurance/corporate, review InsuranceReceivableEntry manually — '
                    'auto-reversal only adjusts AdvancedAccountsReceivable when present.'
                )
            )
