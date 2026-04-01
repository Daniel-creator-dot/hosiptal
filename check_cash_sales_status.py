#!/usr/bin/env python
"""Check cash sales status and walk-in pharmacy sales"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting_advanced import CashSale
from hospital.models_pharmacy_walkin import WalkInPharmacySale

print("=" * 80)
print("CASH SALES STATUS CHECK")
print("=" * 80)
print()

# Check CashSale
cash_sales = CashSale.objects.filter(is_deleted=False)
print(f"Total Cash Sales: {cash_sales.count()}")
print()

# Check WalkInPharmacySale
try:
    walkin_sales = WalkInPharmacySale.objects.filter(is_deleted=False)
    print(f"Total Walk-In Pharmacy Sales: {walkin_sales.count()}")
    
    if walkin_sales.exists():
        print("\nRecent Walk-In Sales:")
        for sale in walkin_sales[:5]:
            print(f"   - {sale.sale_number}: {sale.customer_name} - GHS {sale.total_amount} ({sale.sale_date})")
except Exception as e:
    print(f"WalkInPharmacySale not available: {e}")

print()
print("=" * 80)
print("RECOMMENDATION")
print("=" * 80)
if cash_sales.count() == 0:
    print("⚠️  No cash sales found.")
    print("   Cash sales should be created for:")
    print("   - Walk-in pharmacy sales")
    print("   - Direct retail/merchandise sales")
    print("   - Non-patient cash transactions")
    print()
    print("   Consider:")
    print("   1. Auto-creating CashSale from WalkInPharmacySale")
    print("   2. Or manually creating cash sales as needed")
else:
    print(f"✅ Found {cash_sales.count()} cash sales")








