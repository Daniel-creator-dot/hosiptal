"""
Quick verification script to check imported prices
"""
import os
import sys
import django

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import ServiceCode
from hospital.models_flexible_pricing import PricingCategory, ServicePrice
from decimal import Decimal

# Get pricing categories
cash_cat = PricingCategory.objects.filter(code='CASH').first()
corp_cat = PricingCategory.objects.filter(code='CORP').first()
ins_cat = PricingCategory.objects.filter(code='INS').first()
nhis_cat = PricingCategory.objects.filter(code='NHIS').first()

print("="*80)
print("PRICE IMPORT VERIFICATION")
print("="*80)

# Get sample services with prices
services_with_prices = ServiceCode.objects.filter(
    flexible_prices__isnull=False
).distinct()[:10]

print(f"\nSample of {services_with_prices.count()} services with prices:\n")

for service in services_with_prices:
    print(f"\n{service.code} - {service.description}")
    print(f"  Category: {service.category}")
    
    # Get all prices for this service
    prices = ServicePrice.objects.filter(
        service_code=service,
        is_active=True,
        is_deleted=False
    ).select_related('pricing_category')
    
    for price in prices:
        cat_name = price.pricing_category.name
        print(f"    {cat_name:30s}: GHS {price.price:>10.2f}")

# Count statistics
total_services = ServiceCode.objects.filter(
    flexible_prices__isnull=False
).distinct().count()

cash_prices = ServicePrice.objects.filter(
    pricing_category=cash_cat,
    is_active=True,
    is_deleted=False
).count() if cash_cat else 0

corp_prices = ServicePrice.objects.filter(
    pricing_category=corp_cat,
    is_active=True,
    is_deleted=False
).count() if corp_cat else 0

ins_prices = ServicePrice.objects.filter(
    pricing_category=ins_cat,
    is_active=True,
    is_deleted=False
).count() if ins_cat else 0

nhis_prices = ServicePrice.objects.filter(
    pricing_category=nhis_cat,
    is_active=True,
    is_deleted=False
).count() if nhis_cat else 0

total_prices = ServicePrice.objects.filter(
    is_active=True,
    is_deleted=False
).count()

print("\n" + "="*80)
print("SUMMARY STATISTICS")
print("="*80)
print(f"Total services with prices: {total_services}")
print(f"Total price entries: {total_prices}")
print(f"\nBy Price Category:")
print(f"  Cash prices: {cash_prices}")
print(f"  Corporate prices: {corp_prices}")
print(f"  Insurance prices: {ins_prices}")
print(f"  NHIS prices: {nhis_prices}")

# Check insurance company specific prices
insurance_cats = PricingCategory.objects.filter(
    category_type='insurance',
    code__startswith='INS-',
    is_active=True
)

print(f"\nInsurance Company Specific Categories: {insurance_cats.count()}")
for cat in insurance_cats[:5]:
    count = ServicePrice.objects.filter(
        pricing_category=cat,
        is_active=True,
        is_deleted=False
    ).count()
    print(f"  {cat.name}: {count} prices")

print("\n" + "="*80)
