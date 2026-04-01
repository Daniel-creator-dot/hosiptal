"""
Inventory Monitoring Utilities
Provides low stock alerts and transfer suggestions
"""
from django.db.models import Q, F
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def get_low_stock_items(store, threshold_percentage=0.2):
    """
    Get items in a store that are below reorder level or at low stock
    threshold_percentage: Percentage of reorder_level to consider as "low"
    """
    from .models_procurement import InventoryItem
    
    low_stock_items = InventoryItem.objects.filter(
        store=store,
        is_active=True,
        is_deleted=False
    ).filter(
        Q(quantity_on_hand__lte=F('reorder_level')) |
        Q(quantity_on_hand__lte=F('reorder_level') * threshold_percentage)
    ).select_related('category', 'drug', 'preferred_supplier')
    
    return low_stock_items


def get_finished_stock_items(store):
    """Get items in a store that are completely out of stock"""
    from .models_procurement import InventoryItem
    
    finished_items = InventoryItem.objects.filter(
        store=store,
        quantity_on_hand=0,
        is_active=True,
        is_deleted=False
    ).select_related('category', 'drug', 'preferred_supplier')
    
    return finished_items


def suggest_transfers_from_drug_store(pharmacy_store):
    """
    Suggest transfers from Drug Store (DRUGS) to Pharmacy Store (PHARM)
    for items that are low or finished in Pharmacy Store
    """
    from .models_procurement import Store, InventoryItem
    
    # Get Drug Store
    drug_store = Store.objects.filter(code='DRUGS', is_deleted=False).first()
    if not drug_store:
        return []
    
    # Get low/finished items in Pharmacy Store
    low_stock_items = get_low_stock_items(pharmacy_store)
    finished_items = get_finished_stock_items(pharmacy_store)
    
    suggestions = []
    
    for item in low_stock_items:
        # Find corresponding item in Drug Store
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
        
        drug_store_item = InventoryItem.objects.filter(**lookup_kwargs).first()
        
        if drug_store_item and drug_store_item.quantity_on_hand > 0:
            # Calculate suggested transfer quantity
            # Transfer enough to bring pharmacy stock to reorder_quantity level
            current_qty = item.quantity_on_hand
            target_qty = item.reorder_quantity if item.reorder_quantity > 0 else item.reorder_level * 2
            suggested_qty = min(
                target_qty - current_qty,
                drug_store_item.quantity_on_hand
            )
            
            if suggested_qty > 0:
                suggestions.append({
                    'pharmacy_item': item,
                    'drug_store_item': drug_store_item,
                    'suggested_quantity': suggested_qty,
                    'current_pharmacy_qty': current_qty,
                    'available_in_drug_store': drug_store_item.quantity_on_hand,
                    'priority': 'high' if current_qty == 0 else 'medium',
                    'reason': 'Out of stock' if current_qty == 0 else f'Low stock (below reorder level: {item.reorder_level})'
                })
    
    # Also check finished items
    for item in finished_items:
        # Skip if already in suggestions
        if any(s['pharmacy_item'].id == item.id for s in suggestions):
            continue
        
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
        
        drug_store_item = InventoryItem.objects.filter(**lookup_kwargs).first()
        
        if drug_store_item and drug_store_item.quantity_on_hand > 0:
            suggested_qty = min(
                item.reorder_quantity if item.reorder_quantity > 0 else item.reorder_level * 2,
                drug_store_item.quantity_on_hand
            )
            
            if suggested_qty > 0:
                suggestions.append({
                    'pharmacy_item': item,
                    'drug_store_item': drug_store_item,
                    'suggested_quantity': suggested_qty,
                    'current_pharmacy_qty': 0,
                    'available_in_drug_store': drug_store_item.quantity_on_hand,
                    'priority': 'critical',
                    'reason': 'Out of stock - urgent transfer needed'
                })
    
    # Sort by priority (critical > high > medium)
    priority_order = {'critical': 0, 'high': 1, 'medium': 2}
    suggestions.sort(key=lambda x: priority_order.get(x['priority'], 3))
    
    return suggestions


def get_transfer_suggestions_summary(pharmacy_store):
    """
    Get a summary of transfer suggestions for the pharmacy store
    Returns counts and total value
    """
    suggestions = suggest_transfers_from_drug_store(pharmacy_store)
    
    critical_count = sum(1 for s in suggestions if s['priority'] == 'critical')
    high_count = sum(1 for s in suggestions if s['priority'] == 'high')
    medium_count = sum(1 for s in suggestions if s['priority'] == 'medium')
    
    total_value = sum(
        s['suggested_quantity'] * s['drug_store_item'].unit_cost
        for s in suggestions
    )
    
    return {
        'total_suggestions': len(suggestions),
        'critical_count': critical_count,
        'high_count': high_count,
        'medium_count': medium_count,
        'total_value': Decimal(str(total_value)),
        'suggestions': suggestions
    }
