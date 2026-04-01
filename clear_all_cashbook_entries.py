"""
Clear All Cashbook Entries - Start Fresh
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting_advanced import Cashbook
from django.db import transaction
from django.utils import timezone

print("=" * 80)
print("CLEARING ALL CASHBOOK ENTRIES")
print("=" * 80)

# Count entries before deletion
total_entries = Cashbook.objects.filter(is_deleted=False).count()
pending_entries = Cashbook.objects.filter(status='pending', is_deleted=False).count()
classified_entries = Cashbook.objects.filter(status='classified', is_deleted=False).count()
void_entries = Cashbook.objects.filter(status='void', is_deleted=False).count()

print(f"\nCurrent Cashbook Entries:")
print(f"  Total: {total_entries}")
print(f"  Pending: {pending_entries}")
print(f"  Classified: {classified_entries}")
print(f"  Void: {void_entries}")

if total_entries == 0:
    print("\n[OK] No cashbook entries to clear.")
    sys.exit(0)

# Show entries that will be deleted
print(f"\nEntries to be deleted:")
entries = Cashbook.objects.filter(is_deleted=False).order_by('-entry_date', '-entry_number')[:20]
for entry in entries:
    print(f"  - {entry.entry_number}: {entry.entry_date} | {entry.payee_or_payer} | GHS {entry.amount} | {entry.status}")

if total_entries > 20:
    print(f"  ... and {total_entries - 20} more entries")

# Auto-confirm deletion (for script execution)
print("\n" + "=" * 80)
print(f"Proceeding to delete ALL {total_entries} cashbook entries...")

# Delete all entries
print("\nDeleting entries...")
try:
    with transaction.atomic():
        deleted_count = Cashbook.objects.filter(is_deleted=False).update(is_deleted=True)
        print(f"\n[OK] Successfully marked {deleted_count} entries as deleted.")
        
        # Verify
        remaining = Cashbook.objects.filter(is_deleted=False).count()
        print(f"[OK] Remaining active entries: {remaining}")
        
except Exception as e:
    print(f"\n[ERROR] Failed to delete entries: {e}")
    sys.exit(1)

print("\n" + "=" * 80)
print("[OK] ALL CASHBOOK ENTRIES CLEARED")
print("=" * 80)
print("\nYou can now start fresh with new cashbook entries.")
