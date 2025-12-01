#!/usr/bin/env python
"""
Grant all financial model permissions to Accountant group
This ensures accountants can access all financial stuff in Django admin
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

# All financial/accounting models that accountants should access
FINANCIAL_MODELS = [
    # Core Accounting
    'account', 'costcenter', 'transaction', 'paymentreceipt',
    
    # Advanced Accounting
    'advancedjournalentry', 'advancedjournalentryline', 'advancedgeneralledger',
    'paymentvoucher', 'receiptvoucher', 'cheque',
    'revenue', 'revenuecategory', 'expense', 'expensecategory',
    'advancedaccountsreceivable', 'accountspayable',
    'bankaccount', 'banktransaction', 'budget', 'budgetline',
    'cashbook', 'bankreconciliation', 'bankreconciliationitem',
    'insurancereceivable', 'procurementpurchase',
    'accountingpayroll', 'accountingpayrollentry', 'doctorcommission',
    'incomegroup', 'profitlossreport',
    'registrationfee', 'cashsale', 'accountingcorporateaccount',
    'withholdingreceivable', 'deposit', 'initialrevaluation',
    'accountcategory', 'fiscalyear', 'accountingperiod', 'journal',
    
    # Primecare Accounting
    'undepositedfunds', 'insurancereceivableentry', 'insurancepaymentreceived',
    
    # Related Financial Models
    'invoice', 'invoiceline', 'payment', 'cashiersession',
    'revenuestream', 'departmentrevenue',
    'procurementrequest', 'procurementrequestitem',
    'corporateaccount',
]

print("=" * 70)
print("GRANTING ALL FINANCIAL PERMISSIONS TO ACCOUNTANT GROUP")
print("=" * 70)
print()

# Get or create Accountant group
accountant_group, created = Group.objects.get_or_create(name='Accountant')
if created:
    print("✅ Created Accountant group")
else:
    print("✅ Found existing Accountant group")
print()

# Grant permissions for all financial models
total_permissions = 0
granted_models = []
failed_models = []

for model_name in FINANCIAL_MODELS:
    try:
        content_type = ContentType.objects.get(
            app_label='hospital',
            model=model_name
        )
        # Get all permissions for this model
        permissions = Permission.objects.filter(content_type=content_type)
        
        for perm in permissions:
            accountant_group.permissions.add(perm)
            total_permissions += 1
        
        granted_models.append(model_name)
        print(f"  ✅ {model_name}: {permissions.count()} permissions")
    except ContentType.DoesNotExist:
        failed_models.append(model_name)
        print(f"  ⚠️  {model_name}: Model not found (may not exist)")

print()
print("=" * 70)
print(f"✅ COMPLETE!")
print("=" * 70)
print(f"Total permissions granted: {total_permissions}")
print(f"Models configured: {len(granted_models)}")
if failed_models:
    print(f"Models not found: {len(failed_models)}")
print()
print("All users in the Accountant group now have access to all financial models!")
print()














