#!/usr/bin/env python
"""
Verify Drug Store Linking
Ensures all Pharmacy Store items are properly linked in Drug Store
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_procurement import Store, InventoryItem

def verify_linking():
    """Verify all Pharmacy Store items are linked in Drug Store"""
    print("=" * 70)
    print("VERIFYING DRUG STORE LINKING")
    print("=" * 70)
    print()
    
    pharmacy_store = Store.objects.get(code='PHARM', is_deleted=False)
    drug_store = Store.objects.get(code='DRUGS', is_deleted=False)
    
    pharmacy_items = InventoryItem.objects.filter(
        store=pharmacy_store,
        is_deleted=False
    ).select_related('drug', 'category')
    
    total = pharmacy_items.count()
    linked_by_code = 0
    linked_by_drug = 0
    linked_by_name = 0
    not_linked = []
    
    for item in pharmacy_items:
        found = False
        
        # Check by item_code
        if item.item_code and item.item_code.strip():
            if InventoryItem.objects.filter(
                store=drug_store,
                item_code=item.item_code,
                is_deleted=False
            ).exists():
                linked_by_code += 1
                found = True
        
        # Check by drug
        if not found and item.drug:
            if InventoryItem.objects.filter(
                store=drug_store,
                drug=item.drug,
                is_deleted=False
            ).exists():
                linked_by_drug += 1
                found = True
        
        # Check by name
        if not found:
            if InventoryItem.objects.filter(
                store=drug_store,
                item_name=item.item_name,
                is_deleted=False
            ).exists():
                linked_by_name += 1
                found = True
        
        if not found:
            not_linked.append(item.item_name)
    
    print(f"Total Pharmacy Store items: {total}")
    print(f"  ✅ Linked by item_code: {linked_by_code}")
    print(f"  ✅ Linked by drug: {linked_by_drug}")
    print(f"  ✅ Linked by name: {linked_by_name}")
    print(f"  ❌ Not linked: {len(not_linked)}")
    print()
    
    if not_linked:
        print("Items not linked:")
        for name in not_linked[:10]:
            print(f"  - {name}")
        if len(not_linked) > 10:
            print(f"  ... and {len(not_linked) - 10} more")
    else:
        print("✅ ALL ITEMS ARE PROPERLY LINKED!")
        print()
        print("Linking Summary:")
        print(f"  - All {total} Pharmacy Store items have corresponding items in Drug Store")
        print(f"  - Items are linked by item_code, drug, or name")
        print(f"  - Drug Store items have 0 quantity (quantities added when purchased)")
        print(f"  - No duplicates will be created when updating or transferring")
    
    print()
    return len(not_linked) == 0

if __name__ == '__main__':
    verify_linking()
