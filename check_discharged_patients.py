"""
Check Discharged Patients and Their Invoices
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
from django.utils import timezone
from datetime import timedelta

print("=" * 80)
print("CHECKING DISCHARGED PATIENTS")
print("=" * 80)

# Check recent discharges
print("\n1. Recent Discharges (Last 7 Days):")
print("-" * 80)
recent_date = timezone.now() - timedelta(days=7)
discharges = Admission.objects.filter(
    discharge_date__gte=recent_date,
    is_deleted=False
).order_by('-discharge_date')

print(f"  Total discharges: {discharges.count()}")

if discharges.exists():
    for admission in discharges[:10]:
        print(f"\n    Patient: {admission.encounter.patient.full_name if admission.encounter and admission.encounter.patient else 'N/A'}")
        print(f"      Discharge Date: {admission.discharge_date}")
        print(f"      Status: {admission.status}")
        
        # Check for invoice
        if admission.encounter:
            try:
                invoice = Invoice.objects.get(
                    encounter=admission.encounter,
                    is_deleted=False
                )
                print(f"      Invoice: {invoice.invoice_number}")
                print(f"        Total: GHS {invoice.total_amount}")
                print(f"        Balance: GHS {invoice.balance}")
                print(f"        Status: {invoice.status}")
                
                # Check for AR entry
                try:
                    ar = invoice.advanced_ar
                    print(f"        AR Entry: GHS {ar.balance_due}")
                except AdvancedAccountsReceivable.DoesNotExist:
                    print(f"        AR Entry: MISSING")
            except Invoice.DoesNotExist:
                print(f"      Invoice: NOT FOUND")
            except Invoice.MultipleObjectsReturned:
                invoices = Invoice.objects.filter(encounter=admission.encounter, is_deleted=False)
                print(f"      Invoices: {invoices.count()} found")
                for inv in invoices:
                    print(f"        - {inv.invoice_number}: GHS {inv.balance}")

# Check all discharges
print("\n2. All Discharges:")
print("-" * 80)
all_discharges = Admission.objects.filter(
    status='discharged',
    is_deleted=False
).order_by('-discharge_date')[:10]

print(f"  Showing first 10 of {Admission.objects.filter(status='discharged', is_deleted=False).count()} total")

for admission in all_discharges:
    if admission.encounter:
        try:
            invoice = Invoice.objects.get(encounter=admission.encounter, is_deleted=False)
            if invoice.balance > 0:
                print(f"\n    {admission.encounter.patient.full_name if admission.encounter.patient else 'N/A'}")
                print(f"      Invoice: {invoice.invoice_number}")
                print(f"      Balance: GHS {invoice.balance}")
                print(f"      Discharge: {admission.discharge_date}")
        except:
            pass

print("\n" + "=" * 80)
print("CHECK COMPLETE")
print("=" * 80)
