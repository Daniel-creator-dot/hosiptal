"""
Inventory Duplicate Detection and Management Views
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.http import JsonResponse
from .models_procurement import InventoryItem, Store
from .utils_roles import is_procurement_staff
from django.contrib.auth.decorators import user_passes_test


def normalize_name(name):
    """Normalize item name for comparison"""
    if not name:
        return ""
    return " ".join(name.split()).lower().strip()


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def inventory_duplicates_view(request):
    """View to identify and manage duplicate inventory items"""
    from collections import defaultdict
    
    # Get all active, non-deleted items
    all_items = InventoryItem.objects.filter(
        is_deleted=False
    ).select_related('store', 'category').order_by('store', 'item_name')
    
    # Group by store and normalized name
    duplicates_by_store = defaultdict(list)
    
    for item in all_items:
        normalized = normalize_name(item.item_name)
        key = (item.store_id, normalized, item.store.name if item.store else 'Unknown')
        duplicates_by_store[key].append(item)
    
    # Find groups with more than one item
    duplicate_groups = []
    for (store_id, normalized_name, store_name), items in duplicates_by_store.items():
        if len(items) > 1:
            # Calculate total quantity and value
            total_qty = sum(item.quantity_on_hand for item in items)
            total_value = sum(item.quantity_on_hand * item.unit_cost for item in items)
            avg_cost = total_value / total_qty if total_qty > 0 else 0
            
            duplicate_groups.append({
                'store_id': store_id,
                'store_name': store_name,
                'normalized_name': normalized_name,
                'items': sorted(items, key=lambda x: (x.created, -x.quantity_on_hand)),
                'count': len(items),
                'total_quantity': total_qty,
                'total_value': total_value,
                'avg_cost': avg_cost,
            })
    
    # Sort by count (most duplicates first)
    duplicate_groups.sort(key=lambda x: x['count'], reverse=True)
    
    context = {
        'duplicate_groups': duplicate_groups,
        'total_duplicates': sum(len(g['items']) - 1 for g in duplicate_groups),
        'total_groups': len(duplicate_groups),
    }
    
    return render(request, 'hospital/inventory_duplicates.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def merge_duplicates(request):
    """Merge duplicate inventory items"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=400)
    
    from django.db import transaction
    import json
    
    try:
        data = json.loads(request.body)
        keep_id = data.get('keep_id')
        merge_ids = data.get('merge_ids', [])
        
        if not keep_id or not merge_ids:
            return JsonResponse({'error': 'keep_id and merge_ids required'}, status=400)
        
        keep_item = InventoryItem.objects.get(pk=keep_id, is_deleted=False)
        merge_items = InventoryItem.objects.filter(
            pk__in=merge_ids,
            is_deleted=False
        ).exclude(pk=keep_id)
        
        if not merge_items.exists():
            return JsonResponse({'error': 'No items to merge'}, status=400)
        
        with transaction.atomic():
            # Calculate merged quantities and weighted average cost
            total_qty = keep_item.quantity_on_hand
            total_value = keep_item.quantity_on_hand * keep_item.unit_cost
            
            for item in merge_items:
                total_qty += item.quantity_on_hand
                total_value += item.quantity_on_hand * item.unit_cost
                
                # Merge metadata if keep item doesn't have it
                if not keep_item.category and item.category:
                    keep_item.category = item.category
                if not keep_item.description and item.description:
                    keep_item.description = item.description
                if not keep_item.preferred_supplier and item.preferred_supplier:
                    keep_item.preferred_supplier = item.preferred_supplier
                if not keep_item.drug and item.drug:
                    keep_item.drug = item.drug
            
            # Calculate weighted average cost
            if total_qty > 0:
                keep_item.quantity_on_hand = total_qty
                keep_item.unit_cost = total_value / total_qty
            
            keep_item.save()
            
            # Soft delete merged items
            merged_count = merge_items.update(is_deleted=True, is_active=False)
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully merged {merged_count} items into {keep_item.item_name}',
                'merged_count': merged_count,
                'new_quantity': total_qty,
                'new_cost': float(keep_item.unit_cost),
            })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
