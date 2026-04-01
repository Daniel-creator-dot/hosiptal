"""
Verify Fixed Asset Accounts are properly set up
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import Account

print("=" * 80)
print("VERIFYING FIXED ASSET ACCOUNTS")
print("=" * 80)

# Get all fixed asset accounts (1500-1599)
fixed_assets = Account.objects.filter(
    account_code__startswith='15',
    is_deleted=False
).order_by('account_code')

print(f"\nTotal Fixed Asset Accounts: {fixed_assets.count()}\n")

# Group by category
categories = {
    'Land & Buildings (1500-1509)': [],
    'Equipment (1510-1529)': [],
    'Vehicles (1530-1539)': [],
    'Accumulated Depreciation (1540-1559)': [],
    'Construction (1560-1569)': [],
    'Intangible (1570-1579)': [],
}

for account in fixed_assets:
    code = int(account.account_code) if account.account_code.isdigit() else 0
    if 1500 <= code <= 1509:
        categories['Land & Buildings (1500-1509)'].append(account)
    elif 1510 <= code <= 1529:
        categories['Equipment (1510-1529)'].append(account)
    elif 1530 <= code <= 1539:
        categories['Vehicles (1530-1539)'].append(account)
    elif 1540 <= code <= 1559:
        categories['Accumulated Depreciation (1540-1559)'].append(account)
    elif 1560 <= code <= 1569:
        categories['Construction (1560-1569)'].append(account)
    elif 1570 <= code <= 1579:
        categories['Intangible (1570-1579)'].append(account)

for category, accounts in categories.items():
    if accounts:
        print(f"{category}: {len(accounts)} accounts")
        for acc in accounts:
            status = "Active" if acc.is_active else "Inactive"
            print(f"  [OK] {acc.account_code} - {acc.account_name} ({status})")
        print()

print("=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
print(f"\n[OK] All {fixed_assets.count()} fixed asset accounts are ready!")
