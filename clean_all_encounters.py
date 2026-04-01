"""
Clean All Encounters - Delete all encounter records
Also clean related data (VisitRecord, QueueEntry, etc.)
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Encounter
from django.db import transaction
from django.core.cache import cache

# Try to import related models
try:
    from hospital.models_medical_records import VisitRecord
    HAS_VISIT_RECORD = True
except ImportError:
    HAS_VISIT_RECORD = False

try:
    from hospital.models_queue import QueueEntry
    HAS_QUEUE = True
except ImportError:
    HAS_QUEUE = False

print("=" * 80)
print("CLEAN ALL ENCOUNTERS")
print("Delete all encounter records and related data")
print("=" * 80)

# Step 1: Count encounters
print("\n1. Counting encounters...")
print("-" * 80)

all_encounters = Encounter.objects.filter(is_deleted=False)
encounter_count = all_encounters.count()

print(f"  Total encounters: {encounter_count}")

if encounter_count == 0:
    print("  [OK] No encounters to delete")
    exit(0)

# Step 2: Count related data
print("\n2. Counting related data...")
print("-" * 80)

visit_record_count = 0
queue_entry_count = 0

if HAS_VISIT_RECORD:
    visit_records = VisitRecord.objects.filter(is_deleted=False)
    visit_record_count = visit_records.count()
    print(f"  VisitRecord entries: {visit_record_count}")

if HAS_QUEUE:
    queue_entries = QueueEntry.objects.filter(is_deleted=False)
    queue_entry_count = queue_entries.count()
    print(f"  QueueEntry entries: {queue_entry_count}")

# Step 3: Delete all encounters and related data
print("\n3. Deleting all encounters and related data...")
print("-" * 80)

deleted_encounters = 0
deleted_visit_records = 0
deleted_queue_entries = 0

with transaction.atomic():
    # Delete VisitRecords first (they have OneToOne relationship)
    if HAS_VISIT_RECORD:
        visit_records = VisitRecord.objects.filter(is_deleted=False)
        for visit_record in visit_records:
            visit_record.is_deleted = True
            visit_record.save()
            deleted_visit_records += 1
        print(f"  [OK] Deleted {deleted_visit_records} VisitRecord entries")
    
    # Delete QueueEntries
    if HAS_QUEUE:
        queue_entries = QueueEntry.objects.filter(is_deleted=False)
        for queue_entry in queue_entries:
            queue_entry.is_deleted = True
            queue_entry.save()
            deleted_queue_entries += 1
        print(f"  [OK] Deleted {deleted_queue_entries} QueueEntry entries")
    
    # Delete all encounters
    for encounter in all_encounters:
        encounter.is_deleted = True
        encounter.save()
        deleted_encounters += 1
    
    print(f"  [OK] Deleted {deleted_encounters} Encounter records")

# Step 4: Clear cache
print("\n4. Clearing cache...")
print("-" * 80)
try:
    cache.clear()
    print("  [OK] Django cache cleared")
except Exception as e:
    print(f"  [WARNING] Could not clear cache: {e}")

# Step 5: Verify
print("\n5. Verifying deletion...")
print("-" * 80)

remaining_encounters = Encounter.objects.filter(is_deleted=False).count()
remaining_visit_records = 0
remaining_queue_entries = 0

if HAS_VISIT_RECORD:
    remaining_visit_records = VisitRecord.objects.filter(is_deleted=False).count()

if HAS_QUEUE:
    remaining_queue_entries = QueueEntry.objects.filter(is_deleted=False).count()

print(f"  Remaining encounters: {remaining_encounters}")
if HAS_VISIT_RECORD:
    print(f"  Remaining VisitRecords: {remaining_visit_records}")
if HAS_QUEUE:
    print(f"  Remaining QueueEntries: {remaining_queue_entries}")

if remaining_encounters == 0:
    print("  [OK] All encounters deleted successfully")
else:
    print(f"  [WARNING] {remaining_encounters} encounters still remain")

print("\n" + "=" * 80)
print("CLEANUP COMPLETE")
print("=" * 80)
print(f"\nSummary:")
print(f"  - Encounters deleted: {deleted_encounters}")
if HAS_VISIT_RECORD:
    print(f"  - VisitRecords deleted: {deleted_visit_records}")
if HAS_QUEUE:
    print(f"  - QueueEntries deleted: {deleted_queue_entries}")
print(f"  - Cache cleared: YES")
print(f"\n[OK] All encounters cleaned!")
