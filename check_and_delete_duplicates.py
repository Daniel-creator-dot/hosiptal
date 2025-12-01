#!/usr/bin/env python
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Staff
from django.contrib.auth.models import User
from django.db.models import Count
from django.db import transaction

print("=" * 70)
print("CHECKING FOR DUPLICATE STAFF RECORDS")
print("=" * 70)
print()

# Find users with multiple staff records
duplicates = Staff.objects.filter(is_deleted=False).values('user').annotate(
    count=Count('id')
).filter(count__gt=1).order_by('-count')

print(f"Found {duplicates.count()} users with multiple staff records\n")

if duplicates.count() == 0:
    print("No duplicates found by user_id")
    print("\nChecking by phone number...")
    
    # Check by phone number
    phone_duplicates = Staff.objects.filter(
        is_deleted=False,
        phone_number__isnull=False
    ).exclude(phone_number='').values('phone_number').annotate(
        count=Count('id')
    ).filter(count__gt=1)
    
    print(f"Found {phone_duplicates.count()} phone numbers with multiple staff records")
    
    if phone_duplicates.count() > 0:
        print("\nPhone number duplicates:")
        for dup in phone_duplicates[:10]:
            phone = dup['phone_number']
            count = dup['count']
            staff_list = Staff.objects.filter(
                phone_number=phone,
                is_deleted=False
            ).select_related('user')
            print(f"\n  Phone: {phone} - {count} records:")
            for staff in staff_list:
                print(f"    - User: {staff.user.get_full_name()} ({staff.user.username}), "
                      f"Staff ID: {staff.id}, Employee ID: {staff.employee_id}, "
                      f"User ID: {staff.user_id}")

else:
    total_to_delete = 0
    records_to_delete = []
    
    for dup in duplicates:
        user_id = dup['user']
        count = dup['count']
        total_to_delete += (count - 1)
        
        try:
            user = User.objects.get(id=user_id)
            staff_records = Staff.objects.filter(
                user=user,
                is_deleted=False
            ).order_by('-created')
            
            keep = staff_records.first()
            delete_list = list(staff_records[1:])
            
            print(f"\nUser: {user.get_full_name()} ({user.username}) - {count} records")
            print(f"  Keeping: Staff ID {keep.id}, Employee ID: {keep.employee_id}")
            print(f"  Deleting {len(delete_list)}:")
            for staff in delete_list:
                print(f"    - Staff ID: {staff.id}, Employee ID: {staff.employee_id}")
                records_to_delete.append(staff)
        except Exception as e:
            print(f"Error: {e}")
    
    print("\n" + "=" * 70)
    print(f"Total to delete: {len(records_to_delete)}")
    print("=" * 70)
    
    if records_to_delete:
        response = input("\nDelete these duplicates? (yes/no): ")
        if response.lower() == 'yes':
            deleted = 0
            with transaction.atomic():
                for staff in records_to_delete:
                    staff.is_deleted = True
                    staff.save(update_fields=['is_deleted'])
                    deleted += 1
            print(f"\n✅ Deleted {deleted} duplicate records")
        else:
            print("\nCancelled")


