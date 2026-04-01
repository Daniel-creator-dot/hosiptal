"""
Fix Discharged Patient Invoice - Add Bed Charges and Create AR
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Admission, Invoice
from hospital.models_accounting_advanced import AdvancedAccountsReceivable
from hospital.services.bed_billing_service import bed_billing_service
from django.utils import timezone

print("=" * 80)
print("FIXING DISCHARGED PATIENT INVOICES")
print("=" * 80)

# Find discharged patients with invoices that have 0 balance
discharges = Admission.objects.filter(
    status='discharged',
    is_deleted=False,
    discharge_date__isnull=False
).order_by('-discharge_date')

print(f"\nFound {discharges.count()} discharged patients")

fixed_count = 0

for admission in discharges:
    if not admission.encounter:
        continue
        
    try:
        invoice = Invoice.objects.get(
            encounter=admission.encounter,
            is_deleted=False
        )
        
        # Check if invoice needs fixing
        if invoice.total_amount == 0 or invoice.balance == 0:
            print(f"\n  Patient: {admission.encounter.patient.full_name}")
            print(f"    Invoice: {invoice.invoice_number}")
            print(f"    Current Total: GHS {invoice.total_amount}")
            print(f"    Current Balance: GHS {invoice.balance}")
            
            # Recalculate bed charges
            try:
                billing_result = bed_billing_service.update_bed_charges_on_discharge(admission)
                
                if billing_result.get('success'):
                    # Reload invoice
                    invoice.refresh_from_db()
                    print(f"    [FIXED] New Total: GHS {invoice.total_amount}")
                    print(f"    [FIXED] New Balance: GHS {invoice.balance}")
                    print(f"    [FIXED] Status: {invoice.status}")
                    
                    # Ensure invoice is issued if it has balance
                    if invoice.balance > 0 and invoice.status == 'draft':
                        invoice.status = 'issued'
                        if not invoice.issued_at:
                            invoice.issued_at = timezone.now()
                        invoice.save()
                        print(f"    [FIXED] Status updated to 'issued'")
                    
                    # Trigger AR creation signal
                    from django.db.models.signals import post_save
                    post_save.send(sender=Invoice, instance=invoice, created=False)
                    
                    fixed_count += 1
                else:
                    print(f"    [ERROR] Bed billing failed: {billing_result.get('message', 'Unknown error')}")
            except Exception as e:
                print(f"    [ERROR] Failed to update bed charges: {e}")
        else:
            # Invoice has balance but might not have AR entry
            if invoice.balance > 0:
                try:
                    ar = invoice.advanced_ar
                    print(f"  Patient: {admission.encounter.patient.full_name} - AR exists: GHS {ar.balance_due}")
                except AdvancedAccountsReceivable.DoesNotExist:
                    # Create AR entry
                    if invoice.status in ['issued', 'partially_paid', 'overdue']:
                        from hospital.signals_accounting import auto_create_ar_on_invoice
                        auto_create_ar_on_invoice(sender=Invoice, instance=invoice, created=False)
                        print(f"  Patient: {admission.encounter.patient.full_name} - AR entry created")
                        fixed_count += 1
    except Invoice.DoesNotExist:
        print(f"  Patient: {admission.encounter.patient.full_name if admission.encounter else 'N/A'} - No invoice found")
    except Exception as e:
        print(f"  [ERROR] Processing admission: {e}")

print(f"\n" + "=" * 80)
print(f"SUMMARY: {fixed_count} invoices fixed")
print("=" * 80)

# Check final AR total
total_ar = sum(ar.balance_due for ar in AdvancedAccountsReceivable.objects.filter(balance_due__gt=0, is_deleted=False))
print(f"\nTotal AR Balance: GHS {total_ar}")
