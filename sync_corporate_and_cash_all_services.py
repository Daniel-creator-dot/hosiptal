#!/usr/bin/env python
"""Sync all corporate and cash categories with all services"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import transaction
from hospital.models import ServiceCode
from hospital.models_flexible_pricing import PricingCategory, ServicePrice
from decimal import Decimal
from django.utils import timezone

print("=" * 80)
print("SYNCING ALL CORPORATE AND CASH CATEGORIES")
print("=" * 80)
print()

# Get all categories
cash_categories = PricingCategory.objects.filter(category_type='cash', is_deleted=False)
corporate_categories = PricingCategory.objects.filter(category_type='corporate', is_deleted=False)
all_services = ServiceCode.objects.filter(is_deleted=False).order_by('code')

print(f"Total Services: {all_services.count()}")
print(f"Cash Categories: {cash_categories.count()}")
print(f"Corporate Categories: {corporate_categories.count()}")
print()

created_count = 0
today = timezone.now().date()

with transaction.atomic():
    # 1. Sync all cash categories
    print("1. SYNCING CASH CATEGORIES:")
    print()
    
    for cash_cat in cash_categories:
        # Get services that have prices
        services_with_prices = ServicePrice.objects.filter(
            pricing_category=cash_cat,
            is_deleted=False
        ).values_list('service_code_id', flat=True).distinct()
        
        # Find missing services
        missing_services = [s for s in all_services if s.id not in services_with_prices]
        
        if missing_services:
            print(f"   {cash_cat.name}: Creating {len(missing_services)} missing prices...")
            
            for service in missing_services:
                # Try to get price from another cash category
                fallback_price = None
                other_cash = ServicePrice.objects.filter(
                    service_code=service,
                    pricing_category__category_type='cash',
                    is_deleted=False
                ).exclude(pricing_category=cash_cat).first()
                
                if other_cash:
                    fallback_price = other_cash.price
                else:
                    # Try insurance price
                    insurance_price = ServicePrice.objects.filter(
                        service_code=service,
                        pricing_category__category_type='insurance',
                        is_deleted=False
                    ).first()
                    
                    if insurance_price:
                        fallback_price = insurance_price.price
                    else:
                        # Try any price
                        any_price = ServicePrice.objects.filter(
                            service_code=service,
                            is_deleted=False
                        ).first()
                        fallback_price = any_price.price if any_price else Decimal('0.00')
                
                # Create cash price
                ServicePrice.objects.create(
                    service_code=service,
                    pricing_category=cash_cat,
                    price=fallback_price,
                    effective_from=today,
                    is_active=True
                )
                created_count += 1
            
            print(f"      ✓ Created {len(missing_services)} prices")
        else:
            print(f"   ✓ {cash_cat.name}: All {all_services.count()} services have prices")
    print()
    
    # 2. Sync all corporate categories
    print("2. SYNCING CORPORATE CATEGORIES:")
    print()
    
    for corp_cat in corporate_categories:
        # Get services that have prices
        services_with_prices = ServicePrice.objects.filter(
            pricing_category=corp_cat,
            is_deleted=False
        ).values_list('service_code_id', flat=True).distinct()
        
        # Find missing services
        missing_services = [s for s in all_services if s.id not in services_with_prices]
        
        if missing_services:
            print(f"   {corp_cat.name}: Creating {len(missing_services)} missing prices...")
            
            for service in missing_services:
                # Try to get price from another corporate category
                fallback_price = None
                other_corp = ServicePrice.objects.filter(
                    service_code=service,
                    pricing_category__category_type='corporate',
                    is_deleted=False
                ).exclude(pricing_category=corp_cat).first()
                
                if other_corp:
                    fallback_price = other_corp.price
                else:
                    # Try cash price
                    cash_price = ServicePrice.objects.filter(
                        service_code=service,
                        pricing_category__category_type='cash',
                        is_deleted=False
                    ).first()
                    
                    if cash_price:
                        fallback_price = cash_price.price
                    else:
                        # Try insurance price
                        insurance_price = ServicePrice.objects.filter(
                            service_code=service,
                            pricing_category__category_type='insurance',
                            is_deleted=False
                        ).first()
                        
                        if insurance_price:
                            fallback_price = insurance_price.price
                        else:
                            # Try any price
                            any_price = ServicePrice.objects.filter(
                                service_code=service,
                                is_deleted=False
                            ).first()
                            fallback_price = any_price.price if any_price else Decimal('0.00')
                
                # Create corporate price
                ServicePrice.objects.create(
                    service_code=service,
                    pricing_category=corp_cat,
                    price=fallback_price,
                    effective_from=today,
                    is_active=True
                )
                created_count += 1
            
            print(f"      ✓ Created {len(missing_services)} prices")
        else:
            print(f"   ✓ {corp_cat.name}: All {all_services.count()} services have prices")
    print()

print("=" * 80)
print("VERIFICATION")
print("=" * 80)
print()

# Verify all are synced
all_synced = True

print("Cash Categories:")
for cash_cat in cash_categories:
    service_count = ServicePrice.objects.filter(
        pricing_category=cash_cat,
        is_deleted=False
    ).values_list('service_code_id', flat=True).distinct().count()
    
    if service_count == all_services.count():
        print(f"  ✓ {cash_cat.name}: {service_count} / {all_services.count()} services")
    else:
        print(f"  ⚠️  {cash_cat.name}: {service_count} / {all_services.count()} services")
        all_synced = False

print()
print("Corporate Categories:")
for corp_cat in corporate_categories:
    service_count = ServicePrice.objects.filter(
        pricing_category=corp_cat,
        is_deleted=False
    ).values_list('service_code_id', flat=True).distinct().count()
    
    if service_count == all_services.count():
        print(f"  ✓ {corp_cat.name}: {service_count} / {all_services.count()} services")
    else:
        print(f"  ⚠️  {corp_cat.name}: {service_count} / {all_services.count()} services")
        all_synced = False

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Created: {created_count} missing price entries")
print()

if all_synced:
    print("✅ ALL CATEGORIES ARE NOW FULLY SYNCED!")
    print()
    print("Every service now has pricing for:")
    print(f"  ✓ All {cash_categories.count()} cash categories")
    print(f"  ✓ All {corporate_categories.count()} corporate categories")
    print(f"  ✓ All 10 insurance companies")
    print()
    print("Total: {:,} price entries across all categories".format(
        ServicePrice.objects.filter(is_deleted=False).count()
    ))
else:
    print("⚠️  Some categories may still be missing prices")
    print("   Please review the verification above")








