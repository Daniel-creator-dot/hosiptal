#!/usr/bin/env python
"""Test balance sheet view output"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from hospital.views_accounting_advanced import balance_sheet
from decimal import Decimal

factory = RequestFactory()
request = factory.get('/accounting/balance-sheet/')
user = User.objects.filter(is_superuser=True).first() or User.objects.first()
request.user = user

try:
    response = balance_sheet(request)
    context = response.context_data
    
    print("=" * 80)
    print("BALANCE SHEET CONTEXT CHECK")
    print("=" * 80)
    print()
    
    print("Context Keys:", list(context.keys()))
    print()
    
    # Check assets
    if 'assets' in context:
        assets = context['assets']
        print("Assets Type:", type(assets))
        if isinstance(assets, dict):
            print("Assets Keys:", list(assets.keys()))
            print()
            print("Assets Values:")
            for key, value in assets.items():
                print(f"  {key}: {value} (type: {type(value)})")
        else:
            print("ERROR: Assets is not a dictionary!")
    else:
        print("ERROR: 'assets' not in context!")
    
    print()
    
    # Check liabilities
    if 'liabilities' in context:
        liabilities = context['liabilities']
        print("Liabilities Type:", type(liabilities))
        if isinstance(liabilities, dict):
            print("Liabilities Keys:", list(liabilities.keys()))
            print()
            print("Liabilities Values:")
            for key, value in liabilities.items():
                print(f"  {key}: {value} (type: {type(value)})")
        else:
            print("ERROR: Liabilities is not a dictionary!")
    else:
        print("ERROR: 'liabilities' not in context!")
    
    print()
    print("Totals:")
    print(f"  Total Assets: {context.get('total_assets', 'MISSING')}")
    print(f"  Total Liabilities: {context.get('total_liabilities', 'MISSING')}")
    print(f"  Total Equity: {context.get('total_equity', 'MISSING')}")
    print(f"  Net Income: {context.get('net_income', 'MISSING')}")
    print(f"  Total Equity with Income: {context.get('total_equity_with_income', 'MISSING')}")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()








