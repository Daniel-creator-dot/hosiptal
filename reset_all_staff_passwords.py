#!/usr/bin/env python
"""
Reset all staff passwords to a default password.
Run this from the project root: python reset_all_staff_passwords.py
Or via Docker: docker-compose exec web python reset_all_staff_passwords.py
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth import get_user_model
from hospital.models import Staff

User = get_user_model()

def reset_all_staff_passwords(default_password='staff123'):
    """Reset passwords for all active staff users"""
    print("=" * 70)
    print("RESETTING ALL STAFF PASSWORDS")
    print("=" * 70)
    print()
    
    # Get all active staff
    staff_list = Staff.objects.filter(is_deleted=False, is_active=True).select_related('user')
    
    updated = 0
    no_user = 0
    missing_users = []
    
    print(f"Found {staff_list.count()} active staff records")
    print()
    
    for staff in staff_list:
        if staff.user:
            # Reset password
            staff.user.set_password(default_password)
            staff.user.is_active = True
            staff.user.save()
            updated += 1
            print(f"✅ {staff.user.username:20} - {staff.user.get_full_name():30} - {staff.profession}")
        else:
            no_user += 1
            missing_users.append({
                'employee_id': staff.employee_id,
                'profession': staff.profession
            })
            print(f"⚠️  {staff.employee_id:20} - NO USER ACCOUNT - {staff.profession}")
    
    print()
    print("=" * 70)
    print(f"✅ Updated: {updated} staff passwords")
    print(f"⚠️  No user account: {no_user} staff records")
    print()
    print(f"Default password for all staff: {default_password}")
    print()
    
    if missing_users:
        print("Staff records without user accounts:")
        for item in missing_users[:10]:
            print(f"  - {item['employee_id']} ({item['profession']})")
        if len(missing_users) > 10:
            print(f"  ... and {len(missing_users) - 10} more")
        print()
        print("These staff records need user accounts created.")
        print("You can create them via the admin panel or StaffForm.")
    
    print("=" * 70)
    return updated, no_user

if __name__ == '__main__':
    import sys
    
    # Get password from command line or use default
    default_password = sys.argv[1] if len(sys.argv) > 1 else 'staff123'
    
    reset_all_staff_passwords(default_password)






