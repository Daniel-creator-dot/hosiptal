"""
Enhanced Procurement Receiving System with Proper Date Tracking
Senior Engineer & Data Engineer Approach
"""
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Sum, F
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import JsonResponse
from django.db import transaction

from .models import Staff
from .models_procurement import (
    Store, InventoryItem, ProcurementRequest, ProcurementRequestItem
)
from .utils_roles import is_procurement_staff

logger = logging.getLogger(__name__)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def receive_procurement_modern(request, pk):
    """
    Modern Procurement Receiving Interface
    Enhanced with proper date tracking and partial receiving support
    """
    proc_request = get_object_or_404(
        ProcurementRequest.objects.select_related(
            'requested_by_store', 'requested_by'
        ).prefetch_related('items'),
        pk=pk,
        is_deleted=False
    )
    
    if proc_request.status not in ['ordered', 'payment_processed']:
        messages.error(
            request,
            'Request must be ordered or payment processed before receiving.'
        )
        return redirect('hospital:procurement_requests_list')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                staff = Staff.objects.get(user=request.user, is_deleted=False)
                
                # Get received date
                received_date_str = request.POST.get('received_date')
                if received_date_str:
                    try:
                        received_date = datetime.strptime(received_date_str, '%Y-%m-%d').date()
                    except ValueError:
                        received_date = timezone.now().date()
                else:
                    received_date = timezone.now().date()
                
                # Process each item
                item_ids = request.POST.getlist('item_id[]')
                received_quantities = request.POST.getlist('received_quantity[]')
                
                total_received = 0
                items_processed = 0
                
                from hospital.services.inventory_accountability_service import InventoryAccountabilityService
                
                for item_id, received_qty in zip(item_ids, received_quantities):
                    try:
                        item = ProcurementRequestItem.objects.get(
                            pk=item_id,
                            request=proc_request,
                            is_deleted=False
                        )
                        
                        received_qty = int(received_qty) if received_qty else 0
                        if received_qty <= 0:
                            continue
                        
                        # Don't allow receiving more than ordered
                        if received_qty > item.quantity:
                            messages.warning(
                                request,
                                f'Cannot receive {received_qty} units of {item.item_name}. '
                                f'Ordered quantity is {item.quantity}.'
                            )
                            continue
                        
                        # Determine target store based on item type
                        if item.drug or (proc_request.requested_by_store and proc_request.requested_by_store.store_type == 'pharmacy'):
                            # Pharmacy items go to Drug Store (DRUGS)
                            target_store = Store.objects.filter(code='DRUGS', is_deleted=False).first()
                            if not target_store:
                                target_store = Store.objects.filter(store_type='pharmacy', is_deleted=False).first()
                        elif proc_request.requested_by_store and proc_request.requested_by_store.store_type == 'lab':
                            # Lab items go to Lab Store (LAB)
                            target_store = Store.objects.filter(code='LAB', is_deleted=False).first()
                            if not target_store:
                                target_store = Store.objects.filter(store_type='lab', is_deleted=False).first()
                        else:
                            # Other items go to Main Store (MAIN)
                            target_store = Store.objects.filter(code='MAIN', is_deleted=False).first()
                            if not target_store:
                                target_store = Store.objects.filter(store_type='main', is_deleted=False).first()
                        
                        if not target_store:
                            # Fallback: create main store if doesn't exist
                            target_store = Store.objects.create(
                                name='Main Store',
                                code='MAIN',
                                store_type='main',
                                manager=staff
                            )
                        
                        # Get or create inventory item
                        inventory_item, created = InventoryItem.objects.get_or_create(
                            store=target_store,
                            item_code=item.item_code if item.item_code else item.item_name,
                            is_deleted=False,
                            defaults={
                                'item_name': item.item_name,
                                'description': item.description,
                                'drug': item.drug,
                                'quantity_on_hand': 0,
                                'unit_cost': item.estimated_unit_price,
                                'unit_of_measure': item.unit_of_measure,
                                'reorder_level': 10,
                                'reorder_quantity': item.quantity,
                                'preferred_supplier': item.preferred_supplier,
                            }
                        )
                        
                        # Use accountability service to receive from supplier
                        InventoryAccountabilityService.receive_from_supplier(
                            inventory_item=inventory_item,
                            quantity=received_qty,
                            unit_cost=item.estimated_unit_price,
                            staff=staff,
                            reference_number=proc_request.request_number,
                            supplier_name=item.preferred_supplier.name if item.preferred_supplier else '',
                            notes=f"Received via procurement request {proc_request.request_number} on {received_date}"
                        )
                        
                        # Update received quantity
                        item.received_quantity = received_qty
                        item.save()
                        
                        total_received += received_qty
                        items_processed += 1
                        
                    except (ValueError, ProcurementRequestItem.DoesNotExist) as e:
                        logger.error(f"Error processing item {item_id}: {e}")
                        continue
                
                if items_processed == 0:
                    messages.error(request, 'No items were received. Please check quantities.')
                    return redirect('hospital:receive_procurement_modern', pk=pk)
                
                # Check if all items fully received
                all_items = proc_request.items.filter(is_deleted=False)
                fully_received = all(
                    item.received_quantity >= item.quantity
                    for item in all_items
                )
                
                # Update request status
                if fully_received:
                    proc_request.status = 'received'
                    # Add received date to notes
                    proc_request.notes = (
                        f"{proc_request.notes or ''}\n"
                        f"[RECEIVED: {received_date} - {staff.user.get_full_name() or staff.user.username}] "
                        f"All items received. Total: {total_received} units."
                    ).strip()
                else:
                    # Partial receiving - keep status but add note
                    proc_request.notes = (
                        f"{proc_request.notes or ''}\n"
                        f"[PARTIAL RECEIVING: {received_date} - {staff.user.get_full_name() or staff.user.username}] "
                        f"Received {total_received} units. Partial receiving in progress."
                    ).strip()
                
                proc_request.save()
                
                # Post accounting entry if fully received
                if fully_received:
                    try:
                        from .views_procurement_enhanced import post_procurement_accounting_entry
                        post_procurement_accounting_entry(proc_request)
                    except Exception as e:
                        logger.warning(f"Could not post accounting entry: {e}")
                
                messages.success(
                    request,
                    f'Successfully received {items_processed} item(s), '
                    f'total {total_received} units on {received_date}. '
                    f'Items added to {main_store.name} inventory.'
                )
                
                return redirect('hospital:procurement_request_detail', pk=pk)
                
        except Staff.DoesNotExist:
            messages.error(request, 'Staff profile not found.')
        except Exception as e:
            logger.error(f"Error receiving procurement: {e}", exc_info=True)
            messages.error(request, f'Error receiving items: {str(e)}')
    
    # GET request - show receiving form
    # Calculate totals
    total_items = proc_request.items.filter(is_deleted=False).count()
    total_quantity = proc_request.items.filter(is_deleted=False).aggregate(
        total=Sum('quantity')
    )['total'] or 0
    total_received = proc_request.items.filter(is_deleted=False).aggregate(
        total=Sum('received_quantity')
    )['total'] or 0
    pending_quantity = total_quantity - total_received
    
    # Check if fully received
    all_items = proc_request.items.filter(is_deleted=False)
    fully_received = all(
        item.received_quantity >= item.quantity
        for item in all_items
    )
    
    context = {
        'title': f'Receive Items - {proc_request.request_number}',
        'proc_request': proc_request,
        'total_items': total_items,
        'total_quantity': total_quantity,
        'total_received': total_received,
        'pending_quantity': pending_quantity,
        'fully_received': fully_received,
        'default_received_date': timezone.now().date(),
    }
    
    return render(request, 'hospital/receive_procurement_modern.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def procurement_receiving_dashboard(request):
    """
    Procurement Receiving Dashboard
    Shows all requests ready for receiving with date tracking
    """
    now = timezone.now()
    today = now.date()
    
    # Get requests ready for receiving
    ready_for_receiving = ProcurementRequest.objects.filter(
        status__in=['ordered', 'payment_processed'],
        is_deleted=False
    ).select_related(
        'requested_by_store', 'requested_by'
    ).prefetch_related('items').order_by('-request_date')
    
    # Get partially received requests
    partially_received = ProcurementRequest.objects.filter(
        status='received',
        is_deleted=False
    ).select_related(
        'requested_by_store', 'requested_by'
    ).prefetch_related('items')
    
    # Filter to only those with partial receiving
    partially_received_list = []
    for req in partially_received:
        all_items = req.items.filter(is_deleted=False)
        if any(item.received_quantity < item.quantity for item in all_items):
            partially_received_list.append(req)
    
    # Get fully received requests (last 30 days) - base queryset for stats
    fully_received_base = ProcurementRequest.objects.filter(
        status='received',
        is_deleted=False,
        created__gte=now - timedelta(days=30)
    ).select_related(
        'requested_by_store', 'requested_by'
    ).order_by('-created')
    
    # Get fully received today count BEFORE slicing
    fully_received_today_count = fully_received_base.filter(
        created__date=today
    ).count()
    
    # Now slice for display
    fully_received = fully_received_base[:20]
    
    # Statistics
    stats = {
        'ready_for_receiving': ready_for_receiving.count(),
        'partially_received': len(partially_received_list),
        'fully_received_today': fully_received_today_count,
        'total_value_pending': ready_for_receiving.aggregate(
            total=Sum('estimated_total')
        )['total'] or Decimal('0.00'),
    }
    
    context = {
        'title': 'Procurement Receiving Dashboard',
        'ready_for_receiving': ready_for_receiving[:20],
        'partially_received': partially_received_list[:10],
        'fully_received': fully_received,
        'stats': stats,
    }
    
    return render(request, 'hospital/procurement_receiving_dashboard.html', context)
