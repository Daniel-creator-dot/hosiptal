"""
Check Services and Their Amounts
"""
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import ServiceCode, LabTest, Drug
from decimal import Decimal

print("\n" + "=" * 70)
print("SERVICE CODES AND PRICING CHECK")
print("=" * 70)

# Check Service Codes
service_codes = ServiceCode.objects.filter(is_active=True)
print(f"\n📋 Total Active Service Codes: {service_codes.count()}")

if service_codes.count() > 0:
    print("\n" + "-" * 70)
    print("SERVICE CODES (Note: Uses PriceBook for pricing):")
    print("-" * 70)
    
    for service in service_codes[:20]:  # Show first 20
        print(f"\n{service.code} - {service.description}")
        print(f"  Category: {service.category}")
        
        # Check for price books
        from hospital.models import PriceBook
        prices = PriceBook.objects.filter(service_code=service, is_active=True)
        if prices.exists():
            for pb in prices[:3]:
                print(f"  Price ({pb.payer.name if pb.payer else 'Default'}): GHS {pb.unit_price:,.2f}")
        else:
            print(f"  ⚠️ No prices set in PriceBook")
else:
    print("\n❌ NO SERVICE CODES FOUND!")

# Check Lab Tests
print("\n" + "=" * 70)
print("LAB TESTS")
print("=" * 70)

lab_tests = LabTest.objects.filter(is_active=True)
print(f"\nTotal Active Lab Tests: {lab_tests.count()}")

if lab_tests.count() > 0:
    print("\n" + "-" * 70)
    print("LAB TEST PRICING:")
    print("-" * 70)
    
    for test in lab_tests[:15]:  # Show first 15
        print(f"\n{test.code} - {test.name}")
        print(f"  Price: GHS {test.price:,.2f}")
        print(f"  Specimen: {test.specimen_type}")
        print(f"  TAT: {test.tat_minutes} minutes")
else:
    print("\n❌ NO LAB TESTS FOUND!")

# Check Drugs/Medications
print("\n" + "=" * 70)
print("DRUGS/MEDICATIONS")
print("=" * 70)

drugs = Drug.objects.filter(is_active=True)
print(f"\nTotal Active Drugs: {drugs.count()}")

if drugs.count() > 0:
    print("\n" + "-" * 70)
    print("DRUG PRICING:")
    print("-" * 70)
    
    for drug in drugs[:15]:  # Show first 15
        print(f"\n{drug.name} {drug.strength}")
        print(f"  Unit Price: GHS {drug.unit_price:,.2f}")
        print(f"  Cost Price: GHS {drug.cost_price:,.2f}")
        print(f"  Form: {drug.form}")
        print(f"  Pack Size: {drug.pack_size}")
        
        # Check stock
        from hospital.models import PharmacyStock
        stock = PharmacyStock.objects.filter(drug=drug, is_deleted=False).first()
        if stock:
            print(f"  Current Stock: {stock.quantity_on_hand}")
else:
    print("\n❌ NO DRUGS FOUND!")

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

print(f"\n✅ Service Codes: {service_codes.count()}")
print(f"✅ Lab Tests: {lab_tests.count()}")
print(f"✅ Drugs: {drugs.count()}")

total_services = service_codes.count() + lab_tests.count() + drugs.count()
print(f"\n📊 TOTAL BILLABLE SERVICES: {total_services}")

if total_services == 0:
    print("\n❌ CRITICAL: NO SERVICES FOUND!")
    print("   You need to add services/prices to create invoices with amounts.")
    print("\n   TO FIX:")
    print("   1. Go to Django Admin: /admin/")
    print("   2. Add Service Codes (for consultations, procedures)")
    print("   3. Add Lab Tests (for laboratory services)")
    print("   4. Add Drugs (for pharmacy items)")
else:
    print("\n✅ Services exist! Invoices can be created with amounts.")
    print("\n   If invoices are still GHS 0.00, check:")
    print("   1. Are services being added to orders?")
    print("   2. Is billing service creating invoice lines?")
    print("   3. Check invoice detail pages for line items")

print("=" * 70 + "\n")

