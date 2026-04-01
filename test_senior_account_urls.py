#!/usr/bin/env python
"""Test all URLs used in Senior Account Officer dashboard"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.urls import reverse

urls_to_test = [
    'hospital:account_staff_list',
    'hospital:accountant_comprehensive_dashboard',
    'hospital:cashbook_list',
    'hospital:bank_reconciliation_list',
    'hospital:insurance_receivable_list',
    'hospital:pv_list',
    'hospital:general_ledger_report',
    'hospital:profit_loss_list',
]

print("Testing URL names used in Senior Account Officer dashboard:")
print("=" * 60)

all_ok = True
for url_name in urls_to_test:
    try:
        url = reverse(url_name)
        print(f"✅ {url_name:45} -> {url}")
    except Exception as e:
        print(f"❌ {url_name:45} -> ERROR: {e}")
        all_ok = False

print("=" * 60)
if all_ok:
    print("✅ All URLs work correctly!")
else:
    print("❌ Some URLs failed!")

