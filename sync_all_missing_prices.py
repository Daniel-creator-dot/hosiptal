#!/usr/bin/env python
"""Sync all missing prices for all services across all insurance companies"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import transaction
from hospital.models_insurance_companies import InsuranceCompany
from hospital.models import ServiceCode
from hospital.models_flexible_pricing import PricingCategory, ServicePrice
from decimal import Decimal
from django.utils import timezone

print("=" * 80)
print("SYNCING ALL MISSING PRICES")
print("=" * 80)
print()

# Get all categories
cash_category = PricingCategory.objects.filter(category_type='cash', is_deleted=False).first()
insurance_companies = InsuranceCompany.objects.filter(is_active=True, is_deleted=False).order_by('name')
all_services = ServiceCode.objects.filter(is_deleted=False).order_by('code')

print(f"Total Services: {all_services.count()}")
print(f"Cash Category: {cash_category.name if cash_category else 'MISSING'}")
print(f"Insurance Companies: {insurance_companies.count()}")
print()

created_count = 0
today = timezone.now().date()

with transaction.atomic():
    # 1. Fix missing insurance prices (use cash price as fallback)
    print("1. FIXING MISSING INSURANCE PRICES:")
    print()
    
    for ins_company in insurance_companies:
        # Find pricing category
        pricing_cat = PricingCategory.objects.filter(
            insurance_company=ins_company,
            is_deleted=False
        ).first()
        
        if not pricing_cat:
            continue
        
        # Get services that have prices
        services_with_prices = ServicePrice.objects.filter(
            pricing_category=pricing_cat,
            is_deleted=False
        ).values_list('service_code_id', flat=True).distinct()
        
        # Find missing services
        missing_services = [s for s in all_services if s.id not in services_with_prices]
        
        if missing_services:
            print(f"   {ins_company.name}: Creating {len(missing_services)} missing prices...")
            
            for service in missing_services:
                # Try to get cash price as fallback
                cash_price = None
                if cash_category:
                    cash_price_obj = ServicePrice.objects.filter(
                        service_code=service,
                        pricing_category=cash_category,
                        is_deleted=False
                    ).first()
                    if cash_price_obj:
                        cash_price = cash_price_obj.price
                
                # If no cash price, try to get any existing price for this service
                if not cash_price:
                    any_price = ServicePrice.objects.filter(
                        service_code=service,
                        is_deleted=False
                    ).first()
                    if any_price:
                        cash_price = any_price.price
                
                # Default to 0 if still no price found
                if not cash_price:
                    cash_price = Decimal('0.00')
                
                # Create insurance price (use cash price as base, can be adjusted later)
                ServicePrice.objects.create(
                    service_code=service,
                    pricing_category=pricing_cat,
                    price=cash_price,
                    effective_from=today,
                    is_active=True
                )
                created_count += 1
            
            print(f"      ✓ Created {len(missing_services)} prices")
        else:
            print(f"   ✓ {ins_company.name}: All prices exist")
    print()
    
    # 2. Fix missing cash prices (use average from insurance or default)
    print("2. FIXING MISSING CASH PRICES:")
    print()
    
    if cash_category:
        cash_services = ServicePrice.objects.filter(
            pricing_category=cash_category,
            is_deleted=False
        ).values_list('service_code_id', flat=True).distinct()
        
        missing_cash = [s for s in all_services if s.id not in cash_services]
        
        if missing_cash:
            print(f"   Creating {len(missing_cash)} missing cash prices...")
            
            for service in missing_cash:
                # Try to get average from insurance prices
                insurance_prices = ServicePrice.objects.filter(
                    service_code=service,
                    pricing_category__category_type='insurance',
                    is_deleted=False
                ).exclude(price=0)
                
                if insurance_prices.exists():
                    # Use average of insurance prices
                    from django.db.models import Avg
                    avg_price = insurance_prices.aggregate(avg=Avg('price'))['avg']
                    price = Decimal(str(avg_price)) if avg_price else Decimal('0.00')
                else:
                    # Try to get any existing price
                    any_price = ServicePrice.objects.filter(
                        service_code=service,
                        is_deleted=False
                    ).first()
                    price = any_price.price if any_price else Decimal('0.00')
                
                # Create cash price
                ServicePrice.objects.create(
                    service_code=service,
                    pricing_category=cash_category,
                    price=price,
                    effective_from=today,
                    is_active=True
                )
                created_count += 1
            
            print(f"      ✓ Created {len(missing_cash)} cash prices")
        else:
            print(f"   ✓ Cash: All prices exist")
    print()

print("=" * 80)
print("VERIFICATION")
print("=" * 80)
print()

# Verify all are synced now
all_synced = True

for ins_company in insurance_companies:
    pricing_cat = PricingCategory.objects.filter(
        insurance_company=ins_company,
        is_deleted=False
    ).first()
    
    if pricing_cat:
        service_count = ServicePrice.objects.filter(
            pricing_category=pricing_cat,
            is_deleted=False
        ).values_list('service_code_id', flat=True).distinct().count()
        
        if service_count == all_services.count():
            print(f"✓ {ins_company.name}: {service_count} / {all_services.count()} services")
        else:
            print(f"⚠️  {ins_company.name}: {service_count} / {all_services.count()} services")
            all_synced = False
    else:
        print(f"✗ {ins_company.name}: No pricing category")
        all_synced = False

if cash_category:
    cash_count = ServicePrice.objects.filter(
        pricing_category=cash_category,
        is_deleted=False
    ).values_list('service_code_id', flat=True).distinct().count()
    
    if cash_count == all_services.count():
        print(f"✓ Cash: {cash_count} / {all_services.count()} services")
    else:
        print(f"⚠️  Cash: {cash_count} / {all_services.count()} services")
        all_synced = False

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Created: {created_count} missing price entries")
print()

if all_synced:
    print("✅ ALL SERVICES ARE NOW FULLY SYNCED!")
    print()
    print("Every service now has pricing for:")
    print(f"  ✓ All {insurance_companies.count()} insurance companies")
    print(f"  ✓ Cash category")
    print()
    print("The system is ready for billing with any insurance company!")
else:
    print("⚠️  Some services may still be missing prices")
    print("   Please review the verification above")








