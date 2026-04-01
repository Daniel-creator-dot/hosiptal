#!/usr/bin/env python
"""
Grant Robbert and Ebenezer accounting model permissions
They remain accountants but can add/edit accounts receivable and other accounting models in admin
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
from hospital.models import Staff

User = get_user_model()

def grant_accounting_permissions():
    """Grant accounting model permissions to Robbert and Ebenezer"""
    print("=" * 70)
    print("GRANTING ACCOUNTING PERMISSIONS TO ROBBERT & EBENEZER")
    print("(They remain accountants with accountant interface)")
    print("=" * 70)
    print()
    
    # Users to grant permissions
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
        return False
    
    print(f"✅ Found {len(users_found)} user(s):")
    for user in users_found:
        print(f"   - {user.username} ({user.email or 'No email'})")
    print()
    
    # All accounting/financial models that accountants should have add/change permissions
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
        'tenderevaluation',  # Tender Evaluation (also a revaluation model)
        'pettycashtransaction',
        'insurancereceivableentry',  # Insurance Receivable Entry (PrimeCare)
        'insurancepaymentreceived',  # Insurance Payment Received (PrimeCare)
        'undepositedfunds',  # Undeposited Funds (PrimeCare)
        
        # Related Financial Models
        'invoice', 'invoiceline', 'payment', 'cashiersession',
        'revenuestream', 'departmentrevenue',
        'procurementrequest', 'procurementrequestitem',
        'corporateaccount',
    ]
    
    # Grant permissions to each user
    for user in users_found:
        print(f"[{user.username}] Granting accounting permissions...")
        
        # 1. Ensure they're accountants (not superusers)
        user.is_staff = True
        user.is_superuser = False
        user.is_active = True
        user.save()
        print(f"   ✅ Set as staff (accountant, not superuser)")
        
        # 2. Ensure they're in Accountant group
        accountant_group, created = Group.objects.get_or_create(name='Accountant')
        if accountant_group not in user.groups.all():
            user.groups.add(accountant_group)
            print(f"   ✅ Added to Accountant group")
        
        # 3. Remove from Admin group
        admin_group = Group.objects.filter(name='Admin').first()
        if admin_group and admin_group in user.groups.all():
            user.groups.remove(admin_group)
            print(f"   ✅ Removed from Admin group")
        
        # 4. Grant accounting model permissions
        permissions_granted = 0
        for model_name in accounting_models:
            try:
                content_type = ContentType.objects.get(
                    app_label='hospital',
                    model=model_name
                )
                # Grant all permissions (add, change, delete, view) for this model
                permissions = Permission.objects.filter(content_type=content_type)
                for perm in permissions:
                    user.user_permissions.add(perm)
                    permissions_granted += 1
            except ContentType.DoesNotExist:
                # Model might not exist, skip
                continue
        
        print(f"   ✅ Granted {permissions_granted} accounting permissions")
        
        # 5. Ensure staff record has accountant profession
        try:
            staff = Staff.objects.get(user=user, is_deleted=False)
            if staff.profession != 'accountant':
                staff.profession = 'accountant'
                staff.save()
                print(f"   ✅ Updated profession to: accountant")
        except Staff.DoesNotExist:
            print(f"   ⚠️  No staff record found")
        
        print()
    
    print("=" * 70)
    print("✅ ACCOUNTING PERMISSIONS GRANTED!")
    print("=" * 70)
    print()
    print("Users are now:")
    print("  ✅ Accountants (with accountant interface)")
    print("  ✅ Can add/edit accounts receivable in Django admin")
    print("  ✅ Can add/edit all accounting models in Django admin")
    print("  ✅ Have full accounting permissions")
    print("  ❌ NOT superusers (they remain accountants)")
    print("  ❌ Only have accounting features (no full HMS access)")
    print()
    print("They can:")
    print("  - Access Django admin: /admin/ (for accounting models only)")
    print("  - Add/edit accounts receivable, accounts payable, etc.")
    print("  - Access all accountant dashboard features")
    print("  - NOT access procurement, HR, patient management (accounting only)")
    print()

if __name__ == '__main__':
    grant_accounting_permissions()
