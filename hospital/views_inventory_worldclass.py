"""
World-Class Inventory Management Views
State-of-the-art supply chain management with complete accountability
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, F, Q, Avg, Min, Max, Value, IntegerField, Case, When, CharField, UUIDField
from django.db.models.functions import Coalesce, NullIf, Trim, Cast, Cast
from django.utils import timezone
from django.http import JsonResponse
from django.urls import reverse
from decimal import Decimal
from datetime import date, timedelta
import json
import uuid

from .models_procurement import Store, InventoryItem, InventoryCategory, StoreTransfer, StoreTransferLine
from .models_inventory_advanced import (
    InventoryTransaction, InventoryBatch, StockAlert, InventoryCount,
    InventoryCountLine, InventoryRequisition, InventoryRequisitionLine
)
from .models import Staff, Department
from .models_procurement import Store
from hospital.utils_pagination import get_pagination_html


# ==================== MAIN INVENTORY DASHBOARD ====================

@login_required
def inventory_dashboard(request):
    """
    World-Class Inventory Dashboard
    Real-time analytics, alerts, and comprehensive overview
    """
    # Get filter parameters
    store_id = request.GET.get('store', '').strip()
    # Normalize - handle "None" string, empty strings, and None
    if store_id in ('None', 'none', '', None):
        store_id = None
        selected_store = None
    elif store_id:
        try:
            # Validate it's a valid UUID before querying
            import uuid
            uuid.UUID(str(store_id))  # Will raise ValueError if invalid
            selected_store = get_object_or_404(Store, id=store_id, is_deleted=False)
        except (ValueError, TypeError):
            # Invalid UUID, ignore filter
            store_id = None
            selected_store = None
    else:
        selected_store = None
    
    if store_id and selected_store:
        stores_filter = [selected_store]
    else:
        stores_filter = Store.objects.filter(is_deleted=False, is_active=True)
        selected_store = None
    
    # ===== KEY METRICS =====
    
    # Total inventory value
    total_inventory_value = InventoryItem.objects.filter(
        store__in=stores_filter,
        is_deleted=False
    ).annotate(
        item_value=F('quantity_on_hand') * F('unit_cost')
    ).aggregate(
        total=Sum('item_value')
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
    ).annotate(
        item_value=F('quantity_on_hand') * F('unit_cost')
    ).values(
        'category__name',
        'category__id'
    ).annotate(
        total_items=Sum('quantity_on_hand'),
        total_value=Sum('item_value'),
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
    store_id = request.GET.get('store', '').strip()
    category_id = request.GET.get('category', '').strip()
    status = request.GET.get('status', 'all')  # all, low_stock, out_of_stock, normal
    search = request.GET.get('search', '').strip()
    group_mode = (request.GET.get('group') or '').strip()  # '1' grouped, '0' per-store
    show_dispensing_hub = request.GET.get('dispensing_hub', '').strip() == '1'  # Show only dispensing hub store
    
    # Normalize filter values - handle "None" string, empty strings, and None
    if category_id in ('None', 'none', '', None):
        category_id = None
    if store_id in ('None', 'none', '', None):
        store_id = None
    
    # Get the active pharmacy store used for dispensing
    active_pharmacy_store = Store.get_pharmacy_store_for_prescriptions()
    
    # If user wants to see dispensing hub, or if no store selected and there's a dispensing hub, default to it
    if show_dispensing_hub and active_pharmacy_store:
        store_id = str(active_pharmacy_store.pk)
    elif not store_id and active_pharmacy_store:
        # Check if user is pharmacist or pharmacy staff - default to dispensing hub
        try:
            staff = Staff.objects.get(user=request.user, is_deleted=False)
            is_pharmacy_staff = staff.profession in ['pharmacist'] or request.user.groups.filter(name__icontains='pharmacy').exists()
            if is_pharmacy_staff:
                # Default to dispensing hub for pharmacy staff
                store_id = str(active_pharmacy_store.pk)
        except:
            pass
    
    # Base query - include drug relationship for search
    # Filter by is_deleted=False and is_active=True (only show active items)
    # Also ensure store and category are active
    items = InventoryItem.objects.filter(
        is_deleted=False,
        is_active=True
    ).filter(
        store__is_deleted=False,
        store__is_active=True
    ).select_related(
        'store', 'category', 'preferred_supplier', 'drug'
    )
    
    # Apply filters - only if we have valid non-empty values
    if store_id:
        try:
            # Validate it's a valid UUID before filtering
            import uuid
            uuid.UUID(str(store_id))  # Will raise ValueError if invalid
            items = items.filter(store_id=store_id)
        except (ValueError, TypeError):
            # Invalid UUID, ignore filter
            store_id = None
    
    if category_id:
        try:
            # Validate it's a valid UUID before filtering
            import uuid
            uuid.UUID(str(category_id))  # Will raise ValueError if invalid
            items = items.filter(category_id=category_id)
        except (ValueError, TypeError):
            # Invalid UUID (including "None" string), ignore filter
            category_id = None
    
    if search:
        items = items.filter(
            Q(item_name__icontains=search) |
            Q(item_code__icontains=search) |
            Q(description__icontains=search) |
            Q(drug__name__icontains=search) |
            Q(drug__generic_name__icontains=search)
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
    
    # Default view mode:
    # - If no store is selected, show a grouped view (prevents "duplicates" across stores)
    # - If a store is selected, show per-store rows
    if group_mode not in ('0', '1'):
        group_mode = '1' if not store_id else '0'
    grouped = (group_mode == '1') and (not store_id)

    # Annotate with total value and low_stock flag (per-store rows)
    items = items.annotate(
        total_value=F('quantity_on_hand') * F('unit_cost'),
        is_low_stock=Case(
            When(Q(quantity_on_hand__lte=F('reorder_level')) & Q(reorder_level__gt=0), then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    )

    if grouped:
        # Group across stores by a stable key:
        # Prefer item_code when present; fall back to item_name.
        group_key = Coalesce(
            NullIf(Trim('item_code'), Value('')),
            Trim('item_name'),
        )

        # Postgres can aggregate store names nicely; fall back gracefully elsewhere.
        StringAgg = None
        try:
            from django.contrib.postgres.aggregates import StringAgg as _StringAgg
            StringAgg = _StringAgg
        except Exception:
            StringAgg = None

        base = items.annotate(group_key=group_key)
        
        # Get first ID per group - PostgreSQL doesn't support Min() on UUIDs
        # Use subquery to get first ID ordered by created date
        from django.db.models import Subquery, OuterRef
        first_id_subquery = InventoryItem.objects.filter(
            is_deleted=False,
            is_active=True,
            store__is_deleted=False,
            store__is_active=True
        ).annotate(
            item_group_key=Coalesce(
                NullIf(Trim('item_code'), Value('')),
                Trim('item_name'),
            )
        ).filter(
            item_group_key=OuterRef('group_key')
        ).order_by('created', 'id').values('id')[:1]
        
        id_annotation = Subquery(first_id_subquery, output_field=UUIDField())

        annotations = {
            # Representative ID for single-store groups (so View/Edit/Delete can still work)
            'id': id_annotation,
            'item_name': Min('item_name'),
            'item_code': Min('item_code'),
            'unit_of_measure': Min('unit_of_measure'),
            'category_name': Min('category__name'),
            'category_is_for_pharmacy': Max(
                Case(
                    When(category__is_for_pharmacy=True, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            'store_count': Count('store', distinct=True),
            'quantity_on_hand': Sum('quantity_on_hand'),
            # Use the pre-annotated total_value field instead of computing in Sum()
            'total_value': Sum('total_value'),
            'unit_cost_min': Min('unit_cost'),
            'unit_cost_max': Max('unit_cost'),
            # Use the pre-annotated is_low_stock field instead of computing in Max()
            'any_low_stock': Max('is_low_stock'),
        }
        if StringAgg:
            annotations['store_names'] = StringAgg('store__name', delimiter=', ', distinct=True)

        items = base.values('group_key').annotate(**annotations).order_by('item_name')
    else:
        # Order by created date (newest first) so newly transferred items appear at top
        # Then by item_name for consistent sorting within same date
        items = items.order_by('-created', 'item_name')
    
    # Use pagination for better performance with 300+ users and large stores
    from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
    paginator = Paginator(items, 50)  # 50 items per page
    page_number = request.GET.get('page', 1)
    try:
        items_page = paginator.page(page_number)
    except PageNotAnInteger:
        items_page = paginator.page(1) if paginator.num_pages > 0 else None
    except EmptyPage:
        # e.g. ?page=22 when there are 21 pages: show last valid page
        items_page = paginator.page(paginator.num_pages) if paginator.num_pages > 0 else None

    # Filter out items with invalid IDs (None, 'INVALID', etc.)
    # Convert to list and filter in Python since we can't easily filter on annotated fields
    items_list = list(items_page) if items_page else []
    import uuid
    valid_items = []
    for item in items_list:
        item_id = getattr(item, 'id', None)
        
        # For grouped items, we can show them even without a valid ID (template will handle it)
        # For non-grouped items, we need a valid ID
        if not grouped:
            # Non-grouped items must have a valid ID
            if not item_id:
                continue
            item_id_str = str(item_id).strip()
            # Explicitly check for invalid strings
            if item_id_str.upper() in ('INVALID', 'NONE', 'NULL', ''):
                continue
            try:
                # Try to convert to UUID to validate
                uuid.UUID(item_id_str)
                # Also check it's a proper UUID format (36 chars with hyphens)
                if len(item_id_str) == 36 and item_id_str.count('-') == 4:
                    valid_items.append(item)
                else:
                    continue
            except (ValueError, TypeError, AttributeError):
                # Invalid UUID, skip this item
                continue
        else:
            # Grouped items - allow them even if ID is invalid
            # The template will handle hiding action buttons for invalid IDs
            if item_id:
                item_id_str = str(item_id).strip()
                # Only skip if explicitly invalid string
                if item_id_str.upper() in ('INVALID', 'NONE', 'NULL', ''):
                    # Still include it, template will handle it
                    pass
            valid_items.append(item)
    
    # Get filter options
    stores = Store.objects.filter(is_deleted=False, is_active=True)
    categories = InventoryCategory.objects.filter(is_deleted=False, is_active=True)

    # Full pagination HTML built in Python (same as patient list — no INVALID in template)
    pagination_html = get_pagination_html(request, items_page, 25) if items_page else ''

    context = {
        'items': valid_items,
        'stores': stores,
        'categories': categories,
        'selected_store': store_id,
        'selected_category': category_id,
        'selected_status': status,
        'search_query': search,
        'group_mode': group_mode,
        'grouped': grouped,
        'active_pharmacy_store': active_pharmacy_store,
        'show_dispensing_hub': show_dispensing_hub,
        'items_page': items_page,
        'is_paginated': items_page.has_other_pages() if items_page else False,
        'pagination_html': pagination_html,
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
    store_id = request.GET.get('store', '').strip()
    
    # Normalize filter values - handle "None" string, empty strings, and None
    if store_id in ('None', 'none', '', None):
        store_id = None
    
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
        try:
            # Validate it's a valid UUID before filtering
            import uuid
            uuid.UUID(str(store_id))  # Will raise ValueError if invalid
            alerts = alerts.filter(store_id=store_id)
        except (ValueError, TypeError):
            # Invalid UUID, ignore filter
            store_id = None
    
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
        
        return redirect('hospital:inventory:alerts_list')
    
    return redirect('hospital:inventory:alerts_list')


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
        
        return redirect('hospital:inventory:alerts_list')
    
    context = {'alert': alert}
    return render(request, 'hospital/inventory/resolve_alert.html', context)


# ==================== INVENTORY REQUISITIONS ====================

@login_required
def requisitions_list(request):
    """List inventory requisitions"""
    status = request.GET.get('status', 'all')
    department_id = request.GET.get('department')
    
    # Base query for filtering
    base_queryset = InventoryRequisition.objects.filter(
        is_deleted=False
    )
    
    # Calculate statistics BEFORE filtering (for dashboard stats)
    stats = {
        'total': base_queryset.count(),
        'draft': base_queryset.filter(status='draft').count(),
        'submitted': base_queryset.filter(status='submitted').count(),
        'approved': base_queryset.filter(status='approved').count(),
        'partially_issued': base_queryset.filter(status='partially_issued').count(),
        'completed': base_queryset.filter(status='completed').count(),
        'cancelled': base_queryset.filter(status='cancelled').count(),
    }
    
    # Apply filters to the queryset for display
    requisitions = base_queryset.select_related(
        'requesting_department',
        'requested_by',
        'requested_from_store'
    )
    
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
        'stats': stats,
    }
    
    return render(request, 'hospital/inventory/requisitions_list.html', context)


@login_required
def api_store_items_for_requisition(request):
    """Store items API under inventory namespace so requisition form can load items reliably."""
    from .views_store_transfer_enhanced import api_get_store_items
    return api_get_store_items(request)


@login_required
def create_requisition(request):
    """Create new inventory requisition with optional line items (items from selected store)."""
    if request.method == 'POST':
        try:
            from django.utils.dateparse import parse_date
            required_by_date = request.POST.get('required_by_date')
            if required_by_date:
                required_by_date = parse_date(required_by_date)
            staff = getattr(request.user, 'staff', None)
            if not staff:
                messages.error(request, 'Your account is not linked to a staff member. Cannot create requisition.')
                return redirect('hospital:inventory:create_requisition')
            # Parse line items: JSON in hidden field or legacy single-item
            lines_payload = request.POST.get('requisition_lines')
            line_items = []
            if lines_payload:
                try:
                    line_items = json.loads(lines_payload)
                except (json.JSONDecodeError, TypeError):
                    pass
            if not line_items and request.POST.get('item_id') and request.POST.get('quantity_requested'):
                line_items = [{
                    'item_id': request.POST.get('item_id'),
                    'quantity': int(request.POST.get('quantity_requested', 0) or 0),
                }]
            line_items = [x for x in line_items if x.get('item_id') and (x.get('quantity') or 0) > 0]

            requisition = InventoryRequisition.objects.create(
                requesting_department_id=request.POST.get('department'),
                requested_by=staff,
                requested_from_store_id=request.POST.get('store'),
                priority=request.POST.get('priority', 'normal'),
                purpose=request.POST.get('purpose', ''),
                notes=request.POST.get('notes', ''),
                required_by_date=required_by_date,
                status='draft'
            )
            for line in line_items:
                try:
                    item_id = line.get('item_id')
                    qty = int(line.get('quantity', 0))
                    if not item_id or qty <= 0:
                        continue
                    inv_item = InventoryItem.objects.get(pk=item_id, is_deleted=False, store_id=requisition.requested_from_store_id)
                    InventoryRequisitionLine.objects.create(
                        requisition=requisition,
                        inventory_item=inv_item,
                        quantity_requested=qty,
                        quantity_approved=0,
                        quantity_issued=0,
                        unit_of_measure=inv_item.unit_of_measure or 'units',
                        notes=line.get('notes', '')
                    )
                except (InventoryItem.DoesNotExist, ValueError, TypeError):
                    continue
            messages.success(request, f'Requisition {requisition.requisition_number} created successfully!')
            return redirect('hospital:inventory:requisition_detail', req_id=requisition.id)
        except Exception as e:
            messages.error(request, f'Error creating requisition: {e}')

    stores = Store.objects.filter(is_deleted=False, is_active=True)
    departments = Department.objects.filter(is_deleted=False)
    initial_store_id = request.GET.get('store', '').strip()
    if initial_store_id:
        try:
            uuid.UUID(str(initial_store_id))
        except (ValueError, TypeError):
            initial_store_id = None
    else:
        initial_store_id = None
    api_store_items_url = reverse('hospital:inventory:api_store_items')
    context = {
        'stores': stores,
        'departments': departments,
        'initial_requested_from_store_id': initial_store_id,
        'api_store_items_url': api_store_items_url,
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
    store_id = request.GET.get('store', '').strip()
    days = int(request.GET.get('days', 30))
    
    # Normalize filter values - handle "None" string, empty strings, and None
    if store_id in ('None', 'none', '', None):
        store_id = None
    
    # Filter stores
    if store_id:
        try:
            # Validate it's a valid UUID before filtering
            import uuid
            uuid.UUID(str(store_id))  # Will raise ValueError if invalid
            stores_filter = Store.objects.filter(id=store_id, is_deleted=False)
        except (ValueError, TypeError):
            # Invalid UUID, ignore filter
            store_id = None
            stores_filter = Store.objects.filter(is_deleted=False, is_active=True)
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
    
    # ===== INVENTORY VALUE BY STORE =====
    # Use subquery to compute total value per store (Django doesn't support Sum() on combined F() expressions)
    from django.db.models import Subquery, OuterRef, DecimalField
    
    inventory_by_store = Store.objects.filter(
        id__in=[s.id for s in stores_filter]
    ).annotate(
        total_value=Coalesce(
            Subquery(
                InventoryItem.objects.filter(
                    store=OuterRef('pk'),
                    is_deleted=False
                ).annotate(
                    item_value=F('quantity_on_hand') * F('unit_cost')
                ).values('store').annotate(
                    total=Sum('item_value')
                ).values('total')[:1],
                output_field=DecimalField()
            ),
            Value(Decimal('0.00')),
            output_field=DecimalField()
        ),
        total_items=Sum('inventory_items__quantity_on_hand', 
                       filter=Q(inventory_items__is_deleted=False)),
        item_count=Count('inventory_items', filter=Q(inventory_items__is_deleted=False))
    ).order_by('-total_value')
    
    # ===== INVENTORY VALUE BY CATEGORY =====
    inventory_by_category = InventoryItem.objects.filter(
        store__in=stores_filter,
        is_deleted=False,
        category__isnull=False
    ).annotate(
        item_value=F('quantity_on_hand') * F('unit_cost')
    ).values('category__name', 'category__id').annotate(
        total_value=Sum('item_value'),
        total_items=Sum('quantity_on_hand'),
        item_count=Count('id')
    ).order_by('-total_value')[:10]
    
    # ===== STOCK STATUS BREAKDOWN =====
    total_items_count = InventoryItem.objects.filter(
        store__in=stores_filter,
        is_deleted=False,
        is_active=True
    ).count()
    
    out_of_stock_count = InventoryItem.objects.filter(
        store__in=stores_filter,
        is_deleted=False,
        is_active=True,
        quantity_on_hand=0
    ).count()
    
    low_stock_count = InventoryItem.objects.filter(
        store__in=stores_filter,
        is_deleted=False,
        is_active=True
    ).filter(
        Q(quantity_on_hand__lte=F('reorder_level')) & 
        Q(reorder_level__gt=0) &
        Q(quantity_on_hand__gt=0)
    ).count()
    
    in_stock_count = total_items_count - out_of_stock_count - low_stock_count
    
    # ===== TOP ITEMS BY VALUE =====
    top_items_by_value = InventoryItem.objects.filter(
        store__in=stores_filter,
        is_deleted=False,
        is_active=True
    ).annotate(
        item_value=F('quantity_on_hand') * F('unit_cost')
    ).order_by('-item_value')[:10]
    
    # ===== MONTHLY INVENTORY VALUE TREND =====
    monthly_trends = []
    # Calculate weekly trends for the selected period
    num_weeks = min(max(days // 7, 1), 12)  # Between 1 and 12 weeks
    for i in range(num_weeks, 0, -1):
        week_start = end_date - timedelta(weeks=i)
        week_end = week_start + timedelta(weeks=1)
        
        # Get current inventory value (approximate based on transactions)
        # This is a simplified calculation - in production, you'd track actual inventory snapshots
        week_value = InventoryItem.objects.filter(
            store__in=stores_filter,
            is_deleted=False,
            is_active=True
        ).annotate(
            item_value=F('quantity_on_hand') * F('unit_cost')
        ).aggregate(
            total=Sum('item_value')
        )['total'] or Decimal('0.00')
        
        monthly_trends.append({
            'period': week_start.strftime('%b %d'),
            'value': float(week_value)
        })
    
    # ===== TRANSFER STATISTICS =====
    transfers_in = StoreTransfer.objects.filter(
        to_store__in=stores_filter,
        created__gte=start_date,
        is_deleted=False
    ).count()
    
    transfers_out = StoreTransfer.objects.filter(
        from_store__in=stores_filter,
        created__gte=start_date,
        is_deleted=False
    ).count()
    
    # ===== TURNOVER RATE =====
    total_inventory_value = InventoryItem.objects.filter(
        store__in=stores_filter,
        is_deleted=False
    ).annotate(
        item_value=F('quantity_on_hand') * F('unit_cost')
    ).aggregate(
        total=Sum('item_value')
    )['total'] or Decimal('0.00')
    
    total_issues_value = InventoryTransaction.objects.filter(
        store__in=stores_filter,
        transaction_type='issue',
        transaction_date__gte=start_date,
        is_deleted=False
    ).aggregate(
        total=Sum('total_value')
    )['total'] or Decimal('0.00')
    
    turnover_rate = (float(total_issues_value) / float(total_inventory_value) * (365 / days)) if total_inventory_value > 0 else 0
    
    context = {
        'all_stores': all_stores,
        'selected_store': store_id,
        'days': days,
        'transactions_by_type': transactions_by_type,
        'daily_transactions': daily_transactions,
        'fast_moving': fast_moving,
        'slow_moving': slow_moving,
        'inventory_by_store': inventory_by_store,
        'inventory_by_category': inventory_by_category,
        'stock_status': {
            'total': total_items_count,
            'out_of_stock': out_of_stock_count,
            'low_stock': low_stock_count,
            'in_stock': in_stock_count,
        },
        'top_items_by_value': top_items_by_value,
        'monthly_trends': monthly_trends,
        'transfers': {
            'in': transfers_in,
            'out': transfers_out,
        },
        'turnover_rate': turnover_rate,
        'total_inventory_value': total_inventory_value,
        'total_issues_value': total_issues_value,
    }
    
    return render(request, 'hospital/inventory/analytics.html', context)


# ==================== TRANSFER MANAGEMENT ====================

@login_required
def transfers_list(request):
    """List store transfers"""
    status = request.GET.get('status', 'all')
    store_id = request.GET.get('store', '').strip()
    
    # Normalize filter values - handle "None" string, empty strings, and None
    if store_id in ('None', 'none', '', None):
        store_id = None
    
    # Base query
    transfers = StoreTransfer.objects.filter(is_deleted=False).select_related(
        'from_store', 'to_store', 'requested_by'
    )
    
    # Apply filters
    if status != 'all':
        transfers = transfers.filter(status=status)
    
    if store_id:
        try:
            # Validate it's a valid UUID before filtering
            import uuid
            uuid.UUID(str(store_id))  # Will raise ValueError if invalid
            transfers = transfers.filter(
                Q(from_store_id=store_id) | Q(to_store_id=store_id)
            )
        except (ValueError, TypeError):
            # Invalid UUID, ignore filter
            store_id = None
    
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
    store_id = request.GET.get('store', '').strip()
    
    # Normalize filter values - handle "None" string, empty strings, and None
    if store_id in ('None', 'none', '', None):
        store_id = None
    
    if store_id:
        try:
            # Validate it's a valid UUID before filtering
            import uuid
            uuid.UUID(str(store_id))  # Will raise ValueError if invalid
            stores = Store.objects.filter(id=store_id, is_deleted=False)
        except (ValueError, TypeError):
            # Invalid UUID, ignore filter
            store_id = None
            stores = Store.objects.filter(is_deleted=False, is_active=True)
    else:
        stores = Store.objects.filter(is_deleted=False, is_active=True)
    
    # Calculate stats
    total_value = InventoryItem.objects.filter(
        store__in=stores,
        is_deleted=False
    ).annotate(
        item_value=F('quantity_on_hand') * F('unit_cost')
    ).aggregate(
        total=Sum('item_value')
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



















