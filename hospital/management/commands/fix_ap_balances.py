"""
Management command to fix all Accounts Payable balance_due calculations
"""
from django.core.management.base import BaseCommand
from hospital.models_accounting_advanced import AccountsPayable
from decimal import Decimal


class Command(BaseCommand):
    help = 'Recalculate balance_due for all Accounts Payable records'

    def handle(self, *args, **options):
        self.stdout.write('Recalculating Accounts Payable balances...')
        
        ap_records = AccountsPayable.objects.filter(is_deleted=False)
        fixed_count = 0
        error_count = 0
        
        for ap in ap_records:
            try:
                # Calculate correct balance
                correct_balance = ap.amount - ap.amount_paid
                
                # Only update if balance is incorrect
                if ap.balance_due != correct_balance:
                    old_balance = ap.balance_due
                    ap.balance_due = correct_balance
                    ap.save(update_fields=['balance_due', 'is_overdue', 'days_overdue'])
                    
                    self.stdout.write(
                        f'Fixed AP {ap.bill_number}: {old_balance} → {correct_balance}'
                    )
                    fixed_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error fixing AP {ap.bill_number}: {str(e)}')
                )
                error_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Fixed {fixed_count} records. Errors: {error_count}'
            )
        )
