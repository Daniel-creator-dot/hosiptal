#!/usr/bin/env python
"""
Ensure Drug Store has ALL items from Pharmacy Store
Creates missing items with 0 quantity and proper linking
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_procurement import Store, InventoryItem
from django.db import transaction

def ensure_complete_sync():
    """Ensure Drug Store has all Pharmacy Store items"""
    print("=" * 70)
    print("ENSURING COMPLETE SYNC: PHARMACY STORE → DRUG STORE")
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
    print("Checking for missing items in Drug Store...")
    print("-" * 70)
    
    # Get all items from pharmacy store
    pharmacy_items = InventoryItem.objects.filter(
        store=pharmacy_store,
        is_deleted=False
    ).select_related('category', 'drug', 'preferred_supplier')
    
    total_items = pharmacy_items.count()
    print(f"Total items in Pharmacy Store: {total_items}")
    print()
    
    created_count = 0
    updated_count = 0
    already_exists_count = 0
    missing_items = []
    
    with transaction.atomic():
        for item in pharmacy_items:
            # Check if item exists in Drug Store using multiple lookup strategies
            lookup_kwargs = {
                'store': drug_store,
                'is_deleted': False
            }
            
            # Strategy 1: Match by item_code if available
            if item.item_code and item.item_code.strip():
                lookup_kwargs['item_code'] = item.item_code
                existing_item = InventoryItem.objects.filter(**lookup_kwargs).first()
            else:
                existing_item = None
            
            # Strategy 2: Match by drug if available
            if not existing_item and item.drug:
                lookup_kwargs = {
                    'store': drug_store,
                    'drug': item.drug,
                    'is_deleted': False
                }
                existing_item = InventoryItem.objects.filter(**lookup_kwargs).first()
            
            # Strategy 3: Match by exact item_name
            if not existing_item:
                lookup_kwargs = {
                    'store': drug_store,
                    'item_name': item.item_name,
                    'is_deleted': False
                }
                existing_item = InventoryItem.objects.filter(**lookup_kwargs).first()
            
            if existing_item:
                # Item exists - update metadata but preserve Drug Store quantity
                existing_item.item_name = item.item_name
                existing_item.description = item.description
                existing_item.category = item.category
                existing_item.drug = item.drug
                existing_item.unit_of_measure = item.unit_of_measure
                existing_item.preferred_supplier = item.preferred_supplier
                existing_item.reorder_level = item.reorder_level
                existing_item.reorder_quantity = item.reorder_quantity
                # Ensure item_code matches if Pharmacy has one
                if item.item_code and item.item_code.strip() and not existing_item.item_code:
                    existing_item.item_code = item.item_code
                # Don't update quantity_on_hand - keep Drug Store's quantity
                # Don't update unit_cost - keep Drug Store's cost
                existing_item.is_active = item.is_active
                existing_item.save()
                updated_count += 1
                already_exists_count += 1
            else:
                # Item doesn't exist - create it with 0 quantity
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
                missing_items.append(item.item_name)
                print(f"  ✅ Created: {item.item_name} (Category: {item.category.name if item.category else 'None'})")
    
    print()
    print("=" * 70)
    print(f"✅ SYNC COMPLETE!")
    print(f"   Created: {created_count} missing items")
    print(f"   Updated: {updated_count} existing items")
    print(f"   Already exists: {already_exists_count} items")
    print("=" * 70)
    print()
    
    # Verify sync
    drug_store_items = InventoryItem.objects.filter(
        store=drug_store,
        is_deleted=False
    ).count()
    pharmacy_store_items = InventoryItem.objects.filter(
        store=pharmacy_store,
        is_deleted=False
    ).count()
    
    print("Verification:")
    print(f"  Pharmacy Store (PHARM): {pharmacy_store_items} items")
    print(f"  Drug Store (DRUGS): {drug_store_items} items")
    
    if drug_store_items >= pharmacy_store_items:
        print("  ✅ All Pharmacy Store items are in Drug Store!")
    else:
        print(f"  ⚠️  Warning: Drug Store has {drug_store_items} items, Pharmacy Store has {pharmacy_store_items}")
        print(f"  Missing: {pharmacy_store_items - drug_store_items} items")
    
    print()
    
    # Show linking statistics
    print("Linking Statistics:")
    linked_by_code = InventoryItem.objects.filter(
        store=drug_store,
        item_code__isnull=False,
        item_code__gt='',
        is_deleted=False
    ).count()
    linked_by_drug = InventoryItem.objects.filter(
        store=drug_store,
        drug__isnull=False,
        is_deleted=False
    ).count()
    print(f"  Items linked by item_code: {linked_by_code}")
    print(f"  Items linked by drug: {linked_by_drug}")
    print()
    
    return True

if __name__ == '__main__':
    ensure_complete_sync()
