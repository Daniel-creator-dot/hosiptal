#!/usr/bin/env python
"""Sync insurance companies for registration and billing"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import transaction
from hospital.models_insurance_companies import InsuranceCompany
from hospital.models import Payer
from hospital.models_flexible_pricing import PricingCategory

print("=" * 80)
print("SYNCING INSURANCE FOR REGISTRATION AND BILLING")
print("=" * 80)
print()

# 1. Ensure all InsuranceCompany have corresponding Payer
print("1. SYNCING INSURANCE COMPANIES TO PAYERS:")
print()

insurance_companies = InsuranceCompany.objects.filter(is_deleted=False, is_active=True)
created_payers = 0
updated_payers = 0

with transaction.atomic():
    for ins_company in insurance_companies:
        # Find or create Payer
        payer, created = Payer.objects.get_or_create(
            name=ins_company.name,
            defaults={
                'payer_type': 'insurance',
                'is_active': ins_company.is_active,
            }
        )
        
        if created:
            created_payers += 1
            print(f"   ✓ Created Payer: {ins_company.name}")
        else:
            # Update existing
            payer.payer_type = 'insurance'
            payer.is_active = ins_company.is_active
            payer.is_deleted = False
            payer.save()
            updated_payers += 1
            print(f"   ✓ Updated Payer: {ins_company.name}")

print()
print(f"   Created: {created_payers}, Updated: {updated_payers}")
print()

# 2. Link PricingCategory to InsuranceCompany
print("2. LINKING PRICING CATEGORIES TO INSURANCE COMPANIES:")
print()

insurance_categories = PricingCategory.objects.filter(
    category_type='insurance',
    is_deleted=False
).exclude(name__icontains='cash').exclude(name__icontains='other company')

linked_count = 0

with transaction.atomic():
    for cat in insurance_categories:
        # Extract company name from category name
        # Format: "Insurance - ACE" -> "ACE"
        company_name = cat.name.replace('Insurance - ', '').replace('Insurance ', '').strip()
        
        if not company_name or company_name in ['(General)', 'INSURANCE']:
            continue
        
        # Find matching InsuranceCompany
        ins_company = InsuranceCompany.objects.filter(
            name__iexact=company_name,
            is_deleted=False
        ).first()
        
        if ins_company:
            if cat.insurance_company != ins_company:
                cat.insurance_company = ins_company
                cat.save()
                linked_count += 1
                print(f"   ✓ Linked: {cat.name} → {ins_company.name}")
            else:
                print(f"   ✓ Already linked: {cat.name} → {ins_company.name}")
        else:
            print(f"   ⚠️  No InsuranceCompany found for: {cat.name}")

print()
print(f"   Linked: {linked_count} pricing categories")
print()

# 3. Verify the chain: InsuranceCompany → Payer → PricingCategory
print("3. VERIFYING SYNC CHAIN:")
print()

verified_count = 0
missing_count = 0

for ins_company in insurance_companies:
    # Check Payer exists
    payer = Payer.objects.filter(
        name__iexact=ins_company.name,
        payer_type='insurance',
        is_deleted=False
    ).first()
    
    # Check PricingCategory exists and is linked
    pricing_cat = PricingCategory.objects.filter(
        insurance_company=ins_company,
        is_deleted=False
    ).first()
    
    if not pricing_cat:
        # Try by name
        pricing_cat = PricingCategory.objects.filter(
            name__icontains=ins_company.name,
            category_type='insurance',
            is_deleted=False
        ).first()
    
    if payer and pricing_cat:
        verified_count += 1
        print(f"   ✓ {ins_company.name}:")
        print(f"      Payer: {payer.name} ({payer.payer_type})")
        print(f"      Pricing: {pricing_cat.name} ({pricing_cat.code})")
    else:
        missing_count += 1
        print(f"   ⚠️  {ins_company.name}:")
        if not payer:
            print(f"      Missing Payer")
        if not pricing_cat:
            print(f"      Missing PricingCategory")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"✅ Insurance Companies: {insurance_companies.count()}")
print(f"✅ Payers Created/Updated: {created_payers + updated_payers}")
print(f"✅ Pricing Categories Linked: {linked_count}")
print(f"✅ Fully Synced: {verified_count}")
if missing_count > 0:
    print(f"⚠️  Missing Links: {missing_count}")
print()
print("SYNC COMPLETE!")
print()
print("Registration Flow:")
print("  1. Patient selects Insurance Company at registration")
print("  2. System creates PatientInsurance enrollment")
print("  3. Patient.primary_insurance is set to corresponding Payer")
print()
print("Billing Flow:")
print("  1. System gets patient.primary_insurance (Payer)")
print("  2. Finds InsuranceCompany from Payer name")
print("  3. Gets PricingCategory linked to InsuranceCompany")
print("  4. Uses ServicePrice for that PricingCategory")
print("  5. Applies correct insurance price to invoice")








