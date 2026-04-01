#!/usr/bin/env python
"""
Update Robbert to Senior Account Officer Role
Removes superuser status and restricts to accounting + account staff management only
"""
import os
import sys
import django
from datetime import date

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from hospital.models import Staff, Department
from hospital.utils_roles import assign_user_to_role, create_default_groups

User = get_user_model()

def update_robbert_to_senior_account_officer():
    """
    Update Robbert to Senior Account Officer
    - Remove superuser status
    - Set profession to senior_account_officer
    - Assign senior_account_officer role
    - Restrict to accounting and account staff only
    """
    print("=" * 70)
    print("UPDATING ROBBERT TO SENIOR ACCOUNT OFFICER")
    print("=" * 70)
    print()
    
    # Find Robbert
    username = None
    user = None
    
    for possible_username in ['robbert.kwamegbologah', 'robbert', 'robbert.kwame']:
        try:
            user = User.objects.get(username=possible_username)
            username = possible_username
            break
        except User.DoesNotExist:
            continue
    
    if not user:
        users = User.objects.filter(username__icontains='robbert')
        if users.exists():
            user = users.first()
            username = user.username
        else:
            print("❌ User 'robbert' not found!")
            print()
            print("Available users with 'robbert':")
            users = User.objects.filter(username__icontains='robbert')
            for u in users:
                print(f"  - {u.username} ({u.email})")
            return False
    
    print(f"✅ Found user: {username}")
    print(f"   Email: {user.email or 'No email'}")
    print(f"   Full Name: {user.get_full_name()}")
    print()
    
    # 1. Remove superuser status (CRITICAL - restricts to accounting only)
    print("[1/5] Removing superuser status (restricting to accounting only)...")
    if user.is_superuser:
        user.is_superuser = False
        user.save()
        print("   ✅ Removed superuser status")
    else:
        print("   ✅ Already not a superuser")
    print()
    
    # 2. Ensure staff flag is set
    print("[2/5] Ensuring staff privileges...")
    user.is_staff = True
    user.is_active = True
    user.save()
    print("   ✅ Staff privileges set")
    print()
    
    # 3. Get or create staff record
    print("[3/5] Updating staff record...")
    staff, created = Staff.objects.get_or_create(
        user=user,
        defaults={
            'profession': 'account_officer',  # Use account_officer as base, role will be senior_account_officer
            'is_active': True,
            'is_deleted': False,
        }
    )
    
    if not created:
        old_profession = staff.get_profession_display()
        # Use account_officer profession (role will be senior_account_officer via group)
        staff.profession = 'account_officer'
        staff.is_active = True
        staff.is_deleted = False
        staff.save()
        print(f"   ✅ Updated profession: {old_profession} → Account Officer (Senior role via group)")
    else:
        print("   ✅ Created staff record with Account Officer profession (Senior role via group)")
    
    # Get or create Accounts department
    if not staff.department:
        dept = Department.objects.filter(name__icontains='account').first()
        if not dept:
            dept = Department.objects.filter(name__icontains='finance').first()
        if not dept:
            dept = Department.objects.create(
                name='Accounts',
                code='ACC',
                description='Accounts Department',
                is_active=True
            )
        staff.department = dept
        staff.save()
    
    print(f"   ✅ Department: {staff.department.name}")
    print()
    
    # 4. Create default groups if needed
    print("[4/5] Ensuring role groups exist...")
    create_default_groups()
    print("   ✅ Role groups ready")
    print()
    
    # 5. Assign senior_account_officer role
    print("[5/5] Assigning Senior Account Officer role...")
    assign_user_to_role(user, 'senior_account_officer')
    
    # Also add to group explicitly
    group, _ = Group.objects.get_or_create(name='Senior Account Officer')
    user.groups.clear()  # Clear existing groups
    user.groups.add(group)
    user.save()
    
    print("   ✅ Assigned Senior Account Officer role")
    print("   ✅ Added to Senior Account Officer group")
    print()
    
    # Summary
    print("=" * 70)
    print("✅ UPDATE COMPLETE!")
    print("=" * 70)
    print()
    print("User Details:")
    print(f"  Username: {username}")
    print(f"  Email: {user.email}")
    print(f"  Full Name: {user.get_full_name()}")
    print(f"  Employee ID: {staff.employee_id}")
    print()
    print("Role & Access:")
    print(f"  Role: Senior Account Officer")
    print(f"  Dashboard: /hms/senior-account-officer/dashboard/")
    print(f"  Groups: {[g.name for g in user.groups.all()]}")
    print()
    print("Access Restrictions:")
    print("  ✅ Full accounting access")
    print("  ✅ Account staff management (accountants, officers, personnel)")
    print("  ❌ NO superuser access")
    print("  ❌ NO general staff management (HR function)")
    print("  ❌ NO admin dashboard access")
    print()
    print("Login:")
    print(f"  URL: http://127.0.0.1:8000/hms/login/")
    print(f"  Username: {username}")
    print()
    print("=" * 70)
    
    return True

if __name__ == '__main__':
    try:
        update_robbert_to_senior_account_officer()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

