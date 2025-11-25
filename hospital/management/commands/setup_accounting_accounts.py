"""
Management command to set up default accounting accounts
Usage: python manage.py setup_accounting_accounts
"""

from django.core.management.base import BaseCommand
from hospital.models_accounting import Account


class Command(BaseCommand):
    help = 'Set up default accounting accounts for the hospital'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Setting up default accounting accounts...'))
        
        # Define default accounts
        default_accounts = [
            # Assets
            ('1010', 'Cash on Hand', 'asset', None),
            ('1020', 'Card Receipts', 'asset', None),
            ('1030', 'Mobile Money', 'asset', None),
            ('1040', 'Bank Transfer', 'asset', None),
            ('1200', 'Accounts Receivable', 'asset', None),
            
            # Liabilities
            ('2010', 'Unearned Revenue', 'liability', None),
            ('2020', 'Accounts Payable', 'liability', None),
            
            # Equity
            ('3010', 'Owner\'s Equity', 'equity', None),
            ('3020', 'Retained Earnings', 'equity', None),
            
            # Revenue
            ('4000', 'General Revenue', 'revenue', None),
            ('4010', 'Laboratory Revenue', 'revenue', None),
            ('4020', 'Pharmacy Revenue', 'revenue', None),
            ('4030', 'Imaging Revenue', 'revenue', None),
            ('4040', 'Consultation Revenue', 'revenue', None),
            ('4050', 'Procedure Revenue', 'revenue', None),
            ('4060', 'Admission Revenue', 'revenue', None),
            
            # Expenses
            ('5010', 'Salaries & Wages', 'expense', None),
            ('5020', 'Medical Supplies', 'expense', None),
            ('5030', 'Utilities', 'expense', None),
            ('5040', 'Rent', 'expense', None),
            ('5050', 'Depreciation', 'expense', None),
        ]
        
        created_count = 0
        updated_count = 0
        
        for code, name, acc_type, parent in default_accounts:
            account, created = Account.objects.get_or_create(
                account_code=code,
                defaults={
                    'account_name': name,
                    'account_type': acc_type,
                    'is_active': True,
                    'description': f'Default {acc_type} account - {name}'
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Created: {code} - {name}')
                )
            else:
                # Update if needed
                if not account.is_active:
                    account.is_active = True
                    account.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'  ↻ Reactivated: {code} - {name}')
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f'  - Already exists: {code} - {name}')
                    )
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'✅ Setup complete!'))
        self.stdout.write(self.style.SUCCESS(f'   Created: {created_count} accounts'))
        if updated_count > 0:
            self.stdout.write(self.style.SUCCESS(f'   Updated: {updated_count} accounts'))
        self.stdout.write(self.style.SUCCESS(f'   Total: {len(default_accounts)} accounts configured'))
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('You can now:'))
        self.stdout.write('  1. Process payments at the cashier')
        self.stdout.write('  2. View accounting dashboard: http://127.0.0.1:8000/hms/accounting/')
        self.stdout.write('  3. Check general ledger for entries')

























