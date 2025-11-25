"""
Setup Advanced Accounting System
Automatically configure and initialize the accounting system
"""

import os
import sys
import re


def update_admin_file():
    """Add accounting admin import to hospital/admin.py"""
    
    admin_file = 'hospital/admin.py'
    
    print("="*70)
    print("STEP 1: Updating Admin Configuration")
    print("="*70)
    print()
    
    # Read current admin.py
    with open(admin_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already imported
    if 'admin_accounting_advanced' in content:
        print("[INFO] Accounting admin already imported")
        return True
    
    # Find the line after admin_biometric
    pattern = r'(from \.admin_biometric import \*\n)'
    
    if not re.search(pattern, content):
        print("[WARNING] Could not find admin_biometric import")
        # Try alternative pattern
        pattern = r'(from \. import views_backup\n)'
        if not re.search(pattern, content):
            print("[ERROR] Could not find insertion point")
            return False
    
    # Add the import
    replacement = r'\1# Import advanced accounting admin\nfrom .admin_accounting_advanced import *\n'
    new_content = re.sub(pattern, replacement, content, count=1)
    
    # Write back
    with open(admin_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("[OK] Added accounting admin import to hospital/admin.py")
    return True


def run_migrations():
    """Run Django migrations"""
    
    print()
    print("="*70)
    print("STEP 2: Creating Database Tables")
    print("="*70)
    print()
    
    print("Creating migrations...")
    ret1 = os.system('python manage.py makemigrations')
    
    if ret1 != 0:
        print("[WARNING] Migration creation had issues")
    
    print()
    print("Applying migrations...")
    ret2 = os.system('python manage.py migrate')
    
    if ret2 != 0:
        print("[ERROR] Migration application failed")
        return False
    
    print()
    print("[OK] Database tables created successfully!")
    return True


def create_initial_data():
    """Create initial accounting data"""
    
    print()
    print("="*70)
    print("STEP 3: Creating Initial Accounting Data")
    print("="*70)
    print()
    
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
    django.setup()
    
    from hospital.models_accounting import Account
    from hospital.models_accounting_advanced import (
        FiscalYear, AccountingPeriod, Journal, RevenueCategory, ExpenseCategory, AccountCategory
    )
    from datetime import datetime
    
    # Create Fiscal Year
    print("Creating Fiscal Year...")
    fiscal_year, created = FiscalYear.objects.get_or_create(
        name='FY2025',
        defaults={
            'start_date': datetime(2025, 1, 1).date(),
            'end_date': datetime(2025, 12, 31).date(),
        }
    )
    if created:
        print(f"[OK] Created fiscal year: {fiscal_year.name}")
    else:
        print(f"[INFO] Fiscal year already exists: {fiscal_year.name}")
    
    # Create Accounting Periods
    print()
    print("Creating Accounting Periods...")
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
    print("Creating Journals...")
    journals = [
        ('GJ', 'General Journal', 'general'),
        ('SJ', 'Sales Journal', 'sales'),
        ('PJ', 'Purchase Journal', 'purchase'),
        ('PRJ', 'Payment Journal', 'payment'),
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
    if Account.objects.count() == 0:
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
            ('1510', 'Office Equipment', 'asset'),
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
            ('5100', 'Medical Supplies Expense', 'expense'),
            ('5200', 'Utilities', 'expense'),
            ('5300', 'Rent', 'expense'),
            ('5400', 'Depreciation', 'expense'),
        ]
        
        for code, name, acc_type in sample_accounts:
            Account.objects.create(
                account_code=code,
                account_name=name,
                account_type=acc_type,
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
            ('EXP-SALARY', 'Salaries & Wages', True, 100000),
            ('EXP-SUPPLIES', 'Medical Supplies', True, 50000),
            ('EXP-UTIL', 'Utilities', False, None),
            ('EXP-RENT', 'Rent', False, None),
            ('EXP-MAINT', 'Maintenance', True, 20000),
        ]
        
        for code, name, requires_approval, limit in expense_cats:
            cat, created = ExpenseCategory.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'account': expense_account,
                    'requires_approval': requires_approval,
                    'approval_limit': limit,
                }
            )
            if created:
                print(f"  [OK] {name}")
    
    print()
    print("="*70)
    print("INITIAL DATA CREATED SUCCESSFULLY!")
    print("="*70)


def main():
    print("╔══════════════════════════════════════════════════════════════════════════════╗")
    print("║                                                                              ║")
    print("║            ADVANCED ACCOUNTING SYSTEM - AUTOMATIC SETUP                      ║")
    print("║                                                                              ║")
    print("╚══════════════════════════════════════════════════════════════════════════════╝")
    print()
    
    # Step 1: Update admin.py
    if not update_admin_file():
        print()
        print("[ERROR] Failed to update admin.py")
        print("Please manually add this line to hospital/admin.py:")
        print("  from .admin_accounting_advanced import *")
        return
    
    # Step 2: Run migrations
    if not run_migrations():
        print()
        print("[ERROR] Migration failed")
        print("Please run manually:")
        print("  python manage.py makemigrations")
        print("  python manage.py migrate")
        return
    
    # Step 3: Create initial data
    try:
        create_initial_data()
    except Exception as e:
        print(f"[WARNING] Initial data creation had issues: {e}")
        print("You can create data manually in Django admin")
    
    # Success
    print()
    print("="*70)
    print("✅ ACCOUNTING SYSTEM SETUP COMPLETE!")
    print("="*70)
    print()
    print("Next steps:")
    print("1. Restart server: python manage.py runserver")
    print("2. Visit: http://127.0.0.1:8000/hms/accounting/")
    print("3. Start using your world-class accounting system!")
    print()
    print("Documentation: Read ✅_STATE_OF_THE_ART_ACCOUNTING_SYSTEM_COMPLETE.txt")
    print()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()




















