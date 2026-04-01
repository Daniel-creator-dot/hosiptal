#!/usr/bin/env python
"""
Update Ebenezer to use the same department and dashboard as Robbert
Since Account and Finance are one department, they should be together
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth.models import User, Group
from hospital.models import Staff, Department

def update_ebenezer_same_as_robbert():
    print("=" * 70)
    print("UPDATING EBENEZER TO USE SAME DEPARTMENT & DASHBOARD AS ROBBERT")
    print("=" * 70)
    print()
    
    # 1. Find Robbert
    print("[1/5] Finding Robbert...")
    robbert = None
    for username in ['robbert.kwamegbologah', 'robbert', 'robbert.kwame']:
        try:
            user = User.objects.filter(username__icontains=username).first()
            if user:
                robbert = Staff.objects.filter(user=user, is_deleted=False).first()
                if robbert:
                    break
        except:
            continue
    
    if not robbert:
        # Try searching by name
        robbert = Staff.objects.filter(
            user__first_name__icontains='Robbert',
            is_deleted=False
        ).first()
    
    if not robbert:
        print("  [ERROR] Robbert not found!")
        return False
    
    print(f"  [OK] Found Robbert: {robbert.user.get_full_name()} ({robbert.user.username})")
    print(f"  [OK] Robbert's Department: {robbert.department.name if robbert.department else 'None'}")
    print(f"  [OK] Robbert's Profession: {robbert.profession}")
    print()
    
    # 2. Find Ebenezer
    print("[2/5] Finding Ebenezer...")
    ebenezer = None
    for username in ['ebenezer.donkor', 'ebenezer', 'ebenezer.moses']:
        try:
            user = User.objects.filter(username__icontains=username).first()
            if user:
                ebenezer = Staff.objects.filter(user=user, is_deleted=False).first()
                if ebenezer:
                    break
        except:
            continue
    
    if not ebenezer:
        # Try searching by name
        ebenezer = Staff.objects.filter(
            user__first_name__icontains='Ebenezer',
            is_deleted=False
        ).first()
    
    if not ebenezer:
        print("  [ERROR] Ebenezer not found!")
        print("  Searching all users with 'ebenezer' in name...")
        users = User.objects.filter(
            username__icontains='ebenezer'
        ) | User.objects.filter(
            first_name__icontains='ebenezer'
        ) | User.objects.filter(
            last_name__icontains='ebenezer'
        )
        for u in users[:5]:
            print(f"    - {u.username} ({u.get_full_name()})")
        return False
    
    print(f"  [OK] Found Ebenezer: {ebenezer.user.get_full_name()} ({ebenezer.user.username})")
    print(f"  [OK] Current Department: {ebenezer.department.name if ebenezer.department else 'None'}")
    print(f"  [OK] Current Profession: {ebenezer.profession}")
    print()
    
    # 3. Update Ebenezer to use Robbert's department
    print("[3/5] Updating Ebenezer's department to match Robbert...")
    if robbert.department:
        ebenezer.department = robbert.department
        ebenezer.save()
        print(f"  [OK] Updated Ebenezer's department to: {robbert.department.name}")
    else:
        print("  [WARNING] Robbert has no department assigned!")
    print()
    
    # 4. Update Ebenezer's profession to match Robbert (if needed)
    print("[4/5] Updating Ebenezer's profession...")
    if robbert.profession:
        ebenezer.profession = robbert.profession
        ebenezer.save()
        print(f"  [OK] Updated Ebenezer's profession to: {robbert.profession}")
    print()
    
    # 5. Ensure both are in the same groups
    print("[5/5] Ensuring both are in Accountant group...")
    accountant_group, created = Group.objects.get_or_create(name='Accountant')
    if created:
        print(f"  [OK] Created Accountant group")
    
    # Add Robbert to Accountant group if not already
    if accountant_group not in robbert.user.groups.all():
        robbert.user.groups.add(accountant_group)
        print(f"  [OK] Added Robbert to Accountant group")
    else:
        print(f"  [INFO] Robbert already in Accountant group")
    
    # Add Ebenezer to Accountant group if not already
    if accountant_group not in ebenezer.user.groups.all():
        ebenezer.user.groups.add(accountant_group)
        print(f"  [OK] Added Ebenezer to Accountant group")
    else:
        print(f"  [INFO] Ebenezer already in Accountant group")
    print()
    
    # Summary
    print("=" * 70)
    print("UPDATE COMPLETE!")
    print("=" * 70)
    print()
    print("ROBBERT:")
    print(f"  Username: {robbert.user.username}")
    print(f"  Department: {robbert.department.name if robbert.department else 'None'}")
    print(f"  Profession: {robbert.profession}")
    print(f"  Dashboard: /hms/accountant/comprehensive-dashboard/")
    print()
    print("EBENEZER:")
    print(f"  Username: {ebenezer.user.username}")
    print(f"  Department: {ebenezer.department.name if ebenezer.department else 'None'}")
    print(f"  Profession: {ebenezer.profession}")
    print(f"  Dashboard: /hms/accountant/comprehensive-dashboard/")
    print()
    print("[OK] Both users are now in the same department and will use the same dashboard!")
    print()
    print("Both will be automatically redirected to:")
    print("  /hms/accountant/comprehensive-dashboard/")
    print()
    
    return True

if __name__ == '__main__':
    update_ebenezer_same_as_robbert()

