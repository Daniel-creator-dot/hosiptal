#!/usr/bin/env python
"""
Update Esther Og to Procurement Officer
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from hospital.models import Staff
from hospital.utils_roles import ROLE_FEATURES, assign_user_to_role, create_default_groups

User = get_user_model()

def update_esther_og():
    """Find and update Esther Og to procurement officer"""
    print("=" * 70)
    print("UPDATING ESTHER OG TO PROCUREMENT OFFICER")
    print("=" * 70)
    print()
    
    # Search for Esther Og
    found = False
    
    # Search by username
    users = User.objects.filter(username__icontains='esther') | User.objects.filter(username__icontains='og') | User.objects.filter(email__icontains='esther')
    staff_list = Staff.objects.none()
    
    if users.exists():
        for user in users:
            try:
                staff = Staff.objects.get(user=user, is_deleted=False)
                staff_list = Staff.objects.filter(pk=staff.pk) | staff_list
            except:
                pass
    
    # Also search all staff and look for similar names
    if not staff_list.exists():
        all_staff = Staff.objects.filter(is_deleted=False).select_related('user')
        for staff in all_staff:
            if staff.user:
                username_lower = staff.user.username.lower()
                email_lower = (staff.user.email or '').lower()
                if 'esther' in username_lower or 'og' in username_lower or 'esther' in email_lower:
                    staff_list = Staff.objects.filter(pk=staff.pk) | staff_list
    
    if not staff_list.exists():
        print("❌ Esther Og not found!")
        print()
        print("Searching all staff for similar names...")
        all_staff = Staff.objects.filter(is_deleted=False)[:50]
        for s in all_staff:
            if s.user:
                print(f"  - {s.first_name} {s.last_name} ({s.user.username}) - {s.profession}")
        return False
    
    # Update each matching staff
    for staff in staff_list:
        user_name = staff.user.get_full_name() if staff.user else 'No user'
        if not user_name or user_name.strip() == '':
            user_name = staff.user.username if staff.user else 'No user'
        print(f"Found: {user_name}")
        print(f"  Username: {staff.user.username if staff.user else 'No user'}")
        print(f"  Email: {staff.user.email if staff.user else 'No email'}")
        print(f"  Current Profession: {staff.profession}")
        print()
        
        # Update profession to store_manager (closest to procurement)
        # We'll use store_manager as it has procurement access
        old_profession = staff.profession
        staff.profession = 'store_manager'  # This gives procurement access
        staff.save()
        print(f"✅ Updated profession from '{old_profession}' to 'store_manager'")
        
        # Assign to Procurement group
        if staff.user:
            # Create Procurement group if it doesn't exist
            group, created = Group.objects.get_or_create(name='Procurement')
            if created:
                print(f"✅ Created 'Procurement' group")
            
            # Add user to group
            staff.user.groups.add(group)
            print(f"✅ Added {staff.user.username} to 'Procurement' group")
            
            # Make sure user is staff
            if not staff.user.is_staff:
                staff.user.is_staff = True
                staff.user.save()
                print(f"✅ Set {staff.user.username} as staff")
        
        found = True
        print()
    
    if found:
        print("=" * 70)
        print("✅ ESTHER OG UPDATED SUCCESSFULLY!")
        print("=" * 70)
        print()
        print("She can now access:")
        print("  - Procurement Dashboard: /hms/procurement/")
        print("  - Inventory Management")
        print("  - Store Management")
        print("  - Procurement Requests")
        print()
    else:
        print("❌ No matching staff found to update")
    
    return found

if __name__ == '__main__':
    update_esther_og()

