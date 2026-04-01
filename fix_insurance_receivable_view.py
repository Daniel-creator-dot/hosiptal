#!/usr/bin/env python
"""Fix insurance receivable view to use InsuranceCompany and create Payers if needed"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import transaction
from hospital.models_insurance_companies import InsuranceCompany
from hospital.models import Payer

print("=" * 80)
print("FIXING INSURANCE RECEIVABLE VIEW")
print("=" * 80)
print()

# Get all insurance companies
insurance_companies = InsuranceCompany.objects.filter(is_deleted=False)
print(f"Found {insurance_companies.count()} insurance companies")
print()

# Create or update Payers for each insurance company
created_count = 0
updated_count = 0

with transaction.atomic():
    for ins_company in insurance_companies:
        # Check if Payer exists
        payer = Payer.objects.filter(
            name__iexact=ins_company.name,
            is_deleted=False
        ).first()
        
        if not payer:
            # Create new Payer
            payer = Payer.objects.create(
                name=ins_company.name,
                payer_type='insurance',
                is_active=ins_company.is_active,
            )
            created_count += 1
            print(f"✓ Created Payer: {ins_company.name}")
        else:
            # Update existing
            payer.payer_type = 'insurance'
            payer.is_active = ins_company.is_active
            payer.save()
            updated_count += 1
            print(f"✓ Updated Payer: {ins_company.name}")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Created Payers: {created_count}")
print(f"Updated Payers: {updated_count}")
print()

# Verify
insurance_payers = Payer.objects.filter(
    payer_type='insurance',
    is_deleted=False
)
print(f"Total insurance Payers: {insurance_payers.count()}")
for payer in insurance_payers:
    print(f"  ✓ {payer.name}")








