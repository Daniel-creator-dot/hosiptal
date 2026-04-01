"""
Check Recent Invoices and AR Creation
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Invoice
from hospital.models_accounting_advanced import AdvancedAccountsReceivable
from django.utils import timezone
from datetime import timedelta

print("=" * 80)
print("CHECKING RECENT INVOICES")
print("=" * 80)

# Check all invoices
print("\n1. All Invoices:")
print("-" * 80)
all_invoices = Invoice.objects.filter(is_deleted=False).order_by('-created')
print(f"  Total invoices: {all_invoices.count()}")

if all_invoices.exists():
    for inv in all_invoices[:10]:
        print(f"\n    Invoice: {inv.invoice_number}")
        print(f"      Patient: {inv.patient.full_name if inv.patient else 'N/A'}")
        print(f"      Total: GHS {inv.total_amount}")
        print(f"      Balance: GHS {inv.balance}")
        print(f"      Status: {inv.status}")
        print(f"      Created: {inv.created}")
        print(f"      Issued At: {inv.issued_at}")
        print(f"      Payer: {inv.payer.name if inv.payer else 'N/A'}")
        if inv.payer:
            print(f"      Payer Type: {inv.payer.payer_type if hasattr(inv.payer, 'payer_type') else 'N/A'}")
        
        # Check if AdvancedAccountsReceivable exists
        try:
            adv_ar = inv.advanced_ar
            print(f"      ✅ Has AdvancedAccountsReceivable")
            print(f"         Balance Due: GHS {adv_ar.balance_due}")
            print(f"         Is Deleted: {adv_ar.is_deleted}")
        except AdvancedAccountsReceivable.DoesNotExist:
            print(f"      [MISSING] NO AdvancedAccountsReceivable entry")
        except Exception as e:
            print(f"      ⚠️  Error checking AR: {e}")

# Check recent invoices (last 7 days)
print("\n2. Recent Invoices (Last 7 Days):")
print("-" * 80)
recent_date = timezone.now() - timedelta(days=7)
recent_invoices = Invoice.objects.filter(
    created__gte=recent_date,
    is_deleted=False
).order_by('-created')
print(f"  Recent invoices: {recent_invoices.count()}")

# Check invoices that should have AR
print("\n3. Invoices That Should Have AR (status=issued, balance>0):")
print("-" * 80)
should_have_ar = Invoice.objects.filter(
    status__in=['issued', 'partially_paid', 'overdue'],
    balance__gt=0,
    is_deleted=False
)
print(f"  Invoices that should have AR: {should_have_ar.count()}")

for inv in should_have_ar[:5]:
    print(f"\n    Invoice: {inv.invoice_number}")
    print(f"      Balance: GHS {inv.balance}")
    print(f"      Status: {inv.status}")
    has_ar = AdvancedAccountsReceivable.objects.filter(invoice=inv, is_deleted=False).exists()
    print(f"      Has AR Entry: {has_ar}")
    if not has_ar:
        print(f"      ⚠️  MISSING AR ENTRY - Signal may not have fired!")

print("\n" + "=" * 80)
print("CHECK COMPLETE")
print("=" * 80)
