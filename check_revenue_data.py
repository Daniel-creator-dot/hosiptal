#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import PaymentReceipt
from django.db.models import Sum
from decimal import Decimal

print("\n" + "="*70)
print("Checking Revenue Data")
print("="*70)

# Get all receipts
receipts = PaymentReceipt.objects.filter(is_deleted=False)
print(f"\nTotal PaymentReceipts: {receipts.count()}")
print(f"Total Revenue: GHS {receipts.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0}")

# Group by service type
print("\nRevenue by Service Type:")
print("-"*70)
by_service = receipts.values('service_type').annotate(total=Sum('amount_paid')).order_by('-total')
for item in by_service:
    print(f"  {item['service_type']:20s}: GHS {item['total']}")

# Show recent receipts
print("\nRecent Receipts (last 5):")
print("-"*70)
recent = receipts.order_by('-receipt_date')[:5]
for r in recent:
    print(f"  {r.receipt_number}: GHS {r.amount_paid} - Type: {r.service_type} - Date: {r.receipt_date}")

print("\n" + "="*70)

