#!/usr/bin/env python
"""
Fix Robbert's Accountant Dashboard Access
Ensures Robbert has access to accountant dashboard WITHOUT making him superuser
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
from hospital.utils_roles import get_user_role, get_user_dashboard_url

User = get_user_model()

def fix_robbert_access():
    """Fix Robbert's accountant dashboard access"""
    print("=" * 70)
    print("FIXING ROBBERT'S ACCOUNTANT DASHBOARD ACCESS")
    print("=" * 70)
    print()
    
    # Find Robbert
    user = None
    for username in ['robbert.kwamegbologah', 'robbert', 'robbert.kwame']:
        try:
            user = User.objects.get(username=username)
            break
        except User.DoesNotExist:
            continue
    
    if not user:
        users = User.objects.filter(username__icontains='robbert')
        if users.exists():
            user = users.first()
    
    if not user:
        print("❌ User 'robbert' not found!")
        print()
        print("Available users with 'robbert':")
        users = User.objects.filter(username__icontains='robbert')
        for u in users:
            print(f"  - {u.username} ({u.email})")
        return False
    
    print(f"✅ Found user: {user.username}")
    print(f"   Email: {user.email or 'No email'}")
    print(f"   Full Name: {user.get_full_name()}")
    print()
    
    # Step 1: Ensure NOT superuser (accounting only)
    print("[1/5] Ensuring NOT superuser (accounting access only)...")
    if user.is_superuser:
        user.is_superuser = False
        user.save(update_fields=['is_superuser'])
        print("   ✅ Removed superuser status")
    else:
        print("   ✅ Already not superuser")
    print()
    
    # Step 2: Ensure is_staff = True (required for login)
    print("[2/5] Ensuring staff access...")
    if not user.is_staff:
        user.is_staff = True
        user.save(update_fields=['is_staff'])
        print("   ✅ Set as staff")
    else:
        print("   ✅ Already staff")
    print()
    
    # Step 3: Ensure is_active = True
    print("[3/5] Ensuring account is active...")
    if not user.is_active:
        user.is_active = True
        user.save(update_fields=['is_active'])
        print("   ✅ Activated account")
    else:
        print("   ✅ Account already active")
    print()
    
    # Step 4: Add to Accountant group
    print("[4/5] Adding to Accountant group...")
    accountant_group, created = Group.objects.get_or_create(name='Accountant')
    if not user.groups.filter(name='Accountant').exists():
        user.groups.add(accountant_group)
        print("   ✅ Added to Accountant group")
    else:
        print("   ✅ Already in Accountant group")
    print()
    
    # Step 5: Ensure staff record has profession='accountant'
    print("[5/5] Setting up staff record...")
    staff, staff_created = Staff.objects.get_or_create(
        user=user,
        defaults={
            'profession': 'accountant',
            'department': Department.objects.filter(name__icontains='account').first() or Department.objects.first(),
            'is_active': True,
            'is_deleted': False,
        }
    )
    
    if not staff_created:
        # Update existing staff record
        staff.profession = 'accountant'
        staff.is_active = True
        staff.is_deleted = False
        staff.save(update_fields=['profession', 'is_active', 'is_deleted'])
        print("   ✅ Updated staff record as accountant")
    else:
        print("   ✅ Created staff record as accountant")
    print()
    
    # Verify setup
    print("=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    print()
    
    # Check role
    role = get_user_role(user)
    dashboard_url = get_user_dashboard_url(user)
    groups = list(user.groups.values_list('name', flat=True))
    
    print(f"Username: {user.username}")
    print(f"Full Name: {user.get_full_name()}")
    print(f"Email: {user.email or 'No email'}")
    print()
    print(f"is_staff: {user.is_staff}")
    print(f"is_superuser: {user.is_superuser} ❌ (Should be False)")
    print(f"is_active: {user.is_active}")
    print()
    print(f"Groups: {groups}")
    print(f"Staff Profession: {staff.profession if staff else 'None'}")
    print()
    print(f"Detected Role: {role}")
    print(f"Dashboard URL: {dashboard_url}")
    print()
    
    # Check if setup is correct
    if role == 'accountant' and dashboard_url == '/hms/accountant/comprehensive-dashboard/':
        print("✅ SUCCESS! Robbert is properly configured as Accountant!")
        print()
        print("Access Details:")
        print("  ✅ Can log in (is_staff=True, is_active=True)")
        print("  ✅ NOT superuser (accounting access only)")
        print("  ✅ In Accountant group")
        print("  ✅ Staff profession = 'accountant'")
        print("  ✅ Will redirect to: /hms/accountant/comprehensive-dashboard/")
        print()
        print("Dashboard Access:")
        print("  • Main Dashboard: /hms/accountant/comprehensive-dashboard/")
        print("  • All accounting features under /hms/accountant/")
        print("  • Payment vouchers: /hms/accounting/pv/")
        print("  • Cheques: /hms/accounting/cheques/")
        print("  • Chart of Accounts: /hms/accountant/chart-of-accounts/")
        return True
    else:
        print("⚠️  WARNING: Setup may not be complete")
        print(f"   Expected role: 'accountant', Got: '{role}'")
        print(f"   Expected dashboard: '/hms/accountant/comprehensive-dashboard/', Got: '{dashboard_url}'")
        return False

if __name__ == '__main__':
    success = fix_robbert_access()
    sys.exit(0 if success else 1)






