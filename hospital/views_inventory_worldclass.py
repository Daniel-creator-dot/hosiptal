"""
World-Class Inventory Management Views
State-of-the-art supply chain management with complete accountability
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, F, Q, Avg
from django.utils import timezone
from django.http import JsonResponse
from decimal import Decimal
from datetime import date, timedelta

from .models_procurement import Store, InventoryItem, InventoryCategory, StoreTransfer, StoreTransferLine
from .models_inventory_advanced import (
    InventoryTransaction, InventoryBatch, StockAlert, InventoryCount,
    InventoryCountLine, InventoryRequisition, InventoryRequisitionLine
)
from .models import Staff, Department


# ==================== MAIN INVENTORY DASHBOARD ====================

@login_required
def inventory_dashboard(request):
    """
    World-Class Inventory Dashboard
    Real-time analytics, alerts, and comprehensive overview
    """
    # Get filter parameters
    store_id = request.GET.get('store')
    if store_id:
        selected_store = get_object_or_404(Store, id=store_id, is_deleted=False)
        stores_filter = [selected_store]
    else:
        stores_filter = Store.objects.filter(is_deleted=False, is_active=True)
        selected_store = None
    
    # ===== KEY METRICS =====
    
    # Total inventory value
    total_inventory_value = InventoryItem.objects.filter(
        store__in=stores_filter,
        is_deleted=False
    ).aggregate(
        total=Sum(F('quantity_on_hand') * F('unit_cost'))
    )['total'] or Decimal('0.00')
    
    # Total items and SKUs
    total_items = InventoryItem.objects.filter(
        store__in=stores_filter,
        is_deleted=False
    ).aggregate(total=Sum('quantity_on_hand'))['total'] or 0
    
    total_skus = InventoryItem.objects.filter(
        store__in=stores_filter,
        is_deleted=False
    ).count()
    
    # Low stock items
    low_stock_count = InventoryItem.objects.filter(
        store__in=stores_filter,
        is_deleted=False,
        is_active=True
    ).filter(
        Q(quantity_on_hand__lte=F('reorder_level')) & Q(reorder_level__gt=0)
    ).count()
    
    # Out of stock items
    out_of_stock_count = InventoryItem.objects.filter(
        store__in=stores_filter,
        is_deleted=False,
        is_active=True,
        quantity_on_hand=0
    ).count()
    
    # ===== ALERTS & WARNINGS =====
    
    # Active stock alerts
    critical_alerts = StockAlert.objects.filter(
        store__in=stores_filter,
        severity='critical',
        is_resolved=False,
        is_deleted=False
    ).count()
    
    high_alerts = StockAlert.objects.filter(
        store__in=stores_filter,
        severity='high',
        is_resolved=False,
        is_deleted=False
    ).count()
    
    total_alerts = StockAlert.objects.filter(
        store__in=stores_filter,
        is_resolved=False,
        is_deleted=False
    ).count()
    
    # Expiring soon (next 30 days)
    expiring_soon_count = InventoryBatch.objects.filter(
        store__in=stores_filter,
        is_deleted=False,
        is_expired=False,
        expiry_date__isnull=False,
        expiry_date__lte=date.today() + timedelta(days=30),
        expiry_date__gte=date.today()
    ).count()
    
    # Already expired
    expired_count = InventoryBatch.objects.filter(
        store__in=stores_filter,
        is_deleted=False,
        expiry_date__lt=date.today()
    ).count()
    
    # ===== RECENT ACTIVITY =====
    
    # Recent transactions (last 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    recent_transactions = InventoryTransaction.objects.filter(
        store__in=stores_filter,
        transaction_date__gte=seven_days_ago,
        is_deleted=False
    ).count()
    
    # Pending requisitions
    pending_requisitions = InventoryRequisition.objects.filter(
        requested_from_store__in=stores_filter,
        status__in=['submitted', 'approved'],
        is_deleted=False
    ).count()
    
    # Pending transfers
    pending_transfers_in = StoreTransfer.objects.filter(
        to_store__in=stores_filter,
        status__in=['pending', 'approved', 'in_transit'],
        is_deleted=False
    ).count()
    
    pending_transfers_out = StoreTransfer.objects.filter(
        from_store__in=stores_filter,
        status__in=['pending', 'approved', 'in_transit'],
        is_deleted=False
    ).count()
    
    # ===== INVENTORY BY CATEGORY =====
    
    inventory_by_category = InventoryItem.objects.filter(
        store__in=stores_filter,
        is_deleted=False,
        category__isnull=False
    ).values(
        'category__name',
        'category__id'
    ).annotate(
        total_items=Sum('quantity_on_hand'),
        total_value=Sum(F('quantity_on_hand') * F('unit_cost')),
        item_count=Count('id')
    ).order_by('-total_value')[:10]
    
    # ===== TOP 10 ITEMS BY VALUE =====
    
    top_items_by_value = InventoryItem.objects.filter(
        store__in=stores_filter,
        is_deleted=False
    ).annotate(
        total_value=F('quantity_on_hand') * F('unit_cost')
    ).order_by('-total_value')[:10]
    
    # ===== RECENT ALERTS =====
    
    recent_alerts = StockAlert.objects.filter(
        store__in=stores_filter,
        is_resolved=False,
        is_deleted=False
    ).select_related(
        'inventory_item',
        'store'
    ).order_by('-created')[:10]
    
    # ===== STORES LIST =====
    
    all_stores = Store.objects.filter(is_deleted=False, is_active=True).order_by('name')
    
    # ===== TURNOVER RATE (Last 30 days) =====
    
    thirty_days_ago = timezone.now() - timedelta(days=30)
    total_issues = InventoryTransaction.objects.filter(
        store__in=stores_filter,
        transaction_type='issue',
        transaction_date__gte=thirty_days_ago,
        is_deleted=False
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    # Calculate turnover rate
    if total_items > 0:
        turnover_rate = (total_issues / total_items) * 100
    else:
        turnover_rate = 0
    
    context = {
        'all_stores': all_stores,
        'selected_store': selected_store,
        'total_inventory_value': total_inventory_value,
        'total_items': total_items,
        'total_skus': total_skus,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'critical_alerts': critical_alerts,
        'high_alerts': high_alerts,
        'total_alerts': total_alerts,
        'expiring_soon_count': expiring_soon_count,
        'expired_count': expired_count,
        'recent_transactions': recent_transactions,
        'pending_requisitions': pending_requisitions,
        'pending_transfers_in': pending_transfers_in,
        'pending_transfers_out': pending_transfers_out,
        'inventory_by_category': inventory_by_category,
        'top_items_by_value': top_items_by_value,
        'recent_alerts': recent_alerts,
        'turnover_rate': round(turnover_rate, 2),
    }
    
    return render(request, 'hospital/inventory/dashboard.html', context)


# ==================== INVENTORY ITEMS MANAGEMENT ====================

@login_required
def inventory_items_list(request):
    """List all inventory items with advanced filtering"""
    store_id = request.GET.get('store')
    category_id = request.GET.get('category')
    status = request.GET.get('status', 'all')  # all, low_stock, out_of_stock, normal
    search = request.GET.get('search', '')
    
    # Base query
    items = InventoryItem.objects.filter(is_deleted=False).select_related(
        'store', 'category', 'preferred_supplier'
    )
    
    # Apply filters
    if store_id:
        items = items.filter(store_id=store_id)
    
    if category_id:
        items = items.filter(category_id=category_id)
    
    if search:
        items = items.filter(
            Q(item_name__icontains=search) |
            Q(item_code__icontains=search) |
            Q(description__icontains=search)
        )
    
    # Status filters
    if status == 'low_stock':
        items = items.filter(
            Q(quantity_on_hand__lte=F('reorder_level')) & Q(reorder_level__gt=0)
        )
    elif status == 'out_of_stock':
        items = items.filter(quantity_on_hand=0)
    elif status == 'normal':
        items = items.filter(quantity_on_hand__gt=F('reorder_level'))
    
    # Annotate with total value
    items = items.annotate(
        total_value=F('quantity_on_hand') * F('unit_cost')
    ).order_by('item_name')
    
    # Get filter options
    stores = Store.objects.filter(is_deleted=False, is_active=True)
    categories = InventoryCategory.objects.filter(is_deleted=False, is_active=True)
    
    context = {
        'items': items[:200],  # Limit for performance
        'stores': stores,
        'categories': categories,
        'selected_store': store_id,
        'selected_category': category_id,
        'selected_status': status,
        'search_query': search,
    }
    
    return render(request, 'hospital/inventory/items_list.html', context)


@login_required
def inventory_item_detail(request, item_id):
    """Detailed view of inventory item with transaction history"""
    item = get_object_or_404(
        InventoryItem.objects.select_related('store', 'category', 'preferred_supplier'),
        id=item_id,
        is_deleted=False
    )
    
    # Get transaction history
    transactions = InventoryTransaction.objects.filter(
        inventory_item=item,
        is_deleted=False
    ).select_related('performed_by', 'approved_by').order_by('-transaction_date')[:50]
    
    # Get batches
    batches = InventoryBatch.objects.filter(
        inventory_item=item,
        is_deleted=False,
        quantity_remaining__gt=0
    ).order_by('expiry_date')
    
    # Get active alerts
    alerts = StockAlert.objects.filter(
        inventory_item=item,
        is_resolved=False,
        is_deleted=False
    ).order_by('-created')
    
    # Calculate statistics
    thirty_days_ago = timezone.now() - timedelta(days=30)
    usage_last_30_days = InventoryTransaction.objects.filter(
        inventory_item=item,
        transaction_type='issue',
        transaction_date__gte=thirty_days_ago,
        is_deleted=False
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    # Average daily usage
    avg_daily_usage = usage_last_30_days / 30 if usage_last_30_days > 0 else 0
    
    # Days of stock remaining
    if avg_daily_usage > 0:
        days_of_stock = item.quantity_on_hand / avg_daily_usage
    else:
        days_of_stock = None
    
    context = {
        'item': item,
        'transactions': transactions,
        'batches': batches,
        'alerts': alerts,
        'usage_last_30_days': abs(usage_last_30_days),
        'avg_daily_usage': round(avg_daily_usage, 2),
        'days_of_stock': round(days_of_stock, 1) if days_of_stock else None,
        'total_value': item.get_total_value(),
    }
    
    return render(request, 'hospital/inventory/item_detail.html', context)


# ==================== STOCK ALERTS ====================

@login_required
def stock_alerts_list(request):
    """View and manage stock alerts"""
    severity = request.GET.get('severity', 'all')
    alert_type = request.GET.get('type', 'all')
    store_id = request.GET.get('store')
    
    # Base query
    alerts = StockAlert.objects.filter(
        is_resolved=False,
        is_deleted=False
    ).select_related('inventory_item', 'store', 'batch')
    
    # Apply filters
    if severity != 'all':
        alerts = alerts.filter(severity=severity)
    
    if alert_type != 'all':
        alerts = alerts.filter(alert_type=alert_type)
    
    if store_id:
        alerts = alerts.filter(store_id=store_id)
    
    alerts = alerts.order_by('-created')
    
    # Get filter options
    stores = Store.objects.filter(is_deleted=False, is_active=True)
    
    context = {
        'alerts': alerts,
        'stores': stores,
        'selected_severity': severity,
        'selected_type': alert_type,
        'selected_store': store_id,
    }
    
    return render(request, 'hospital/inventory/alerts_list.html', context)


@login_required
def acknowledge_alert(request, alert_id):
    """Acknowledge a stock alert"""
    alert = get_object_or_404(StockAlert, id=alert_id, is_deleted=False)
    
    if request.method == 'POST':
        if hasattr(request.user, 'staff'):
            alert.acknowledge(request.user.staff)
            messages.success(request, f'Alert acknowledged successfully.')
        else:
            messages.error(request, 'Only staff members can acknowledge alerts.')
        
        return redirect('hospital:stock_alerts_list')
    
    return redirect('hospital:stock_alerts_list')


@login_required
def resolve_alert(request, alert_id):
    """Resolve a stock alert"""
    alert = get_object_or_404(StockAlert, id=alert_id, is_deleted=False)
    
    if request.method == 'POST':
        notes = request.POST.get('resolution_notes', '')
        
        if hasattr(request.user, 'staff'):
            alert.resolve(request.user.staff, notes)
            messages.success(request, f'Alert resolved successfully.')
        else:
            messages.error(request, 'Only staff members can resolve alerts.')
        
        return redirect('hospital:stock_alerts_list')
    
    context = {'alert': alert}
    return render(request, 'hospital/inventory/resolve_alert.html', context)


# ==================== INVENTORY REQUISITIONS ====================

@login_required
def requisitions_list(request):
    """List inventory requisitions"""
    status = request.GET.get('status', 'all')
    department_id = request.GET.get('department')
    
    # Base query
    requisitions = InventoryRequisition.objects.filter(
        is_deleted=False
    ).select_related(
        'requesting_department',
        'requested_by',
        'requested_from_store'
    )
    
    # Apply filters
    if status != 'all':
        requisitions = requisitions.filter(status=status)
    
    if department_id:
        requisitions = requisitions.filter(requesting_department_id=department_id)
    
    requisitions = requisitions.order_by('-request_date')
    
    # Get filter options
    departments = Department.objects.filter(is_deleted=False)
    
    context = {
        'requisitions': requisitions,
        'departments': departments,
        'selected_status': status,
        'selected_department': department_id,
    }
    
    return render(request, 'hospital/inventory/requisitions_list.html', context)


@login_required
def create_requisition(request):
    """Create new inventory requisition"""
    if request.method == 'POST':
        try:
            # Create requisition
            requisition = InventoryRequisition.objects.create(
                requesting_department_id=request.POST.get('department'),
                requested_by=request.user.staff if hasattr(request.user, 'staff') else None,
                requested_from_store_id=request.POST.get('store'),
                priority=request.POST.get('priority', 'normal'),
                purpose=request.POST.get('purpose', ''),
                notes=request.POST.get('notes', ''),
                status='draft'
            )
            
            messages.success(request, f'Requisition {requisition.requisition_number} created successfully!')
            return redirect('hospital:requisition_detail', req_id=requisition.id)
        
        except Exception as e:
            messages.error(request, f'Error creating requisition: {e}')
    
    # Get form data
    stores = Store.objects.filter(is_deleted=False, is_active=True)
    departments = Department.objects.filter(is_deleted=False)
    
    context = {
        'stores': stores,
        'departments': departments,
    }
    
    return render(request, 'hospital/inventory/create_requisition.html', context)


@login_required
def requisition_detail(request, req_id):
    """View requisition details"""
    requisition = get_object_or_404(
        InventoryRequisition.objects.select_related(
            'requesting_department',
            'requested_by',
            'requested_from_store',
            'approved_by'
        ),
        id=req_id,
        is_deleted=False
    )
    
    # Get line items
    lines = requisition.lines.filter(is_deleted=False).select_related('inventory_item')
    
    context = {
        'requisition': requisition,
        'lines': lines,
    }
    
    return render(request, 'hospital/inventory/requisition_detail.html', context)


# ==================== INVENTORY ANALYTICS ====================

@login_required
def inventory_analytics(request):
    """Advanced analytics and reports"""
    store_id = request.GET.get('store')
    days = int(request.GET.get('days', 30))
    
    # Filter stores
    if store_id:
        stores_filter = Store.objects.filter(id=store_id, is_deleted=False)
    else:
        stores_filter = Store.objects.filter(is_deleted=False, is_active=True)
    
    # Date range
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    # Transaction analysis
    transactions_by_type = InventoryTransaction.objects.filter(
        store__in=stores_filter,
        transaction_date__gte=start_date,
        is_deleted=False
    ).values('transaction_type').annotate(
        count=Count('id'),
        total_value=Sum('total_value')
    ).order_by('-count')
    
    # Daily transaction trends
    daily_transactions = InventoryTransaction.objects.filter(
        store__in=stores_filter,
        transaction_date__gte=start_date,
        is_deleted=False
    ).extra(
        select={'day': 'date(transaction_date)'}
    ).values('day').annotate(
        count=Count('id'),
        total_value=Sum('total_value')
    ).order_by('day')
    
    # Stock movement velocity (fast/slow moving items)
    fast_moving = InventoryItem.objects.filter(
        store__in=stores_filter,
        is_deleted=False
    ).annotate(
        usage=Count('transactions', filter=Q(
            transactions__transaction_type='issue',
            transactions__transaction_date__gte=start_date
        ))
    ).order_by('-usage')[:10]
    
    slow_moving = InventoryItem.objects.filter(
        store__in=stores_filter,
        is_deleted=False,
        quantity_on_hand__gt=0
    ).annotate(
        usage=Count('transactions', filter=Q(
            transactions__transaction_type='issue',
            transactions__transaction_date__gte=start_date
        ))
    ).filter(usage__lte=2).order_by('usage')[:10]
    
    # Get all stores for filter
    all_stores = Store.objects.filter(is_deleted=False, is_active=True)
    
    context = {
        'all_stores': all_stores,
        'selected_store': store_id,
        'days': days,
        'transactions_by_type': transactions_by_type,
        'daily_transactions': daily_transactions,
        'fast_moving': fast_moving,
        'slow_moving': slow_moving,
    }
    
    return render(request, 'hospital/inventory/analytics.html', context)


# ==================== TRANSFER MANAGEMENT ====================

@login_required
def transfers_list(request):
    """List store transfers"""
    status = request.GET.get('status', 'all')
    store_id = request.GET.get('store')
    
    # Base query
    transfers = StoreTransfer.objects.filter(is_deleted=False).select_related(
        'from_store', 'to_store', 'requested_by'
    )
    
    # Apply filters
    if status != 'all':
        transfers = transfers.filter(status=status)
    
    if store_id:
        transfers = transfers.filter(
            Q(from_store_id=store_id) | Q(to_store_id=store_id)
        )
    
    transfers = transfers.order_by('-transfer_date')
    
    # Get stores for filter
    stores = Store.objects.filter(is_deleted=False, is_active=True)
    
    context = {
        'transfers': transfers,
        'stores': stores,
        'selected_status': status,
        'selected_store': store_id,
    }
    
    return render(request, 'hospital/inventory/transfers_list.html', context)


# ==================== API ENDPOINTS FOR DASHBOARD ====================

@login_required
def inventory_api_stats(request):
    """API endpoint for real-time inventory statistics"""
    store_id = request.GET.get('store')
    
    if store_id:
        stores = Store.objects.filter(id=store_id, is_deleted=False)
    else:
        stores = Store.objects.filter(is_deleted=False, is_active=True)
    
    # Calculate stats
    total_value = InventoryItem.objects.filter(
        store__in=stores,
        is_deleted=False
    ).aggregate(
        total=Sum(F('quantity_on_hand') * F('unit_cost'))
    )['total'] or 0
    
    low_stock = InventoryItem.objects.filter(
        store__in=stores,
        is_deleted=False
    ).filter(
        Q(quantity_on_hand__lte=F('reorder_level')) & Q(reorder_level__gt=0)
    ).count()
    
    alerts_count = StockAlert.objects.filter(
        store__in=stores,
        is_resolved=False,
        is_deleted=False
    ).count()
    
    return JsonResponse({
        'success': True,
        'total_value': float(total_value),
        'low_stock_count': low_stock,
        'alerts_count': alerts_count,
    })







