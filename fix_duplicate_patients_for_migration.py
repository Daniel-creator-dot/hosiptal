"""
Script to fix duplicate patients that are blocking migrations
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hms.settings")
django.setup()

from hospital.models import Patient
from django.db.models import Count
from django.db import transaction

def fix_duplicate_patients():
    """Fix duplicate patients that prevent unique index creation"""
    print("=" * 70)
    print("FIXING DUPLICATE PATIENTS FOR MIGRATION")
    print("=" * 70)
    print()
    
    # Find duplicates based on the unique constraint fields
    duplicates = Patient.objects.filter(
        is_deleted=False
    ).values(
        'first_name', 'last_name', 'phone_number', 'date_of_birth'
    ).annotate(
        count=Count('id')
    ).filter(count__gt=1)
    
    print(f"Found {duplicates.count()} duplicate patient groups")
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
        
        print(f"Duplicate group: {first_name} {last_name} ({phone}, DOB: {dob})")
        print(f"  Found {patients.count()} duplicate records")
        
        # Keep the first one, mark others as deleted
        if patients.count() > 1:
            primary = patients.first()
            duplicates_to_fix = patients.exclude(id=primary.id)
            
            with transaction.atomic():
                for dup in duplicates_to_fix:
                    # Soft delete the duplicate
                    dup.is_deleted = True
                    dup.save(update_fields=['is_deleted', 'modified'])
                    print(f"  ✅ Marked duplicate as deleted: ID {dup.id} (created {dup.created})")
                    fixed_count += 1
            print()
    
    print("=" * 70)
    print(f"✅ Fixed {fixed_count} duplicate patient records")
    print("=" * 70)
    print()
    print("You can now run: python manage.py migrate")

if __name__ == "__main__":
    fix_duplicate_patients()














