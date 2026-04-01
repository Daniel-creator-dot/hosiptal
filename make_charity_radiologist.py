#!/usr/bin/env python
"""
Script to make Charity a Radiologist
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
from hospital.utils_roles import assign_user_to_role, get_user_role, get_user_dashboard_url, ROLE_FEATURES

def make_charity_radiologist():
    """Change Charity to Radiologist"""
    print("=" * 70)
    print("MAKING CHARITY A RADIOLOGIST")
    print("=" * 70)
    print()
    
    # Find Charity by username (try different variations)
    usernames_to_try = ['charity.kotey', 'charity', 'Charity', 'CHARITY']
    user = None
    
    for username in usernames_to_try:
        try:
            user = User.objects.get(username=username)
            print(f"✅ Found user: {user.get_full_name()} ({user.username})")
            print(f"   Email: {user.email or 'No email'}")
            break
        except User.DoesNotExist:
            continue
    
    if not user:
        # Try case-insensitive search
        try:
            user = User.objects.filter(username__icontains='charity').first()
            if user:
                print(f"✅ Found user: {user.get_full_name()} ({user.username})")
                print(f"   Email: {user.email or 'No email'}")
        except:
            pass
    
    if not user:
        print("❌ User 'charity' not found!")
        print("\nAvailable users with 'charity' in username:")
        users = User.objects.filter(username__icontains='charity')
        for u in users:
            print(f"   - {u.username} ({u.get_full_name()})")
        return False
    
    print()
    
    # 1. Ensure staff flag is set
    print("[1/5] Ensuring staff privileges...")
    user.is_staff = True
    user.is_active = True
    user.save()
    print("   ✅ Staff privileges set")
    print()
    
    # 2. Get or create staff record
    print("[2/5] Updating staff record...")
    staff, created = Staff.objects.get_or_create(
        user=user,
        defaults={
            'profession': 'radiologist',
            'is_active': True,
            'is_deleted': False,
        }
    )
    
    if not created:
        old_profession = staff.get_profession_display()
        staff.profession = 'radiologist'
        staff.is_active = True
        staff.is_deleted = False
        staff.save()
        print(f"   ✅ Updated profession: {old_profession} → Radiologist")
    else:
        print("   ✅ Created staff record with Radiologist profession")
    
    # Get or create Radiology/Imaging department
    if not staff.department:
        dept = Department.objects.filter(
            name__icontains='radiology'
        ).first()
        if not dept:
            dept = Department.objects.filter(
                name__icontains='imaging'
            ).first()
        if not dept:
            dept = Department.objects.filter(
                name__icontains='diagnostic'
            ).first()
        if not dept:
            # Create Radiology department
            dept = Department.objects.create(
                name='Radiology',
                code='RAD',
                description='Radiology and Imaging Department',
                is_active=True
            )
        staff.department = dept
        staff.save()
    
    print(f"   ✅ Department: {staff.department.name}")
    print()
    
    # 3. Assign radiologist role group
    print("[3/5] Assigning radiologist role group...")
    try:
        group, group_created = Group.objects.get_or_create(name='Radiologist')
        user.groups.add(group)
        print(f"   ✅ Added to 'Radiologist' group")
    except Exception as e:
        print(f"   ⚠️  Could not add to group: {e}")
    print()
    
    # 4. Assign radiologist role using utility
    print("[4/5] Assigning radiologist role...")
    try:
        assign_user_to_role(user, 'radiologist')
        print(f"   ✅ Assigned role: {ROLE_FEATURES['radiologist']['name']}")
    except Exception as e:
        print(f"   ⚠️  Could not assign role via utility: {e}")
    print()
    
    # 5. Verify changes
    print("[5/5] Verifying changes...")
    user.refresh_from_db()
    staff.refresh_from_db()
    new_role = get_user_role(user)
    dashboard_url = get_user_dashboard_url(user, new_role)
    
    print(f"   ✅ Current role: {new_role}")
    print(f"   ✅ Dashboard URL: {dashboard_url}")
    print(f"   ✅ Profession: {staff.get_profession_display()}")
    print(f"   ✅ Department: {staff.department.name}")
    print()
    
    print("=" * 70)
    print("✅ CHARITY IS NOW A RADIOLOGIST!")
    print("=" * 70)
    print()
    print("Summary:")
    print(f"   Username: {user.username}")
    print(f"   Full Name: {user.get_full_name()}")
    print(f"   Profession: {staff.get_profession_display()}")
    print(f"   Department: {staff.department.name}")
    print(f"   Role: {new_role}")
    print(f"   Dashboard: {dashboard_url}")
    print()
    print("Charity can now:")
    print("   - Access Radiology Dashboard at /hms/dashboard/radiology/")
    print("   - View and manage imaging studies")
    print("   - Create and verify imaging reports")
    print("   - Access all radiology features")
    print()
    
    return True

if __name__ == '__main__':
    make_charity_radiologist()

