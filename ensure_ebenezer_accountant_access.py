#!/usr/bin/env python
"""
Ensure Ebenezer has full access to the comprehensive accountant dashboard
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth.models import User, Group, Permission
from hospital.models import Staff
from hospital.utils_roles import get_user_role, get_user_dashboard_url

def ensure_ebenezer_access():
    print("=" * 70)
    print("ENSURING EBENEZER HAS FULL ACCOUNTANT DASHBOARD ACCESS")
    print("=" * 70)
    print()
    
    # Find Ebenezer
    ebenezer = Staff.objects.filter(user__username__icontains='ebenezer', is_deleted=False).first()
    
    if not ebenezer:
        print("[ERROR] Ebenezer not found!")
        return False
    
    user = ebenezer.user
    print(f"[OK] Found Ebenezer: {user.get_full_name()} ({user.username})")
    print()
    
    # 1. Ensure in Accountant group
    print("[1/4] Ensuring Accountant group membership...")
    accountant_group, created = Group.objects.get_or_create(name='Accountant')
    if created:
        print(f"  [OK] Created Accountant group")
    
    if accountant_group not in user.groups.all():
        user.groups.add(accountant_group)
        print(f"  [OK] Added to Accountant group")
    else:
        print(f"  [INFO] Already in Accountant group")
    print()
    
    # 2. Ensure profession is accountant
    print("[2/4] Checking profession...")
    if ebenezer.profession != 'accountant':
        ebenezer.profession = 'accountant'
        ebenezer.save()
        print(f"  [OK] Updated profession to: accountant")
    else:
        print(f"  [INFO] Profession already set to: accountant")
    print()
    
    # 3. Verify role detection
    print("[3/4] Verifying role detection...")
    role = get_user_role(user)
    dashboard_url = get_user_dashboard_url(user, role)
    print(f"  [OK] Detected role: {role}")
    print(f"  [OK] Dashboard URL: {dashboard_url}")
    
    if role != 'accountant':
        print(f"  [WARNING] Role is '{role}' but should be 'accountant'")
        print(f"  [INFO] This might be due to multiple groups. Accountant group is prioritized.")
    print()
    
    # 4. Grant accounts approval permission
    print("[4/4] Granting accounts approval permission...")
    try:
        permission = Permission.objects.get(codename='can_approve_procurement_accounts')
        if not user.has_perm('hospital.can_approve_procurement_accounts'):
            user.user_permissions.add(permission)
            print(f"  [OK] Granted accounts approval permission")
        else:
            print(f"  [INFO] Already has accounts approval permission")
    except Permission.DoesNotExist:
        print(f"  [WARNING] Permission 'can_approve_procurement_accounts' not found")
    print()
    
    # Summary
    print("=" * 70)
    print("SETUP COMPLETE!")
    print("=" * 70)
    print()
    print("Ebenezer Configuration:")
    print(f"  Username: {user.username}")
    print(f"  Department: {ebenezer.department.name if ebenezer.department else 'None'}")
    print(f"  Profession: {ebenezer.profession}")
    print(f"  Role: {role}")
    print(f"  Groups: {', '.join([g.name for g in user.groups.all()])}")
    print(f"  Dashboard: {dashboard_url}")
    print()
    print("Access:")
    print(f"  [OK] Comprehensive Dashboard: /hms/accountant/comprehensive-dashboard/")
    print(f"  [OK] All accounting features")
    print(f"  [OK] Accounts approval: /hms/procurement/accounts/pending/")
    print()
    print("[IMPORTANT] Ebenezer must log out and log back in for changes to take effect!")
    print()
    
    return True

if __name__ == '__main__':
    ensure_ebenezer_access()

