"""
Views for Inventory Managers to add reagents via procurement system
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from decimal import Decimal

from django.contrib.auth.decorators import user_passes_test

from .models import Staff
from .models_lab_management import LabReagent
from .models_procurement import ProcurementRequest, ProcurementRequestItem, Store, InventoryItem, InventoryCategory


def is_inventory_manager(user):
    """Check if user is inventory manager or procurement staff"""
    if not user.is_authenticated:
        return False
    try:
        staff = user.staff_profile
        return staff and (staff.profession.lower() in ['inventory_manager', 'procurement', 'store_manager', 'pharmacist'] or user.is_staff)
    except:
        return user.is_staff


@login_required
@user_passes_test(is_inventory_manager, login_url='/admin/login/')
def add_reagent_via_procurement(request):
    """Create procurement request for reagent (goes through approval workflow)"""
    if request.method == 'POST':
        try:
            import json
            
            # Get staff
            staff = request.user.staff_profile if hasattr(request.user, 'staff_profile') else None
            if not staff:
                messages.error(request, 'Staff profile not found.')
                return redirect('hospital:lab_reagent_dashboard')
            
            # Get or create Lab Store
            lab_store, _ = Store.objects.get_or_create(
                name='Laboratory Store',
                defaults={
                    'code': 'LAB',
                    'location': 'Laboratory',
                    'store_type': 'laboratory',
                }
            )
            
            # Get supplier if provided
            supplier_id = request.POST.get('supplier') or None
            supplier = None
            if supplier_id:
                from .models_procurement import Supplier
                try:
                    supplier = Supplier.objects.get(pk=supplier_id, is_deleted=False)
                except Supplier.DoesNotExist:
                    pass
            
            # Create procurement request
            priority = request.POST.get('priority', 'normal')
            justification = request.POST.get('justification', f'Reagent request: {request.POST.get("name")}')
            
            procurement_request = ProcurementRequest.objects.create(
                requested_by_store=lab_store,
                requested_by=staff,
                priority=priority,
                status='draft',  # Start as draft, user can submit later
                justification=justification
            )
            
            # Store reagent-specific metadata in specifications as JSON
            reagent_metadata = {
                'category': request.POST.get('category', 'reagent'),
                'manufacturer': request.POST.get('manufacturer', ''),
                'catalog_number': request.POST.get('catalog_number', ''),
                'batch_number': request.POST.get('batch_number', ''),
                'expiry_date': request.POST.get('expiry_date', ''),
                'storage_conditions': request.POST.get('storage_conditions', ''),
                'location': request.POST.get('location', ''),
                'reorder_level': request.POST.get('reorder_level', '0'),
                'reorder_quantity': request.POST.get('reorder_quantity', '0'),
                'is_lab_reagent': True,  # Flag to identify lab reagent requests
            }
            
            # Create procurement request item
            quantity = int(Decimal(request.POST.get('quantity_on_hand', '0')))
            unit_price = Decimal(request.POST.get('unit_cost', '0'))
            
            ProcurementRequestItem.objects.create(
                request=procurement_request,
                item_name=request.POST.get('name'),
                item_code=request.POST.get('item_code', ''),
                description=request.POST.get('description', ''),
                quantity=quantity,
                unit_of_measure=request.POST.get('unit', 'bottle'),
                estimated_unit_price=unit_price,
                line_total=quantity * unit_price,
                specifications=json.dumps(reagent_metadata),  # Store reagent metadata
                preferred_supplier=supplier,
            )
            
            # Recalculate total
            procurement_request.save()
            
            messages.success(
                request, 
                f'Procurement request {procurement_request.request_number} created for reagent "{request.POST.get("name")}". '
                f'Please submit it for approval to proceed with procurement.'
            )
            return redirect('hospital:lab_reagent_dashboard')
            
        except Exception as e:
            messages.error(request, f'Error creating procurement request: {str(e)}')
    
    # GET request - show form
    from .models_procurement import Supplier
    suppliers = Supplier.objects.filter(is_deleted=False)
    stores = Store.objects.filter(is_deleted=False, store_type__in=['laboratory', 'general'])
    
    context = {
        'suppliers': suppliers,
        'stores': stores,
    }
    return render(request, 'hospital/add_reagent_via_procurement.html', context)


@login_required
@user_passes_test(is_inventory_manager, login_url='/admin/login/')
def sync_reagent_from_inventory(request, reagent_id):
    """Sync reagent quantity from linked inventory item"""
    reagent = get_object_or_404(LabReagent, pk=reagent_id, is_deleted=False)
    
    if reagent.inventory_item_id:
        try:
            from .models_procurement import InventoryItem
            inventory_item = InventoryItem.objects.get(pk=reagent.inventory_item_id, is_deleted=False)
            # Sync quantity from inventory (convert int to Decimal)
            reagent.quantity_on_hand = Decimal(str(inventory_item.quantity_on_hand))
            reagent.unit_cost = inventory_item.unit_cost
            reagent.save()
            messages.success(request, f'Reagent "{reagent.name}" synced with inventory.')
        except InventoryItem.DoesNotExist:
            messages.warning(request, 'Linked inventory item not found.')
    else:
        messages.warning(request, 'Reagent is not linked to an inventory item.')
    
    return redirect('hospital:lab_reagent_dashboard')










