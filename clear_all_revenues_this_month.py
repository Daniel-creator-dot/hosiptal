"""
Clear All Revenues This Month - Start Fresh
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting_advanced import Revenue
from hospital.models_accounting import GeneralLedger, PaymentReceipt, Account
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal

print("=" * 80)
print("CLEARING ALL REVENUES THIS MONTH")
print("=" * 80)

today = timezone.now().date()
start_of_month = today.replace(day=1)

# 1. Count Revenue model entries
revenue_count = Revenue.objects.filter(
    revenue_date__gte=start_of_month,
    revenue_date__lte=today,
    is_deleted=False
).count()

revenue_total = Revenue.objects.filter(
    revenue_date__gte=start_of_month,
    revenue_date__lte=today,
    is_deleted=False
).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

# 2. Count GeneralLedger revenue entries
gl_revenue_count = GeneralLedger.objects.filter(
    account__account_type='revenue',
    transaction_date__gte=start_of_month,
    transaction_date__lte=today,
    is_deleted=False
).count()

gl_revenue_total = GeneralLedger.objects.filter(
    account__account_type='revenue',
    transaction_date__gte=start_of_month,
    transaction_date__lte=today,
    is_deleted=False
).aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')

# 3. Count PaymentReceipts
receipt_count = PaymentReceipt.objects.filter(
    receipt_date__date__gte=start_of_month,
    receipt_date__date__lte=today,
    is_deleted=False
).count()

receipt_total = PaymentReceipt.objects.filter(
    receipt_date__date__gte=start_of_month,
    receipt_date__date__lte=today,
    is_deleted=False
).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')

print(f"\nPeriod: {start_of_month.strftime('%B %d')} to {today.strftime('%B %d, %Y')}")
print(f"\nCurrent Revenue Entries This Month:")
print(f"  1. Revenue Model: {revenue_count} entries = GHS {revenue_total:,.2f}")
print(f"  2. General Ledger (Revenue): {gl_revenue_count} entries = GHS {gl_revenue_total:,.2f}")
print(f"  3. Payment Receipts: {receipt_count} entries = GHS {receipt_total:,.2f}")

total_entries = revenue_count + gl_revenue_count + receipt_count
total_amount = revenue_total + gl_revenue_total + receipt_total

print(f"\n  TOTAL: {total_entries} entries = GHS {total_amount:,.2f}")

if total_entries == 0:
    print("\n[OK] No revenue entries to clear this month.")
    sys.exit(0)

# Show sample entries
print(f"\nSample Revenue entries to be deleted:")
revenues = Revenue.objects.filter(
    revenue_date__gte=start_of_month,
    revenue_date__lte=today,
    is_deleted=False
).order_by('-revenue_date')[:10]
for rev in revenues:
    print(f"  - {rev.revenue_number}: {rev.revenue_date} | {rev.category} | GHS {rev.amount}")

if revenue_count > 10:
    print(f"  ... and {revenue_count - 10} more Revenue entries")

# Proceed with deletion
print("\n" + "=" * 80)
print(f"Proceeding to delete ALL revenue entries for this month...")

# Delete all revenue entries
print("\nDeleting revenue entries...")
try:
    with transaction.atomic():
        # 1. Delete Revenue model entries
        deleted_revenue = Revenue.objects.filter(
            revenue_date__gte=start_of_month,
            revenue_date__lte=today,
            is_deleted=False
        ).update(is_deleted=True)
        print(f"  [OK] Marked {deleted_revenue} Revenue entries as deleted")
        
        # 2. Delete GeneralLedger revenue entries
        deleted_gl = GeneralLedger.objects.filter(
            account__account_type='revenue',
            transaction_date__gte=start_of_month,
            transaction_date__lte=today,
            is_deleted=False
        ).update(is_deleted=True)
        print(f"  [OK] Marked {deleted_gl} GeneralLedger revenue entries as deleted")
        
        # 3. Delete PaymentReceipts
        deleted_receipts = PaymentReceipt.objects.filter(
            receipt_date__date__gte=start_of_month,
            receipt_date__date__lte=today,
            is_deleted=False
        ).update(is_deleted=True)
        print(f"  [OK] Marked {deleted_receipts} PaymentReceipt entries as deleted")
        
        # Verify
        remaining_revenue = Revenue.objects.filter(
            revenue_date__gte=start_of_month,
            revenue_date__lte=today,
            is_deleted=False
        ).count()
        remaining_gl = GeneralLedger.objects.filter(
            account__account_type='revenue',
            transaction_date__gte=start_of_month,
            transaction_date__lte=today,
            is_deleted=False
        ).count()
        remaining_receipts = PaymentReceipt.objects.filter(
            receipt_date__date__gte=start_of_month,
            receipt_date__date__lte=today,
            is_deleted=False
        ).count()
        
        print(f"\n[OK] Remaining entries this month:")
        print(f"  Revenue Model: {remaining_revenue}")
        print(f"  General Ledger: {remaining_gl}")
        print(f"  Payment Receipts: {remaining_receipts}")
        
except Exception as e:
    print(f"\n[ERROR] Failed to delete revenue entries: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("[OK] ALL REVENUES THIS MONTH CLEARED")
print("=" * 80)
print("\nYou can now start fresh with new revenue entries for this month.")
