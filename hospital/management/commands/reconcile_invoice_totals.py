"""
Reconcile invoice totals from line totals (correctly applies discounts/waivers)
Run: python manage.py reconcile_invoice_totals
Fixes invoices where total_amount or balance doesn't reflect waived/discounted amounts
"""
from django.core.management.base import BaseCommand
from hospital.models import Invoice


class Command(BaseCommand):
    help = 'Reconcile all invoice totals from line totals (fixes waived/discount amounts)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without saving',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        invoices = Invoice.objects.filter(is_deleted=False).prefetch_related('lines')
        updated = 0
        for inv in invoices:
            old_total = inv.total_amount
            old_balance = inv.balance
            inv.calculate_totals()
            if old_total != inv.total_amount or old_balance != inv.balance:
                updated += 1
                if not dry_run:
                    inv.save(update_fields=['total_amount', 'balance', 'status'])
                self.stdout.write(
                    f"  {inv.invoice_number}: total {old_total} -> {inv.total_amount}, "
                    f"balance {old_balance} -> {inv.balance}"
                )
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\nDry run: {updated} invoice(s) would be updated'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\nReconciled {updated} invoice(s)'))
