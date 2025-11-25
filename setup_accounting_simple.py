"""
Simple Accounting Setup
Create initial accounting data without unicode issues
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import Account
from hospital.models_accounting_advanced import (
    FiscalYear, AccountingPeriod, Journal, RevenueCategory, ExpenseCategory
)
from datetime import datetime


def main():
    print("="*70)
    print("SETTING UP ACCOUNTING SYSTEM")
    print("="*70)
    print()
    
    # Create Fiscal Year
    print("Creating Fiscal Year 2025...")
    fiscal_year, created = FiscalYear.objects.get_or_create(
        name='FY2025',
        defaults={
            'start_date': datetime(2025, 1, 1).date(),
            'end_date': datetime(2025, 12, 31).date(),
        }
    )
    if created:
        print(f"  [OK] Created: {fiscal_year.name}")
    else:
        print(f"  [INFO] Already exists: {fiscal_year.name}")
    
    # Create Accounting Periods
    print()
    print("Creating 12 Accounting Periods...")
    months = [
        ('January 2025', 1, 1, 31),
        ('February 2025', 2, 1, 28),
        ('March 2025', 3, 1, 31),
        ('April 2025', 4, 1, 30),
        ('May 2025', 5, 1, 31),
        ('June 2025', 6, 1, 30),
        ('July 2025', 7, 1, 31),
        ('August 2025', 8, 1, 31),
        ('September 2025', 9, 1, 30),
        ('October 2025', 10, 1, 31),
        ('November 2025', 11, 1, 30),
        ('December 2025', 12, 1, 31),
    ]
    
    for month_name, month_num, start_day, end_day in months:
        period, created = AccountingPeriod.objects.get_or_create(
            fiscal_year=fiscal_year,
            period_number=month_num,
            defaults={
                'name': month_name,
                'start_date': datetime(2025, month_num, start_day).date(),
                'end_date': datetime(2025, month_num, end_day).date(),
            }
        )
        if created:
            print(f"  [OK] {month_name}")
    
    # Create Journals
    print()
    print("Creating 7 Journal Types...")
    journals = [
        ('GJ', 'General Journal', 'general'),
        ('SJ', 'Sales Journal', 'sales'),
        ('PJ', 'Purchase Journal', 'purchase'),
        ('PAYJ', 'Payment Journal', 'payment'),
        ('RJ', 'Receipt Journal', 'receipt'),
        ('CJ', 'Cash Journal', 'cash'),
        ('BJ', 'Bank Journal', 'bank'),
    ]
    
    for code, name, j_type in journals:
        journal, created = Journal.objects.get_or_create(
            code=code,
            defaults={
                'name': name,
                'journal_type': j_type,
            }
        )
        if created:
            print(f"  [OK] {name}")
    
    # Create Sample Accounts if none exist
    if Account.objects.count() < 10:
        print()
        print("Creating Sample Chart of Accounts...")
        
        sample_accounts = [
            ('1000', 'Cash on Hand', 'asset'),
            ('1010', 'Bank Account - Main', 'asset'),
            ('1020', 'Bank Account - Savings', 'asset'),
            ('1100', 'Accounts Receivable', 'asset'),
            ('1200', 'Inventory - Pharmacy', 'asset'),
            ('1210', 'Inventory - Medical Supplies', 'asset'),
            ('1500', 'Medical Equipment', 'asset'),
            ('2000', 'Accounts Payable', 'liability'),
            ('2100', 'Salaries Payable', 'liability'),
            ('2200', 'Taxes Payable', 'liability'),
            ('3000', 'Capital', 'equity'),
            ('3100', 'Retained Earnings', 'equity'),
            ('4000', 'Patient Services Revenue', 'revenue'),
            ('4100', 'Laboratory Revenue', 'revenue'),
            ('4200', 'Pharmacy Revenue', 'revenue'),
            ('4300', 'Surgery Revenue', 'revenue'),
            ('5000', 'Salaries & Wages', 'expense'),
            ('5100', 'Medical Supplies', 'expense'),
            ('5200', 'Utilities', 'expense'),
            ('5300', 'Rent', 'expense'),
        ]
        
        for code, name, acc_type in sample_accounts:
            Account.objects.get_or_create(
                account_code=code,
                defaults={
                    'account_name': name,
                    'account_type': acc_type,
                }
            )
            print(f"  [OK] {code} - {name}")
    else:
        print(f"[INFO] Accounts already exist ({Account.objects.count()} accounts)")
    
    # Create Revenue Categories
    print()
    print("Creating Revenue Categories...")
    
    if Account.objects.filter(account_type='revenue').exists():
        revenue_account = Account.objects.filter(account_type='revenue').first()
        
        revenue_cats = [
            ('REV-PATIENT', 'Patient Services'),
            ('REV-LAB', 'Laboratory Services'),
            ('REV-PHARM', 'Pharmacy Sales'),
            ('REV-SURG', 'Surgery & Procedures'),
        ]
        
        for code, name in revenue_cats:
            cat, created = RevenueCategory.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'account': revenue_account,
                }
            )
            if created:
                print(f"  [OK] {name}")
    
    # Create Expense Categories
    print()
    print("Creating Expense Categories...")
    
    if Account.objects.filter(account_type='expense').exists():
        expense_account = Account.objects.filter(account_type='expense').first()
        
        expense_cats = [
            ('EXP-SALARY', 'Salaries & Wages'),
            ('EXP-SUPPLIES', 'Medical Supplies'),
            ('EXP-UTIL', 'Utilities'),
            ('EXP-RENT', 'Rent'),
            ('EXP-MAINT', 'Maintenance'),
        ]
        
        for code, name in expense_cats:
            cat, created = ExpenseCategory.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'account': expense_account,
                    'requires_approval': True,
                    'approval_limit': 50000,
                }
            )
            if created:
                print(f"  [OK] {name}")
    
    print()
    print("="*70)
    print("ACCOUNTING SETUP COMPLETE!")
    print("="*70)
    print()
    print("Created:")
    print(f"  - Fiscal Year: FY2025")
    print(f"  - Accounting Periods: 12 months")
    print(f"  - Journals: 7 types")
    print(f"  - Accounts: {Account.objects.count()}")
    print(f"  - Revenue Categories: {RevenueCategory.objects.count()}")
    print(f"  - Expense Categories: {ExpenseCategory.objects.count()}")
    print()
    print("Next: Import legacy accounting data")
    print("  python import_legacy_accounting.py")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()




















