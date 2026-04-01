#!/usr/bin/env python
"""
Script to change Rebecca from cashier to accountant
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth.models import User
from hospital.models import Staff
from hospital.utils_roles import assign_user_to_role, get_user_role, get_user_dashboard_url, ROLE_FEATURES

def make_rebecca_accountant():
    """Change Rebecca from cashier to accountant"""
    print("=" * 70)
    print("CHANGING REBECCA FROM CASHIER TO ACCOUNTANT")
    print("=" * 70)
    print()
    
    # Find Rebecca by username
    username = 'rebecca.'
    try:
        user = User.objects.get(username=username)
        print(f"✓ Found user: {user.get_full_name()} ({user.username})")
    except User.DoesNotExist:
        print(f"✗ User not found: {username}")
        return
    
    # Get staff record
    try:
        staff = Staff.objects.get(user=user, is_deleted=False)
        old_profession = staff.profession
        print(f"✓ Found staff record")
        print(f"  Current profession: {old_profession}")
    except Staff.DoesNotExist:
        print("✗ Staff record not found")
        return
    
    # Check current role
    current_role = get_user_role(user)
    print(f"  Current role: {current_role}")
    print()
    
    # Update profession to accountant
    print("Updating profession to 'accountant'...")
    staff.profession = 'accountant'
    staff.save(update_fields=['profession'])
    print(f"✓ Updated profession: {old_profession} → accountant")
    print()
    
    # Assign accountant role
    print("Assigning accountant role...")
    assign_user_to_role(user, 'accountant')
    print(f"✓ Assigned role: {ROLE_FEATURES['accountant']['name']}")
    print()
    
    # Verify changes
    user.refresh_from_db()
    staff.refresh_from_db()
    new_role = get_user_role(user)
    dashboard_url = get_user_dashboard_url(user, new_role)
    
    print("=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    print(f"  Username: {user.username}")
    print(f"  Full Name: {user.get_full_name()}")
    print(f"  Staff Profession: {staff.profession}")
    print(f"  User Groups: {', '.join([g.name for g in user.groups.all()])}")
    print(f"  Detected Role: {new_role}")
    print(f"  Dashboard URL: {dashboard_url}")
    print()
    
    if new_role == 'accountant' and dashboard_url == '/hms/accountant/comprehensive-dashboard/':
        print("=" * 70)
        print("✓ SUCCESS! Rebecca is now an accountant")
        print("=" * 70)
        print()
        print("Rebecca will now:")
        print("  • Be redirected to the Comprehensive Accountant Dashboard on login")
        print("  • Have access to all accounting features")
        print("  • See the account dashboard at: /hms/accountant/comprehensive-dashboard/")
    else:
        print("=" * 70)
        print("⚠ WARNING: Role assignment may not have worked correctly")
        print("=" * 70)
        print(f"  Expected role: accountant, Got: {new_role}")
        print(f"  Expected dashboard: /hms/accountant/comprehensive-dashboard/, Got: {dashboard_url}")

if __name__ == '__main__':
    make_rebecca_accountant()






