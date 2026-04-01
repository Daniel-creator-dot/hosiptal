#!/usr/bin/env python
"""Check corporate accounts"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting_advanced import AccountingCorporateAccount
from hospital.models_enterprise_billing import CorporateAccount

print("=" * 80)
print("CHECKING CORPORATE ACCOUNTS")
print("=" * 80)
print()

# Check AccountingCorporateAccount (for accountant view)
print("1. ACCOUNTING CORPORATE ACCOUNTS (AccountingCorporateAccount):")
acc_accounts = AccountingCorporateAccount.objects.filter(is_deleted=False)
print(f"   Found: {acc_accounts.count()} accounts")
for acc in acc_accounts:
    print(f"   - {acc.account_number}: {acc.company_name}")
    print(f"     Contact: {acc.contact_person or 'N/A'}, Email: {acc.contact_email or 'N/A'}")
    print(f"     Credit Limit: GHS {acc.credit_limit}, Balance: GHS {acc.current_balance}")
    print(f"     Active: {acc.is_active}")
print()

# Check CorporateAccount (enterprise billing)
print("2. ENTERPRISE CORPORATE ACCOUNTS (CorporateAccount):")
ent_accounts = CorporateAccount.objects.filter(is_deleted=False)
print(f"   Found: {ent_accounts.count()} accounts")
for acc in ent_accounts:
    print(f"   - {acc.company_code}: {acc.company_name}")
    print(f"     Contact: {acc.billing_contact_name}, Email: {acc.billing_email}")
    print(f"     Credit Limit: GHS {acc.credit_limit}, Balance: GHS {acc.current_balance}")
    print(f"     Status: {acc.credit_status}, Active: {acc.is_active}")
print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"AccountingCorporateAccount: {acc_accounts.count()} accounts")
print(f"CorporateAccount (Enterprise): {ent_accounts.count()} accounts")
print()
if acc_accounts.count() == 0:
    print("⚠️  No accounting corporate accounts found!")
    print("   To add accounts, go to:")
    print("   http://192.168.2.216:8000/admin/hospital/accountingcorporateaccount/add/")
else:
    print("✅ Corporate accounts are available and should be visible in the list")








