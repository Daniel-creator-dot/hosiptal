#!/usr/bin/env python
"""
Ensure Ebenezer Donkor has full financial admin access
This script completes the setup by adding him to Accountant group
and ensuring his staff record is properly configured.
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth.models import User, Group
from hospital.models import Staff, Department

def ensure_ebenezer_financial_access():
    """Ensure Ebenezer has full financial admin access"""
    print("=" * 70)
    print("ENSURING EBENEZER DONKOR HAS FULL FINANCIAL ADMIN ACCESS")
    print("=" * 70)
    print()
    
    # Find Ebenezer
    try:
        user = User.objects.get(username='ebenezer.donkor')
    except User.DoesNotExist:
        print("❌ User 'ebenezer.donkor' not found!")
        return False
    
    print(f"[OK] Found user: {user.get_full_name()} ({user.username})")
    print(f"   Email: {user.email or 'No email'}")
    print()
    
    # Step 1: Ensure is_staff = True (required for Django admin)
    print("[1/4] Ensuring staff access...")
    if not user.is_staff:
        user.is_staff = True
        user.save(update_fields=['is_staff'])
        print("   [OK] Set is_staff = True")
    else:
        print("   [OK] Already has is_staff = True")
    print()
    
    # Step 2: Ensure is_active = True
    print("[2/4] Ensuring account is active...")
    if not user.is_active:
        user.is_active = True
        user.save(update_fields=['is_active'])
        print("   [OK] Activated account")
    else:
        print("   [OK] Account already active")
    print()
    
    # Step 3: Add to Accountant group
    print("[3/4] Adding to Accountant group...")
    accountant_group, created = Group.objects.get_or_create(name='Accountant')
    if not user.groups.filter(name='Accountant').exists():
        user.groups.add(accountant_group)
        print("   [OK] Added to Accountant group")
    else:
        print("   [OK] Already in Accountant group")
    print()
    
    # Step 4: Ensure staff record has profession='accountant'
    print("[4/4] Setting up staff record...")
    finance_dept = Department.objects.filter(
        name__icontains='finance'
    ).first() or Department.objects.filter(
        name__icontains='account'
    ).first() or Department.objects.first()
    
    staff, staff_created = Staff.objects.get_or_create(
        user=user,
        defaults={
            'profession': 'accountant',
            'department': finance_dept,
            'is_active': True,
            'is_deleted': False,
        }
    )
    
    if not staff_created:
        # Update existing staff record
        updated = False
        if staff.profession != 'accountant':
            staff.profession = 'accountant'
            updated = True
        if finance_dept and staff.department != finance_dept:
            staff.department = finance_dept
            updated = True
        if not staff.is_active:
            staff.is_active = True
            updated = True
        if staff.is_deleted:
            staff.is_deleted = False
            updated = True
        if updated:
            staff.save()
            print("   [OK] Updated staff record")
        else:
            print("   [OK] Staff record already configured correctly")
    else:
        print("   [OK] Created staff record as accountant")
    print()
    
    # Summary
    print("=" * 70)
    print("[OK] EBENEZER FINANCIAL ADMIN ACCESS SETUP COMPLETE!")
    print("=" * 70)
    print()
    print("Ebenezer Configuration:")
    print(f"  Username: {user.username}")
    print(f"  is_staff: {user.is_staff}")
    print(f"  is_active: {user.is_active}")
    print(f"  Groups: {', '.join([g.name for g in user.groups.all()])}")
    print(f"  Staff Profession: {staff.profession if staff else 'No staff record'}")
    print(f"  Staff Department: {staff.department.name if staff and staff.department else 'None'}")
    print(f"  Permissions: {user.user_permissions.count()} direct permissions")
    print()
    print("IMPORTANT: Ebenezer must log out and log back in for changes to take effect!")
    print()
    
    return True

if __name__ == '__main__':
    ensure_ebenezer_financial_access()
