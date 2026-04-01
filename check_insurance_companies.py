#!/usr/bin/env python
"""Check all insurance companies in the system"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Payer
from hospital.models_insurance_companies import InsuranceCompany
from hospital.models_flexible_pricing import PricingCategory, ServicePrice
from hospital.models_accounting_advanced import AccountingCorporateAccount
from decimal import Decimal

print("=" * 80)
print("CHECKING INSURANCE COMPANIES")
print("=" * 80)
print()

# 1. Check InsuranceCompany model
print("1. INSURANCE COMPANY MODEL:")
try:
    insurance_companies = InsuranceCompany.objects.filter(is_deleted=False)
    print(f"   Found {insurance_companies.count()} insurance companies:")
    for ins in insurance_companies:
        print(f"      - {ins.name} (Code: {ins.code or 'N/A'})")
        print(f"        Type: {ins.insurance_type}, Active: {ins.is_active}")
except Exception as e:
    print(f"   ⚠️  InsuranceCompany model check: {e}")
print()

# 2. Check Payers with insurance type
print("2. PAYERS (Insurance Type):")
insurance_payers = Payer.objects.filter(
    payer_type__icontains='insurance',
    is_deleted=False
)
print(f"   Found {insurance_payers.count()} insurance payers:")
for payer in insurance_payers:
    print(f"      - {payer.name} (Type: {payer.payer_type})")
print()

# 3. Check PricingCategories with insurance type
print("3. PRICING CATEGORIES (Insurance Type):")
insurance_categories = PricingCategory.objects.filter(
    category_type='insurance',
    is_deleted=False
)
print(f"   Found {insurance_categories.count()} insurance pricing categories:")
for cat in insurance_categories:
    service_count = ServicePrice.objects.filter(
        pricing_category=cat,
        is_deleted=False
    ).count()
    print(f"      - {cat.name} ({cat.code})")
    print(f"        Services with prices: {service_count}")
print()

# 4. Check which insurance companies have pricing
print("4. INSURANCE COMPANIES WITH PRICING:")
insurance_with_pricing = {}
for cat in insurance_categories:
    service_count = ServicePrice.objects.filter(
        pricing_category=cat,
        is_deleted=False
    ).count()
    if service_count > 0:
        # Extract company name from category name
        company_name = cat.name.replace('Insurance - ', '').replace('Insurance ', '')
        insurance_with_pricing[company_name] = {
            'category': cat,
            'service_count': service_count
        }

print(f"   Found {len(insurance_with_pricing)} insurance companies with pricing:")
for company, data in sorted(insurance_with_pricing.items()):
    print(f"      ✓ {company}")
    print(f"        Category: {data['category'].name} ({data['category'].code})")
    print(f"        Services priced: {data['service_count']}")
print()

# 5. Check if they're in AccountingCorporateAccount
print("5. INSURANCE COMPANIES IN ACCOUNTING CORPORATE ACCOUNTS:")
acc_accounts = AccountingCorporateAccount.objects.filter(is_deleted=False)
print(f"   Found {acc_accounts.count()} accounting corporate accounts:")
for acc in acc_accounts:
    # Check if this matches an insurance company
    matches_insurance = False
    for company_name in insurance_with_pricing.keys():
        if company_name.upper() in acc.company_name.upper() or acc.company_name.upper() in company_name.upper():
            matches_insurance = True
            break
    
    if matches_insurance:
        print(f"      ✓ {acc.account_number}: {acc.company_name} (Linked to insurance pricing)")
    else:
        print(f"      - {acc.account_number}: {acc.company_name}")
print()

# 6. Summary - Insurance companies that need corporate accounts
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Insurance Companies with Pricing: {len(insurance_with_pricing)}")
print()
print("Insurance Companies:")
for company in sorted(insurance_with_pricing.keys()):
    print(f"  - {company}")

# Check which ones are missing from AccountingCorporateAccount
missing_accounts = []
for company_name in insurance_with_pricing.keys():
    found = False
    for acc in acc_accounts:
        if company_name.upper() in acc.company_name.upper() or acc.company_name.upper() in company_name.upper():
            found = True
            break
    if not found:
        missing_accounts.append(company_name)

if missing_accounts:
    print()
    print(f"⚠️  {len(missing_accounts)} insurance companies missing from AccountingCorporateAccount:")
    for company in missing_accounts:
        print(f"   - {company}")
    print()
    print("To add missing insurance companies, run:")
    print("  docker exec chm-web-1 python /app/add_missing_insurance_accounts.py")
else:
    print()
    print("✅ All insurance companies with pricing are in AccountingCorporateAccount!")

