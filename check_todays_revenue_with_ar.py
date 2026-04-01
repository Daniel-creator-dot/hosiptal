"""
Check Today's Revenue Including Receivables
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import GeneralLedger, PaymentReceipt, Account, Invoice
from hospital.models_accounting_advanced import AdvancedAccountsReceivable
from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal

print("=" * 80)
print("CHECKING TODAY'S REVENUE (INCLUDING RECEIVABLES)")
print("=" * 80)

today = timezone.now().date()

# 1. From General Ledger
today_revenue_gl = GeneralLedger.objects.filter(
    account__account_type='revenue',
    transaction_date=today,
    is_deleted=False
).aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')

# 2. From Payment Receipts
today_revenue_receipts = PaymentReceipt.objects.filter(
    receipt_date__date=today,
    is_deleted=False
).aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')

# 3. From Receivables - Use invoice issued_at date (not AR created date)
today_revenue_from_ar = Decimal('0.00')
today_ar_entries = AdvancedAccountsReceivable.objects.filter(
    invoice__issued_at__date=today,
    is_deleted=False
).select_related('invoice')

print(f"\nAR Entries with Invoices Issued Today: {today_ar_entries.count()}")

for ar in today_ar_entries:
    print(f"\n  AR Entry:")
    print(f"    Invoice: {ar.invoice.invoice_number if ar.invoice else 'N/A'}")
    print(f"    Invoice Amount: GHS {ar.invoice_amount}")
    if ar.invoice:
        print(f"    Invoice Issued At: {ar.invoice.issued_at}")
        print(f"    AR Created: {ar.created}")
        # Only include if invoice was issued today
        if ar.invoice.issued_at and ar.invoice.issued_at.date() == today:
            today_revenue_from_ar += ar.invoice_amount
            print(f"    [INCLUDED] Invoice issued today - Revenue: GHS {ar.invoice_amount}")
        else:
            print(f"    [EXCLUDED] Invoice not issued today")

# 4. From Invoices Issued Today
today_invoices_revenue = Invoice.objects.filter(
    issued_at__date=today,
    status__in=['issued', 'partially_paid', 'overdue'],
    is_deleted=False
).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')

today_invoices = Invoice.objects.filter(
    issued_at__date=today,
    status__in=['issued', 'partially_paid', 'overdue'],
    is_deleted=False
)

print(f"\nInvoices Issued Today: {today_invoices.count()}")
for inv in today_invoices:
    print(f"  - {inv.invoice_number}: GHS {inv.total_amount} (Status: {inv.status})")

# Calculate final today's revenue
today_revenue = max(
    today_revenue_gl,
    today_revenue_from_ar,
    today_invoices_revenue,
    today_revenue_receipts
)

print("\n" + "=" * 80)
print("TODAY'S REVENUE BREAKDOWN:")
print("=" * 80)
print(f"  1. From General Ledger: GHS {today_revenue_gl:,.2f}")
print(f"  2. From Payment Receipts: GHS {today_revenue_receipts:,.2f}")
print(f"  3. From Receivables Created Today: GHS {today_revenue_from_ar:,.2f}")
print(f"  4. From Invoices Issued Today: GHS {today_invoices_revenue:,.2f}")
print(f"\n  FINAL TODAY'S REVENUE: GHS {today_revenue:,.2f}")

print("\n" + "=" * 80)
print("CHECK COMPLETE")
print("=" * 80)
