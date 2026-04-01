#!/usr/bin/env python
"""
Script to assign Rebecca to Procurement role
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth.models import User, Group
from hospital.models import Staff, Department
from hospital.utils_roles import get_user_role

def make_rebecca_procurement():
    """Assign Rebecca to Procurement role"""
    print("=" * 70)
    print("ASSIGNING REBECCA TO PROCUREMENT ROLE")
    print("=" * 70)
    print()
    
    # Find Rebecca - try multiple username variations
    usernames = ['rebecca', 'rebecca.', 'Rebecca']
    user = None
    
    for username in usernames:
        try:
            user = User.objects.get(username__iexact=username)
            print(f"✅ Found user: {user.get_full_name()} ({user.username})")
            break
        except User.DoesNotExist:
            continue
    
    if not user:
        # Try by first name
        try:
            user = User.objects.filter(first_name__iexact='Rebecca').first()
            if user:
                print(f"✅ Found user by name: {user.get_full_name()} ({user.username})")
        except:
            pass
    
    if not user:
        print("❌ User 'Rebecca' not found!")
        print("   Available users with 'rebecca' in username:")
        for u in User.objects.filter(username__icontains='rebecca'):
            print(f"   - {u.username} ({u.get_full_name()})")
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
            'profession': 'store_manager',
            'is_active': True,
            'is_deleted': False,
        }
    )
    
    if not created:
        old_profession = staff.profession
        staff.profession = 'store_manager'  # Procurement officer profession
        staff.is_active = True
        staff.is_deleted = False
        staff.save()
        print(f"   ✅ Updated profession: {old_profession} → store_manager")
    else:
        print("   ✅ Created staff record with store_manager profession")
    
    # Get or create Procurement/Stores department
    if not staff.department:
        procurement_dept, dept_created = Department.objects.get_or_create(
            name='Procurement',
            defaults={'description': 'Procurement and Stores Department'}
        )
        if not procurement_dept:
            # Try Stores
            procurement_dept, dept_created = Department.objects.get_or_create(
                name='Stores',
                defaults={'description': 'Stores Department'}
            )
        staff.department = procurement_dept
        staff.save()
        if dept_created:
            print(f"   ✅ Created '{procurement_dept.name}' department")
        print(f"   ✅ Assigned to {procurement_dept.name} department")
    else:
        print(f"   ✅ Already in department: {staff.department.name}")
    
    print()
    
    # 3. Assign Procurement groups
    print("[3/4] Assigning Procurement groups...")
    procurement_groups = ['Procurement', 'Procurement Officer', 'Store Manager']
    
    for group_name in procurement_groups:
        group, group_created = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
        if group_created:
            print(f"   ✅ Created '{group_name}' group")
        print(f"   ✅ Added to '{group_name}' group")
    
    # Also add to Admin group if needed for full access
    admin_group, _ = Group.objects.get_or_create(name='Admin')
    if admin_group not in user.groups.all():
        user.groups.add(admin_group)
        print(f"   ✅ Added to 'Admin' group for full access")
    
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
    
    # Test procurement access
    from hospital.utils_roles import is_procurement_staff
    has_access = is_procurement_staff(user)
    print(f"   ✅ Has Procurement Access: {has_access}")
    
    print()
    print("=" * 70)
    print("✅ SUCCESS! Rebecca is now a Procurement Officer")
    print("=" * 70)
    print()
    print("Rebecca will now:")
    print("  - Have profession: store_manager")
    print("  - Be in Procurement/Stores department")
    print("  - Have Procurement role access")
    print("  - Can access all procurement and transfer features")
    print()
    
    return True

if __name__ == '__main__':
    make_rebecca_procurement()
