#!/usr/bin/env python
"""
Grant Robbert Kwame Gbologah and Ebenezer Donkor full HMS access
They remain accountants but can access everything in HMS (not Django admin)
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
from hospital.models import Staff

User = get_user_model()

def grant_full_hms_access():
    """Grant full HMS access to Robbert and Ebenezer while keeping them as accountants"""
    print("=" * 70)
    print("GRANTING FULL HMS ACCESS TO ROBBERT & EBENEZER")
    print("(They remain accountants with accountant interface)")
    print("=" * 70)
    print()
    
    # Users to grant access
    usernames = [
        'robbert.kwamegbologah',
        'robbert',
        'robbert.kwame',
        'ebenezer.donkor',
        'ebenezer',
    ]
    
    users_found = []
    
    # Find users
    for username in usernames:
        try:
            user = User.objects.get(username=username)
            if user not in users_found:
                users_found.append(user)
        except User.DoesNotExist:
            continue
    
    # Also search by partial match
    for partial in ['robbert', 'ebenezer']:
        users = User.objects.filter(username__icontains=partial)
        for user in users:
            if user not in users_found:
                users_found.append(user)
    
    if not users_found:
        print("❌ No users found!")
        print()
        print("Searched for:")
        for u in usernames:
            print(f"  - {u}")
        return False
    
    print(f"✅ Found {len(users_found)} user(s):")
    for user in users_found:
        print(f"   - {user.username} ({user.email or 'No email'})")
    print()
    
    # Grant HMS access to each user (keep as accountant, not superuser)
    for user in users_found:
        print(f"[{user.username}] Configuring for full HMS access...")
        
        # 1. Keep as staff (not superuser) - they remain accountants
        user.is_staff = True
        user.is_superuser = False  # NOT superuser - they are accountants
        user.is_active = True
        user.save()
        print(f"   ✅ Set as staff (accountant, not superuser)")
        
        # 2. Ensure they're in Accountant group
        accountant_group, created = Group.objects.get_or_create(name='Accountant')
        if created:
            print(f"   ✅ Created Accountant group")
        if accountant_group not in user.groups.all():
            user.groups.add(accountant_group)
            print(f"   ✅ Added to Accountant group")
        else:
            print(f"   ℹ️  Already in Accountant group")
        
        # 3. Remove from Admin group (they're accountants, not admins)
        admin_group = Group.objects.filter(name='Admin').first()
        if admin_group and admin_group in user.groups.all():
            user.groups.remove(admin_group)
            print(f"   ✅ Removed from Admin group (they're accountants)")
        
        # 4. Ensure staff record has accountant profession
        try:
            staff = Staff.objects.get(user=user, is_deleted=False)
            if staff.profession != 'accountant':
                staff.profession = 'accountant'
                staff.save()
                print(f"   ✅ Updated profession to: accountant")
            else:
                print(f"   ✅ Staff profession already: accountant")
        except Staff.DoesNotExist:
            print(f"   ⚠️  No staff record found")
        
        print()
    
    print("=" * 70)
    print("✅ FULL HMS ACCESS CONFIGURED!")
    print("=" * 70)
    print()
    print("Users are now:")
    print("  ✅ Accountants (with accountant interface)")
    print("  ✅ Staff status (can log in)")
    print("  ✅ Accountant group membership")
    print("  ✅ Full access to ALL HMS features (via middleware bypass)")
    print("  ❌ NOT superusers (they remain accountants)")
    print()
    print("They will:")
    print("  - See accountant dashboard/interface")
    print("  - Access all HMS features (procurement, HR, patient management, etc.)")
    print("  - NOT have Django admin access (they're accountants)")
    print("  - Have no URL restrictions in HMS")
    print()

if __name__ == '__main__':
    grant_full_hms_access()
