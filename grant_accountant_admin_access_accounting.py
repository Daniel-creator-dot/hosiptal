"""
Grant accountants admin access to all accounting-related models
Including InsuranceReceivableEntry and InsurancePaymentReceived
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, Group
from django.contrib.contenttypes.models import ContentType

User = get_user_model()

def grant_accountant_admin_access():
    """Grant all accountants admin access to accounting models"""
    print("="*80)
    print("GRANTING ACCOUNTANTS ADMIN ACCESS TO ACCOUNTING MODELS")
    print("="*80)
    print()
    
    # Get or create Accountant group
    accountant_group, _ = Group.objects.get_or_create(name='Accountant')
    print(f"SUCCESS: Accountant group: {accountant_group.name}")
    print()
    
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
        'pettycashtransaction',
        
        # PrimeCare Accounting Models
        'insurancereceivableentry',  # NEW: Insurance Receivable Entry
        'insurancepaymentreceived',  # NEW: Insurance Payment Received
        'undepositedfunds',  # NEW: Undeposited Funds
        
        # Related Financial Models
        'invoice', 'invoiceline', 'payment', 'cashiersession',
        'revenuestream', 'departmentrevenue',
        'procurementrequest', 'procurementrequestitem',
        'corporateaccount',
        'payer',  # Insurance payers
        'supplier',  # Suppliers
    ]
    
    print(f"[1/3] Granting permissions for {len(accounting_models)} accounting models...")
    permissions_granted = 0
    
    for model_name in accounting_models:
        try:
            # Get content type
            content_type = ContentType.objects.filter(
                app_label='hospital',
                model=model_name.lower()
            ).first()
            
            if not content_type:
                # Try alternative model names
                alt_names = {
                    'insurancereceivableentry': 'insurancereceivableentry',
                    'insurancepaymentreceived': 'insurancepaymentreceived',
                    'undepositedfunds': 'undepositedfunds',
                }
                if model_name.lower() in alt_names:
                    content_type = ContentType.objects.filter(
                        app_label='hospital',
                        model=alt_names[model_name.lower()]
                    ).first()
            
            if content_type:
                # Get all permissions for this model
                perms = Permission.objects.filter(content_type=content_type)
                for perm in perms:
                    accountant_group.permissions.add(perm)
                    permissions_granted += 1
                print(f"   OK: {model_name}: {perms.count()} permissions")
            else:
                print(f"   WARNING: {model_name}: ContentType not found (model may not exist yet)")
        except Exception as e:
            print(f"   ERROR: {model_name}: Error - {e}")
    
    print(f"\nSUCCESS: Total permissions granted to group: {permissions_granted}")
    print()
    
    # Update all accountant users
    print("[2/3] Updating all accountant users...")
    accountant_users = User.objects.filter(
        groups__name='Accountant'
    ).distinct()
    
    updated_count = 0
    for user in accountant_users:
        # Ensure is_staff is True
        if not user.is_staff:
            user.is_staff = True
            user.save()
            updated_count += 1
            print(f"   OK: {user.username}: Set is_staff=True")
        else:
            print(f"   OK: {user.username}: Already has is_staff=True")
    
    print(f"\nSUCCESS: Updated {updated_count} users")
    print()
    
    # Grant individual permissions to all accountants
    print("[3/3] Granting individual permissions to accountant users...")
    for user in accountant_users:
        # Add user to group (gets group permissions)
        user.groups.add(accountant_group)
        
        # Also grant individual permissions for insurance receivable entry
        try:
            content_type = ContentType.objects.filter(
                app_label='hospital',
                model='insurancereceivableentry'
            ).first()
            
            if content_type:
                perms = Permission.objects.filter(content_type=content_type)
                for perm in perms:
                    user.user_permissions.add(perm)
                print(f"   OK: {user.username}: Granted InsuranceReceivableEntry permissions")
        except Exception as e:
            print(f"   WARNING: {user.username}: Error granting permissions - {e}")
    
    print()
    print("="*80)
    print("SUCCESS: COMPLETE!")
    print("="*80)
    print()
    print("Accountants can now access:")
    print("  - /admin/hospital/insurancereceivableentry/")
    print("  - /admin/hospital/insurancepaymentreceived/")
    print("  - /admin/hospital/undepositedfunds/")
    print("  - All other accounting models in admin")
    print()
    print("IMPORTANT: Accountants must log out and log back in for permissions to take effect!")
    print("="*80)

if __name__ == '__main__':
    grant_accountant_admin_access()

