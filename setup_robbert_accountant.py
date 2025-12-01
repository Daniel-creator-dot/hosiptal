#!/usr/bin/env python
"""
Setup robbert kwame as Accountant with accounting-only access
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

def setup_robbert():
    """Setup robbert kwame as Accountant with accounting-only access"""
    print("=" * 70)
    print("SETTING UP ROBBERT KWAME AS ACCOUNTANT")
    print("=" * 70)
    print()
    
    # Find user
    user = None
    for username in ['robbert.kwamegbologah', 'robbert', 'robbert.kwame']:
        try:
            user = User.objects.get(username=username)
            break
        except User.DoesNotExist:
            continue
    
    if not user:
        # Try searching
        users = User.objects.filter(username__icontains='robbert')
        if users.exists():
            user = users.first()
    
    if not user:
        print("❌ User 'robbert kwame' not found!")
        print()
        print("Available users with 'robbert':")
        users = User.objects.filter(username__icontains='robbert')
        for u in users:
            print(f"  - {u.username} ({u.email})")
        return False
    
    print(f"✅ Found user: {user.username}")
    print(f"   Email: {user.email or 'No email'}")
    print()
    
    # Set as staff (not superuser - accounting only)
    print("[1/5] Setting staff privileges...")
    user.is_staff = True
    user.is_superuser = False  # NOT superuser - accounting only
    user.is_active = True
    user.save()
    print("   ✅ Set as staff (accounting access only)")
    print()
    
    # Get or create staff record
    print("[2/5] Setting up staff record...")
    staff, created = Staff.objects.get_or_create(
        user=user,
        defaults={
            'profession': 'accountant',
            'department': Department.objects.filter(name__icontains='account').first() or Department.objects.first(),
            'is_active': True,
            'is_deleted': False,
        }
    )
    if not created:
        staff.profession = 'accountant'
        staff.is_active = True
        staff.is_deleted = False
        staff.save()
    print(f"   ✅ Staff record {'created' if created else 'updated'} as accountant")
    print()
    
    # Remove from Admin group if exists
    print("[3/5] Managing group memberships...")
    admin_group = Group.objects.filter(name='Admin').first()
    if admin_group and user.groups.filter(name='Admin').exists():
        user.groups.remove(admin_group)
        print("   ✅ Removed from Admin group")
    
    # Add to Accountant group
    accountant_group, _ = Group.objects.get_or_create(name='Accountant')
    user.groups.add(accountant_group)
    print("   ✅ Added to Accountant group")
    print()
    
    # Remove all permissions except accounting-related
    print("[4/5] Setting accounting-only permissions...")
    user.user_permissions.clear()
    
    # Add accounting permissions
    try:
        from hospital.models_accounting import GeneralLedger
        from hospital.models_procurement import ProcurementRequest
        from hospital.models import Invoice, PaymentReceipt, CashierSession
        
        # Accounting permissions
        accounting_models = [
            GeneralLedger,
            Invoice, PaymentReceipt, CashierSession
        ]
        
        for model in accounting_models:
            try:
                content_type = ContentType.objects.get_for_model(model)
                permissions = Permission.objects.filter(content_type=content_type)
                user.user_permissions.add(*permissions)
            except Exception as e:
                pass
        
        # Procurement approval permission (for accounts approval)
        try:
            content_type = ContentType.objects.get_for_model(ProcurementRequest)
            accounts_perm = Permission.objects.get(
                codename='can_approve_procurement_accounts',
                content_type=content_type
            )
            user.user_permissions.add(accounts_perm)
            print("   ✅ Added procurement accounts approval permission")
        except Exception:
            pass
        
        print("   ✅ Set accounting-only permissions")
    except Exception as e:
        print(f"   ⚠️  Could not set all permissions: {e}")
    print()
    
    # Remove from other groups
    print("[5/5] Cleaning up group memberships...")
    groups_to_remove = ['Admin', 'Medical Director', 'Procurement', 'Store Manager']
    for group_name in groups_to_remove:
        group = Group.objects.filter(name=group_name).first()
        if group and user.groups.filter(name=group_name).exists():
            user.groups.remove(group)
            print(f"   ✅ Removed from {group_name} group")
    print()
    
    print("=" * 70)
    print("✅ ROBBERT KWAME SETUP COMPLETE!")
    print("=" * 70)
    print()
    print("User: " + user.username)
    print("Role: Accountant (Accounting Staff Only)")
    print("Privileges:")
    print("  ✅ Staff access")
    print("  ❌ NOT superuser (accounting only)")
    print("  ✅ Can approve procurement requests (Accounts)")
    print("  ✅ Access to accounting dashboards")
    print("  ✅ Access to invoices, payments, cashier")
    print("  ❌ NO admin access")
    print("  ❌ NO procurement management")
    print()
    print("Dashboard URL: /hms/accountant/comprehensive-dashboard/")
    print("Procurement Approvals: /hms/procurement/accounts/pending/")
    print()
    return True

if __name__ == '__main__':
    setup_robbert()

