"""
Check all ledger tables for Insurance Receivables and Accounts Payable entries
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import GeneralLedger, Account
from django.db.models import Sum, Q
from decimal import Decimal

# Try to import AdvancedGeneralLedger if it exists
try:
    from hospital.models_accounting_advanced import AdvancedGeneralLedger
    HAS_ADVANCED = True
except ImportError:
    HAS_ADVANCED = False
    print("[INFO] AdvancedGeneralLedger not available")

print("=" * 80)
print("CHECKING ALL LEDGER TABLES")
print("=" * 80)

# Check Insurance Receivables (1201)
print("\n" + "=" * 80)
print("INSURANCE RECEIVABLES (1201) - ALL LEDGER TABLES")
print("=" * 80)

ir_account = Account.objects.filter(account_code='1201', is_deleted=False).first()
if ir_account:
    print(f"\nAccount: {ir_account.account_code} - {ir_account.account_name}")
    
    # Check GeneralLedger
    print("\n1. GeneralLedger entries:")
    print("-" * 80)
    gl_entries = GeneralLedger.objects.filter(account=ir_account, is_deleted=False)
    gl_debits = gl_entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    gl_credits = gl_entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    gl_balance = gl_debits - gl_credits
    
    print(f"  Entries: {gl_entries.count()}")
    print(f"  Debits:  GHS {gl_debits:,.2f}")
    print(f"  Credits: GHS {gl_credits:,.2f}")
    print(f"  Balance: GHS {gl_balance:,.2f}")
    
    if gl_entries.exists():
        print(f"  Recent entries:")
        for entry in gl_entries.order_by('-transaction_date', '-created')[:5]:
            print(f"    - {entry.transaction_date}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f} "
                  f"(Ref: {entry.reference_number or 'N/A'})")
    
    # Check AdvancedGeneralLedger if available
    if HAS_ADVANCED:
        print("\n2. AdvancedGeneralLedger entries:")
        print("-" * 80)
        try:
            adv_entries = AdvancedGeneralLedger.objects.filter(
                account=ir_account,
                is_voided=False,
                is_deleted=False
            )
            adv_debits = adv_entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
            adv_credits = adv_entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
            adv_balance = adv_debits - adv_credits
            
            print(f"  Entries: {adv_entries.count()}")
            print(f"  Debits:  GHS {adv_debits:,.2f}")
            print(f"  Credits: GHS {adv_credits:,.2f}")
            print(f"  Balance: GHS {adv_balance:,.2f}")
            
            if adv_entries.exists():
                print(f"  Recent entries:")
                for entry in adv_entries.order_by('-transaction_date', '-created')[:5]:
                    print(f"    - {entry.transaction_date}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f}")
            
            # Combined balance
            total_balance = gl_balance + adv_balance
            print(f"\n  Combined Balance (GL + Advanced): GHS {total_balance:,.2f}")
            
        except Exception as e:
            print(f"  [ERROR] Could not check AdvancedGeneralLedger: {e}")
    
    # Check for entries with the specific amount
    target_amount = Decimal('1836602.62')
    print(f"\n3. Searching for entries with amount: GHS {target_amount:,.2f}")
    print("-" * 80)
    
    matching_entries = GeneralLedger.objects.filter(
        account=ir_account,
        is_deleted=False
    ).filter(Q(debit_amount=target_amount) | Q(credit_amount=target_amount))
    
    if matching_entries.exists():
        print(f"  [FOUND] {matching_entries.count()} entries with exact amount:")
        for entry in matching_entries:
            print(f"    Entry {entry.entry_number}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f} "
                  f"on {entry.transaction_date} (Ref: {entry.reference_number or 'N/A'})")
    else:
        print(f"  [OK] No entries found with exact amount")

# Check Accounts Payable (2000)
print("\n\n" + "=" * 80)
print("ACCOUNTS PAYABLE (2000) - ALL LEDGER TABLES")
print("=" * 80)

ap_account = Account.objects.filter(account_code='2000', is_deleted=False).first()
if ap_account:
    print(f"\nAccount: {ap_account.account_code} - {ap_account.account_name}")
    
    # Check GeneralLedger
    print("\n1. GeneralLedger entries:")
    print("-" * 80)
    gl_entries = GeneralLedger.objects.filter(account=ap_account, is_deleted=False)
    gl_debits = gl_entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    gl_credits = gl_entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    # Liability balance = credits - debits
    gl_balance = gl_credits - gl_debits
    
    print(f"  Entries: {gl_entries.count()}")
    print(f"  Debits:  GHS {gl_debits:,.2f}")
    print(f"  Credits: GHS {gl_credits:,.2f}")
    print(f"  Balance: GHS {gl_balance:,.2f}")
    
    if gl_entries.exists():
        print(f"  Recent entries:")
        for entry in gl_entries.order_by('-transaction_date', '-created')[:5]:
            print(f"    - {entry.transaction_date}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f} "
                  f"(Ref: {entry.reference_number or 'N/A'})")
    
    # Check AdvancedGeneralLedger if available
    if HAS_ADVANCED:
        print("\n2. AdvancedGeneralLedger entries:")
        print("-" * 80)
        try:
            adv_entries = AdvancedGeneralLedger.objects.filter(
                account=ap_account,
                is_voided=False,
                is_deleted=False
            )
            adv_debits = adv_entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
            adv_credits = adv_entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
            # Liability balance = credits - debits
            adv_balance = adv_credits - adv_debits
            
            print(f"  Entries: {adv_entries.count()}")
            print(f"  Debits:  GHS {adv_debits:,.2f}")
            print(f"  Credits: GHS {adv_credits:,.2f}")
            print(f"  Balance: GHS {adv_balance:,.2f}")
            
            if adv_entries.exists():
                print(f"  Recent entries:")
                for entry in adv_entries.order_by('-transaction_date', '-created')[:5]:
                    print(f"    - {entry.transaction_date}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f}")
            
            # Combined balance
            total_balance = gl_balance + adv_balance
            print(f"\n  Combined Balance (GL + Advanced): GHS {total_balance:,.2f}")
            
        except Exception as e:
            print(f"  [ERROR] Could not check AdvancedGeneralLedger: {e}")
    
    # Check for entries with the specific amount
    target_amount = Decimal('600834.40')
    print(f"\n3. Searching for entries with amount: GHS {target_amount:,.2f}")
    print("-" * 80)
    
    matching_entries = GeneralLedger.objects.filter(
        account=ap_account,
        is_deleted=False
    ).filter(Q(debit_amount=target_amount) | Q(credit_amount=target_amount))
    
    if matching_entries.exists():
        print(f"  [FOUND] {matching_entries.count()} entries with exact amount:")
        for entry in matching_entries:
            print(f"    Entry {entry.entry_number}: DR {entry.debit_amount:,.2f} / CR {entry.credit_amount:,.2f} "
                  f"on {entry.transaction_date} (Ref: {entry.reference_number or 'N/A'})")
    else:
        print(f"  [OK] No entries found with exact amount")

print("\n" + "=" * 80)
print("CHECK COMPLETE")
print("=" * 80)
print("\n[NOTE] If displayed amounts don't match calculated balances:")
print("  1. Clear browser cache and refresh")
print("  2. Check if a different date filter is being used")
print("  3. Verify you're looking at the correct database instance")
print("  4. Check if there are entries in other ledger tables")
