#!/usr/bin/env python
"""
Grant all accounting model permissions to Senior Account Officers
This ensures senior account officers can access all accounting models in Django admin
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from hospital.utils_roles import get_user_role

User = get_user_model()

# All accounting/financial models that senior account officers should access
ACCOUNTING_MODELS = [
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
    'pettycashtransaction',
    
    # Related Financial Models
    'invoice', 'invoiceline', 'payment', 'cashiersession',
    'revenuestream', 'departmentrevenue',
    'procurementrequest', 'procurementrequestitem',
    'corporateaccount',
]

print("=" * 70)
print("GRANTING ALL ACCOUNTING PERMISSIONS TO SENIOR ACCOUNT OFFICERS")
print("=" * 70)
print()

# Get or create Senior Account Officer group
senior_account_officer_group, created = Group.objects.get_or_create(name='Senior Account Officer')
if created:
    print("✅ Created Senior Account Officer group")
else:
    print("✅ Found Senior Account Officer group")
print()

# Grant all accounting permissions to the group
print("[1/2] Granting all accounting model permissions to Senior Account Officer group...")
permissions_granted = 0
granted_models = []
failed_models = []

for model_name in ACCOUNTING_MODELS:
    try:
        content_type = ContentType.objects.get(
            app_label='hospital',
            model=model_name.lower()
        )
        permissions = Permission.objects.filter(content_type=content_type)
        senior_account_officer_group.permissions.add(*permissions)
        count = permissions.count()
        permissions_granted += count
        granted_models.append(f"{model_name} ({count} perms)")
    except ContentType.DoesNotExist:
        failed_models.append(model_name)
        continue

print(f"   ✅ Granted {permissions_granted} permissions for {len(granted_models)} models")
if granted_models:
    print("   Models granted:")
    for model in granted_models[:10]:  # Show first 10
        print(f"      - {model}")
    if len(granted_models) > 10:
        print(f"      ... and {len(granted_models) - 10} more")
if failed_models:
    print(f"   ⚠️  {len(failed_models)} models not found (may not exist): {', '.join(failed_models[:5])}")
print()

# Grant permissions to all users with senior_account_officer role
print("[2/2] Granting permissions to all Senior Account Officers...")
all_users = User.objects.filter(is_active=True, is_staff=True)
senior_account_officers = []

for user in all_users:
    user_role = get_user_role(user)
    if user_role == 'senior_account_officer':
        senior_account_officers.append(user)
        # Add user to group (which grants all permissions)
        user.groups.add(senior_account_officer_group)
        # Also grant permissions directly as backup
        for model_name in ACCOUNTING_MODELS:
            try:
                content_type = ContentType.objects.get(
                    app_label='hospital',
                    model=model_name.lower()
                )
                permissions = Permission.objects.filter(content_type=content_type)
                user.user_permissions.add(*permissions)
            except ContentType.DoesNotExist:
                continue

if senior_account_officers:
    print(f"   ✅ Updated {len(senior_account_officers)} Senior Account Officer(s):")
    for user in senior_account_officers:
        print(f"      - {user.username} ({user.get_full_name()})")
        print(f"        Groups: {', '.join([g.name for g in user.groups.all()])}")
        print(f"        Permissions: {user.user_permissions.count()} direct permissions")
else:
    print("   ⚠️  No Senior Account Officers found")
print()

print("=" * 70)
print("✅ COMPLETE!")
print("=" * 70)
print()
print("Senior Account Officers now have:")
print(f"  ✅ {permissions_granted} Django admin permissions")
print(f"  ✅ Access to {len(granted_models)} accounting models")
print(f"  ✅ Full admin access to bank reconciliation and all accounting features")
print()





