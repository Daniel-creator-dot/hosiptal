"""
Final fix for all balances - recalculate from scratch
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
print("FINAL BALANCE FIX - RECALCULATE ALL")
print("=" * 80)

accounts = Account.objects.filter(is_deleted=False)
total_fixed = 0

with transaction.atomic():
    for account in accounts:
        # Fix GeneralLedger balances
        gl_entries = GeneralLedger.objects.filter(
            account=account,
            is_deleted=False
        ).order_by('transaction_date', 'created', 'id')
        
        running_balance = Decimal('0.00')
        for entry in gl_entries:
            if account.account_type in ['asset', 'expense']:
                balance_change = entry.debit_amount - entry.credit_amount
            else:
                balance_change = entry.credit_amount - entry.debit_amount
            
            running_balance += balance_change
            
            if abs(entry.balance - running_balance) > Decimal('0.01'):
                entry.balance = running_balance
                entry.save(update_fields=['balance'])
                total_fixed += 1
        
        # Fix AdvancedGeneralLedger balances
        if HAS_ADVANCED:
            adv_entries = AdvancedGeneralLedger.objects.filter(
                account=account,
                is_voided=False,
                is_deleted=False
            ).order_by('transaction_date', 'created', 'id')
            
            running_balance = Decimal('0.00')
            for entry in adv_entries:
                if account.account_type in ['asset', 'expense']:
                    balance_change = entry.debit_amount - entry.credit_amount
                else:
                    balance_change = entry.credit_amount - entry.debit_amount
                
                running_balance += balance_change
                
                if abs(entry.balance - running_balance) > Decimal('0.01'):
                    entry.balance = running_balance
                    entry.save(update_fields=['balance'])
                    total_fixed += 1

print(f"\n[OK] Fixed {total_fixed} balance calculations")

# Show summary
print("\n" + "=" * 80)
print("ACCOUNT SUMMARY")
print("=" * 80)

key_accounts = ['1000', '1201', '2000', '5100']
for acc_code in key_accounts:
    account = Account.objects.filter(account_code=acc_code, is_deleted=False).first()
    if account:
        gl_entries = GeneralLedger.objects.filter(account=account, is_deleted=False)
        gl_debits = sum(e.debit_amount for e in gl_entries)
        gl_credits = sum(e.credit_amount for e in gl_entries)
        
        if HAS_ADVANCED:
            adv_entries = AdvancedGeneralLedger.objects.filter(
                account=account, is_voided=False, is_deleted=False
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
        
        print(f"\n{acc_code} - {account.account_name}")
        print(f"  GL: {gl_entries.count()} entries, Adv: {adv_entries.count() if HAS_ADVANCED else 0} entries")
        print(f"  Total Debits: GHS {total_debits:,.2f}")
        print(f"  Total Credits: GHS {total_credits:,.2f}")
        print(f"  Balance: GHS {balance:,.2f}")

print("\n" + "=" * 80)
print("FIX COMPLETE - READY TO RESTART")
print("=" * 80)
