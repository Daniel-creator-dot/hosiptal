#!/usr/bin/env python
"""
Create Essential Stores: Lab, Main, and Drugs (Pharmacy)
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_procurement import Store
from hospital.models import Department

def create_essential_stores():
    """Create essential stores if they don't exist"""
    print("=" * 70)
    print("CREATING ESSENTIAL STORES")
    print("=" * 70)
    print()
    
    stores_to_create = [
        {
            'name': 'Main Store',
            'code': 'MAIN',
            'store_type': 'main',
            'description': 'Main central store for all inventory items'
        },
        {
            'name': 'Laboratory Store',
            'code': 'LAB',
            'store_type': 'lab',
            'description': 'Laboratory store for lab supplies, reagents, and equipment'
        },
        {
            'name': 'Pharmacy Store',
            'code': 'PHARM',
            'store_type': 'pharmacy',
            'description': 'Pharmacy store for drugs and pharmaceutical items'
        },
        {
            'name': 'Drugs Store',
            'code': 'DRUGS',
            'store_type': 'pharmacy',
            'description': 'Drugs store for pharmaceutical items and medications'
        },
    ]
    
    created_count = 0
    existing_count = 0
    
    for store_data in stores_to_create:
        store, created = Store.objects.get_or_create(
            code=store_data['code'],
            defaults={
                'name': store_data['name'],
                'store_type': store_data['store_type'],
                'description': store_data['description'],
                'is_active': True,
                'is_deleted': False,
            }
        )
        
        if created:
            print(f"✅ Created: {store.name} ({store.code}) - {store.get_store_type_display()}")
            created_count += 1
        else:
            # Update if exists but inactive
            if not store.is_active or store.is_deleted:
                store.is_active = True
                store.is_deleted = False
                store.name = store_data['name']
                store.store_type = store_data['store_type']
                store.description = store_data['description']
                store.save()
                print(f"🔄 Updated: {store.name} ({store.code}) - Reactivated")
                created_count += 1
            else:
                print(f"ℹ️  Already exists: {store.name} ({store.code})")
                existing_count += 1
    
    print()
    print("=" * 70)
    print(f"✅ SUCCESS! Created/Updated: {created_count}, Already existed: {existing_count}")
    print("=" * 70)
    print()
    
    # List all active stores
    print("All Active Stores:")
    print("-" * 70)
    all_stores = Store.objects.filter(is_active=True, is_deleted=False).order_by('store_type', 'name')
    for store in all_stores:
        print(f"  • {store.name} ({store.code}) - {store.get_store_type_display()}")
    print()
    
    return True

if __name__ == '__main__':
    create_essential_stores()
