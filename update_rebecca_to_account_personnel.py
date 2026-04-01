#!/usr/bin/env python
"""
Update Rebecca to Account Personnel Role
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
from hospital.models import Staff, Department
from hospital.utils_roles import assign_user_to_role, get_user_role

User = get_user_model()

def update_rebecca_to_account_personnel():
    """Update Rebecca to Account Personnel"""
    print("=" * 70)
    print("UPDATING REBECCA TO ACCOUNT PERSONNEL")
    print("=" * 70)
    print()
    
    # Find Rebecca
    username = 'rebecca'
    try:
        user = User.objects.get(username=username)
        print(f"✅ Found user: {user.get_full_name()} ({user.username})")
        print(f"   Email: {user.email or 'No email'}")
    except User.DoesNotExist:
        print(f"❌ User '{username}' not found!")
        return False
    
    print()
    
    # 1. Ensure staff flag is set
    print("[1/4] Ensuring staff privileges...")
    user.is_staff = True
    user.is_active = True
    user.save()
    print("   ✅ Staff privileges set")
    print()
    
    # 2. Get or create staff record
    print("[2/4] Updating staff record...")
    staff, created = Staff.objects.get_or_create(
        user=user,
        defaults={
            'profession': 'account_personnel',
            'is_active': True,
            'is_deleted': False,
        }
    )
    
    if not created:
        old_profession = staff.profession
        staff.profession = 'account_personnel'
        staff.is_active = True
        staff.is_deleted = False
        staff.save()
        print(f"   ✅ Updated profession: {old_profession} → account_personnel")
    else:
        print("   ✅ Created staff record with account_personnel profession")
    
    # Get or create Accounts department
    if not staff.department:
        accounts_dept, dept_created = Department.objects.get_or_create(
            name='Accounts',
            defaults={'description': 'Accounts Department'}
        )
        staff.department = accounts_dept
        staff.save()
        if dept_created:
            print(f"   ✅ Created 'Accounts' department")
        print(f"   ✅ Assigned to Accounts department")
    else:
        print(f"   ✅ Already in department: {staff.department.name}")
    
    print()
    
    # 3. Assign Account Personnel role
    print("[3/4] Assigning Account Personnel role...")
    try:
        assign_user_to_role(user, 'account_personnel')
        print("   ✅ Assigned 'account_personnel' role")
    except Exception as e:
        print(f"   ⚠️  Error assigning role: {e}")
        # Fallback: manually add to group
        group, created = Group.objects.get_or_create(name='Account Personnel')
        user.groups.add(group)
        if created:
            print(f"   ✅ Created 'Account Personnel' group")
        print(f"   ✅ Added to 'Account Personnel' group")
    
    print()
    
    # 4. Verify changes
    print("[4/4] Verifying changes...")
    user.refresh_from_db()
    staff.refresh_from_db()
    
    new_role = get_user_role(user)
    print(f"   ✅ Current profession: {staff.profession}")
    print(f"   ✅ Current role: {new_role}")
    print(f"   ✅ Department: {staff.department.name if staff.department else 'None'}")
    print(f"   ✅ Is Active: {staff.is_active}")
    print(f"   ✅ Groups: {', '.join([g.name for g in user.groups.all()])}")
    
    print()
    print("=" * 70)
    print("✅ SUCCESS! Rebecca is now an Account Personnel")
    print("=" * 70)
    print()
    print("Rebecca will now:")
    print("  - Have profession: account_personnel")
    print("  - Be in Accounts department")
    print("  - Have Account Personnel role access")
    print("  - Be able to access accounting features for account personnel")
    print()
    
    return True

if __name__ == '__main__':
    update_rebecca_to_account_personnel()





