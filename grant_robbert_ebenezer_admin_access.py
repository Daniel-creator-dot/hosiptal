#!/usr/bin/env python
"""
Grant Robbert Kwame Gbologah and Ebenezer Donkor full admin access
Makes them superusers so they have access to everything in HMS
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from hospital.models import Staff

User = get_user_model()

def grant_admin_access():
    """Grant full admin access to Robbert and Ebenezer"""
    print("=" * 70)
    print("GRANTING ADMIN ACCESS TO ROBBERT & EBENEZER")
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
    
    # Grant admin access to each user
    for user in users_found:
        print(f"[{user.username}] Granting admin privileges...")
        
        # 1. Make superuser
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save()
        print(f"   ✅ Set as superuser and staff")
        
        # 2. Add to Admin group
        admin_group, created = Group.objects.get_or_create(name='Admin')
        if created:
            print(f"   ✅ Created Admin group")
        if admin_group not in user.groups.all():
            user.groups.add(admin_group)
            print(f"   ✅ Added to Admin group")
        else:
            print(f"   ℹ️  Already in Admin group")
        
        # 3. Update staff profession (keep as accountant but with admin access)
        try:
            staff = Staff.objects.get(user=user, is_deleted=False)
            # Keep profession as accountant but they'll have admin access via superuser
            print(f"   ✅ Staff record found: {staff.profession}")
        except Staff.DoesNotExist:
            print(f"   ⚠️  No staff record found (not required for admin)")
        
        print()
    
    print("=" * 70)
    print("✅ ADMIN ACCESS GRANTED!")
    print("=" * 70)
    print()
    print("Users now have:")
    print("  ✅ Superuser status (full Django admin access)")
    print("  ✅ Staff status (can log in)")
    print("  ✅ Admin group membership")
    print("  ✅ Full access to all HMS features")
    print()
    print("They can now:")
    print("  - Access Django admin: /admin/")
    print("  - Access all HMS features")
    print("  - No restrictions on any URLs")
    print()

if __name__ == '__main__':
    grant_admin_access()
