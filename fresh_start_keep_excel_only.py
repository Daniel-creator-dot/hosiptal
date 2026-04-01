"""
Fresh Start - Keep Only Excel-Imported Insurance and Corporate Data
Clear all caches, revenues, and non-Excel data
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import GeneralLedger, Account
from django.db import transaction
from django.core.cache import cache
from decimal import Decimal

# Try to import AdvancedGeneralLedger
try:
    from hospital.models_accounting_advanced import AdvancedGeneralLedger
    HAS_ADVANCED = True
except ImportError:
    HAS_ADVANCED = False

print("=" * 80)
print("FRESH START - KEEP ONLY EXCEL DATA")
print("Clear all caches, revenues, and non-Excel entries")
print("=" * 80)

# Step 1: Clear Django cache
print("\n1. Clearing Django cache...")
print("-" * 80)
try:
    cache.clear()
    print("  [OK] Django cache cleared")
except Exception as e:
    print(f"  [WARNING] Could not clear cache: {e}")

# Step 2: Identify Excel-imported accounts (1200 and 1201)
print("\n2. Identifying Excel-imported accounts...")
print("-" * 80)

excel_accounts = ['1200', '1201']  # Corporate and Insurance from Excel
excel_account_objects = Account.objects.filter(
    account_code__in=excel_accounts,
    is_deleted=False
)

print(f"  Excel accounts to keep: {[acc.account_code for acc in excel_account_objects]}")

# Step 3: Clear all revenue entries
print("\n3. Clearing ALL revenue entries...")
print("-" * 80)

revenue_accounts = Account.objects.filter(account_type='revenue', is_deleted=False)
revenue_count_gl = 0
revenue_count_adv = 0

with transaction.atomic():
    # Clear from GeneralLedger
    revenue_entries_gl = GeneralLedger.objects.filter(
        account__account_type='revenue',
        is_deleted=False
    )
    revenue_count_gl = revenue_entries_gl.count()
    for entry in revenue_entries_gl:
        entry.is_deleted = True
        entry.save()
    
    # Clear from AdvancedGeneralLedger
    if HAS_ADVANCED:
        revenue_entries_adv = AdvancedGeneralLedger.objects.filter(
            account__account_type='revenue',
            is_voided=False,
            is_deleted=False
        )
        revenue_count_adv = revenue_entries_adv.count()
        for entry in revenue_entries_adv:
            entry.is_voided = True
            entry.is_deleted = True
            entry.save()

print(f"  [OK] Deleted {revenue_count_gl} revenue entries from GeneralLedger")
if HAS_ADVANCED:
    print(f"  [OK] Deleted {revenue_count_adv} revenue entries from AdvancedGeneralLedger")

# Step 4: Clear all non-Excel entries (keep only 1200 and 1201)
print("\n4. Clearing all non-Excel entries...")
print("-" * 80)

# Get all accounts except Excel accounts
all_accounts = Account.objects.filter(is_deleted=False)
non_excel_accounts = all_accounts.exclude(account_code__in=excel_accounts)

deleted_gl = 0
deleted_adv = 0

with transaction.atomic():
    # Clear GeneralLedger entries for non-Excel accounts
    for account in non_excel_accounts:
        gl_entries = GeneralLedger.objects.filter(account=account, is_deleted=False)
        count = gl_entries.count()
        for entry in gl_entries:
            entry.is_deleted = True
            entry.save()
        deleted_gl += count
    
    # Clear AdvancedGeneralLedger entries for non-Excel accounts
    if HAS_ADVANCED:
        for account in non_excel_accounts:
            adv_entries = AdvancedGeneralLedger.objects.filter(
                account=account,
                is_voided=False,
                is_deleted=False
            )
            count = adv_entries.count()
            for entry in adv_entries:
                entry.is_voided = True
                entry.is_deleted = True
                entry.save()
            deleted_adv += count

print(f"  [OK] Deleted {deleted_gl} GeneralLedger entries from non-Excel accounts")
if HAS_ADVANCED:
    print(f"  [OK] Deleted {deleted_adv} AdvancedGeneralLedger entries from non-Excel accounts")

# Step 5: Verify Excel accounts still have data
print("\n5. Verifying Excel accounts still have data...")
print("-" * 80)

for acc_code in excel_accounts:
    account = Account.objects.filter(account_code=acc_code, is_deleted=False).first()
    if account:
        gl_entries = GeneralLedger.objects.filter(account=account, is_deleted=False)
        gl_debits = sum(e.debit_amount for e in gl_entries)
        gl_credits = sum(e.credit_amount for e in gl_entries)
        
        if HAS_ADVANCED:
            adv_entries = AdvancedGeneralLedger.objects.filter(
                account=account,
                is_voided=False,
                is_deleted=False
            )
            adv_debits = sum(e.debit_amount for e in adv_entries)
            adv_credits = sum(e.credit_amount for e in adv_entries)
        else:
            adv_debits = Decimal('0.00')
            adv_credits = Decimal('0.00')
        
        total_debits = gl_debits + adv_debits
        total_credits = gl_credits + adv_credits
        
        if account.account_type in ['asset', 'expense']:
            balance = total_debits - total_credits
        else:
            balance = total_credits - total_debits
        
        print(f"\n  {acc_code} - {account.account_name}")
        print(f"    GL entries: {gl_entries.count()}")
        if HAS_ADVANCED:
            print(f"    Adv entries: {adv_entries.count()}")
        print(f"    Balance: GHS {balance:,.2f}")

# Step 6: Clear Python cache files
print("\n6. Clearing Python cache files...")
print("-" * 80)

import shutil
cache_dirs = ['__pycache__', '*.pyc']
cleared = 0

for root, dirs, files in os.walk('.'):
    # Skip virtual environments and .git
    if 'venv' in root or '.git' in root or 'node_modules' in root:
        continue
    
    # Remove __pycache__ directories
    if '__pycache__' in dirs:
        pycache_path = os.path.join(root, '__pycache__')
        try:
            shutil.rmtree(pycache_path)
            cleared += 1
        except:
            pass
    
    # Remove .pyc files
    for file in files:
        if file.endswith('.pyc'):
            try:
                os.remove(os.path.join(root, file))
                cleared += 1
            except:
                pass

print(f"  [OK] Cleared {cleared} cache files/directories")

# Step 7: Summary
print("\n" + "=" * 80)
print("FRESH START COMPLETE")
print("=" * 80)
print(f"\nSummary:")
print(f"  - Django cache: CLEARED")
print(f"  - Python cache: CLEARED ({cleared} files/dirs)")
print(f"  - Revenue entries deleted: GL={revenue_count_gl}, Adv={revenue_count_adv}")
print(f"  - Non-Excel entries deleted: GL={deleted_gl}, Adv={deleted_adv}")
print(f"\nKept Excel data:")
for acc_code in excel_accounts:
    account = Account.objects.filter(account_code=acc_code, is_deleted=False).first()
    if account:
        if HAS_ADVANCED:
            entries = AdvancedGeneralLedger.objects.filter(
                account=account, is_voided=False, is_deleted=False
            )
        else:
            entries = GeneralLedger.objects.filter(account=account, is_deleted=False)
        print(f"  - {acc_code}: {entries.count()} entries")
print(f"\n[OK] System is now fresh - only Excel data remains!")
