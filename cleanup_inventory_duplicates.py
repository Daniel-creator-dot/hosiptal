#!/usr/bin/env python
"""
Script to identify and merge duplicate inventory items
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db.models import Q, Count, Sum, F
from django.db import transaction
from hospital.models_procurement import InventoryItem, Store
from collections import defaultdict

def normalize_name(name):
    """Normalize item name for comparison"""
    if not name:
        return ""
    # Remove extra spaces, convert to lowercase
    name = " ".join(name.split()).lower().strip()
    # Remove common variations
    name = name.replace("'", "").replace('"', '').replace('-', ' ').replace('_', ' ')
    return name

def find_duplicates(dry_run=True):
    """Find duplicate inventory items"""
    print("=" * 70)
    print("INVENTORY DUPLICATE DETECTION AND CLEANUP")
    print("=" * 70)
    print()
    
    if dry_run:
        print("[DRY RUN MODE - No changes will be made]")
    else:
        print("[LIVE MODE - Changes will be saved]")
    print()
    
    # Get all active, non-deleted items
    all_items = InventoryItem.objects.filter(
        is_deleted=False
    ).select_related('store', 'category', 'drug').order_by('store', 'item_name')
    
    print(f"Total items to check: {all_items.count()}")
    print()
    
    # Group by store and normalized name
    duplicates_by_store = defaultdict(list)
    
    for item in all_items:
        normalized = normalize_name(item.item_name)
        key = (item.store_id, normalized)
        duplicates_by_store[key].append(item)
    
    # Find groups with more than one item
    duplicate_groups = {k: v for k, v in duplicates_by_store.items() if len(v) > 1}
    
    print(f"Found {len(duplicate_groups)} duplicate groups")
    print()
    
    total_duplicates = 0
    total_merged = 0
    merged_items = []
    
    for (store_id, normalized_name), items in duplicate_groups.items():
        store = items[0].store
        print(f"\n{'='*70}")
        print(f"Store: {store.name}")
        print(f"Item Name (normalized): {normalized_name}")
        print(f"Duplicate Count: {len(items)}")
        print(f"{'='*70}")
        
        # Sort by creation date (keep oldest) and quantity (keep one with most stock)
        items_sorted = sorted(items, key=lambda x: (x.created, -x.quantity_on_hand))
        keep_item = items_sorted[0]
        duplicates = items_sorted[1:]
        
        print(f"\nKEEPING (oldest, highest quantity):")
        print(f"  - ID: {keep_item.id}")
        print(f"  - Name: {keep_item.item_name}")
        print(f"  - Code: {keep_item.item_code}")
        print(f"  - Quantity: {keep_item.quantity_on_hand}")
        print(f"  - Cost: GHS {keep_item.unit_cost}")
        print(f"  - Created: {keep_item.created}")
        
        total_quantity = keep_item.quantity_on_hand
        total_value = keep_item.quantity_on_hand * keep_item.unit_cost
        
        for dup in duplicates:
            total_duplicates += 1
            print(f"\nDUPLICATE TO MERGE:")
            print(f"  - ID: {dup.id}")
            print(f"  - Name: {dup.item_name}")
            print(f"  - Code: {dup.item_code}")
            print(f"  - Quantity: {dup.quantity_on_hand}")
            print(f"  - Cost: GHS {dup.unit_cost}")
            print(f"  - Created: {dup.created}")
            
            # Calculate weighted average cost
            if dup.quantity_on_hand > 0:
                total_value += dup.quantity_on_hand * dup.unit_cost
                total_quantity += dup.quantity_on_hand
        
        # Calculate new weighted average cost
        if total_quantity > 0:
            new_cost = total_value / total_quantity
        else:
            new_cost = keep_item.unit_cost
        
        print(f"\nMERGED RESULT:")
        print(f"  - Total Quantity: {total_quantity}")
        print(f"  - Weighted Avg Cost: GHS {new_cost:.2f}")
        
        if not dry_run:
            try:
                with transaction.atomic():
                    # Update keep item with merged data
                    keep_item.quantity_on_hand = total_quantity
                    keep_item.unit_cost = new_cost
                    
                    # Use best category if available
                    if not keep_item.category:
                        for dup in duplicates:
                            if dup.category:
                                keep_item.category = dup.category
                                break
                    
                    # Use best description if available
                    if not keep_item.description:
                        for dup in duplicates:
                            if dup.description:
                                keep_item.description = dup.description
                                break
                    
                    # Use best supplier if available
                    if not keep_item.preferred_supplier:
                        for dup in duplicates:
                            if dup.preferred_supplier:
                                keep_item.preferred_supplier = dup.preferred_supplier
                                break
                    
                    # Use best drug link if available
                    if not keep_item.drug:
                        for dup in duplicates:
                            if dup.drug:
                                keep_item.drug = dup.drug
                                break
                    
                    keep_item.save()
                    
                    # Soft delete duplicates
                    for dup in duplicates:
                        dup.is_deleted = True
                        dup.is_active = False
                        dup.save()
                        merged_items.append(dup.id)
                    
                    total_merged += len(duplicates)
                    print(f"  [OK] Merged {len(duplicates)} duplicates into item {keep_item.id}")
            except Exception as e:
                print(f"  [ERROR] Failed to merge: {e}")
        else:
            print(f"  [DRY RUN] Would merge {len(duplicates)} duplicates")
    
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total duplicate groups: {len(duplicate_groups)}")
    print(f"Total duplicate items: {total_duplicates}")
    if not dry_run:
        print(f"Total items merged: {total_merged}")
        print(f"Merged item IDs: {merged_items[:20]}{'...' if len(merged_items) > 20 else ''}")
    print()
    
    return len(duplicate_groups), total_duplicates

if __name__ == '__main__':
    import sys
    
    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] == '--execute':
        dry_run = False
        print("\n⚠️  WARNING: This will permanently merge duplicate items!")
        response = input("Type 'YES' to continue: ")
        if response != 'YES':
            print("Aborted.")
            sys.exit(0)
    
    find_duplicates(dry_run=dry_run)
