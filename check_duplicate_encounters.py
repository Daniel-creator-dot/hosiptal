"""
Check for duplicate encounters in the database
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Encounter
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta

print("=" * 70)
print("CHECKING FOR DUPLICATE ENCOUNTERS")
print("=" * 70)
print()

# Find duplicates by patient, started_at, and chief_complaint (exact match)
duplicates_exact = Encounter.objects.filter(
    is_deleted=False
).values(
    'patient', 'started_at', 'chief_complaint'
).annotate(
    count=Count('id')
).filter(
    count__gt=1
).order_by('-count', '-started_at')

# Also find duplicates by patient and date (same day, same complaint)
from django.db.models.functions import TruncDate
duplicates_same_day = Encounter.objects.filter(
    is_deleted=False
).annotate(
    encounter_date=TruncDate('started_at')
).values(
    'patient', 'encounter_date', 'chief_complaint'
).annotate(
    count=Count('id')
).filter(
    count__gt=1
).order_by('-count', '-encounter_date')

duplicates = duplicates_exact

total_duplicate_groups = duplicates.count()
total_same_day_duplicates = duplicates_same_day.count()

print(f"Found {total_duplicate_groups} exact duplicate encounter groups")
print(f"Found {total_same_day_duplicates} same-day duplicate encounter groups\n")

# Check same-day duplicates if no exact duplicates
if total_duplicate_groups == 0 and total_same_day_duplicates > 0:
    print("SAME-DAY DUPLICATES (same patient, same day, same complaint):")
    print("-" * 70)
    for dup in duplicates_same_day[:20]:
        patient_id = dup['patient']
        encounter_date = dup['encounter_date']
        chief_complaint = dup['chief_complaint'] or '(empty)'
        count = dup['count']
        
        # Get the actual encounters
        encounters = Encounter.objects.filter(
            patient_id=patient_id,
            started_at__date=encounter_date,
            chief_complaint=chief_complaint,
            is_deleted=False
        ).select_related('patient').order_by('created')
        
        patient = encounters.first().patient if encounters.exists() else None
        patient_name = patient.full_name if patient else f"Patient ID: {patient_id}"
        patient_mrn = patient.mrn if patient else "N/A"
        
        print(f"\nPatient: {patient_name} ({patient_mrn})")
        print(f"  Date: {encounter_date}")
        print(f"  Complaint: {chief_complaint[:50]}")
        print(f"  Duplicate Count: {count}")
        print(f"  Encounter IDs: {', '.join([str(e.id) for e in encounters])}")
        print(f"  Times: {', '.join([str(e.started_at) for e in encounters])}")

if total_duplicate_groups > 0:
    print("DUPLICATE ENCOUNTERS:")
    print("-" * 70)
    
    for dup in duplicates[:20]:  # Show first 20 groups
        patient_id = dup['patient']
        started_at = dup['started_at']
        chief_complaint = dup['chief_complaint'] or '(empty)'
        count = dup['count']
        
        # Get the actual encounters
        encounters = Encounter.objects.filter(
            patient_id=patient_id,
            started_at=started_at,
            chief_complaint=chief_complaint,
            is_deleted=False
        ).select_related('patient').order_by('created')
        
        patient = encounters.first().patient if encounters.exists() else None
        patient_name = patient.full_name if patient else f"Patient ID: {patient_id}"
        patient_mrn = patient.mrn if patient else "N/A"
        
        print(f"\nPatient: {patient_name} ({patient_mrn})")
        print(f"  Time: {started_at}")
        print(f"  Complaint: {chief_complaint[:50]}")
        print(f"  Duplicate Count: {count}")
        print(f"  Encounter IDs: {', '.join([str(e.id) for e in encounters])}")
        print(f"  Created Times: {', '.join([str(e.created) for e in encounters])}")
    
    if total_duplicate_groups > 20:
        print(f"\n... and {total_duplicate_groups - 20} more duplicate groups")
    
    print("\n" + "=" * 70)
    print("RECOMMENDATION: Run cleanup command to remove duplicates")
    print("=" * 70)
else:
    print("\n[OK] NO DUPLICATE ENCOUNTERS FOUND!")
    print("=" * 70)

# Also check for very recent duplicates (within 5 minutes)
print("\n" + "=" * 70)
print("CHECKING FOR VERY RECENT DUPLICATES (within 5 minutes)")
print("=" * 70)
print()

recent_cutoff = timezone.now() - timedelta(minutes=5)
recent_duplicates = Encounter.objects.filter(
    is_deleted=False,
    created__gte=recent_cutoff
).values(
    'patient', 'started_at', 'chief_complaint'
).annotate(
    count=Count('id')
).filter(
    count__gt=1
).order_by('-count', '-started_at')

recent_count = recent_duplicates.count()
print(f"Found {recent_count} recent duplicate groups (created in last 5 minutes)\n")

if recent_count > 0:
    print("RECENT DUPLICATES:")
    print("-" * 70)
    for dup in recent_duplicates[:10]:
        patient_id = dup['patient']
        started_at = dup['started_at']
        chief_complaint = dup['chief_complaint'] or '(empty)'
        count = dup['count']
        
        encounters = Encounter.objects.filter(
            patient_id=patient_id,
            started_at=started_at,
            chief_complaint=chief_complaint,
            is_deleted=False
        ).select_related('patient').order_by('created')
        
        patient = encounters.first().patient if encounters.exists() else None
        patient_name = patient.full_name if patient else f"Patient ID: {patient_id}"
        
        print(f"  {patient_name}: {count} duplicates at {started_at}")
else:
    print("[OK] NO RECENT DUPLICATES FOUND!")

print("\n" + "=" * 70)
