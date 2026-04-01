"""
Inventory & Stores Manager Dashboard
Streamlined dashboard for inventory and stores management
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, F, Count
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

try:
    from .models_procurement import Store, InventoryItem, StoreTransfer, Supplier
    from .models_inventory_advanced import InventoryTransaction, InventoryBatch, StockAlert, InventoryRequisition
except ImportError as e:
    logger.warning(f"Inventory models not available: {e}")
    Store = InventoryItem = StoreTransfer = Supplier = None
    InventoryTransaction = InventoryBatch = StockAlert = InventoryRequisition = None


@login_required
def inventory_stores_manager_dashboard(request):
    """
    Streamlined Dashboard for Inventory & Stores Manager
    Focuses on key metrics and actionable items
    """
    if not Store:
        return render(request, 'hospital/inventory_stores_manager/dashboard.html', {
            'error': 'Inventory module not available'
        })
    
    # Get all active stores
    all_stores = Store.objects.filter(is_deleted=False, is_active=True)
    
    # ===== KEY METRICS =====
    
    # Total inventory value across all stores
    total_inventory_value = InventoryItem.objects.filter(
        store__in=all_stores,
        is_deleted=False
    ).aggregate(
        total=Sum(F('quantity_on_hand') * F('unit_cost'))
    )['total'] or Decimal('0.00')
    
    # Total items count
    total_items = InventoryItem.objects.filter(
        store__in=all_stores,
        is_deleted=False
    ).aggregate(total=Sum('quantity_on_hand'))['total'] or 0
    
    # Total SKUs
    total_skus = InventoryItem.objects.filter(
        store__in=all_stores,
        is_deleted=False
    ).count()
    
    # Number of stores
    total_stores = all_stores.count()
    
    # ===== CRITICAL ALERTS =====
    
    # Low stock items (at or below reorder level)
    low_stock_count = InventoryItem.objects.filter(
        store__in=all_stores,
        is_deleted=False,
        is_active=True,
        reorder_level__gt=0
    ).filter(
        Q(quantity_on_hand__lte=F('reorder_level'))
    ).count()
    
    # Out of stock items
    out_of_stock_count = InventoryItem.objects.filter(
        store__in=all_stores,
        is_deleted=False,
        is_active=True,
        quantity_on_hand=0
    ).count()
    
    # Critical stock alerts
    critical_alerts = StockAlert.objects.filter(
        store__in=all_stores,
        severity='critical',
        is_resolved=False,
        is_deleted=False
    ).count() if StockAlert else 0
    
    # High priority alerts
    high_alerts = StockAlert.objects.filter(
        store__in=all_stores,
        severity='high',
        is_resolved=False,
        is_deleted=False
    ).count() if StockAlert else 0
    
    # Total active alerts
    total_alerts = StockAlert.objects.filter(
        store__in=all_stores,
        is_resolved=False,
        is_deleted=False
    ).count() if StockAlert else 0
    
    # ===== PENDING ACTIONS =====
    
    # Pending requisitions
    pending_requisitions = InventoryRequisition.objects.filter(
        requested_from_store__in=all_stores,
        status__in=['submitted', 'approved'],
        is_deleted=False
    ).count() if InventoryRequisition else 0
    
    # Pending transfers (incoming)
    pending_transfers_in = StoreTransfer.objects.filter(
        to_store__in=all_stores,
        status__in=['pending', 'approved', 'in_transit'],
        is_deleted=False
    ).count()
    
    # Pending transfers (outgoing)
    pending_transfers_out = StoreTransfer.objects.filter(
        from_store__in=all_stores,
        status__in=['pending', 'approved', 'in_transit'],
        is_deleted=False
    ).count()
    
    # ===== EXPIRY TRACKING =====
    
    # Expiring soon (next 30 days)
    expiring_soon_count = InventoryBatch.objects.filter(
        store__in=all_stores,
        is_deleted=False,
        is_expired=False,
        expiry_date__isnull=False,
        expiry_date__lte=date.today() + timedelta(days=30),
        expiry_date__gte=date.today()
    ).count() if InventoryBatch else 0
    
    # Already expired
    expired_count = InventoryBatch.objects.filter(
        store__in=all_stores,
        is_deleted=False,
        expiry_date__lt=date.today()
    ).count() if InventoryBatch else 0
    
    # ===== RECENT ACTIVITY =====
    
    # Recent transactions (last 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    recent_transactions = InventoryTransaction.objects.filter(
        store__in=all_stores,
        transaction_date__gte=seven_days_ago,
        is_deleted=False
    ).count() if InventoryTransaction else 0
    
    # ===== STORE BREAKDOWN =====
    
    stores_summary = []
    for store in all_stores[:10]:  # Top 10 stores
        item_count = InventoryItem.objects.filter(
            store=store,
            is_deleted=False
        ).count()
        
        store_value = InventoryItem.objects.filter(
            store=store,
            is_deleted=False
        ).aggregate(
            total=Sum(F('quantity_on_hand') * F('unit_cost'))
        )['total'] or Decimal('0.00')
        
        low_stock = InventoryItem.objects.filter(
            store=store,
            is_deleted=False,
            is_active=True,
            reorder_level__gt=0
        ).filter(
            Q(quantity_on_hand__lte=F('reorder_level'))
        ).count()
        
        stores_summary.append({
            'store': store,
            'item_count': item_count,
            'total_value': store_value,
            'low_stock_count': low_stock,
        })
    
    # ===== TOP LOW STOCK ITEMS =====
    
    top_low_stock = InventoryItem.objects.filter(
        store__in=all_stores,
        is_deleted=False,
        is_active=True,
        reorder_level__gt=0
    ).filter(
        Q(quantity_on_hand__lte=F('reorder_level'))
    ).select_related('store', 'category').order_by('quantity_on_hand')[:10]
    
    # ===== RECENT ALERTS =====
    
    recent_alerts = StockAlert.objects.filter(
        store__in=all_stores,
        is_resolved=False,
        is_deleted=False
    ).select_related('store', 'inventory_item').order_by('-created')[:10] if StockAlert else []
    
    # ===== PENDING REQUISITIONS =====
    
    pending_requisitions_list = InventoryRequisition.objects.filter(
        requested_from_store__in=all_stores,
        status__in=['submitted', 'approved'],
        is_deleted=False
    ).select_related('requested_from_store', 'requested_by').order_by('-created')[:10] if InventoryRequisition else []
    
    # ===== PENDING TRANSFERS =====
    
    pending_transfers = StoreTransfer.objects.filter(
        Q(from_store__in=all_stores) | Q(to_store__in=all_stores),
        status__in=['pending', 'approved', 'in_transit'],
        is_deleted=False
    ).select_related('from_store', 'to_store', 'requested_by').order_by('-created')[:10]
    
    context = {
        'total_inventory_value': total_inventory_value,
        'total_items': total_items,
        'total_skus': total_skus,
        'total_stores': total_stores,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'critical_alerts': critical_alerts,
        'high_alerts': high_alerts,
        'total_alerts': total_alerts,
        'pending_requisitions': pending_requisitions,
        'pending_transfers_in': pending_transfers_in,
        'pending_transfers_out': pending_transfers_out,
        'expiring_soon_count': expiring_soon_count,
        'expired_count': expired_count,
        'recent_transactions': recent_transactions,
        'stores_summary': stores_summary,
        'top_low_stock': top_low_stock,
        'recent_alerts': recent_alerts,
        'pending_requisitions_list': pending_requisitions_list,
        'pending_transfers': pending_transfers,
    }
    
    return render(request, 'hospital/inventory_stores_manager/dashboard.html', context)





