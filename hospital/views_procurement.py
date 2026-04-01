"""
Procurement and Inventory Management Views
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum, Count, F
from django.http import JsonResponse
from django.forms import inlineformset_factory
from datetime import date, timedelta
from decimal import Decimal
from .models_procurement import (
    Store, InventoryItem, StoreTransfer, StoreTransferLine,
    ProcurementRequest, ProcurementRequestItem, InventoryCategory
)
from .models_missing_features import Supplier
from .forms_procurement import (
    SupplierForm, StoreForm, InventoryItemForm,
    ProcurementRequestForm, ProcurementRequestItemFormSet,
    StoreTransferForm, StoreTransferLineFormSet
)
from .models import Staff


def is_admin_user(user):
    """Check if user is admin - only admins can edit/change stock levels"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=['Admin', 'Administrator']).exists()


def is_procurement_staff(user):
    """Check if user has procurement access"""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    # Check if user is in Procurement group
    if user.groups.filter(name__in=[
        'Admin', 'Administrator',
        'Store Manager', 'Inventory Stores Manager',
        'Procurement', 'Procurement Officer'
    ]).exists():
        return True
    # Check if user's staff profession is store_manager (procurement officer)
    try:
        if hasattr(user, 'staff'):
            if user.staff.profession in ['store_manager', 'inventory_manager', 'procurement_officer']:
                return True
            # Also check department name for procurement/stores
            if user.staff.department and user.staff.department.name:
                dept = user.staff.department.name.lower()
                if 'procurement' in dept or 'store' in dept:
                    return True
    except:
        pass
    return False


def is_pharmacy_staff(user):
    """Check if user is pharmacy staff (can view but not edit inventory)"""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    # Allow pharmacy staff to view
    try:
        if hasattr(user, 'staff'):
            if user.staff.profession == 'pharmacist':
                return True
    except:
        pass
    # Also allow through groups
    return user.groups.filter(name__in=['Admin', 'Administrator', 'Pharmacy', 'Pharmacist']).exists()


def can_edit_inventory(user):
    """Check if user can edit inventory/stock (admin and procurement/stores staff)."""
    if not user or not user.is_authenticated:
        return False
    return is_admin_user(user) or is_procurement_staff(user)


def can_add_pharmacy_stock(user):
    """Check if user can add pharmacy stock (admin or procurement/stores staff)."""
    if not user or not user.is_authenticated:
        return False
    return is_admin_user(user) or is_procurement_staff(user)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def procurement_dashboard(request):
    """Procurement main dashboard"""
    today = timezone.now().date()
    
    # Store statistics
    try:
        stores = Store.objects.filter(is_active=True, is_deleted=False)
        total_stores = stores.count()
    except Exception as e:
        stores = []
        total_stores = 0
    
    # Inventory summary
    try:
        inventory_stats = InventoryItem.objects.filter(
            is_active=True,
            is_deleted=False
        ).aggregate(
            total_items=Count('id'),
            total_value=Sum(F('quantity_on_hand') * F('unit_cost')),
            low_stock_items=Count('id', filter=Q(quantity_on_hand__lte=F('reorder_level')))
        )
    except Exception as e:
        inventory_stats = {
            'total_items': 0,
            'total_value': 0,
            'low_stock_items': 0
        }
    
    # Procurement requests summary
    try:
        procurement_stats = ProcurementRequest.objects.filter(
            is_deleted=False
        ).aggregate(
            total_requests=Count('id'),
            pending_admin=Count('id', filter=Q(status='submitted')),
            pending_accounts=Count('id', filter=Q(status='admin_approved')),
            pending_payment=Count('id', filter=Q(status='accounts_approved')),
            total_value=Sum('estimated_total')
        )
    except Exception as e:
        procurement_stats = {
            'total_requests': 0,
            'pending_admin': 0,
            'pending_accounts': 0,
            'pending_payment': 0,
            'total_value': 0
        }
    
    # Recent procurement requests
    try:
        recent_requests = ProcurementRequest.objects.filter(
            is_deleted=False
        ).select_related('requested_by_store', 'requested_by').order_by('-created')[:10]
    except Exception as e:
        recent_requests = []
    
    # Low stock items
    try:
        low_stock_items = InventoryItem.objects.filter(
            is_active=True,
            is_deleted=False
        ).annotate(
            total_value=F('quantity_on_hand') * F('unit_cost')
        ).filter(
            quantity_on_hand__lte=F('reorder_level')
        ).select_related('store', 'drug')[:20]
    except Exception as e:
        low_stock_items = []
    
    # Pending store transfers
    try:
        pending_transfers = StoreTransfer.objects.filter(
            status='pending',
            is_deleted=False
        ).select_related('from_store', 'to_store', 'requested_by')[:10]
    except Exception as e:
        pending_transfers = []
    
    # Top suppliers by purchase value
    top_suppliers = []
    top_suppliers_by_items = []
    try:
        from .models_missing_features import PurchaseOrder
        top_suppliers = Supplier.objects.filter(
            is_deleted=False
        ).annotate(
            total_spent=Sum('purchase_orders__total_amount', 
                           filter=Q(purchase_orders__is_deleted=False,
                                   purchase_orders__status__in=['received', 'approved'])),
            order_count=Count('purchase_orders', 
                             filter=Q(purchase_orders__is_deleted=False))
        ).filter(
            total_spent__gt=0
        ).order_by('-total_spent')[:10]
    except Exception as e:
        # If PurchaseOrder doesn't exist or relationship is wrong, use empty list
        top_suppliers = []
    
    # Top suppliers by item count (using Django default related_name: inventoryitem_set)
    try:
        top_suppliers_by_items = Supplier.objects.filter(
            is_deleted=False
        ).annotate(
            items_count=Count('inventoryitem', 
                             filter=Q(inventoryitem__is_deleted=False),
                             distinct=True)
        ).filter(
            items_count__gt=0
        ).order_by('-items_count')[:10]
    except Exception as e:
        # If relationship doesn't exist, use empty list
        top_suppliers_by_items = []
    
    context = {
        'total_stores': total_stores,
        'stores': stores[:5],
        'inventory_stats': inventory_stats,
        'procurement_stats': procurement_stats,
        'recent_requests': recent_requests,
        'low_stock_items': low_stock_items,
        'pending_transfers': pending_transfers,
        'top_suppliers': top_suppliers,
        'top_suppliers_by_items': top_suppliers_by_items,
        'can_add_pharmacy_stock': can_add_pharmacy_stock(request.user),
    }
    return render(request, 'hospital/procurement_dashboard.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def stores_list(request):
    """List all stores with transfer correlation and stats"""
    stores = Store.objects.filter(is_deleted=False).select_related(
        'department', 'manager__user'
    ).annotate(
        item_count=Count('inventory_items', filter=Q(inventory_items__is_deleted=False)),
        total_value=Sum(
            F('inventory_items__quantity_on_hand') * F('inventory_items__unit_cost'),
            filter=Q(inventory_items__is_deleted=False)
        )
    )
    
    store_type_filter = request.GET.get('store_type', '')
    if store_type_filter:
        stores = stores.filter(store_type=store_type_filter)
    
    # Get the active pharmacy store for prescriptions
    active_pharmacy_store = Store.get_pharmacy_store_for_prescriptions()
    
    # Pending transfers count (for guidelines/context)
    pending_transfers_count = StoreTransfer.objects.filter(
        is_deleted=False, status='pending'
    ).count()
    
    # Total inventory value (from inventory items in active, non-deleted stores)
    store_ids = list(stores.values_list('pk', flat=True))
    total_inventory_value = 0
    if store_ids:
        total_inventory_value = InventoryItem.objects.filter(
            store_id__in=store_ids,
            is_deleted=False
        ).aggregate(
            tot=Sum(F('quantity_on_hand') * F('unit_cost'))
        ).get('tot') or 0
    
    context = {
        'stores': stores,
        'store_types': Store.STORE_TYPES,
        'store_type_filter': store_type_filter,
        'active_pharmacy_store': active_pharmacy_store,
        'pending_transfers_count': pending_transfers_count,
        'total_inventory_value': total_inventory_value,
        'can_add_pharmacy_stock': can_add_pharmacy_stock(request.user),
    }
    return render(request, 'hospital/stores_list.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def store_detail(request, pk):
    """Store detail view with inventory and transfer correlation"""
    store = get_object_or_404(Store, pk=pk, is_deleted=False)
    
    inventory_items = InventoryItem.objects.filter(
        store=store,
        is_deleted=False
    ).select_related('drug', 'preferred_supplier').annotate(
        total_value=F('quantity_on_hand') * F('unit_cost')
    ).order_by('item_name')
    
    # Filter options
    search_query = request.GET.get('q', '')
    low_stock_only = request.GET.get('low_stock', '') == '1'
    
    if search_query:
        inventory_items = inventory_items.filter(
            Q(item_name__icontains=search_query) |
            Q(item_code__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    if low_stock_only:
        inventory_items = inventory_items.filter(
            quantity_on_hand__lte=F('reorder_level')
        )
    
    # Check if this store is the one used for prescriptions/dispensing
    active_pharmacy_store = Store.get_pharmacy_store_for_prescriptions()
    is_active_pharmacy_store = active_pharmacy_store and active_pharmacy_store.pk == store.pk
    
    # Recent transfers involving this store (from or to)
    recent_transfers_out = StoreTransfer.objects.filter(
        from_store=store, is_deleted=False
    ).select_related('to_store', 'requested_by__user').order_by('-created')[:5]
    recent_transfers_in = StoreTransfer.objects.filter(
        to_store=store, is_deleted=False
    ).select_related('from_store', 'requested_by__user').order_by('-created')[:5]
    pending_out = StoreTransfer.objects.filter(
        from_store=store, is_deleted=False, status='pending'
    ).count()
    pending_in = StoreTransfer.objects.filter(
        to_store=store, is_deleted=False, status='pending'
    ).count()
    
    # Other stores for "transfer to" destination (exclude current)
    other_stores = Store.objects.filter(
        is_active=True, is_deleted=False
    ).exclude(pk=store.pk).order_by('store_type', 'name')
    
    context = {
        'store': store,
        'inventory_items': inventory_items,
        'search_query': search_query,
        'low_stock_only': low_stock_only,
        'is_active_pharmacy_store': is_active_pharmacy_store,
        'active_pharmacy_store': active_pharmacy_store,
        'recent_transfers_out': recent_transfers_out,
        'recent_transfers_in': recent_transfers_in,
        'pending_out': pending_out,
        'pending_in': pending_in,
        'other_stores': other_stores,
        'can_edit_stock': is_procurement_staff(request.user),
    }
    return render(request, 'hospital/store_detail.html', context)


@login_required
def procurement_requests_list(request):
    """List procurement requests (Pharmacy can view their own, Procurement can view all)"""
    # Check permissions
    if is_procurement_staff(request.user):
        # Procurement can see all requests
        requests = ProcurementRequest.objects.filter(
            is_deleted=False
        ).select_related(
            'requested_by_store', 'requested_by__user',
            'admin_approved_by__user', 'accounts_approved_by__user'
        ).order_by('-request_date', '-created')
    elif is_pharmacy_staff(request.user):
        # Pharmacy can see requests from pharmacy store
        pharmacy_store = Store.objects.filter(store_type='pharmacy').first()
        if pharmacy_store:
            requests = ProcurementRequest.objects.filter(
                requested_by_store=pharmacy_store,
                is_deleted=False
            ).select_related(
                'requested_by_store', 'requested_by__user',
                'admin_approved_by__user', 'accounts_approved_by__user'
            ).order_by('-request_date', '-created')
        else:
            requests = ProcurementRequest.objects.none()
    else:
        messages.error(request, 'You do not have permission to view procurement requests.')
        return redirect('hospital:procurement_dashboard')
    
    # Filters
    status_filter = request.GET.get('status', '')
    store_filter = request.GET.get('store', '')
    
    if status_filter:
        requests = requests.filter(status=status_filter)
    
    if store_filter:
        requests = requests.filter(requested_by_store_id=store_filter)
    
    stores = Store.objects.filter(is_active=True, is_deleted=False)
    
    context = {
        'requests': requests,
        'stores': stores,
        'status_choices': ProcurementRequest.STATUS_CHOICES,
        'status_filter': status_filter,
        'store_filter': store_filter,
        'can_edit': is_procurement_staff(request.user),
    }
    return render(request, 'hospital/procurement_requests_list.html', context)


@login_required
def procurement_request_detail(request, pk):
    """Procurement request detail view (Pharmacy can view their own, Procurement can view all)"""
    req = get_object_or_404(ProcurementRequest.objects.select_related(
        'requested_by_store', 'requested_by__user',
        'admin_approved_by__user', 'accounts_approved_by__user',
        'purchase_order'
    ).prefetch_related('items'), pk=pk, is_deleted=False)
    
    # Check permissions - pharmacy can view their own requests, procurement can view all
    can_view = False
    if is_procurement_staff(request.user):
        can_view = True
    elif is_pharmacy_staff(request.user):
        # Pharmacy can view requests from pharmacy store or requests they created
        try:
            pharmacy_store = Store.objects.filter(store_type='pharmacy').first()
            if pharmacy_store and (req.requested_by_store == pharmacy_store or req.requested_by == request.user.staff):
                can_view = True
        except:
            pass
    
    if not can_view:
        messages.error(request, 'You do not have permission to view this procurement request.')
        return redirect('hospital:pharmacy_dashboard' if is_pharmacy_staff(request.user) else 'hospital:procurement_dashboard')
    
    context = {
        'request': req,
        'items': req.items.filter(is_deleted=False),
        'can_edit': is_procurement_staff(request.user) and req.status == 'draft',
    }
    return render(request, 'hospital/procurement_request_detail.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def store_transfers_list(request):
    """List all store transfers"""
    transfers = StoreTransfer.objects.filter(
        is_deleted=False
    ).select_related(
        'from_store', 'to_store', 'requested_by', 'requested_by__user',
        'approved_by', 'approved_by__user', 'received_by', 'received_by__user'
    ).prefetch_related('lines').order_by('-transfer_date', '-created')
    
    status_filter = request.GET.get('status', '')
    if status_filter:
        transfers = transfers.filter(status=status_filter)
    
    # Statistics
    total_transfers = StoreTransfer.objects.filter(is_deleted=False).count()
    pending_count = StoreTransfer.objects.filter(is_deleted=False, status='pending').count()
    completed_count = StoreTransfer.objects.filter(is_deleted=False, status='completed').count()
    
    context = {
        'transfers': transfers,
        'status_choices': StoreTransfer.STATUS_CHOICES,
        'status_filter': status_filter,
        'total_transfers': total_transfers,
        'pending_count': pending_count,
        'completed_count': completed_count,
    }
    return render(request, 'hospital/store_transfers_list.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def store_transfer_detail(request, pk):
    """Store transfer detail view"""
    transfer = get_object_or_404(StoreTransfer.objects.select_related(
        'from_store', 'to_store', 'requested_by__user',
        'approved_by__user', 'received_by__user'
    ).prefetch_related('lines'), pk=pk, is_deleted=False)
    
    lines = transfer.lines.filter(is_deleted=False)
    # Calculate total value and add line_total to each line for template
    total_value = Decimal('0.00')
    for line in lines:
        line.line_total = line.quantity * line.unit_cost
        total_value += line.line_total
    
    context = {
        'transfer': transfer,
        'lines': lines,
        'total_value': total_value,
    }
    return render(request, 'hospital/store_transfer_detail.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def low_stock_report(request):
    """Low stock items report"""
    low_stock_items = InventoryItem.objects.filter(
        is_active=True,
        is_deleted=False
    ).select_related('store', 'drug', 'preferred_supplier').annotate(
        total_value=F('quantity_on_hand') * F('unit_cost'),
        stock_status=F('quantity_on_hand') - F('reorder_level')
    ).filter(
        quantity_on_hand__lte=F('reorder_level')
    ).order_by('store__name', 'item_name')
    
    store_filter = request.GET.get('store', '')
    if store_filter:
        low_stock_items = low_stock_items.filter(store_id=store_filter)
    
    stores = Store.objects.filter(is_active=True, is_deleted=False)
    
    context = {
        'low_stock_items': low_stock_items,
        'stores': stores,
        'store_filter': store_filter,
    }
    return render(request, 'hospital/low_stock_report.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def suppliers_list(request):
    """List all suppliers"""
    suppliers = Supplier.objects.filter(is_deleted=False).annotate(
        total_orders=Count('purchase_orders', filter=Q(purchase_orders__is_deleted=False)),
        total_spent=Sum('purchase_orders__total_amount', filter=Q(purchase_orders__is_deleted=False)),
        items_count=Count('inventoryitem', filter=Q(inventoryitem__is_deleted=False), distinct=True)
    ).order_by('-total_spent', 'name')
    
    search_query = request.GET.get('q', '')
    if search_query:
        suppliers = suppliers.filter(
            Q(name__icontains=search_query) |
            Q(contact_person__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    context = {
        'suppliers': suppliers,
        'search_query': search_query,
    }
    return render(request, 'hospital/suppliers_list.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def inventory_management(request):
    """Inventory management dashboard"""
    # Inventory summary by store
    inventory_by_store = Store.objects.filter(
        is_active=True,
        is_deleted=False
    ).annotate(
        item_count=Count('inventory_items', filter=Q(inventory_items__is_deleted=False)),
        total_value=Sum(F('inventory_items__quantity_on_hand') * F('inventory_items__unit_cost'),
                       filter=Q(inventory_items__is_deleted=False)),
        low_stock_count=Count('inventory_items', 
                             filter=Q(inventory_items__is_deleted=False,
                                     inventory_items__quantity_on_hand__lte=F('inventory_items__reorder_level')))
    )
    
    # Recent inventory movements (from transfers and procurement)
    recent_transfers = StoreTransfer.objects.filter(
        is_deleted=False
    ).select_related('from_store', 'to_store').order_by('-created')[:10]
    
    recent_procurements = ProcurementRequest.objects.filter(
        is_deleted=False,
        status='received'
    ).select_related('requested_by_store').order_by('-created')[:10]
    
    # Top items by value
    top_items_by_value = InventoryItem.objects.filter(
        is_active=True,
        is_deleted=False
    ).annotate(
        total_value=F('quantity_on_hand') * F('unit_cost')
    ).order_by('-total_value')[:10]
    
    # Inventory aging (items that haven't moved)
    context = {
        'inventory_by_store': inventory_by_store,
        'recent_transfers': recent_transfers,
        'recent_procurements': recent_procurements,
        'top_items_by_value': top_items_by_value,
    }
    return render(request, 'hospital/inventory_management.html', context)


# ==================== CREATE/EDIT VIEWS ====================

@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def supplier_create(request):
    """Create a new supplier"""
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save()
            messages.success(request, f'Supplier "{supplier.name}" created successfully!')
            return redirect('hospital:suppliers_list')
    else:
        form = SupplierForm()
    
    context = {
        'form': form,
        'title': 'Add New Supplier',
    }
    return render(request, 'hospital/procurement_form.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def supplier_edit(request, pk):
    """Edit an existing supplier"""
    supplier = get_object_or_404(Supplier, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            supplier = form.save()
            messages.success(request, f'Supplier "{supplier.name}" updated successfully!')
            return redirect('hospital:suppliers_list')
    else:
        form = SupplierForm(instance=supplier)
    
    context = {
        'form': form,
        'title': f'Edit Supplier: {supplier.name}',
        'object': supplier,
    }
    return render(request, 'hospital/procurement_form.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def store_create(request):
    """Create a new store"""
    if request.method == 'POST':
        form = StoreForm(request.POST)
        if form.is_valid():
            store = form.save()
            messages.success(request, f'Store "{store.name}" created successfully!')
            return redirect('hospital:stores_list')
    else:
        form = StoreForm()
    
    context = {
        'form': form,
        'title': 'Add New Store',
    }
    return render(request, 'hospital/procurement_form.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def store_edit(request, pk):
    """Edit an existing store"""
    store = get_object_or_404(Store, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        form = StoreForm(request.POST, instance=store)
        if form.is_valid():
            store = form.save()
            messages.success(request, f'Store "{store.name}" updated successfully!')
            return redirect('hospital:stores_list')
    else:
        form = StoreForm(instance=store)
    
    context = {
        'form': form,
        'title': f'Edit Store: {store.name}',
        'object': store,
    }
    return render(request, 'hospital/procurement_form.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def inventory_item_create(request):
    """Create a new inventory item"""
    store_id = request.GET.get('store')
    
    if request.method == 'POST':
        form = InventoryItemForm(request.POST)
        if form.is_valid():
            try:
                item = form.save()
                messages.success(request, f'Inventory item "{item.item_name}" created successfully!')
                if store_id:
                    return redirect('hospital:store_detail', pk=store_id)
                return redirect('hospital:procurement_dashboard')
            except ValueError as e:
                # Handle duplicate detection from model save
                messages.error(request, str(e))
                # Show existing items with similar names
                item_name = form.cleaned_data.get('item_name', '')
                store = form.cleaned_data.get('store')
                if store and item_name:
                    similar = InventoryItem.objects.filter(
                        store=store,
                        item_name__icontains=item_name,
                        is_deleted=False
                    )[:5]
                    if similar.exists():
                        messages.info(request, f"Similar items found: {', '.join([s.item_name for s in similar])}")
    else:
        form = InventoryItemForm()
        if store_id:
            try:
                store = Store.objects.get(pk=store_id, is_deleted=False)
                form.fields['store'].initial = store
            except Store.DoesNotExist:
                pass
    
    from hospital.models import Drug
    
    context = {
        'form': form,
        'title': 'Add New Inventory Item',
        'drug_categories': Drug.CATEGORIES,
    }
    return render(request, 'hospital/procurement_form.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def inventory_item_edit(request, pk):
    """Edit an existing inventory item (procurement staff can update stock/cost)."""
    item = get_object_or_404(InventoryItem, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        form = InventoryItemForm(request.POST, instance=item)
        if form.is_valid():
            item = form.save()
            messages.success(request, f'Inventory item "{item.item_name}" updated successfully!')
            return redirect('hospital:store_detail', pk=item.store.pk)
    else:
        form = InventoryItemForm(instance=item)
    
    context = {
        'form': form,
        'title': f'Edit Inventory Item: {item.item_name}',
        'object': item,
    }
    return render(request, 'hospital/procurement_form.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def inventory_item_delete(request, pk):
    """Delete (soft delete) an inventory item"""
    # Require explicit delete permission (so edit-only users can't delete)
    if not (request.user.is_superuser or request.user.has_perm('hospital.delete_inventoryitem')):
        messages.error(request, "You do not have permission to delete inventory items.")
        return redirect('hospital:inventory_management')

    item = get_object_or_404(InventoryItem, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        item_name = item.item_name
        item.is_deleted = True
        item.is_active = False
        item.save()
        messages.success(request, f'Inventory item "{item_name}" has been deleted.')
        return redirect('hospital:inventory_management')
    
    context = {
        'item': item,
        'title': f'Delete Inventory Item: {item.item_name}',
    }
    return render(request, 'hospital/inventory_item_delete_confirm.html', context)


@login_required
def procurement_request_create(request):
    """Create a new procurement request (Pharmacy and Procurement can create)"""
    # Allow pharmacy staff and procurement staff to create requests
    if not (is_procurement_staff(request.user) or is_pharmacy_staff(request.user)):
        messages.error(request, 'You do not have permission to create procurement requests.')
        return redirect('hospital:procurement_dashboard')
    
    # Pre-fill from low stock item if provided
    item_id = request.GET.get('item')
    prefill_item = None
    if item_id:
        try:
            prefill_item = InventoryItem.objects.get(pk=item_id, is_deleted=False)
        except InventoryItem.DoesNotExist:
            pass
    
    if request.method == 'POST':
        action = (request.POST.get('action') or 'save').strip().lower()
        want_submit = action == 'submit'
        form = ProcurementRequestForm(request.POST, user=request.user)
        # Create formset with instance=None for new requests and prefix='items'
        formset = ProcurementRequestItemFormSet(request.POST, instance=None, prefix='items')
        
        # Validate formset
        formset_valid = formset.is_valid()
        has_items = False
        if formset_valid:
            # Determine whether at least one line item is actually provided
            for item_form in formset.forms:
                cd = getattr(item_form, 'cleaned_data', None) or {}
                if cd.get('DELETE'):
                    continue
                item_name = (cd.get('item_name') or '').strip()
                quantity = cd.get('quantity')
                unit_price = cd.get('estimated_unit_price')
                if item_name and quantity and unit_price is not None:
                    has_items = True
                    break

            # For submit, require at least one completed line item.
            # For save (draft), allow saving even with zero items.
            if want_submit and not has_items:
                formset_valid = False
                messages.error(request, 'Add at least one item before submitting the request.')
        
        if form.is_valid() and formset_valid:
            procurement_request = form.save(commit=False)
            # Set requested_by if user has staff profile
            try:
                staff = request.user.staff
                procurement_request.requested_by = staff
            except:
                pass
            procurement_request.status = 'draft'
            procurement_request.save()
            
            # Save formset
            formset.instance = procurement_request
            items = formset.save()
            
            # Ensure item codes are generated for new items (they should auto-generate via save())
            # Item codes will be auto-generated in the model's save() method

            if want_submit:
                procurement_request.submit()
                messages.success(request, f'Procurement request "{procurement_request.request_number}" submitted for approval.')
            else:
                messages.success(request, f'Procurement request "{procurement_request.request_number}" saved as draft.')
            return redirect('hospital:procurement_request_detail', pk=procurement_request.pk)
    else:
        form = ProcurementRequestForm(user=request.user)
        
        # Pre-select pharmacy store if user is pharmacy staff
        if is_pharmacy_staff(request.user):
            pharmacy_store = Store.objects.filter(store_type='pharmacy').first()
            if pharmacy_store:
                form.fields['requested_by_store'].initial = pharmacy_store
        
        # Create empty formset - explicitly pass instance=None and prefix='items'
        formset = ProcurementRequestItemFormSet(instance=None, prefix='items')
        
        # Pre-fill formset with low stock item if provided
        # Note: We can't use initial with inlineformset_factory without an instance
        # So we'll populate the first form manually after formset creation
        if prefill_item:
            # Get the first form and set its initial values
            if formset.forms:
                first_form = formset.forms[0]
                first_form.initial = {
                    'item_name': prefill_item.item_name,
                    'item_code': prefill_item.item_code if prefill_item.item_code else '',
                    'description': prefill_item.description,
                    'drug': prefill_item.drug.pk if prefill_item.drug else None,
                    'quantity': prefill_item.reorder_quantity or prefill_item.reorder_level * 2,
                    'unit_of_measure': prefill_item.unit_of_measure,
                    'estimated_unit_price': float(prefill_item.unit_cost) if prefill_item.unit_cost else 0,
                    'preferred_supplier': prefill_item.preferred_supplier.pk if prefill_item.preferred_supplier else None,
                }
                # Populate the form fields
                for field_name, value in first_form.initial.items():
                    if field_name in first_form.fields:
                        first_form.fields[field_name].initial = value
    
    context = {
        'form': form,
        'formset': formset,
        'title': 'Create Procurement Request',
        'prefill_item': prefill_item,
    }
    return render(request, 'hospital/procurement_request_form.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def procurement_request_edit(request, pk):
    """Edit an existing procurement request (only if in draft)"""
    req = get_object_or_404(ProcurementRequest, pk=pk, is_deleted=False)
    
    if req.status != 'draft':
        messages.warning(request, 'Only draft requests can be edited.')
        return redirect('hospital:procurement_request_detail', pk=req.pk)
    
    if request.method == 'POST':
        action = (request.POST.get('action') or 'save').strip().lower()
        want_submit = action == 'submit'
        form = ProcurementRequestForm(request.POST, instance=req, user=request.user)
        formset = ProcurementRequestItemFormSet(request.POST, instance=req)
        
        if form.is_valid() and formset.is_valid():
            # For submit, require at least one non-deleted line item.
            has_items = False
            for item_form in formset.forms:
                cd = getattr(item_form, 'cleaned_data', None) or {}
                if cd.get('DELETE'):
                    continue
                item_name = (cd.get('item_name') or '').strip()
                quantity = cd.get('quantity')
                unit_price = cd.get('estimated_unit_price')
                if item_name and quantity and unit_price is not None:
                    has_items = True
                    break

            if want_submit and not has_items:
                messages.error(request, 'Add at least one item before submitting the request.')
            else:
                procurement_request = form.save()
                formset.save()
                if want_submit:
                    procurement_request.submit()
                    messages.success(request, f'Procurement request "{procurement_request.request_number}" submitted for approval.')
                else:
                    messages.success(request, f'Procurement request "{procurement_request.request_number}" updated successfully!')
                return redirect('hospital:procurement_request_detail', pk=procurement_request.pk)
    else:
        form = ProcurementRequestForm(instance=req, user=request.user)
        formset = ProcurementRequestItemFormSet(instance=req)
    
    context = {
        'form': form,
        'formset': formset,
        'title': f'Edit Procurement Request: {req.request_number}',
        'object': req,
    }
    return render(request, 'hospital/procurement_request_form.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def store_transfer_create(request):
    """
    Redirect to the inventory-based transfer form (create_transfer_modern).
    Transfers must be created from actual store inventory so quantities and items stay in sync.
    """
    from django.urls import reverse
    url = reverse('hospital:create_transfer_modern')
    if request.GET:
        url += '?' + request.GET.urlencode()
    return redirect(url)


@login_required
def pharmacy_procurement_requests(request):
    """Pharmacy view of their procurement requests"""
    pharmacy_store = Store.objects.filter(store_type='pharmacy', is_deleted=False).first()
    
    if not pharmacy_store:
        messages.warning(request, 'No pharmacy store found. Please create one in admin.')
        return redirect('hospital:pharmacy_dashboard')
    
    requests = ProcurementRequest.objects.filter(
        requested_by_store=pharmacy_store,
        is_deleted=False
    ).select_related(
        'requested_by__user',
        'admin_approved_by__user',
        'accounts_approved_by__user'
    ).prefetch_related('items').order_by('-created')
    
    total_requests = requests.count()
    pending_requests = requests.filter(status='submitted').count()
    approved_requests = requests.filter(status__in=['admin_approved', 'accounts_approved']).count()
    received_requests = requests.filter(status='received').count()
    
    context = {
        'requests': list(requests[:50]),
        'total_requests': total_requests,
        'pending_requests': pending_requests,
        'approved_requests': approved_requests,
        'received_requests': received_requests,
        'pharmacy_store': pharmacy_store,
    }
    
    return render(request, 'hospital/pharmacy_procurement_worldclass.html', context)


@login_required
def pharmacy_request_create(request):
    """Create new procurement request from pharmacy"""
    pharmacy_store = Store.objects.filter(store_type='pharmacy', is_deleted=False).first()
    
    if not pharmacy_store:
        messages.error(request, 'No pharmacy store configured.')
        return redirect('hospital:pharmacy_dashboard')
    
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('hospital:pharmacy_dashboard')
    
    if request.method == 'POST':
        priority = request.POST.get('priority', 'normal')
        justification = request.POST.get('justification', '')
        
        procurement_request = ProcurementRequest.objects.create(
            requested_by_store=pharmacy_store,
            requested_by=staff,
            priority=priority,
            status='draft',
            justification=justification
        )
        
        item_names = request.POST.getlist('item_name[]')
        item_quantities = request.POST.getlist('item_quantity[]')
        item_prices = request.POST.getlist('item_price[]')
        
        for i in range(len(item_names)):
            if item_names[i]:
                ProcurementRequestItem.objects.create(
                    request=procurement_request,
                    item_name=item_names[i],
                    quantity=int(item_quantities[i]) if item_quantities[i] else 1,
                    estimated_unit_price=float(item_prices[i]) if item_prices[i] else 0,
                    unit_of_measure='units'
                )
        
        procurement_request.save()
        
        messages.success(request, f'Procurement request {procurement_request.request_number} created successfully!')
        return redirect('hospital:pharmacy_procurement_requests')
    
    context = {
        'pharmacy_store': pharmacy_store,
    }
    
    return render(request, 'hospital/pharmacy_request_create.html', context)


@login_required
def submit_procurement_request(request, pk):
    """Submit procurement request for approval"""
    proc_request = get_object_or_404(ProcurementRequest, pk=pk, is_deleted=False)
    
    if proc_request.status == 'draft':
        proc_request.submit()
        messages.success(request, f'Request {proc_request.request_number} submitted for approval.')
    else:
        messages.warning(request, 'Request has already been submitted.')
    
    return redirect('hospital:pharmacy_procurement_requests')


@login_required
def approve_procurement_request(request, pk):
    """Approve procurement request"""
    proc_request = get_object_or_404(ProcurementRequest, pk=pk, is_deleted=False)
    
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'Staff profile required')
        return redirect('hospital:procurement_requests_list')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'admin_approve' and proc_request.status == 'submitted':
            proc_request.approve_by_admin(staff)
            messages.success(request, 'Request approved by admin.')
        elif action == 'accounts_approve' and proc_request.status == 'admin_approved':
            proc_request.approve_by_accounts(staff)
            messages.success(request, 'Request approved by accounts.')
        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '')
            if proc_request.status == 'submitted':
                proc_request.reject_by_admin(staff, reason)
            else:
                proc_request.reject_by_accounts(staff, reason)
            messages.success(request, 'Request rejected.')
    
    return redirect('hospital:procurement_request_detail', pk=pk)


@login_required
def mark_request_received(request, pk):
    """Mark procurement request as received and update inventory"""
    proc_request = get_object_or_404(ProcurementRequest, pk=pk, is_deleted=False)
    
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        staff = None
    
    if proc_request.status in ['accounts_approved', 'ordered', 'payment_processed']:
        proc_request.mark_as_received(staff)
        messages.success(request, f'Request {proc_request.request_number} marked as received. Inventory updated!')
    else:
        messages.warning(request, 'Request must be approved before receiving.')
    
    return redirect('hospital:pharmacy_procurement_requests')




"""
Enhanced Procurement Request Views
Pharmacy to Procurement workflow
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, F
from django.utils import timezone

from .models_procurement import ProcurementRequest, ProcurementRequestItem, Store
from .models import Staff


@login_required
def pharmacy_procurement_requests(request):
    """Pharmacy view of their procurement requests"""
    # Get pharmacy store
    pharmacy_store = Store.objects.filter(store_type='pharmacy', is_deleted=False).first()
    
    if not pharmacy_store:
        messages.warning(request, 'No pharmacy store found. Please create one in admin.')
        return redirect('hospital:pharmacy_dashboard')
    
    # Get requests from pharmacy store
    requests = ProcurementRequest.objects.filter(
        requested_by_store=pharmacy_store,
        is_deleted=False
    ).select_related(
        'requested_by__user',
        'admin_approved_by__user',
        'accounts_approved_by__user'
    ).prefetch_related('items').order_by('-created')
    
    # Calculate statistics
    total_requests = requests.count()
    pending_requests = requests.filter(status='submitted').count()
    approved_requests = requests.filter(status__in=['admin_approved', 'accounts_approved']).count()
    received_requests = requests.filter(status='received').count()
    
    context = {
        'requests': list(requests[:50]),
        'total_requests': total_requests,
        'pending_requests': pending_requests,
        'approved_requests': approved_requests,
        'received_requests': received_requests,
        'pharmacy_store': pharmacy_store,
    }
    
    return render(request, 'hospital/pharmacy_procurement_worldclass.html', context)


@login_required
def pharmacy_request_create(request):
    """Create new procurement request from pharmacy"""
    # Get pharmacy store
    pharmacy_store = Store.objects.filter(store_type='pharmacy', is_deleted=False).first()
    
    if not pharmacy_store:
        messages.error(request, 'No pharmacy store configured.')
        return redirect('hospital:pharmacy_dashboard')
    
    # Get current staff
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('hospital:pharmacy_dashboard')
    
    if request.method == 'POST':
        # Create procurement request
        priority = request.POST.get('priority', 'normal')
        justification = request.POST.get('justification', '')
        
        procurement_request = ProcurementRequest.objects.create(
            requested_by_store=pharmacy_store,
            requested_by=staff,
            priority=priority,
            status='draft',
            justification=justification
        )
        
        # Add items
        item_names = request.POST.getlist('item_name[]')
        item_quantities = request.POST.getlist('item_quantity[]')
        item_prices = request.POST.getlist('item_price[]')
        
        for i in range(len(item_names)):
            if item_names[i]:
                ProcurementRequestItem.objects.create(
                    request=procurement_request,
                    item_name=item_names[i],
                    quantity=int(item_quantities[i]) if item_quantities[i] else 1,
                    estimated_unit_price=float(item_prices[i]) if item_prices[i] else 0,
                    unit_of_measure='units'
                )
        
        # Recalculate total
        procurement_request.save()  # Triggers auto-calculation
        
        messages.success(request, f'Procurement request {procurement_request.request_number} created successfully!')
        return redirect('hospital:pharmacy_procurement_requests')
    
    from hospital.models import Drug
    
    context = {
        'pharmacy_store': pharmacy_store,
        'drug_categories': Drug.CATEGORIES,
    }
    
    return render(request, 'hospital/pharmacy_request_create.html', context)


@login_required
def submit_procurement_request(request, pk):
    """Submit procurement request for approval"""
    proc_request = get_object_or_404(ProcurementRequest, pk=pk, is_deleted=False)
    
    if proc_request.status == 'draft':
        proc_request.submit()
        messages.success(request, f'Request {proc_request.request_number} submitted for approval.')
    else:
        messages.warning(request, 'Request has already been submitted.')
    
    return redirect('hospital:pharmacy_procurement_requests')


@login_required  
def approve_procurement_request(request, pk):
    """Approve procurement request (admin/accounts)"""
    proc_request = get_object_or_404(ProcurementRequest, pk=pk, is_deleted=False)
    
    # Get current staff
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'Staff profile required')
        return redirect('hospital:procurement_requests_list')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'admin_approve' and proc_request.status == 'submitted':
            proc_request.approve_by_admin(staff)
            messages.success(request, 'Request approved by admin.')
        elif action == 'accounts_approve' and proc_request.status == 'admin_approved':
            proc_request.approve_by_accounts(staff)
            messages.success(request, 'Request approved by accounts.')
        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '')
            if proc_request.status == 'submitted':
                proc_request.reject_by_admin(staff, reason)
            else:
                proc_request.reject_by_accounts(staff, reason)
            messages.success(request, 'Request rejected.')
    
    return redirect('hospital:procurement_request_detail', pk=pk)


@login_required
def mark_request_received(request, pk):
    """Mark procurement request as received and update inventory"""
    proc_request = get_object_or_404(ProcurementRequest, pk=pk, is_deleted=False)
    
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        staff = None
    
    if proc_request.status in ['accounts_approved', 'ordered', 'payment_processed']:
        proc_request.mark_as_received(staff)
        messages.success(request, f'Request {proc_request.request_number} marked as received. Inventory updated!')
    else:
        messages.warning(request, 'Request must be approved before receiving.')
    
    return redirect('hospital:pharmacy_procurement_requests')


