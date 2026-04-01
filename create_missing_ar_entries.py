"""
Create Missing AR Entries for Existing Invoices
Manually trigger AR creation for invoices that should have AR but don't
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
from hospital.signals_accounting import auto_create_ar_on_invoice
from django.db.models.signals import post_save
from django.utils import timezone
from decimal import Decimal

print("=" * 80)
print("CREATING MISSING AR ENTRIES")
print("=" * 80)

# Find invoices that should have AR but don't
invoices_needing_ar = Invoice.objects.filter(
    status__in=['issued', 'partially_paid', 'overdue'],
    balance__gt=0,
    is_deleted=False
)

print(f"\nFound {invoices_needing_ar.count()} invoices that need AR entries")

created_count = 0
updated_count = 0

for invoice in invoices_needing_ar:
    # Check if AR entry exists
    try:
        ar = invoice.advanced_ar
        # Update if exists but amount is wrong
        if ar.balance_due != invoice.balance:
            ar.balance_due = invoice.balance
            ar.invoice_amount = invoice.total_amount
            ar.amount_paid = invoice.total_amount - invoice.balance
            ar.save()
            updated_count += 1
            print(f"  [UPDATED] Invoice {invoice.invoice_number}: GHS {invoice.balance}")
    except AdvancedAccountsReceivable.DoesNotExist:
        # Create AR entry manually
        try:
            payer = invoice.payer
            payer_type = payer.payer_type if hasattr(payer, 'payer_type') else None
            
            # For cash payers, create AdvancedAccountsReceivable
            if payer_type == 'cash' or not payer_type:
                ar = AdvancedAccountsReceivable.objects.create(
                    invoice=invoice,
                    patient=invoice.patient,
                    invoice_amount=invoice.total_amount,
                    amount_paid=invoice.total_amount - invoice.balance,
                    balance_due=invoice.balance,
                    due_date=invoice.due_at.date() if invoice.due_at else (timezone.now().date() + timezone.timedelta(days=30)),
                )
                ar.update_aging()  # Calculate aging
                created_count += 1
                print(f"  [CREATED] Invoice {invoice.invoice_number}: GHS {invoice.balance}")
            else:
                # For insurance/corporate, we'd create InsuranceReceivableEntry
                # But for now, just create AdvancedAccountsReceivable as fallback
                ar = AdvancedAccountsReceivable.objects.create(
                    invoice=invoice,
                    patient=invoice.patient,
                    invoice_amount=invoice.total_amount,
                    amount_paid=invoice.total_amount - invoice.balance,
                    balance_due=invoice.balance,
                    due_date=invoice.due_at.date() if invoice.due_at else (timezone.now().date() + timezone.timedelta(days=30)),
                )
                ar.update_aging()
                created_count += 1
                print(f"  [CREATED] Invoice {invoice.invoice_number} (insurance/corporate): GHS {invoice.balance}")
        except Exception as e:
            print(f"  [ERROR] Failed to create AR for {invoice.invoice_number}: {e}")

print(f"\n" + "=" * 80)
print(f"SUMMARY:")
print(f"  Created: {created_count}")
print(f"  Updated: {updated_count}")
print(f"=" * 80)

# Verify
total_ar = AdvancedAccountsReceivable.objects.filter(
    balance_due__gt=0,
    is_deleted=False
).aggregate(total=sum(ar.balance_due for ar in AdvancedAccountsReceivable.objects.filter(balance_due__gt=0, is_deleted=False))) if AdvancedAccountsReceivable.objects.filter(balance_due__gt=0, is_deleted=False).exists() else Decimal('0.00')

print(f"\nTotal AR Balance: GHS {total_ar}")
