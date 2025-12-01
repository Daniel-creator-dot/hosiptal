#!/usr/bin/env python
"""
Setup drayisi as Medical Director with Admin privileges and Procurement Approval
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
from django.contrib.contenttypes.models import ContentType
from hospital.models import Staff, Department

User = get_user_model()

def setup_drayisi():
    """Setup drayisi as Medical Director with admin and procurement approval"""
    print("=" * 70)
    print("SETTING UP DRAYISI AS MEDICAL DIRECTOR")
    print("=" * 70)
    print()
    
    # Find user
    try:
        user = User.objects.get(username='drayisi')
    except User.DoesNotExist:
        print("❌ User 'drayisi' not found!")
        print()
        print("Available users:")
        users = User.objects.all()[:20]
        for u in users:
            print(f"  - {u.username}")
        return False
    
    print(f"✅ Found user: {user.username}")
    print(f"   Email: {user.email or 'No email'}")
    print()
    
    # Make superuser and staff
    print("[1/5] Setting admin privileges...")
    user.is_superuser = True
    user.is_staff = True
    user.is_active = True
    user.save()
    print("   ✅ Set as superuser and staff")
    print()
    
    # Get or create staff record
    print("[2/5] Setting up staff record...")
    staff, created = Staff.objects.get_or_create(
        user=user,
        defaults={
            'profession': 'doctor',
            'department': Department.objects.first() if Department.objects.exists() else None,
            'is_active': True,
            'is_deleted': False,
        }
    )
    if not created:
        staff.profession = 'doctor'
        staff.is_active = True
        staff.is_deleted = False
        staff.save()
    print(f"   ✅ Staff record {'created' if created else 'updated'}")
    print()
    
    # Add to Admin group
    print("[3/5] Adding to Admin group...")
    admin_group, _ = Group.objects.get_or_create(name='Admin')
    user.groups.add(admin_group)
    print("   ✅ Added to Admin group")
    print()
    
    # Add procurement approval permissions
    print("[4/5] Adding procurement approval permissions...")
    try:
        # Get content type for ProcurementRequest
        from hospital.models_procurement import ProcurementRequest
        content_type = ContentType.objects.get_for_model(ProcurementRequest)
        
        # Create or get permissions
        admin_perm, _ = Permission.objects.get_or_create(
            codename='can_approve_procurement_admin',
            content_type=content_type,
            defaults={'name': 'Can approve procurement requests (Admin)'}
        )
        
        accounts_perm, _ = Permission.objects.get_or_create(
            codename='can_approve_procurement_accounts',
            content_type=content_type,
            defaults={'name': 'Can approve procurement requests (Accounts)'}
        )
        
        # Add permissions to user
        user.user_permissions.add(admin_perm, accounts_perm)
        print("   ✅ Added procurement approval permissions")
    except Exception as e:
        print(f"   ⚠️  Could not add procurement permissions: {e}")
    print()
    
    # Add to Medical Director group (if exists) or create it
    print("[5/5] Setting up Medical Director role...")
    med_director_group, created = Group.objects.get_or_create(name='Medical Director')
    user.groups.add(med_director_group)
    print(f"   ✅ Added to Medical Director group")
    print()
    
    print("=" * 70)
    print("✅ DRAYISI SETUP COMPLETE!")
    print("=" * 70)
    print()
    print("User: drayisi")
    print("Role: Medical Director + Administrator")
    print("Privileges:")
    print("  ✅ Superuser (full admin access)")
    print("  ✅ Staff access")
    print("  ✅ Can approve procurement requests (Admin)")
    print("  ✅ Can approve procurement requests (Accounts)")
    print("  ✅ Access to all dashboards")
    print()
    print("Dashboard URL: /hms/admin-dashboard/")
    print("Procurement Approvals: /hms/procurement/admin/pending/")
    print()
    return True

if __name__ == '__main__':
    setup_drayisi()

