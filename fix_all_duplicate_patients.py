"""
Script to fix ALL duplicate patients that are blocking migrations
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hms.settings")
django.setup()

from hospital.models import Patient
from django.db.models import Count, Q
from django.db import transaction

def fix_all_duplicates():
    """Fix all duplicate patients"""
    print("=" * 70)
    print("FIXING ALL DUPLICATE PATIENTS")
    print("=" * 70)
    print()
    
    # Find all duplicate groups
    duplicates = Patient.objects.filter(
        is_deleted=False
    ).exclude(
        date_of_birth='2000-01-01'  # Exclude placeholder DOB
    ).values(
        'first_name', 'last_name', 'phone_number', 'date_of_birth'
    ).annotate(
        count=Count('id')
    ).filter(count__gt=1)
    
    total_groups = duplicates.count()
    print(f"Found {total_groups} duplicate patient groups")
    print()
    
    fixed_count = 0
    
    for dup_group in duplicates:
        first_name = dup_group['first_name']
        last_name = dup_group['last_name']
        phone = dup_group['phone_number']
        dob = dup_group['date_of_birth']
        
        # Get all patients with these details
        patients = Patient.objects.filter(
            first_name=first_name,
            last_name=last_name,
            phone_number=phone,
            date_of_birth=dob,
            is_deleted=False
        ).order_by('created')
        
        if patients.count() > 1:
            print(f"Fixing: {first_name} {last_name} ({phone}, DOB: {dob})")
            print(f"  Found {patients.count()} duplicates")
            
            # Keep the first one, mark others as deleted
            primary = patients.first()
            duplicates_to_fix = patients.exclude(id=primary.id)
            
            with transaction.atomic():
                for dup in duplicates_to_fix:
                    dup.is_deleted = True
                    dup.save(update_fields=['is_deleted', 'modified'])
                    print(f"  ✅ Deleted duplicate ID {dup.id}")
                    fixed_count += 1
            print()
    
    print("=" * 70)
    print(f"✅ Fixed {fixed_count} duplicate patient records")
    print(f"✅ Processed {total_groups} duplicate groups")
    print("=" * 70)

if __name__ == "__main__":
    fix_all_duplicates()














