#!/usr/bin/env python
"""
Script to grant Benjamin Business Development and Marketing access
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

def grant_benjamin_business_development():
    """Grant Benjamin Business Development and Marketing access"""
    print("=" * 70)
    print("GRANTING BENJAMIN BUSINESS DEVELOPMENT & MARKETING ACCESS")
    print("=" * 70)
    print()
    
    # Find Benjamin - try multiple username variations
    usernames = ['benjamin.acquah', 'benjamin', 'benjamin.', 'Benjamin']
    user = None
    
    for username in usernames:
        try:
            user = User.objects.get(username__iexact=username)
            print(f"[OK] Found user: {user.get_full_name()} ({user.username})")
            break
        except User.DoesNotExist:
            continue
    
    if not user:
        # Try by first name
        try:
            user = User.objects.filter(first_name__iexact='Benjamin').first()
            if user:
                print(f"[OK] Found user by name: {user.get_full_name()} ({user.username})")
        except:
            pass
    
    if not user:
        print("[ERROR] User 'Benjamin' not found!")
        print("   Available users with 'benjamin' in username:")
        for u in User.objects.filter(username__icontains='benjamin'):
            print(f"   - {u.username} ({u.get_full_name()})")
        return False
    
    print()
    
    # 1. Ensure staff flag is set
    print("[1/5] Ensuring staff privileges...")
    user.is_staff = True
    user.is_active = True
    user.save()
    print("   [OK] Staff privileges set")
    print()
    
    # 2. Get or create staff record with marketing/business_development profession
    print("[2/5] Updating staff record...")
    staff, created = Staff.objects.get_or_create(
        user=user,
        defaults={
            'profession': 'business_development',
            'is_active': True,
            'is_deleted': False,
        }
    )
    
    if not created:
        old_profession = staff.profession
        staff.profession = 'business_development'
        staff.is_active = True
        staff.is_deleted = False
        staff.save()
        print(f"   [OK] Updated profession: {old_profession} -> business_development")
    else:
        print("   [OK] Created staff record with business_development profession")
    
    # Get or create Marketing/Business Development department
    if not staff.department:
        marketing_dept, dept_created = Department.objects.get_or_create(
            name='Marketing & Business Development',
            defaults={'description': 'Marketing and Business Development Department'}
        )
        if not marketing_dept:
            # Try Marketing
            marketing_dept, dept_created = Department.objects.get_or_create(
                name='Marketing',
                defaults={'description': 'Marketing Department'}
            )
        staff.department = marketing_dept
        staff.save()
        if dept_created:
            print(f"   [OK] Created '{marketing_dept.name}' department")
        print(f"   [OK] Assigned to {marketing_dept.name} department")
    else:
        print(f"   [OK] Already in department: {staff.department.name}")
    
    print()
    
    # 3. Assign Marketing/Business Development groups
    print("[3/5] Assigning Marketing/Business Development groups...")
    marketing_groups = ['Marketing', 'Business Development', 'Marketing & Business Development', 'BD']
    
    for group_name in marketing_groups:
        group, group_created = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
        if group_created:
            print(f"   [OK] Created '{group_name}' group")
        print(f"   [OK] Added to '{group_name}' group")
    
    # Remove from other groups that might give unwanted access
    unwanted_groups = ['Admin', 'Procurement', 'Store Manager', 'Account Personnel', 'Accountant']
    for group_name in unwanted_groups:
        try:
            group = Group.objects.get(name=group_name)
            if group in user.groups.all():
                user.groups.remove(group)
                print(f"   [OK] Removed from '{group_name}' group")
        except Group.DoesNotExist:
            pass
    
    print()
    
    # 4. Verify changes
    print("[4/5] Verifying changes...")
    user.refresh_from_db()
    staff.refresh_from_db()
    
    new_role = get_user_role(user)
    print(f"   [OK] Current profession: {staff.profession}")
    print(f"   [OK] Current role: {new_role}")
    print(f"   [OK] Department: {staff.department.name if staff.department else 'None'}")
    print(f"   [OK] Is Active: {staff.is_active}")
    print(f"   [OK] Is Staff: {user.is_staff}")
    print(f"   [OK] Groups: {', '.join([g.name for g in user.groups.all()])}")
    
    print()
    
    # 5. Test marketing access
    print("[5/5] Testing marketing access...")
    from hospital.utils_roles import get_role_navigation
    nav_items = get_role_navigation(user)
    print(f"   [OK] Navigation items: {len(nav_items)}")
    print("   [OK] Available tools:")
    for item in nav_items:
        print(f"      - {item.get('title', 'No title')}: {item.get('url', 'No URL')}")
    
    print()
    print("=" * 70)
    print("[OK] SUCCESS! Benjamin now has Business Development & Marketing access")
    print("=" * 70)
    print()
    print("Benjamin will now:")
    print("  - Have profession: business_development")
    print("  - Be in Marketing & Business Development department")
    print("  - Have Marketing role access")
    print("  - Can access Marketing Dashboard")
    print("  - Can access Business Development tools")
    print("  - Can manage Marketing Objectives")
    print("  - Can manage Marketing Campaigns")
    print("  - Can manage Corporate Partnerships")
    print("  - Can view Marketing Metrics")
    print()
    
    return True

if __name__ == '__main__':
    grant_benjamin_business_development()
