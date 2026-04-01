#!/usr/bin/env python
"""
Fix Ebenezer's accountant role detection and dashboard redirect
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth.models import User, Group
from hospital.models import Staff
from hospital.utils_roles import get_user_role, get_user_dashboard_url

def fix_ebenezer_redirect():
    print("=" * 70)
    print("FIXING EBENEZER'S ACCOUNTANT ROLE & DASHBOARD REDIRECT")
    print("=" * 70)
    print()
    
    # Find Ebenezer
    ebenezer = Staff.objects.filter(user__username='ebenezer.donkor', is_deleted=False).first()
    
    if not ebenezer:
        print("[ERROR] Ebenezer not found!")
        return False
    
    user = ebenezer.user
    print(f"[OK] Found Ebenezer: {user.get_full_name()} ({user.username})")
    print()
    
    # 1. Remove from Account Personnel group (if causing issues)
    print("[1/5] Managing groups...")
    accountant_group = Group.objects.get_or_create(name='Accountant')[0]
    account_personnel_group = Group.objects.filter(name='Account Personnel').first()
    
    # Ensure in Accountant group
    if accountant_group not in user.groups.all():
        user.groups.add(accountant_group)
        print(f"  [OK] Added to Accountant group")
    else:
        print(f"  [INFO] Already in Accountant group")
    
    # Keep Account Personnel but Accountant should be prioritized
    if account_personnel_group and account_personnel_group in user.groups.all():
        print(f"  [INFO] Also in Account Personnel group (OK - Accountant is prioritized)")
    
    print()
    
    # 2. Ensure profession is accountant
    print("[2/5] Checking profession...")
    if ebenezer.profession != 'accountant':
        ebenezer.profession = 'accountant'
        ebenezer.save()
        print(f"  [OK] Updated profession to: accountant")
    else:
        print(f"  [INFO] Profession already: accountant")
    print()
    
    # 3. Ensure department is Finance
    print("[3/5] Checking department...")
    from hospital.models import Department
    finance_dept = Department.objects.filter(name__icontains='finance').first()
    if finance_dept and ebenezer.department != finance_dept:
        ebenezer.department = finance_dept
        ebenezer.save()
        print(f"  [OK] Updated department to: {finance_dept.name}")
    elif ebenezer.department:
        print(f"  [INFO] Department: {ebenezer.department.name}")
    print()
    
    # 4. Verify role detection
    print("[4/5] Verifying role detection...")
    role = get_user_role(user)
    dashboard_url = get_user_dashboard_url(user, role)
    print(f"  [OK] Detected role: {role}")
    print(f"  [OK] Dashboard URL: {dashboard_url}")
    
    if role != 'accountant':
        print(f"  [WARNING] Role is '{role}' but should be 'accountant'")
        print(f"  [INFO] Checking groups priority...")
        groups = list(user.groups.values_list('name', flat=True))
        print(f"  [INFO] User groups: {groups}")
        if 'Accountant' in groups:
            print(f"  [INFO] Accountant group found - should be prioritized")
    else:
        print(f"  [OK] Role detection working correctly!")
    print()
    
    # 5. Ensure user is active and staff
    print("[5/5] Checking user flags...")
    if not user.is_active:
        user.is_active = True
        user.save()
        print(f"  [OK] Activated user")
    else:
        print(f"  [INFO] User is active")
    
    if not user.is_staff:
        user.is_staff = True
        user.save()
        print(f"  [OK] Set is_staff=True")
    else:
        print(f"  [INFO] User is staff")
    print()
    
    # Summary
    print("=" * 70)
    print("FIX COMPLETE!")
    print("=" * 70)
    print()
    print("Ebenezer Configuration:")
    print(f"  Username: {user.username}")
    print(f"  Department: {ebenezer.department.name if ebenezer.department else 'None'}")
    print(f"  Profession: {ebenezer.profession}")
    print(f"  Role: {role}")
    print(f"  Groups: {', '.join([g.name for g in user.groups.all()])}")
    print(f"  Dashboard URL: {dashboard_url}")
    print(f"  is_active: {user.is_active}")
    print(f"  is_staff: {user.is_staff}")
    print()
    
    if role == 'accountant' and dashboard_url == '/hms/accountant/comprehensive-dashboard/':
        print("[OK] Configuration is correct!")
        print()
        print("Ebenezer should be redirected to the accountant dashboard.")
        print("If he's still seeing the main dashboard:")
        print("  1. Have him log out completely")
        print("  2. Clear browser cache (Ctrl + F5)")
        print("  3. Log back in")
        print("  4. He will be automatically redirected to:")
        print("     /hms/accountant/comprehensive-dashboard/")
    else:
        print("[WARNING] Configuration may need adjustment")
        print(f"  Expected role: accountant, Got: {role}")
        print(f"  Expected URL: /hms/accountant/comprehensive-dashboard/")
        print(f"  Got: {dashboard_url}")
    print()
    
    return True

if __name__ == '__main__':
    fix_ebenezer_redirect()



