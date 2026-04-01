"""
Enhanced Store Transfer System with Modern Monitoring
Senior Engineer & Data Engineer Approach
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Count, F, Avg
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.http import JsonResponse
from django.db import transaction
from django.core.exceptions import ValidationError

from .models import Staff
from .models_procurement import (
    Store, InventoryItem, StoreTransfer, StoreTransferLine,
    ProcurementRequest
)
from .utils_roles import is_procurement_staff
from .utils_inventory_monitoring import get_transfer_suggestions_summary
from django.contrib.auth.decorators import user_passes_test

logger = logging.getLogger(__name__)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def transfer_dashboard(request):
    """
    Comprehensive Transfer Monitoring Dashboard
    Real-time tracking of all transfers with analytics
    """
    now = timezone.now()
    today = now.date()
    
    # Get all active transfers
    all_transfers = StoreTransfer.objects.filter(
        is_deleted=False
    ).select_related(
        'from_store', 'to_store', 'requested_by', 'approved_by', 'received_by'
    ).prefetch_related('lines').order_by('-created')
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        all_transfers = all_transfers.filter(status=status_filter)
    
    # Filter by store
    store_filter = request.GET.get('store', '')
    if store_filter:
        all_transfers = all_transfers.filter(
            Q(from_store_id=store_filter) | Q(to_store_id=store_filter)
        )
    
    # Filter by date range
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        try:
            all_transfers = all_transfers.filter(transfer_date__gte=date_from)
        except ValueError:
            pass
    if date_to:
        try:
            all_transfers = all_transfers.filter(transfer_date__lte=date_to)
        except ValueError:
            pass
    
    # Statistics
    stats = {
        'total': all_transfers.count(),
        'pending': all_transfers.filter(status='pending').count(),
        'approved': all_transfers.filter(status='approved').count(),
        'in_transit': all_transfers.filter(status='in_transit').count(),
        'completed': all_transfers.filter(status='completed').count(),
        'cancelled': all_transfers.filter(status='cancelled').count(),
    }
    
    # Recent transfers (last 7 days)
    recent_transfers = all_transfers.filter(
        created__gte=now - timedelta(days=7)
    )[:10]
    
    # Pending transfers requiring attention
    pending_transfers = all_transfers.filter(status='pending').order_by('created')[:10]
    
    # In-transit transfers (overdue check)
    in_transit_transfers = all_transfers.filter(status='in_transit').order_by('created')
    overdue_transfers = []
    for transfer in in_transit_transfers:
        # Consider overdue if in transit for more than 2 days
        if transfer.created and (now - transfer.created).days > 2:
            overdue_transfers.append(transfer)
    
    # Analytics: Transfer volume by store
    # Use different annotation names to avoid conflicts with related_name
    store_analytics = Store.objects.filter(
        is_active=True, is_deleted=False
    ).annotate(
        total_transfers_out=Count('transfers_out', filter=Q(transfers_out__is_deleted=False)),
        total_transfers_in=Count('transfers_in', filter=Q(transfers_in__is_deleted=False)),
        total_value_out=Sum(
            F('transfers_out__lines__quantity') * F('transfers_out__lines__unit_cost'),
            filter=Q(transfers_out__is_deleted=False)
        ),
        total_value_in=Sum(
            F('transfers_in__lines__quantity') * F('transfers_in__lines__unit_cost'),
            filter=Q(transfers_in__is_deleted=False)
        ),
    )
    
    # Get all stores for filter dropdown
    all_stores = Store.objects.filter(is_active=True, is_deleted=False).order_by('name')
    
    # Get transfer suggestions for Pharmacy Store (low stock items)
    pharmacy_store = Store.objects.filter(code='PHARM', is_deleted=False).first()
    transfer_suggestions = None
    if pharmacy_store:
        try:
            transfer_suggestions = get_transfer_suggestions_summary(pharmacy_store)
        except Exception as e:
            logger.error(f"Error getting transfer suggestions: {e}")
            transfer_suggestions = None
    
    context = {
        'title': 'Transfer Monitoring Dashboard',
        'transfers': all_transfers[:50],  # Limit for performance
        'recent_transfers': recent_transfers,
        'pending_transfers': pending_transfers,
        'overdue_transfers': overdue_transfers,
        'stats': stats,
        'store_analytics': store_analytics,
        'all_stores': all_stores,
        'status_filter': status_filter,
        'store_filter': store_filter,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices': StoreTransfer.STATUS_CHOICES,
        'transfer_suggestions': transfer_suggestions,
    }
    
    return render(request, 'hospital/store_transfer_dashboard.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def create_transfer_modern(request):
    """
    World-Class Transfer Creation Interface
    Intelligent item selection with real-time inventory checking
    Supports all store types: Main, Consumables, Lab, Pharmacy, etc.
    """
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Get form data
                from_store_id = (request.POST.get('from_store') or '').strip()
                to_store_id = (request.POST.get('to_store') or '').strip()
                transfer_date = request.POST.get('transfer_date')
                notes = request.POST.get('notes', '')
                
                # Reject invalid UUIDs (e.g. "INVALID" from template string_if_invalid) before DB lookup
                if not _is_valid_uuid(from_store_id):
                    messages.error(request, 'Please select a valid source store.')
                    return redirect('hospital:create_transfer_modern')
                if not _is_valid_uuid(to_store_id):
                    messages.error(request, 'Please select a valid destination store.')
                    return redirect('hospital:create_transfer_modern')
                
                # Validate stores
                from_store = get_object_or_404(Store, pk=from_store_id, is_deleted=False)
                to_store = get_object_or_404(Store, pk=to_store_id, is_deleted=False)
                
                if from_store == to_store:
                    messages.error(request, 'Source and destination stores cannot be the same.')
                    return redirect('hospital:create_transfer_modern')
                
                # Get current staff
                staff = Staff.objects.get(user=request.user, is_deleted=False)
                
                # Create transfer
                transfer = StoreTransfer.objects.create(
                    from_store=from_store,
                    to_store=to_store,
                    transfer_date=transfer_date or timezone.now().date(),
                    notes=notes,
                    requested_by=staff,
                    status='pending'
                )
                
                # Process line items
                item_ids = request.POST.getlist('item_id[]')
                quantities = request.POST.getlist('quantity[]')
                
                if not item_ids or not quantities:
                    transfer.delete()
                    messages.error(request, 'Please add at least one item to transfer.')
                    return redirect('hospital:create_transfer_modern')
                
                total_value = Decimal('0.00')
                errors = []
                
                # Optional: destination item to replenish (from "Transfer in" on low-stock item)
                for_item_id = (request.POST.get('for_item_id') or '').strip()
                to_inventory_item = None
                if _is_valid_uuid(for_item_id):
                    to_inventory_item = InventoryItem.objects.filter(
                        pk=for_item_id,
                        store=to_store,
                        is_deleted=False
                    ).first()
                
                for item_id, quantity in zip(item_ids, quantities):
                    try:
                        quantity = int(quantity)
                        if quantity <= 0:
                            continue
                        
                        # Get inventory item (source)
                        inventory_item = get_object_or_404(
                            InventoryItem,
                            pk=item_id,
                            store=from_store,
                            is_deleted=False
                        )
                        
                        # Check availability
                        if inventory_item.quantity_on_hand < quantity:
                            errors.append(
                                f'Insufficient stock for {inventory_item.item_name}. '
                                f'Available: {inventory_item.quantity_on_hand}, Requested: {quantity}'
                            )
                            continue
                        
                        # Link to destination item when replenishing a specific item (same product)
                        line_to_item = None
                        if to_inventory_item:
                            if (inventory_item.item_code and inventory_item.item_code == to_inventory_item.item_code) or (
                                inventory_item.drug_id and inventory_item.drug_id == to_inventory_item.drug_id
                            ) or (inventory_item.item_name and inventory_item.item_name.strip().lower() == (to_inventory_item.item_name or '').strip().lower()):
                                line_to_item = to_inventory_item
                        
                        # Create transfer line (from_inventory_item + to_inventory_item link for quantity update)
                        line_value = Decimal(str(inventory_item.unit_cost)) * quantity
                        total_value += line_value
                        
                        StoreTransferLine.objects.create(
                            transfer=transfer,
                            from_inventory_item=inventory_item,
                            to_inventory_item=line_to_item,
                            item_code=inventory_item.item_code,
                            item_name=inventory_item.item_name,
                            quantity=quantity,
                            unit_cost=inventory_item.unit_cost,
                            unit_of_measure=inventory_item.unit_of_measure,
                        )
                    except (ValueError, InventoryItem.DoesNotExist) as e:
                        logger.error(f"Error processing transfer line: {e}")
                        errors.append(f"Error processing item: {str(e)}")
                        continue
                
                if transfer.lines.count() == 0:
                    transfer.delete()
                    if errors:
                        for error in errors:
                            messages.error(request, error)
                    messages.error(request, 'No valid items were added to the transfer.')
                    return redirect('hospital:create_transfer_modern')
                
                if errors:
                    for error in errors:
                        messages.warning(request, error)
                
                messages.success(
                    request,
                    f'Transfer {transfer.transfer_number} created successfully! '
                    f'Total value: GHS {total_value:.2f}'
                )
                return redirect('hospital:transfer_dashboard')
                
        except Exception as e:
            logger.error(f"Error creating transfer: {e}", exc_info=True)
            messages.error(request, f'Error creating transfer: {str(e)}')
    
    # GET request - show form
    # Pre-fill from_store / to_store from query params (e.g. from Stores list or Store detail)
    # for_item = destination inventory item to replenish (links transfer line so quantity updates that item)
    from_store_id = request.GET.get('from_store', '').strip()
    to_store_id = request.GET.get('to_store', '').strip()
    for_item_id = request.GET.get('for_item', '').strip()
    
    replenish_item = None
    if _is_valid_uuid(for_item_id):
        replenish_item = InventoryItem.objects.filter(
            pk=for_item_id,
            is_deleted=False
        ).select_related('store', 'category').first()
        if replenish_item and to_store_id and str(replenish_item.store_id) != str(to_store_id):
            to_store_id = str(replenish_item.store_id)
    
    # Only accept valid UUIDs to avoid template/API passing "INVALID" (e.g. from string_if_invalid in DEBUG)
    def valid_store_id(s):
        if not s or not isinstance(s, str):
            return False
        s = s.strip().upper()
        if s in ('INVALID', 'NONE', 'NULL', ''):
            return False
        try:
            import uuid
            uuid.UUID(s)
            return True
        except (ValueError, TypeError):
            return False
    
    initial_from_store = None
    initial_to_store = None
    if valid_store_id(from_store_id):
        try:
            initial_from_store = Store.objects.get(pk=from_store_id, is_deleted=False)
        except (Store.DoesNotExist, ValueError):
            pass
    if valid_store_id(to_store_id):
        try:
            initial_to_store = Store.objects.get(pk=to_store_id, is_deleted=False)
        except (Store.DoesNotExist, ValueError):
            pass
    if replenish_item and not initial_to_store and replenish_item.store_id:
        try:
            initial_to_store = Store.objects.get(pk=replenish_item.store_id, is_deleted=False)
        except (Store.DoesNotExist, ValueError):
            pass
    
    # Get all stores; build option list with UUIDs serialized in Python so template never outputs raw store.pk (avoids string_if_invalid "INVALID")
    all_stores = Store.objects.filter(is_active=True, is_deleted=False).order_by('store_type', 'name')
    stores_by_type = {}
    for store in all_stores:
        store_type = store.get_store_type_display()
        if store_type not in stores_by_type:
            stores_by_type[store_type] = []
        stores_by_type[store_type].append({
            'pk_str': str(store.pk),
            'name': store.name,
            'code': store.code,
        })
    
    import json
    initial_from_pk_str = str(initial_from_store.pk) if initial_from_store else ''
    initial_to_pk_str = str(initial_to_store.pk) if initial_to_store else ''
    initial_store_ids_json = json.dumps({'from': initial_from_pk_str, 'to': initial_to_pk_str})
    replenish_item_id_str = str(replenish_item.pk) if replenish_item else ''
    api_store_items_url = reverse('hospital:api_get_store_items')
    
    context = {
        'title': 'Create Store Transfer',
        'all_stores': all_stores,
        'stores_by_type': stores_by_type,
        'initial_from_store': initial_from_store,
        'initial_to_store': initial_to_store,
        'initial_from_pk_str': initial_from_pk_str,
        'initial_to_pk_str': initial_to_pk_str,
        'initial_store_ids_json': initial_store_ids_json,
        'replenish_item': replenish_item,
        'replenish_item_id_str': replenish_item_id_str,
        'api_store_items_url': api_store_items_url,
    }
    
    return render(request, 'hospital/create_transfer_modern.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def approve_transfer(request, pk):
    """Approve a pending transfer"""
    transfer = get_object_or_404(StoreTransfer, pk=pk, is_deleted=False)
    
    if transfer.status != 'pending':
        messages.error(request, 'Only pending transfers can be approved.')
        return redirect('hospital:transfer_dashboard')
    
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
        
        # Check inventory availability; prefer exact correlation (from_inventory_item)
        validation_errors = []
        for line in transfer.lines.filter(is_deleted=False):
            from_item = None
            if getattr(line, 'from_inventory_item_id', None):
                from_item = InventoryItem.objects.filter(
                    pk=line.from_inventory_item_id,
                    store=transfer.from_store,
                    is_deleted=False
                ).first()
                if not from_item:
                    validation_errors.append(
                        f'Item "{line.item_name}" (Code: {line.item_code or "N/A"}) '
                        f'no longer found in {transfer.from_store.name}.'
                    )
                    continue
                if from_item.quantity_on_hand < line.quantity:
                    validation_errors.append(
                        f'Insufficient stock for "{line.item_name}". '
                        f'Available: {from_item.quantity_on_hand}, Required: {line.quantity}'
                    )
                    continue
            if not from_item and line.item_code:
                from_item = InventoryItem.objects.filter(
                    store=transfer.from_store,
                    item_code=line.item_code,
                    is_deleted=False
                ).first()
            if not from_item and line.item_name:
                from_item = InventoryItem.objects.filter(
                    store=transfer.from_store,
                    item_name__iexact=line.item_name.strip(),
                    is_deleted=False
                ).first()
            if not from_item and line.item_name:
                from_item = InventoryItem.objects.filter(
                    store=transfer.from_store,
                    item_name__icontains=line.item_name.strip(),
                    is_deleted=False
                ).first()
            if not from_item:
                validation_errors.append(
                    f'Item "{line.item_name}" (Code: {line.item_code or "N/A"}) '
                    f'not found in {transfer.from_store.name}'
                )
                continue
            if from_item.quantity_on_hand < line.quantity:
                validation_errors.append(
                    f'Insufficient stock for "{line.item_name}". '
                    f'Available: {from_item.quantity_on_hand}, Required: {line.quantity}'
                )
                continue
        
        if validation_errors:
            messages.error(
                request,
                'Transfer validation failed:\n' + '\n'.join(f'  • {err}' for err in validation_errors)
            )
            return redirect('hospital:transfer_dashboard')
        
        # Approve transfer
        transfer.status = 'approved'
        transfer.approved_by = staff
        transfer.approved_at = timezone.now()
        transfer.save()
        
        messages.success(request, f'Transfer {transfer.transfer_number} approved successfully!')
        
    except Staff.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
    except Exception as e:
        logger.error(f"Error approving transfer: {e}", exc_info=True)
        messages.error(request, f'Error approving transfer: {str(e)}')
    
    return redirect('hospital:transfer_dashboard')


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def complete_transfer(request, pk):
    """Complete a transfer (mark as received)"""
    transfer = get_object_or_404(StoreTransfer, pk=pk, is_deleted=False)
    
    if transfer.status not in ['approved', 'in_transit']:
        messages.error(request, 'Transfer must be approved before completion.')
        return redirect('hospital:transfer_dashboard')
    
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
        
        # Complete transfer using the model method
        transfer.complete_transfer(staff)
        
        messages.success(
            request,
            f'Transfer {transfer.transfer_number} completed successfully! '
            f'Items have been moved from {transfer.from_store.name} to {transfer.to_store.name}.'
        )
        
    except ValueError as e:
        messages.error(request, str(e))
    except Staff.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
    except Exception as e:
        logger.error(f"Error completing transfer: {e}", exc_info=True)
        messages.error(request, f'Error completing transfer: {str(e)}')
    
    return redirect('hospital:transfer_dashboard')


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def transfer_detail_enhanced(request, pk):
    """Enhanced transfer detail view with full tracking"""
    transfer = get_object_or_404(
        StoreTransfer.objects.select_related(
            'from_store', 'to_store', 'requested_by', 'approved_by', 'received_by'
        ).prefetch_related('lines'),
        pk=pk,
        is_deleted=False
    )
    
    # Calculate totals
    total_items = transfer.lines.filter(is_deleted=False).count()
    total_quantity = transfer.lines.filter(is_deleted=False).aggregate(
        total=Sum('quantity')
    )['total'] or 0
    total_value = transfer.lines.filter(is_deleted=False).aggregate(
        total=Sum(F('quantity') * F('unit_cost'))
    )['total'] or Decimal('0.00')
    
    # Timeline events
    timeline = []
    if transfer.created:
        timeline.append({
            'date': transfer.created,
            'event': 'Transfer Created',
            'user': transfer.requested_by.user.get_full_name() if transfer.requested_by and transfer.requested_by.user else 'System',
            'icon': 'plus-circle',
            'color': 'primary'
        })
    if transfer.approved_at:
        timeline.append({
            'date': transfer.approved_at,
            'event': 'Transfer Approved',
            'user': transfer.approved_by.user.get_full_name() if transfer.approved_by and transfer.approved_by.user else 'N/A',
            'icon': 'check-circle',
            'color': 'success'
        })
    if transfer.received_at:
        timeline.append({
            'date': transfer.received_at,
            'event': 'Transfer Completed',
            'user': transfer.received_by.user.get_full_name() if transfer.received_by and transfer.received_by.user else 'N/A',
            'icon': 'check-double',
            'color': 'success'
        })
    
    context = {
        'title': f'Transfer {transfer.transfer_number}',
        'transfer': transfer,
        'total_items': total_items,
        'total_quantity': total_quantity,
        'total_value': total_value,
        'timeline': timeline,
    }
    
    return render(request, 'hospital/transfer_detail_enhanced.html', context)


def _is_valid_uuid(value):
    """Return True if value is a valid UUID string; avoid passing 'INVALID' or junk to DB."""
    if not value or not isinstance(value, str):
        return False
    value = value.strip()
    if value.upper() in ('INVALID', 'NONE', 'NULL', ''):
        return False
    try:
        import uuid
        uuid.UUID(value)
        return True
    except (ValueError, TypeError):
        return False


def _safe_store_items_error(msg):
    """Always return a plain string error, never the raw UUID/INVALID message."""
    if hasattr(msg, '__iter__') and not isinstance(msg, str):
        msg = msg[0] if msg else ''
    msg = str(msg) if msg else ''
    if 'UUID' in msg or 'INVALID' in msg.upper():
        return 'Please select a store from the list.'
    return msg or 'Error loading items. Please try again.'


@login_required
def api_get_store_items(request):
    """
    API endpoint to get items from a store for transfer
    Returns JSON with searchable, selectable items
    """
    raw_store_id = request.GET.get('store_id')
    store_id = str(raw_store_id).strip() if raw_store_id is not None else ''
    search_query = request.GET.get('search', '').strip()
    category_filter = request.GET.get('category', '')
    
    # Reject empty or literal INVALID first (never touch ORM with bad pk)
    if not store_id or store_id.upper() == 'INVALID':
        return JsonResponse({'error': 'Please select a store from the list.'}, status=400)
    if not _is_valid_uuid(store_id):
        return JsonResponse({'error': 'Please select a store from the list.'}, status=400)
    
    try:
        store = Store.objects.get(pk=store_id, is_deleted=False)
        
        # Base queryset - include all items (even with 0 quantity for Drug Store)
        # Drug Store items start with 0 quantity and are updated when purchased
        items_qs = InventoryItem.objects.filter(
            store=store,
            is_deleted=False,
            is_active=True
        ).select_related('drug', 'category')
        
        # Apply search filter
        if search_query:
            items_qs = items_qs.filter(
                Q(item_name__icontains=search_query) |
                Q(item_code__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(drug__name__icontains=search_query) if hasattr(InventoryItem, 'drug') else Q()
            )
        
        # Apply category filter
        if category_filter:
            items_qs = items_qs.filter(category_id=category_filter)
        
        items = list(items_qs.order_by('item_name')[:100])  # Limit to 100 for performance
        item_pks = [item.pk for item in items]
        
        # Optional: last issue (quantity taken) per item for requisition/display
        last_issue_map = {}
        if request.GET.get('with_last_issue') or request.GET.get('with_history'):
            try:
                from .models_inventory_advanced import InventoryTransaction
                last_issues = InventoryTransaction.objects.filter(
                    inventory_item_id__in=item_pks,
                    transaction_type='issue',
                    is_deleted=False
                ).order_by('inventory_item_id', '-transaction_date').values(
                    'inventory_item_id', 'quantity', 'transaction_date'
                )
                for r in last_issues:
                    iid = r['inventory_item_id']
                    if iid not in last_issue_map:
                        last_issue_map[iid] = {
                            'last_issue_quantity': abs(r['quantity']),
                            'last_issue_date': r['transaction_date'].strftime('%Y-%m-%d %H:%M') if r['transaction_date'] else None,
                        }
            except Exception:
                pass
        
        items_data = []
        for item in items:
            last_issue = last_issue_map.get(item.pk, {})
            items_data.append({
                'id': str(item.pk),
                'item_code': item.item_code or 'N/A',
                'item_name': item.item_name,
                'description': item.description or '',
                'available_quantity': item.quantity_on_hand,
                'unit_cost': str(item.unit_cost),
                'unit_of_measure': item.unit_of_measure,
                'category': item.category.name if item.category else 'Uncategorized',
                'category_id': str(item.category.pk) if item.category else '',
                'reorder_level': item.reorder_level,
                'is_low_stock': item.quantity_on_hand <= item.reorder_level if item.reorder_level > 0 else False,
                'drug_name': item.drug.name if item.drug else '',
                'last_issue_quantity': last_issue.get('last_issue_quantity'),
                'last_issue_date': last_issue.get('last_issue_date'),
            })
        
        return JsonResponse({
            'items': items_data,
            'store_name': store.name,
            'store_type': store.get_store_type_display(),
            'total_items': len(items_data)
        }, safe=False)
        
    except Store.DoesNotExist:
        return JsonResponse({'error': 'Store not found'}, status=404)
    except ValidationError as e:
        # Django UUID field raises this for bad pk; never send list to client
        logger.warning("Store items API: ValidationError for store_id=%r", store_id, exc_info=True)
        err_msg = getattr(e, 'messages', None) or str(e)
        safe_msg = _safe_store_items_error(err_msg)
        return JsonResponse({'error': safe_msg if isinstance(safe_msg, str) else 'Please select a store from the list.'}, status=400)
    except Exception as e:
        err_msg = str(e)
        if 'UUID' in err_msg or 'INVALID' in err_msg.upper():
            return JsonResponse({'error': 'Please select a store from the list.'}, status=400)
        logger.error(f"Error fetching store items: {e}", exc_info=True)
        return JsonResponse({'error': _safe_store_items_error(err_msg)}, status=500)


@login_required
def api_get_item_details(request):
    """
    API endpoint to get detailed information about a specific item
    """
    item_id = request.GET.get('item_id')
    
    if not item_id:
        return JsonResponse({'error': 'item_id required'}, status=400)
    
    try:
        item = InventoryItem.objects.select_related('drug', 'category', 'store').get(
            pk=item_id,
            is_deleted=False
        )
        
        return JsonResponse({
            'id': str(item.pk),
            'item_code': item.item_code or 'N/A',
            'item_name': item.item_name,
            'description': item.description or '',
            'available_quantity': item.quantity_on_hand,
            'unit_cost': str(item.unit_cost),
            'unit_of_measure': item.unit_of_measure,
            'category': item.category.name if item.category else 'Uncategorized',
            'reorder_level': item.reorder_level,
            'is_low_stock': item.quantity_on_hand <= item.reorder_level if item.reorder_level > 0 else False,
            'store_name': item.store.name,
            'store_type': item.store.get_store_type_display(),
        }, safe=False)
        
    except InventoryItem.DoesNotExist:
        return JsonResponse({'error': 'Item not found'}, status=404)
    except Exception as e:
        logger.error(f"Error fetching item details: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_get_categories(request):
    """
    API endpoint to get inventory categories for filtering
    """
    store_id = request.GET.get('store_id')
    
    try:
        from .models_procurement import InventoryCategory
        
        categories = InventoryCategory.objects.filter(
            is_active=True,
            is_deleted=False
        ).order_by('name')
        
        categories_data = [{
            'id': str(cat.pk),
            'name': cat.name,
            'code': cat.code,
        } for cat in categories]
        
        return JsonResponse({'categories': categories_data}, safe=False)
        
    except Exception as e:
        logger.error(f"Error fetching categories: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)
