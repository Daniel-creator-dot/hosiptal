"""
Check Accounts Receivable Entries
Diagnose why AR dashboard shows 0
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import AccountsReceivable
from hospital.models_accounting_advanced import AdvancedAccountsReceivable
from hospital.models import Invoice
from decimal import Decimal

print("=" * 80)
print("CHECKING ACCOUNTS RECEIVABLE ENTRIES")
print("=" * 80)

# Check old model
print("\n1. Old Model (AccountsReceivable):")
print("-" * 80)
old_ar = AccountsReceivable.objects.filter(is_deleted=False)
print(f"  Total entries: {old_ar.count()}")
if old_ar.exists():
    for ar in old_ar[:5]:
        print(f"    - Invoice: {ar.invoice.invoice_number if ar.invoice else 'N/A'}")
        print(f"      Outstanding: GHS {ar.outstanding_amount}")
        print(f"      Balance > 0: {ar.outstanding_amount > 0}")

# Check new model
print("\n2. New Model (AdvancedAccountsReceivable):")
print("-" * 80)
new_ar = AdvancedAccountsReceivable.objects.filter(is_deleted=False)
print(f"  Total entries: {new_ar.count()}")
if new_ar.exists():
    for ar in new_ar[:5]:
        print(f"    - Invoice: {ar.invoice.invoice_number if ar.invoice else 'N/A'}")
        print(f"      Balance Due: GHS {ar.balance_due}")
        print(f"      Invoice Amount: GHS {ar.invoice_amount}")
        print(f"      Amount Paid: GHS {ar.amount_paid}")
        print(f"      Balance > 0: {ar.balance_due > 0}")
        print(f"      Is Deleted: {ar.is_deleted}")

# Check invoices with balance
print("\n3. Invoices with Balance > 0:")
print("-" * 80)
invoices = Invoice.objects.filter(balance__gt=0, is_deleted=False)
print(f"  Total invoices with balance: {invoices.count()}")
if invoices.exists():
    for inv in invoices[:5]:
        print(f"    - Invoice: {inv.invoice_number}")
        print(f"      Total: GHS {inv.total_amount}")
        print(f"      Balance: GHS {inv.balance}")
        print(f"      Status: {inv.status}")
        print(f"      Has Advanced AR: {hasattr(inv, 'advanced_ar')}")
        if hasattr(inv, 'advanced_ar'):
            try:
                adv_ar = inv.advanced_ar
                print(f"      Advanced AR Balance: GHS {adv_ar.balance_due}")
            except:
                print(f"      Advanced AR: Does not exist")

# Check dashboard calculation
print("\n4. Dashboard Calculation (AdvancedAccountsReceivable):")
print("-" * 80)
ar_with_balance = AdvancedAccountsReceivable.objects.filter(
    balance_due__gt=0,
    is_deleted=False
)
print(f"  Entries with balance_due > 0: {ar_with_balance.count()}")
total = ar_with_balance.aggregate(total=sum(ar.balance_due for ar in ar_with_balance)) if ar_with_balance.exists() else Decimal('0.00')
print(f"  Total AR (sum): GHS {total}")

# Check all AR entries (even with 0 balance)
print("\n5. All AdvancedAccountsReceivable Entries:")
print("-" * 80)
all_ar = AdvancedAccountsReceivable.objects.all()
print(f"  Total entries (including deleted): {all_ar.count()}")
for ar in all_ar[:10]:
    print(f"    - Invoice: {ar.invoice.invoice_number if ar.invoice else 'N/A'}")
    print(f"      Balance Due: GHS {ar.balance_due}")
    print(f"      Is Deleted: {ar.is_deleted}")
    print(f"      Created: {ar.created}")

print("\n" + "=" * 80)
print("DIAGNOSIS COMPLETE")
print("=" * 80)
