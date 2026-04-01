"""
Check and fix all General Ledger and AdvancedGeneralLedger balances
Fix credit/balance calculation issues
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
from decimal import Decimal

# Try to import AdvancedGeneralLedger
try:
    from hospital.models_accounting_advanced import AdvancedGeneralLedger
    HAS_ADVANCED = True
except ImportError:
    HAS_ADVANCED = False

print("=" * 80)
print("CHECKING AND FIXING ALL BALANCES")
print("=" * 80)

# Fix GeneralLedger balances
print("\n1. Fixing GeneralLedger balances...")
print("-" * 80)

accounts = Account.objects.filter(is_deleted=False)
gl_fixed = 0

with transaction.atomic():
    for account in accounts:
        entries = GeneralLedger.objects.filter(
            account=account,
            is_deleted=False
        ).order_by('transaction_date', 'created', 'id')
        
        if not entries.exists():
            continue
        
        running_balance = Decimal('0.00')
        
        for entry in entries:
            # Calculate balance change
            if account.account_type in ['asset', 'expense']:
                balance_change = entry.debit_amount - entry.credit_amount
            else:
                balance_change = entry.credit_amount - entry.debit_amount
            
            running_balance += balance_change
            
            # Update if different
            if abs(entry.balance - running_balance) > Decimal('0.01'):
                entry.balance = running_balance
                entry.save(update_fields=['balance'])
                gl_fixed += 1

print(f"  [OK] Fixed {gl_fixed} GeneralLedger balances")

# Fix AdvancedGeneralLedger balances
if HAS_ADVANCED:
    print("\n2. Fixing AdvancedGeneralLedger balances...")
    print("-" * 80)
    
    adv_fixed = 0
    
    with transaction.atomic():
        for account in accounts:
            entries = AdvancedGeneralLedger.objects.filter(
                account=account,
                is_voided=False,
                is_deleted=False
            ).order_by('transaction_date', 'created', 'id')
            
            if not entries.exists():
                continue
            
            running_balance = Decimal('0.00')
            
            for entry in entries:
                # Calculate balance change
                if account.account_type in ['asset', 'expense']:
                    balance_change = entry.debit_amount - entry.credit_amount
                else:
                    balance_change = entry.credit_amount - entry.debit_amount
                
                running_balance += balance_change
                
                # Update if different
                if abs(entry.balance - running_balance) > Decimal('0.01'):
                    entry.balance = running_balance
                    entry.save(update_fields=['balance'])
                    adv_fixed += 1
    
    print(f"  [OK] Fixed {adv_fixed} AdvancedGeneralLedger balances")

# Verify Accounts Payable
print("\n3. Checking Accounts Payable (2000)...")
print("-" * 80)

ap_account = Account.objects.filter(account_code='2000', is_deleted=False).first()
if ap_account:
    # GeneralLedger
    gl_entries = GeneralLedger.objects.filter(account=ap_account, is_deleted=False)
    gl_debits = sum(e.debit_amount for e in gl_entries)
    gl_credits = sum(e.credit_amount for e in gl_entries)
    
    # AdvancedGeneralLedger
    if HAS_ADVANCED:
        adv_entries = AdvancedGeneralLedger.objects.filter(
            account=ap_account,
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
    balance = total_credits - total_debits  # Liability
    
    print(f"  GeneralLedger: {gl_entries.count()} entries")
    print(f"    Debits: GHS {gl_debits:,.2f}, Credits: GHS {gl_credits:,.2f}")
    if HAS_ADVANCED:
        print(f"  AdvancedGeneralLedger: {adv_entries.count()} entries")
        print(f"    Debits: GHS {adv_debits:,.2f}, Credits: GHS {adv_credits:,.2f}")
    print(f"  Total Balance: GHS {balance:,.2f}")
    
    if HAS_ADVANCED and adv_entries.exists():
        print(f"\n  All AdvancedGeneralLedger entries:")
        for entry in adv_entries.order_by('transaction_date', 'created'):
            print(f"    - {entry.transaction_date}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f} "
                  f"(Balance: {entry.balance:,.2f}, Desc: {entry.description[:50]})")

print("\n" + "=" * 80)
print("BALANCE FIX COMPLETE")
print("=" * 80)
