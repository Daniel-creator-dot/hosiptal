#!/usr/bin/env python
"""
Setup robbert kwame with FULL accounting admin access
Includes access to all accounting models including petty cash
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

User = get_user_model()

def setup_robbert_full_admin():
    """Setup robbert kwame with full accounting admin access"""
    print("=" * 70)
    print("SETTING UP ROBBERT KWAME WITH FULL ACCOUNTING ADMIN ACCESS")
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
    
    # Set as staff (for Django admin access)
    print("[1/6] Setting staff privileges...")
    user.is_staff = True
    user.is_active = True
    user.save()
    print("   ✅ Set as staff (Django admin access enabled)")
    print()
    
    # Add to Accountant group
    print("[2/6] Managing group memberships...")
    accountant_group, _ = Group.objects.get_or_create(name='Accountant')
    user.groups.add(accountant_group)
    print("   ✅ Added to Accountant group")
    print()
    
    # Grant all accounting model permissions
    print("[3/6] Granting all accounting model permissions...")
    user.user_permissions.clear()
    
    # All accounting/financial models that accountants should access
    accounting_models = [
        # Core Accounting
        'account', 'costcenter', 'transaction', 'paymentreceipt', 'paymentallocation',
        'accountsreceivable', 'generalledger', 'journalentry', 'journalentryline',
        
        # Advanced Accounting
        'accountcategory', 'fiscalyear', 'accountingperiod', 'journal',
        'advancedjournalentry', 'advancedjournalentryline', 'advancedgeneralledger',
        'paymentvoucher', 'receiptvoucher', 'cheque',
        'revenuecategory', 'revenue', 'expensecategory', 'expense',
        'advancedaccountsreceivable', 'accountspayable',
        'bankaccount', 'banktransaction',
        'budget', 'budgetline', 'taxrate',
        'accountingauditlog',
        'cashbook', 'bankreconciliation', 'bankreconciliationitem',
        'insurancereceivable', 'procurementpurchase',
        'accountingpayroll', 'accountingpayrollentry', 'doctorcommission',
        'incomegroup', 'profitlossreport',
        'registrationfee', 'cashsale', 'accountingcorporateaccount',
        'withholdingreceivable', 'withholdingtaxpayable', 'deposit', 'initialrevaluation',
        
        # NEW: Petty Cash
        'pettycashtransaction',
        
        # Related Financial Models
        'invoice', 'invoiceline', 'payment', 'cashiersession',
        'revenuestream', 'departmentrevenue',
        'procurementrequest', 'procurementrequestitem',
        'corporateaccount',
    ]
    
    permissions_granted = 0
    for model_name in accounting_models:
        try:
            content_type = ContentType.objects.get(
                app_label='hospital',
                model=model_name.lower()
            )
            # Grant all permissions (add, change, delete, view) for this model
            permissions = Permission.objects.filter(content_type=content_type)
            for perm in permissions:
                user.user_permissions.add(perm)
                permissions_granted += 1
        except ContentType.DoesNotExist:
            # Model might not exist yet (e.g., after migration), skip
            print(f"   ⚠️  Model {model_name} not found (may need migration)")
            continue
    
    print(f"   ✅ Granted {permissions_granted} permissions to user")
    print()
    
    # Also add permissions to Accountant group
    print("[4/6] Adding permissions to Accountant group...")
    group_permissions_added = 0
    for model_name in accounting_models:
        try:
            content_type = ContentType.objects.get(
                app_label='hospital',
                model=model_name.lower()
            )
            permissions = Permission.objects.filter(content_type=content_type)
            for perm in permissions:
                accountant_group.permissions.add(perm)
                group_permissions_added += 1
        except ContentType.DoesNotExist:
            continue
    
    print(f"   ✅ Added {group_permissions_added} permissions to Accountant group")
    print()
    
    # Verify permissions
    print("[5/6] Verifying permissions...")
    petty_cash_perms = Permission.objects.filter(
        user=user,
        content_type__model='pettycashtransaction'
    )
    print(f"   Petty Cash permissions: {petty_cash_perms.count()}")
    
    admin_access = user.is_staff and user.is_active
    print(f"   Admin access: {'✅ Yes' if admin_access else '❌ No'}")
    print()
    
    # Summary
    print("[6/6] Setup complete!")
    print()
    print("=" * 70)
    print("✅ ROBBERT KWAME FULL ACCOUNTING ADMIN ACCESS SETUP COMPLETE!")
    print("=" * 70)
    print()
    print("User: " + user.username)
    print("Role: Accountant with Full Admin Access")
    print()
    print("Privileges:")
    print("  ✅ Staff access (Django admin panel)")
    print("  ✅ All accounting model permissions")
    print("  ✅ Petty Cash Transaction permissions")
    print("  ✅ Payment Voucher permissions")
    print("  ✅ All financial reporting permissions")
    print()
    print("Access URLs:")
    print("  - Django Admin: /admin/")
    print("  - Petty Cash: /accounting/petty-cash/")
    print("  - Payment Vouchers: /accounting/pv/")
    print("  - Accountant Dashboard: /hms/accountant/comprehensive-dashboard/")
    print()
    print("⚠️  IMPORTANT: User must log out and log back in for permissions to take effect!")
    print()
    return True

if __name__ == '__main__':
    setup_robbert_full_admin()






