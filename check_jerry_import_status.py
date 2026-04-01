"""
Check if JERRY.xlsx import records exist in the database
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Payer
from hospital.models_missing_features import Supplier
from hospital.models_primecare_accounting import InsuranceReceivableEntry
from hospital.models_accounting_advanced import AccountsPayable

print("="*80)
print("CHECKING JERRY.XLSX IMPORT STATUS")
print("="*80)
print()

# Check Payers (insurance companies)
print("1. PAYERS (Insurance Companies):")
payers = Payer.objects.filter(payer_type__in=['private', 'nhis'], is_active=True)
print(f"   Total: {payers.count()}")
if payers.exists():
    print("   Recent payers:")
    for payer in payers[:10]:
        print(f"     - {payer.name} (type: {payer.payer_type})")
print()

# Check Suppliers
print("2. SUPPLIERS:")
suppliers = Supplier.objects.filter(is_active=True)
print(f"   Total: {suppliers.count()}")
if suppliers.exists():
    print("   Recent suppliers:")
    for supplier in suppliers[:10]:
        print(f"     - {supplier.name}")
print()

# Check Insurance Receivable Entries
print("3. INSURANCE RECEIVABLE ENTRIES:")
receivable_entries = InsuranceReceivableEntry.objects.filter(is_deleted=False)
print(f"   Total: {receivable_entries.count()}")
if receivable_entries.exists():
    total_amount = sum(entry.total_amount for entry in receivable_entries)
    outstanding = sum(entry.outstanding_amount for entry in receivable_entries)
    print(f"   Total Amount: GHS {total_amount:,.2f}")
    print(f"   Outstanding: GHS {outstanding:,.2f}")
    print("   Recent entries:")
    for entry in receivable_entries[:10]:
        print(f"     - {entry.entry_number}: {entry.payer.name} - GHS {entry.total_amount:,.2f} (Status: {entry.status})")
else:
    print("   ⚠️  No Insurance Receivable Entries found!")
    print("   Run: python manage.py import_jerry_excel")
print()

# Check Accounts Payable
print("4. ACCOUNTS PAYABLE:")
ap_entries = AccountsPayable.objects.filter(is_deleted=False)
print(f"   Total: {ap_entries.count()}")
if ap_entries.exists():
    total_amount = sum(entry.amount for entry in ap_entries)
    balance_due = sum(entry.balance_due for entry in ap_entries)
    print(f"   Total Amount: GHS {total_amount:,.2f}")
    print(f"   Balance Due: GHS {balance_due:,.2f}")
    print("   Recent entries:")
    for entry in ap_entries[:10]:
        print(f"     - {entry.bill_number}: {entry.vendor_name} - GHS {entry.balance_due:,.2f}")
else:
    print("   ⚠️  No Accounts Payable entries found!")
    print("   Run: python manage.py import_jerry_excel")
print()

print("="*80)
if receivable_entries.exists() or ap_entries.exists():
    print("✅ Import records found! They should be visible in the Insurance Receivable page.")
else:
    print("⚠️  No import records found. Run the import command:")
    print("   python manage.py import_jerry_excel")
print("="*80)


