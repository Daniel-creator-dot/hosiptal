#!/usr/bin/env python
"""
Grant Robbert full account permissions and admin access
Fixes forbidden errors for account changes
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, Group
from django.contrib.contenttypes.models import ContentType

User = get_user_model()

def grant_robbert_full_access():
    """Grant Robbert full accounting admin access including account change permissions"""
    print("=" * 70)
    print("GRANTING ROBBERT FULL ACCOUNT ADMIN ACCESS")
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
        users = User.objects.filter(username__icontains='robbert')
        if users.exists():
            user = users.first()
    
    if not user:
        print("❌ User 'robbert' not found!")
        return False
    
    print(f"✅ Found user: {user.username}")
    print()
    
    # Make user superuser for full admin access OR grant all permissions
    print("[1/4] Setting superuser status...")
    user.is_superuser = True  # This grants full admin access
    user.is_staff = True
    user.is_active = True
    user.save()
    print("   ✅ Set as superuser (full admin access)")
    print()
    
    # Add to Accountant group
    print("[2/4] Adding to Accountant group...")
    accountant_group, _ = Group.objects.get_or_create(name='Accountant')
    user.groups.add(accountant_group)
    print("   ✅ Added to Accountant group")
    print()
    
    # Grant all Account model permissions explicitly
    print("[3/4] Granting Account model permissions...")
    try:
        account_content_type = ContentType.objects.get(
            app_label='hospital',
            model='account'
        )
        account_permissions = Permission.objects.filter(content_type=account_content_type)
        user.user_permissions.add(*account_permissions)
        print(f"   ✅ Granted {account_permissions.count()} Account permissions")
        for perm in account_permissions:
            print(f"      - {perm.codename}")
    except Exception as e:
        print(f"   ⚠️  Could not grant Account permissions: {e}")
    print()
    
    # Grant all accounting model permissions
    print("[4/4] Granting all accounting model permissions...")
    accounting_models = [
        'account', 'costcenter', 'transaction', 'paymentreceipt',
        'advancedjournalentry', 'advancedjournalentryline', 'advancedgeneralledger',
        'paymentvoucher', 'receiptvoucher', 'cheque',
        'revenuecategory', 'revenue', 'expensecategory', 'expense',
        'advancedaccountsreceivable', 'accountspayable',
        'bankaccount', 'banktransaction', 'budget', 'budgetline',
        'cashbook', 'bankreconciliation', 'bankreconciliationitem',
        'insurancereceivable', 'procurementpurchase',
        'accountingpayroll', 'accountingpayrollentry', 'doctorcommission',
        'incomegroup', 'profitlossreport',
        'registrationfee', 'cashsale', 'accountingcorporateaccount',
        'withholdingreceivable', 'withholdingtaxpayable', 'deposit', 'initialrevaluation',
        'accountcategory', 'fiscalyear', 'accountingperiod', 'journal',
        'pettycashtransaction',
    ]
    
    total_perms = 0
    for model_name in accounting_models:
        try:
            content_type = ContentType.objects.get(
                app_label='hospital',
                model=model_name.lower()
            )
            permissions = Permission.objects.filter(content_type=content_type)
            user.user_permissions.add(*permissions)
            total_perms += permissions.count()
        except ContentType.DoesNotExist:
            continue
    
    print(f"   ✅ Granted {total_perms} total accounting permissions")
    print()
    
    # Verify
    print("=" * 70)
    print("✅ SETUP COMPLETE!")
    print("=" * 70)
    print()
    print(f"User: {user.username}")
    print(f"is_superuser: {user.is_superuser}")
    print(f"is_staff: {user.is_staff}")
    print(f"is_active: {user.is_active}")
    print()
    
    # Verify account permissions
    try:
        account_content_type = ContentType.objects.get(app_label='hospital', model='account')
        account_perms = Permission.objects.filter(user=user, content_type=account_content_type)
        print(f"Account permissions: {account_perms.count()}")
        for perm in account_perms:
            print(f"  ✅ {perm.codename}")
    except:
        pass
    
    print()
    print("⚠️  IMPORTANT: User must log out and log back in for changes to take effect!")
    print()
    print("Robbert now has:")
    print("  ✅ Superuser status (full admin access)")
    print("  ✅ Account change permissions")
    print("  ✅ All accounting model permissions")
    print("  ✅ Can modify accounts in Django admin")
    print()
    
    return True

if __name__ == '__main__':
    grant_robbert_full_access()






