#!/usr/bin/env python
"""
Sync Pharmacy Store Items to Drug Store
Migrates all items from Main Pharmacy Store (PHARM) to Drug Store (DRUGS)
without quantities, maintaining proper linking to prevent duplicates
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_procurement import Store, InventoryItem, InventoryCategory
from django.db import transaction

def sync_pharmacy_to_drug_store():
    """Sync all items from Main Pharmacy Store to Drug Store"""
    print("=" * 70)
    print("SYNCING PHARMACY STORE TO DRUG STORE")
    print("=" * 70)
    print()
    
    # Get stores
    try:
        pharmacy_store = Store.objects.get(code='PHARM', is_deleted=False)
        print(f"✅ Found Pharmacy Store: {pharmacy_store.name}")
    except Store.DoesNotExist:
        print("❌ Main Pharmacy Store (PHARM) not found!")
        return False
    
    try:
        drug_store = Store.objects.get(code='DRUGS', is_deleted=False)
        print(f"✅ Found Drug Store: {drug_store.name}")
    except Store.DoesNotExist:
        print("❌ Drug Store (DRUGS) not found!")
        return False
    
    print()
    print("Migrating items from Pharmacy Store to Drug Store...")
    print("-" * 70)
    
    # Get all items from pharmacy store
    pharmacy_items = InventoryItem.objects.filter(
        store=pharmacy_store,
        is_deleted=False
    ).select_related('category', 'drug', 'preferred_supplier')
    
    total_items = pharmacy_items.count()
    print(f"Found {total_items} items in Pharmacy Store")
    print()
    
    created_count = 0
    updated_count = 0
    skipped_count = 0
    
    with transaction.atomic():
        for item in pharmacy_items:
            # Check if item already exists in Drug Store
            # Match by item_code if available, otherwise by item_name
            lookup_kwargs = {
                'store': drug_store,
                'is_deleted': False
            }
            
            if item.item_code:
                lookup_kwargs['item_code'] = item.item_code
            else:
                lookup_kwargs['item_name'] = item.item_name
                if item.drug:
                    lookup_kwargs['drug'] = item.drug
            
            existing_item = InventoryItem.objects.filter(**lookup_kwargs).first()
            
            if existing_item:
                # Update existing item (sync metadata but keep Drug Store quantity)
                existing_item.item_name = item.item_name
                existing_item.description = item.description
                existing_item.category = item.category
                existing_item.drug = item.drug
                existing_item.unit_of_measure = item.unit_of_measure
                existing_item.preferred_supplier = item.preferred_supplier
                existing_item.reorder_level = item.reorder_level
                existing_item.reorder_quantity = item.reorder_quantity
                # Don't update quantity_on_hand - keep Drug Store's quantity
                # Don't update unit_cost - keep Drug Store's cost
                existing_item.is_active = item.is_active
                existing_item.save()
                updated_count += 1
                print(f"  🔄 Updated: {item.item_name}")
            else:
                # Create new item in Drug Store with 0 quantity
                new_item = InventoryItem.objects.create(
                    store=drug_store,
                    category=item.category,
                    item_name=item.item_name,
                    item_code=item.item_code or '',
                    description=item.description,
                    drug=item.drug,
                    quantity_on_hand=0,  # Start with 0 - quantities added when purchased
                    reorder_level=item.reorder_level,
                    reorder_quantity=item.reorder_quantity,
                    unit_cost=item.unit_cost,  # Keep cost for reference
                    unit_of_measure=item.unit_of_measure,
                    preferred_supplier=item.preferred_supplier,
                    is_active=item.is_active
                )
                created_count += 1
                print(f"  ✅ Created: {item.item_name} (Category: {item.category.name if item.category else 'None'})")
    
    print()
    print("=" * 70)
    print(f"✅ SYNC COMPLETE!")
    print(f"   Created: {created_count} items")
    print(f"   Updated: {updated_count} items")
    print(f"   Skipped: {skipped_count} items")
    print("=" * 70)
    print()
    
    # Show summary
    drug_store_items = InventoryItem.objects.filter(
        store=drug_store,
        is_deleted=False
    ).count()
    pharmacy_store_items = InventoryItem.objects.filter(
        store=pharmacy_store,
        is_deleted=False
    ).count()
    
    print("Store Summary:")
    print(f"  Drug Store (DRUGS): {drug_store_items} items")
    print(f"  Pharmacy Store (PHARM): {pharmacy_store_items} items")
    print()
    
    return True

if __name__ == '__main__':
    sync_pharmacy_to_drug_store()
