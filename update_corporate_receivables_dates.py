"""
Update corporate receivables entry dates to December 31, 2025
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_primecare_accounting import InsuranceReceivableEntry
from hospital.models import Payer
from datetime import date

# Target date: December 31, 2025
target_date = date(2025, 12, 31)

print("="*80)
print("UPDATING CORPORATE RECEIVABLES ENTRY DATES TO DECEMBER 31, 2025")
print("="*80)
print()

# Get all corporate payers
corporate_payers = Payer.objects.filter(
    payer_type='corporate',
    is_deleted=False
)

print(f"Found {corporate_payers.count()} corporate payers")
print()

updated_count = 0
total_amount = 0

for payer in corporate_payers:
    # Get InsuranceReceivableEntry records for this corporate payer
    entries = InsuranceReceivableEntry.objects.filter(
        payer=payer,
        outstanding_amount__gt=0,
        is_deleted=False
    )
    
    if entries.exists():
        print(f"Updating {entries.count()} entries for: {payer.name}")
        for entry in entries:
            old_date = entry.entry_date
            entry.entry_date = target_date
            entry.save()
            updated_count += 1
            total_amount += entry.outstanding_amount
            print(f"  Entry {entry.entry_number}: {old_date} -> {target_date} (Balance: GHS {entry.outstanding_amount:,.2f})")
        print()

print("="*80)
print(f"SUMMARY")
print("="*80)
print(f"Updated entries: {updated_count}")
print(f"Total amount: GHS {total_amount:,.2f}")
print()
print("="*80)
print("SUCCESS: All corporate receivables dates updated to December 31, 2025!")
print("="*80)

