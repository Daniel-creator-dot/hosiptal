#!/usr/bin/env python
"""
Setup Role-Based Dashboards for All Users
Assigns appropriate roles based on staff profession
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

def setup_all_roles():
    """Setup roles for all users based on their staff profession"""
    print("=" * 70)
    print("SETTING UP ROLE-BASED DASHBOARDS FOR ALL USERS")
    print("=" * 70)
    print()
    
    # Create default groups
    print("Creating default role groups...")
    create_default_groups()
    print("✅ Default groups created")
    print()
    
    # Profession to role mapping (only map to roles that exist in ROLE_FEATURES)
    profession_role_map = {
        'doctor': 'doctor',
        'nurse': 'nurse',
        'pharmacist': 'pharmacist',
        'lab_technician': 'lab_technician',
        'receptionist': 'receptionist',
        'cashier': 'cashier',
        'radiologist': 'lab_technician',  # Map radiologist to lab_technician for now
        'store_manager': 'store_manager',
    }
    
    # Special assignments
    special_assignments = {
        'robbert.kwamegbologah': 'accountant',
        'nana.yaab.asamoah': 'accountant',  # Also in Accounts department
    }
    
    assigned_count = 0
    skipped_count = 0
    
    print("Assigning roles to staff...")
    print()
    
    # Get all active staff
    all_staff = Staff.objects.filter(is_active=True, is_deleted=False).select_related('user')
    
    for staff in all_staff:
        user = staff.user
        
        # Skip if user doesn't exist
        if not user:
            continue
        
        # Check for special assignment first
        if user.username in special_assignments:
            role = special_assignments[user.username]
            assign_user_to_role(user, role)
            assigned_count += 1
            print(f"  ✅ {user.get_full_name():30} ({user.username:25}) → {ROLE_FEATURES[role]['name']}")
            continue
        
        # Skip superusers (they're already admins)
        if user.is_superuser:
            print(f"  ⚠️  {user.get_full_name():30} ({user.username:25}) → Admin (superuser)")
            skipped_count += 1
            continue
        
        # Map profession to role
        profession = (staff.profession or '').lower()
        role = profession_role_map.get(profession)
        
        if role and role in ROLE_FEATURES:
            assign_user_to_role(user, role)
            assigned_count += 1
            print(f"  ✅ {user.get_full_name():30} ({user.username:25}) → {ROLE_FEATURES[role]['name']}")
        else:
            # For admin profession, check if they should be accountant or hr_manager
            if profession == 'admin':
                # Check department or name
                dept_name = (staff.department.name.lower() if staff.department else '')
                if 'account' in dept_name or 'accountant' in user.get_full_name().lower():
                    assign_user_to_role(user, 'accountant')
                    assigned_count += 1
                    print(f"  ✅ {user.get_full_name():30} ({user.username:25}) → Accountant (from Accounts dept)")
                elif 'hr' in dept_name or 'human resource' in dept_name:
                    assign_user_to_role(user, 'hr_manager')
                    assigned_count += 1
                    print(f"  ✅ {user.get_full_name():30} ({user.username:25}) → HR Manager (from HR dept)")
                else:
                    print(f"  ⚠️  {user.get_full_name():30} ({user.username:25}) → No role (admin profession)")
                    skipped_count += 1
            else:
                print(f"  ⚠️  {user.get_full_name():30} ({user.username:25}) → No role mapping for '{profession}'")
                skipped_count += 1
    
    print()
    print("=" * 70)
    print(f"✅ ROLE ASSIGNMENT COMPLETE!")
    print("=" * 70)
    print()
    print(f"Summary:")
    print(f"  - Assigned roles: {assigned_count}")
    print(f"  - Skipped: {skipped_count}")
    print()
    print("Users will now be redirected to their role-specific dashboards on login!")
    print()

if __name__ == '__main__':
    setup_all_roles()

