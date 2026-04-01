"""
Update corporate debtors from insurance/private to corporate payer type
These companies should be corporate clients, not insurance
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Payer
from hospital.models_accounting_advanced import AdvancedAccountsReceivable
from hospital.models_primecare_accounting import InsuranceReceivableEntry
from decimal import Decimal

# List of corporate companies that should be corporate payers
CORPORATE_COMPANIES = [
    'Anointed Electricals Limited',
    'Assemblies Of God',
    'Asuogyaman Company Limited',
    'Calvary Baptist Church',
    'Electricity Company of Ghana',
    'Ghana Comm. Tech. University',
    'Kofata Motors LTD',
    'OceanAir Logistics & Supply LTD',
    'Minerals Income Investment Fund',
    'Accra Great Olympics Fc',
]

print("="*80)
print("UPDATING CORPORATE DEBTORS TO CORPORATE PAYER TYPE")
print("="*80)
print()

updated_count = 0
not_found = []

for company_name in CORPORATE_COMPANIES:
    # Try to find the payer (case-insensitive, partial match)
    payers = Payer.objects.filter(
        name__icontains=company_name,
        is_deleted=False
    )
    
    if payers.exists():
        for payer in payers:
            old_type = payer.payer_type
            if old_type != 'corporate':
                print(f"Updating: {payer.name}")
                print(f"  Old payer_type: {old_type}")
                print(f"  New payer_type: corporate")
                
                # Update payer type
                payer.payer_type = 'corporate'
                payer.save()
                
                # Check for related receivables
                ar_count = AdvancedAccountsReceivable.objects.filter(
                    invoice__payer=payer,
                    balance_due__gt=0
                ).count()
                
                ire_count = InsuranceReceivableEntry.objects.filter(
                    payer=payer,
                    outstanding_amount__gt=0,
                    is_deleted=False
                ).count()
                
                print(f"  Related AR records: {ar_count}")
                print(f"  Related Insurance Receivable Entry records: {ire_count}")
                print()
                
                updated_count += 1
            else:
                print(f"Already corporate: {payer.name}")
                print()
    else:
        # Try variations
        variations = [
            company_name.replace('Limited', 'Ltd'),
            company_name.replace('Ltd', 'Limited'),
            company_name.replace('LTD', 'Limited'),
            company_name.upper(),
            company_name.lower(),
        ]
        
        found = False
        for variation in variations:
            payers = Payer.objects.filter(
                name__icontains=variation,
                is_deleted=False
            )
            if payers.exists():
                for payer in payers:
                    if payer.payer_type != 'corporate':
                        print(f"Updating (variation): {payer.name}")
                        print(f"  Old payer_type: {payer.payer_type}")
                        print(f"  New payer_type: corporate")
                        payer.payer_type = 'corporate'
                        payer.save()
                        updated_count += 1
                        found = True
                        print()
                break
        
        if not found:
            not_found.append(company_name)
            print(f"NOT FOUND: {company_name}")
            print()

print("="*80)
print(f"SUMMARY")
print("="*80)
print(f"Updated payers: {updated_count}")
if not_found:
    print(f"Not found ({len(not_found)}):")
    for name in not_found:
        print(f"  - {name}")

# Show all corporate payers now
print()
print("="*80)
print("ALL CORPORATE PAYERS (after update)")
print("="*80)
corporate_payers = Payer.objects.filter(
    payer_type='corporate',
    is_deleted=False
).order_by('name')

from django.db.models import Sum

for payer in corporate_payers:
    # Get total receivables
    ar_result = AdvancedAccountsReceivable.objects.filter(
        invoice__payer=payer,
        balance_due__gt=0
    ).aggregate(total=Sum('balance_due'))
    ar_total = ar_result['total'] or Decimal('0.00')
    
    ire_result = InsuranceReceivableEntry.objects.filter(
        payer=payer,
        outstanding_amount__gt=0,
        is_deleted=False
    ).aggregate(total=Sum('outstanding_amount'))
    ire_total = ire_result['total'] or Decimal('0.00')
    
    total = ar_total + ire_total
    print(f"{payer.name:50} GHS {total:>15,.2f}")

print()
print("="*80)
print("SUCCESS: Corporate debtors updated!")
print("="*80)
print()
print("These companies will now appear in:")
print("  - Corporate Receivables: /hms/accounting/corporate-receivables/")
print("  - NOT in Insurance Receivables anymore")
print()

