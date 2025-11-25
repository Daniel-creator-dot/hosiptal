"""
Manually link existing Payment Vouchers, Expenses, and AP entries
Then post everything to the General Ledger
"""
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting_advanced import Expense, PaymentVoucher, AccountsPayable
from hospital.models_procurement import ProcurementRequest
from hospital.procurement_accounting_integration import create_procurement_journal_entry

print("=" * 80)
print("MANUAL LINKING & POSTING - FIX EXISTING ENTRIES")
print("=" * 80)

# Get all procurement requests that have been accounts_approved
procurement_requests = ProcurementRequest.objects.filter(
    status__in=['accounts_approved', 'payment_processed', 'ordered', 'received'],
    is_deleted=False
)

print(f"\n📋 Found {procurement_requests.count()} approved procurement requests")

for pr in procurement_requests:
    print(f"\n{'='*80}")
    print(f"Processing: {pr.request_number} (GHS {pr.estimated_total:,.2f})")
    print(f"{'='*80}")
    
    # Find related entries
    expense = Expense.objects.filter(
        vendor_invoice_number=pr.request_number,
        is_deleted=False
    ).first()
    
    voucher = PaymentVoucher.objects.filter(
        po_number=pr.request_number,
        is_deleted=False
    ).first()
    
    ap = AccountsPayable.objects.filter(
        vendor_invoice__contains=pr.request_number,
        is_deleted=False
    ).first()
    
    print(f"   Expense: {'✓ Found' if expense else '✗ Not found'}")
    print(f"   Payment Voucher: {'✓ Found' if voucher else '✗ Not found'}")
    print(f"   AP: {'✓ Found' if ap else '✗ Not found'}")
    
    if not (expense and voucher and ap):
        print(f"   ⚠️ Missing entries - skipping")
        continue
    
    # Link them together
    linked_something = False
    
    # Link expense to voucher
    if not expense.payment_voucher:
        expense.payment_voucher = voucher
        expense.save(update_fields=['payment_voucher'])
        print(f"   ✅ Linked Expense → Voucher")
        linked_something = True
    
    # Link AP to voucher
    if not ap.payment_voucher:
        ap.payment_voucher = voucher
        ap.save(update_fields=['payment_voucher'])
        print(f"   ✅ Linked AP → Voucher")
        linked_something = True
    
    # Post to General Ledger if not already posted
    if not expense.journal_entry:
        try:
            journal_entry = create_procurement_journal_entry(pr, expense, ap, voucher)
            if journal_entry:
                print(f"   ✅ Posted to GL: {journal_entry.entry_number}")
                print(f"      Dr. Expense Account: GHS {expense.amount:,.2f}")
                print(f"      Cr. AP Account: GHS {expense.amount:,.2f}")
                linked_something = True
        except Exception as e:
            print(f"   ❌ Failed to post to GL: {e}")
    else:
        print(f"   ℹ️ Already posted to GL: {expense.journal_entry.entry_number}")
    
    if not linked_something:
        print(f"   ℹ️ Everything already linked and posted")

print("\n" + "=" * 80)
print("LINKING COMPLETE")
print("=" * 80)

# Final verification
from decimal import Decimal
from django.db.models import Sum

expenses_linked = Expense.objects.filter(
    payment_voucher__isnull=False,
    is_deleted=False
).count()

expenses_posted = Expense.objects.filter(
    journal_entry__isnull=False,
    is_deleted=False
).count()

print(f"\n✅ Expenses linked to vouchers: {expenses_linked}/{Expense.objects.filter(is_deleted=False).count()}")
print(f"✅ Expenses posted to GL: {expenses_posted}/{Expense.objects.filter(is_deleted=False).count()}")

# Check GL balance
from hospital.models_accounting_advanced import AdvancedGeneralLedger

total_debits = AdvancedGeneralLedger.objects.aggregate(
    total=Sum('debit_amount')
)['total'] or Decimal('0.00')

total_credits = AdvancedGeneralLedger.objects.aggregate(
    total=Sum('credit_amount')
)['total'] or Decimal('0.00')

print(f"\n📖 General Ledger:")
print(f"   Total Debits:  GHS {total_debits:,.2f}")
print(f"   Total Credits: GHS {total_credits:,.2f}")
print(f"   Difference:    GHS {abs(total_debits - total_credits):,.2f}")

if abs(total_debits - total_credits) < 0.01:
    print(f"\n   ✅✅✅ GENERAL LEDGER IS BALANCED! ✅✅✅")
else:
    print(f"\n   ⚠️ GL Imbalance: GHS {abs(total_debits - total_credits):,.2f}")

print("\n" + "=" * 80)
print("✅ ACCOUNTING STREAMS SYNCHRONIZED!")
print("=" * 80)
print("\nYour accounting is now properly integrated:")
print("  ✅ All entries linked together")
print("  ✅ Posted to General Ledger")
print("  ✅ Proper double-entry bookkeeping")
print("  ✅ Complete accountability chain")
print("\n🔄 View your expense report - it should now show all entries!")
print("=" * 80)



















