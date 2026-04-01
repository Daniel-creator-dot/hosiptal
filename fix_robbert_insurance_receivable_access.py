#!/usr/bin/env python
"""
Fix Robbert's access to Insurance Receivable - grant all permissions and make superuser
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

User = get_user_model()

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
print()

# Make superuser (this grants all permissions)
print("Making Robbert a superuser...")
user.is_superuser = True
user.is_staff = True
user.is_active = True
user.save()
print("✅ Set as superuser")
print()

# Also explicitly grant InsuranceReceivable permissions
print("Granting InsuranceReceivable permissions...")
try:
    ir_content_type = ContentType.objects.get(
        app_label='hospital',
        model='insurancereceivable'
    )
    ir_permissions = Permission.objects.filter(content_type=ir_content_type)
    user.user_permissions.add(*ir_permissions)
    print(f"✅ Granted {ir_permissions.count()} InsuranceReceivable permissions:")
    for perm in ir_permissions:
        print(f"   - {perm.codename}")
except ContentType.DoesNotExist:
    print("⚠️  InsuranceReceivable model not found (may need migration)")
except Exception as e:
    print(f"⚠️  Error: {e}")
print()

# Grant all accounting model permissions
print("Granting all accounting model permissions...")
accounting_models = [
    'account', 'costcenter', 'transaction', 'paymentreceipt',
    'advancedjournalentry', 'advancedjournalentryline', 'advancedgeneralledger',
    'paymentvoucher', 'receiptvoucher', 'cheque',
    'revenuecategory', 'revenue', 'expensecategory', 'expense',
    'advancedaccountsreceivable', 'accountspayable',
    'bankaccount', 'banktransaction', 'budget', 'budgetline',
    'cashbook', 'bankreconciliation', 'bankreconciliationitem',
    'insurancereceivable',  # This one!
    'procurementpurchase',
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

print(f"✅ Granted {total_perms} total accounting permissions")
print()

print("=" * 70)
print("✅ SETUP COMPLETE!")
print("=" * 70)
print()
print(f"User: {user.username}")
print(f"is_superuser: {user.is_superuser}")
print(f"is_staff: {user.is_staff}")
print()
print("Robbert can now:")
print("  ✅ Access /admin/hospital/insurancereceivable/add/")
print("  ✅ Add Insurance Receivable records")
print("  ✅ Change all accounting models")
print("  ✅ Full admin access")
print()
print("⚠️  IMPORTANT: Robbert must log out and log back in for changes to take effect!")
print()






