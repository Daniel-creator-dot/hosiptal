"""
Setup Chart of Accounts for Primecare Medical Centre
Based on the technical and professional guide
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from hospital.models_accounting import Account


class Command(BaseCommand):
    help = 'Setup Chart of Accounts for Primecare Medical Centre'

    def handle(self, *args, **options):
        self.stdout.write('Setting up Primecare Chart of Accounts...')
        
        with transaction.atomic():
            accounts = [
                # ==================== ASSETS (1000-1999) ====================
                # Current Assets
                {'code': '1010', 'name': 'Cash and Cash Equivalents', 'type': 'asset', 'parent': None},
                {'code': '1015', 'name': 'Undeposited Funds', 'type': 'asset', 'parent': None},
                {'code': '1020', 'name': 'Bank Account - UMB', 'type': 'asset', 'parent': None},
                {'code': '1021', 'name': 'Bank Account - Other', 'type': 'asset', 'parent': None},
                {'code': '1200', 'name': 'Trade Receivables', 'type': 'asset', 'parent': None},
                {'code': '1201', 'name': 'Insurance Receivables', 'type': 'asset', 'parent': None},
                {'code': '1202', 'name': 'Corporate Receivables', 'type': 'asset', 'parent': None},
                {'code': '1300', 'name': 'Withholding Tax Receivable', 'type': 'asset', 'parent': None},
                {'code': '1400', 'name': 'Inventories (Closing Stock)', 'type': 'asset', 'parent': None},
                {'code': '1500', 'name': 'Other Current Assets', 'type': 'asset', 'parent': None},
                {'code': '1501', 'name': 'Advances and Prepayments', 'type': 'asset', 'parent': None},
                {'code': '1600', 'name': 'Income Tax Assets', 'type': 'asset', 'parent': None},
                {'code': '1700', 'name': 'Short-term Investments', 'type': 'asset', 'parent': None},
                
                # Non-Current Assets
                {'code': '1800', 'name': 'Property, Plant and Equipment', 'type': 'asset', 'parent': None},
                {'code': '1801', 'name': 'Land', 'type': 'asset', 'parent': None},
                {'code': '1802', 'name': 'Buildings', 'type': 'asset', 'parent': None},
                {'code': '1803', 'name': 'Medical Equipment', 'type': 'asset', 'parent': None},
                {'code': '1804', 'name': 'Furniture and Fixtures', 'type': 'asset', 'parent': None},
                {'code': '1805', 'name': 'Vehicles', 'type': 'asset', 'parent': None},
                {'code': '1806', 'name': 'Accumulated Depreciation', 'type': 'asset', 'parent': None},
                {'code': '1900', 'name': 'Intangible Assets', 'type': 'asset', 'parent': None},
                {'code': '1901', 'name': 'Long-term Investments', 'type': 'asset', 'parent': None},
                {'code': '1902', 'name': 'Deferred Tax Assets', 'type': 'asset', 'parent': None},
                
                # ==================== LIABILITIES (2000-2999) ====================
                # Current Liabilities
                {'code': '2010', 'name': 'Bank Overdrafts', 'type': 'liability', 'parent': None},
                {'code': '2011', 'name': 'Short-term Borrowings', 'type': 'liability', 'parent': None},
                {'code': '2100', 'name': 'Trade Payables', 'type': 'liability', 'parent': None},
                {'code': '2101', 'name': 'Accounts Payable', 'type': 'liability', 'parent': None},
                {'code': '2200', 'name': 'Provisions', 'type': 'liability', 'parent': None},
                {'code': '2300', 'name': 'Income Tax Liabilities', 'type': 'liability', 'parent': None},
                {'code': '2400', 'name': 'Other Liabilities', 'type': 'liability', 'parent': None},
                
                # Non-Current Liabilities
                {'code': '2500', 'name': 'Long-term Loans', 'type': 'liability', 'parent': None},
                {'code': '2501', 'name': 'Interest-bearing Long-term Loans', 'type': 'liability', 'parent': None},
                {'code': '2600', 'name': 'Long-term Provisions', 'type': 'liability', 'parent': None},
                {'code': '2700', 'name': 'Deferred Tax Liabilities', 'type': 'liability', 'parent': None},
                
                # ==================== EQUITY (3000-3999) ====================
                {'code': '3000', 'name': 'Share Capital', 'type': 'equity', 'parent': None},
                {'code': '3100', 'name': 'Reserves', 'type': 'equity', 'parent': None},
                {'code': '3200', 'name': 'Retained Earnings', 'type': 'equity', 'parent': None},
                
                # ==================== REVENUE (4000-4999) ====================
                {'code': '4100', 'name': 'Registration Revenue', 'type': 'revenue', 'parent': None},
                {'code': '4110', 'name': 'Consultation Revenue', 'type': 'revenue', 'parent': None},
                {'code': '4120', 'name': 'Laboratory Revenue', 'type': 'revenue', 'parent': None},
                {'code': '4130', 'name': 'Pharmacy Revenue', 'type': 'revenue', 'parent': None},
                {'code': '4140', 'name': 'Surgeries Revenue', 'type': 'revenue', 'parent': None},
                {'code': '4150', 'name': 'Admissions & Professional Care Revenue', 'type': 'revenue', 'parent': None},
                {'code': '4160', 'name': 'Radiology Revenue', 'type': 'revenue', 'parent': None},
                {'code': '4170', 'name': 'Dental Revenue', 'type': 'revenue', 'parent': None},
                {'code': '4180', 'name': 'Physiotherapy Revenue', 'type': 'revenue', 'parent': None},
                {'code': '4200', 'name': 'Other Income', 'type': 'revenue', 'parent': None},
                {'code': '4210', 'name': 'Discount Received', 'type': 'revenue', 'parent': None},
                {'code': '4220', 'name': 'Interest Income', 'type': 'revenue', 'parent': None},
                
                # ==================== EXPENSES (5000-5999) ====================
                # Cost of Sales
                {'code': '5100', 'name': 'Opening Inventory', 'type': 'expense', 'parent': None},
                {'code': '5110', 'name': 'Purchases - Drugs', 'type': 'expense', 'parent': None},
                {'code': '5111', 'name': 'Purchases - Laboratory Reagents', 'type': 'expense', 'parent': None},
                {'code': '5112', 'name': 'Purchases - Dental', 'type': 'expense', 'parent': None},
                {'code': '5113', 'name': 'Purchases - Radiology', 'type': 'expense', 'parent': None},
                {'code': '5114', 'name': 'Purchases - Consumables', 'type': 'expense', 'parent': None},
                {'code': '5115', 'name': 'Purchases - Physiotherapy', 'type': 'expense', 'parent': None},
                {'code': '5116', 'name': 'Purchases - Others', 'type': 'expense', 'parent': None},
                {'code': '5120', 'name': 'Closing Inventory', 'type': 'expense', 'parent': None},
                
                # Operating Expenses
                {'code': '5200', 'name': 'Bills Rejections', 'type': 'expense', 'parent': None},
                {'code': '5210', 'name': 'Salaries (Basic + Allowances)', 'type': 'expense', 'parent': None},
                {'code': '5211', 'name': "13% Employer's SSF", 'type': 'expense', 'parent': None},
                {'code': '5220', 'name': 'Printing & Stationery', 'type': 'expense', 'parent': None},
                {'code': '5230', 'name': 'Electricity', 'type': 'expense', 'parent': None},
                {'code': '5240', 'name': 'Water', 'type': 'expense', 'parent': None},
                {'code': '5250', 'name': 'Telephone', 'type': 'expense', 'parent': None},
                {'code': '5260', 'name': 'Cleaning & Sanitation', 'type': 'expense', 'parent': None},
                {'code': '5270', 'name': 'Bank Charges', 'type': 'expense', 'parent': None},
                {'code': '5280', 'name': 'Security Services', 'type': 'expense', 'parent': None},
                {'code': '5290', 'name': 'Insurance', 'type': 'expense', 'parent': None},
                {'code': '5300', 'name': 'Transport & Travelling', 'type': 'expense', 'parent': None},
                {'code': '5310', 'name': 'Fuel', 'type': 'expense', 'parent': None},
                {'code': '5320', 'name': 'Training & Development', 'type': 'expense', 'parent': None},
                {'code': '5330', 'name': 'Hire of Equipment', 'type': 'expense', 'parent': None},
                {'code': '5340', 'name': 'Medical Discount Allowed', 'type': 'expense', 'parent': None},
                {'code': '5350', 'name': 'Advertisement & Promotions', 'type': 'expense', 'parent': None},
                {'code': '5360', 'name': 'Medical Refunds', 'type': 'expense', 'parent': None},
                {'code': '5370', 'name': 'Repairs & Maintenance', 'type': 'expense', 'parent': None},
                {'code': '5380', 'name': 'Depreciation', 'type': 'expense', 'parent': None},
                {'code': '5390', 'name': 'Other Expenses', 'type': 'expense', 'parent': None},
            ]
            
            created_count = 0
            updated_count = 0
            
            for account_data in accounts:
                account, created = Account.objects.get_or_create(
                    account_code=account_data['code'],
                    defaults={
                        'account_name': account_data['name'],
                        'account_type': account_data['type'],
                        'parent_account': account_data['parent'],
                        'is_active': True,
                    }
                )
                
                if not created:
                    # Update existing account
                    account.account_name = account_data['name']
                    account.account_type = account_data['type']
                    account.is_active = True
                    account.save()
                    updated_count += 1
                else:
                    created_count += 1
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{'Created' if created else 'Updated'}: {account.account_code} - {account.account_name}"
                    )
                )
            
            self.stdout.write('')
            self.stdout.write(
                self.style.SUCCESS(
                    f'Chart of Accounts setup complete! '
                    f'Created: {created_count}, Updated: {updated_count}'
                )
            )














