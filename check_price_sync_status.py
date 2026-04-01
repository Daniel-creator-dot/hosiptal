"""
Check price synchronization status
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import ServiceCode, LabTest, Drug
from hospital.models_flexible_pricing import PricingCategory, ServicePrice
from decimal import Decimal

print("="*80)
print("PRICE SYNCHRONIZATION STATUS CHECK")
print("="*80)

cash_category = PricingCategory.objects.filter(code='CASH', is_active=True).first()

# Check Lab Tests
print("\n" + "-"*80)
print("LAB TESTS")
print("-"*80)

lab_tests = LabTest.objects.filter(is_active=True, is_deleted=False)
print(f"Total Lab Tests: {lab_tests.count()}")

lab_with_prices = 0
lab_with_service_code = 0
lab_with_service_price = 0

for lab_test in lab_tests[:20]:  # Sample
    has_price = lab_test.price and lab_test.price > 0
    if has_price:
        lab_with_prices += 1
    
    # Check for ServiceCode
    service_code = ServiceCode.objects.filter(
        code__icontains=lab_test.code,
        category__icontains='Laboratory'
    ).first()
    
    if service_code:
        lab_with_service_code += 1
        
        # Check for ServicePrice
        if cash_category:
            service_price = ServicePrice.objects.filter(
                service_code=service_code,
                pricing_category=cash_category,
                is_active=True
            ).first()
            if service_price:
                lab_with_service_price += 1
                if has_price and service_price.price != lab_test.price:
                    print(f"  MISMATCH: {lab_test.code} - LabTest: GHS {lab_test.price}, ServicePrice: GHS {service_price.price}")

print(f"\nLab Tests with price: {lab_with_prices}")
print(f"Lab Tests with ServiceCode: {lab_with_service_code}")
print(f"Lab Tests with ServicePrice: {lab_with_service_price}")

# Check Drugs
print("\n" + "-"*80)
print("DRUGS")
print("-"*80)

drugs = Drug.objects.filter(is_active=True, is_deleted=False)
print(f"Total Drugs: {drugs.count()}")

drugs_with_prices = 0
drugs_with_service_code = 0
drugs_with_service_price = 0

for drug in drugs[:20]:  # Sample
    unit_price = getattr(drug, 'unit_price', None)
    has_price = unit_price and unit_price > 0
    if has_price:
        drugs_with_prices += 1
    
    # Check for ServiceCode
    service_code = ServiceCode.objects.filter(
        description__icontains=drug.name[:50],
        category__icontains='Pharmacy'
    ).first()
    
    if service_code:
        drugs_with_service_code += 1
        
        # Check for ServicePrice
        if cash_category:
            service_price = ServicePrice.objects.filter(
                service_code=service_code,
                pricing_category=cash_category,
                is_active=True
            ).first()
            if service_price:
                drugs_with_service_price += 1
                if has_price and service_price.price != unit_price:
                    print(f"  MISMATCH: {drug.name} - Drug: GHS {unit_price}, ServicePrice: GHS {service_price.price}")

print(f"\nDrugs with price: {drugs_with_prices}")
print(f"Drugs with ServiceCode: {drugs_with_service_code}")
print(f"Drugs with ServicePrice: {drugs_with_service_price}")

# Check ServiceCode entries
print("\n" + "-"*80)
print("SERVICE CODE ENTRIES")
print("-"*80)

lab_service_codes = ServiceCode.objects.filter(
    category__icontains='Laboratory',
    is_active=True,
    is_deleted=False
)
print(f"Lab ServiceCodes: {lab_service_codes.count()}")

pharmacy_service_codes = ServiceCode.objects.filter(
    category__icontains='Pharmacy',
    is_active=True,
    is_deleted=False
)
print(f"Pharmacy ServiceCodes: {pharmacy_service_codes.count()}")

# Check ServicePrice entries
if cash_category:
    lab_prices = ServicePrice.objects.filter(
        service_code__category__icontains='Laboratory',
        pricing_category=cash_category,
        is_active=True,
        is_deleted=False
    )
    print(f"Lab ServicePrices (Cash): {lab_prices.count()}")
    
    pharmacy_prices = ServicePrice.objects.filter(
        service_code__category__icontains='Pharmacy',
        pricing_category=cash_category,
        is_active=True,
        is_deleted=False
    )
    print(f"Pharmacy ServicePrices (Cash): {pharmacy_prices.count()}")

print("\n" + "="*80)
