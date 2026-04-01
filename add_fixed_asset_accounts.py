"""
Add Fixed Asset Accounts to Chart of Accounts
Senior Programmer Approach - Complete Fixed Asset Setup
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import Account
from django.db import transaction
from decimal import Decimal

print("=" * 80)
print("ADDING FIXED ASSET ACCOUNTS")
print("Senior Programmer Implementation")
print("=" * 80)

# Fixed Asset Accounts (1500-1599 range)
# Based on accounting standards: Property, Plant & Equipment
FIXED_ASSET_ACCOUNTS = [
    # Land and Buildings (1500-1509)
    {
        'code': '1500',
        'name': 'Land',
        'type': 'asset',
        'description': 'Land owned by the hospital'
    },
    {
        'code': '1501',
        'name': 'Land Improvements',
        'type': 'asset',
        'description': 'Improvements to land (fencing, parking lots, landscaping)'
    },
    {
        'code': '1502',
        'name': 'Buildings',
        'type': 'asset',
        'description': 'Hospital buildings and structures'
    },
    {
        'code': '1503',
        'name': 'Building Improvements',
        'type': 'asset',
        'description': 'Improvements and renovations to buildings'
    },
    
    # Equipment (1510-1529)
    {
        'code': '1510',
        'name': 'Medical Equipment',
        'type': 'asset',
        'description': 'Medical equipment and devices'
    },
    {
        'code': '1511',
        'name': 'Laboratory Equipment',
        'type': 'asset',
        'description': 'Laboratory and diagnostic equipment'
    },
    {
        'code': '1512',
        'name': 'Imaging Equipment',
        'type': 'asset',
        'description': 'Radiology and imaging equipment (X-ray, CT, MRI, etc.)'
    },
    {
        'code': '1513',
        'name': 'Surgical Equipment',
        'type': 'asset',
        'description': 'Surgical instruments and equipment'
    },
    {
        'code': '1514',
        'name': 'Office Equipment',
        'type': 'asset',
        'description': 'Office furniture and equipment'
    },
    {
        'code': '1515',
        'name': 'Computer Equipment',
        'type': 'asset',
        'description': 'Computers, servers, and IT equipment'
    },
    {
        'code': '1516',
        'name': 'Furniture and Fixtures',
        'type': 'asset',
        'description': 'Furniture, fixtures, and fittings'
    },
    
    # Vehicles (1530-1539)
    {
        'code': '1530',
        'name': 'Vehicles',
        'type': 'asset',
        'description': 'Hospital vehicles (ambulances, cars, etc.)'
    },
    {
        'code': '1531',
        'name': 'Ambulances',
        'type': 'asset',
        'description': 'Ambulance fleet'
    },
    
    # Accumulated Depreciation (1540-1559)
    {
        'code': '1540',
        'name': 'Accumulated Depreciation - Buildings',
        'type': 'asset',
        'description': 'Accumulated depreciation on buildings (contra-asset)'
    },
    {
        'code': '1541',
        'name': 'Accumulated Depreciation - Medical Equipment',
        'type': 'asset',
        'description': 'Accumulated depreciation on medical equipment (contra-asset)'
    },
    {
        'code': '1542',
        'name': 'Accumulated Depreciation - Laboratory Equipment',
        'type': 'asset',
        'description': 'Accumulated depreciation on laboratory equipment (contra-asset)'
    },
    {
        'code': '1543',
        'name': 'Accumulated Depreciation - Imaging Equipment',
        'type': 'asset',
        'description': 'Accumulated depreciation on imaging equipment (contra-asset)'
    },
    {
        'code': '1544',
        'name': 'Accumulated Depreciation - Vehicles',
        'type': 'asset',
        'description': 'Accumulated depreciation on vehicles (contra-asset)'
    },
    {
        'code': '1545',
        'name': 'Accumulated Depreciation - Office Equipment',
        'type': 'asset',
        'description': 'Accumulated depreciation on office equipment (contra-asset)'
    },
    {
        'code': '1546',
        'name': 'Accumulated Depreciation - Computer Equipment',
        'type': 'asset',
        'description': 'Accumulated depreciation on computer equipment (contra-asset)'
    },
    {
        'code': '1547',
        'name': 'Accumulated Depreciation - Furniture and Fixtures',
        'type': 'asset',
        'description': 'Accumulated depreciation on furniture and fixtures (contra-asset)'
    },
    
    # Construction in Progress (1560-1569)
    {
        'code': '1560',
        'name': 'Construction in Progress',
        'type': 'asset',
        'description': 'Assets under construction or installation'
    },
    
    # Intangible Assets (1570-1579)
    {
        'code': '1570',
        'name': 'Intangible Assets',
        'type': 'asset',
        'description': 'Intangible assets (software licenses, patents, etc.)'
    },
    {
        'code': '1571',
        'name': 'Software Licenses',
        'type': 'asset',
        'description': 'Software licenses and subscriptions'
    },
]

print("\n1. Creating Fixed Asset Accounts...")
print("-" * 80)

created_count = 0
updated_count = 0
skipped_count = 0

with transaction.atomic():
    for account_data in FIXED_ASSET_ACCOUNTS:
        account, created = Account.objects.get_or_create(
            account_code=account_data['code'],
            defaults={
                'account_name': account_data['name'],
                'account_type': account_data['type'],
                'description': account_data.get('description', ''),
                'is_active': True,
            }
        )
        
        if created:
            created_count += 1
            print(f"  [CREATED] {account_data['code']} - {account_data['name']}")
        else:
            # Update if exists but name/description changed
            if account.account_name != account_data['name'] or account.description != account_data.get('description', ''):
                account.account_name = account_data['name']
                account.description = account_data.get('description', '')
                account.account_type = account_data['type']
                account.is_active = True
                account.save()
                updated_count += 1
                print(f"  [UPDATED] {account_data['code']} - {account_data['name']}")
            else:
                skipped_count += 1
                print(f"  [EXISTS] {account_data['code']} - {account_data['name']}")

print(f"\n  Summary:")
print(f"    Created: {created_count}")
print(f"    Updated: {updated_count}")
print(f"    Already exists: {skipped_count}")

# Verify all accounts
print("\n2. Verifying Fixed Asset Accounts...")
print("-" * 80)

fixed_asset_accounts = Account.objects.filter(
    account_code__startswith='15',
    is_deleted=False
).order_by('account_code')

print(f"  Total fixed asset accounts (15xx): {fixed_asset_accounts.count()}")

# Group by category
categories = {
    'Land & Buildings (1500-1509)': [],
    'Equipment (1510-1529)': [],
    'Vehicles (1530-1539)': [],
    'Accumulated Depreciation (1540-1559)': [],
    'Construction (1560-1569)': [],
    'Intangible (1570-1579)': [],
}

for account in fixed_asset_accounts:
    code = int(account.account_code)
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
        print(f"\n  {category}: {len(accounts)} accounts")
        for acc in accounts[:3]:  # Show first 3
            print(f"    - {acc.account_code}: {acc.account_name}")

print("\n" + "=" * 80)
print("FIXED ASSET ACCOUNTS ADDED")
print("=" * 80)
print(f"\nSummary:")
print(f"  - Accounts created: {created_count}")
print(f"  - Accounts updated: {updated_count}")
print(f"  - Total fixed asset accounts: {fixed_asset_accounts.count()}")
print(f"\n[OK] Fixed asset accounts are now available in the Chart of Accounts!")
