#!/usr/bin/env python
"""
Fix ALL forbidden errors for Robbert - Make superuser and grant all accounting permissions
This fixes: Account, Insurance Receivable, Cashbook, and all other models
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

print("=" * 70)
print("FIXING ALL ADMIN ACCESS FOR ROBBERT")
print("=" * 70)
print()

# Find Robbert
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
    sys.exit(1)

print(f"✅ Found user: {user.username}")
print(f"   Email: {user.email or 'No email'}")
print()

# Step 1: Make superuser (this is the key fix!)
print("[1/3] Making Robbert a SUPERUSER...")
user.is_superuser = True
user.is_staff = True
user.is_active = True
user.save()
print("   ✅ is_superuser = True")
print("   ✅ is_staff = True")
print("   ✅ is_active = True")
print()

# Step 2: Add to Accountant group
print("[2/3] Adding to Accountant group...")
accountant_group, _ = Group.objects.get_or_create(name='Accountant')
user.groups.add(accountant_group)
print("   ✅ Added to Accountant group")
print()

# Step 3: Grant all accounting permissions explicitly (as backup)
print("[3/3] Granting all accounting model permissions...")
accounting_models = [
    # Core Accounting
    'account', 'costcenter', 'transaction', 'paymentreceipt',
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
    'cashbook',  # This one!
    'bankreconciliation', 'bankreconciliationitem',
    'insurancereceivable',  # This one!
    'procurementpurchase',
    'accountingpayroll', 'accountingpayrollentry', 'doctorcommission',
    'incomegroup', 'profitlossreport',
    'registrationfee', 'cashsale', 'accountingcorporateaccount',
    'withholdingreceivable', 'withholdingtaxpayable', 'deposit', 'initialrevaluation',
    'pettycashtransaction',  # This one!
]

total_perms = 0
granted_models = []
failed_models = []

for model_name in accounting_models:
    try:
        content_type = ContentType.objects.get(
            app_label='hospital',
            model=model_name.lower()
        )
        permissions = Permission.objects.filter(content_type=content_type)
        user.user_permissions.add(*permissions)
        count = permissions.count()
        total_perms += count
        granted_models.append(f"{model_name} ({count} perms)")
    except ContentType.DoesNotExist:
        failed_models.append(model_name)
        continue

print(f"   ✅ Granted {total_perms} permissions for {len(granted_models)} models")
if granted_models:
    print("   Models granted:")
    for model in granted_models[:10]:  # Show first 10
        print(f"      - {model}")
    if len(granted_models) > 10:
        print(f"      ... and {len(granted_models) - 10} more")

if failed_models:
    print(f"   ⚠️  {len(failed_models)} models not found (may need migration)")
print()

# Verify key models
print("Verifying key models:")
key_models = ['account', 'cashbook', 'insurancereceivable', 'paymentvoucher', 'pettycashtransaction']
for model_name in key_models:
    try:
        content_type = ContentType.objects.get(app_label='hospital', model=model_name.lower())
        perms = Permission.objects.filter(user=user, content_type=content_type)
        status = "✅" if perms.exists() or user.is_superuser else "❌"
        print(f"   {status} {model_name}: {perms.count()} permissions (superuser bypass: {user.is_superuser})")
    except ContentType.DoesNotExist:
        print(f"   ⚠️  {model_name}: Model not found")
print()

print("=" * 70)
print("✅ COMPLETE!")
print("=" * 70)
print()
print(f"User: {user.username}")
print(f"Status:")
print(f"  - is_superuser: {user.is_superuser} ✅")
print(f"  - is_staff: {user.is_staff} ✅")
print(f"  - is_active: {user.is_active} ✅")
print(f"  - Groups: {', '.join(user.groups.values_list('name', flat=True))}")
print()
print("Robbert can now access:")
print("  ✅ /admin/hospital/account/add/")
print("  ✅ /admin/hospital/cashbook/add/")
print("  ✅ /admin/hospital/insurancereceivable/add/")
print("  ✅ /admin/hospital/paymentvoucher/add/")
print("  ✅ /admin/hospital/pettycashtransaction/add/")
print("  ✅ ALL other admin models")
print()
print("=" * 70)
print("⚠️  CRITICAL: Robbert MUST log out and log back in!")
print("=" * 70)
print()
print("Steps:")
print("  1. Log out from Django admin (/admin/logout/)")
print("  2. Log out from main application")
print("  3. Clear browser cache (Ctrl+Shift+Delete)")
print("  4. Log back in")
print("  5. All forbidden errors should be gone!")
print()






