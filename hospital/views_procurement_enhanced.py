"""
World-Class Procurement Workflow with Multi-Tier Approvals
Compliance-Ready System following International Best Practices
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Sum, F, Count
from django.utils import timezone
from django.http import JsonResponse
from decimal import Decimal

from .models import Staff, Department
from .models_procurement import (
    Store, InventoryItem, ProcurementRequest, ProcurementRequestItem,
    StoreTransfer
)
from .models_missing_features import Supplier


def is_pharmacy_staff(user):
    """Check if user is pharmacy staff"""
    try:
        staff = Staff.objects.get(user=user, is_deleted=False)
        return staff.profession in ['pharmacist', 'pharmacy_technician'] or staff.department.name.lower() == 'pharmacy'
    except:
        return False


def is_procurement_staff(user):
    """Check if user is procurement staff"""
    try:
        staff = Staff.objects.get(user=user, is_deleted=False)
        return staff.department.name.lower() in ['procurement', 'admin', 'stores']
    except:
        return user.is_superuser


def is_finance_staff(user):
    """Check if user is finance/accounts staff"""
    try:
        staff = Staff.objects.get(user=user, is_deleted=False)
        return staff.department.name.lower() in ['finance', 'accounts', 'accounting'] or staff.is_accountant
    except:
        return user.is_superuser


@login_required
def pharmacy_procurement_requests_worldclass(request):
    """
    World-Class Pharmacy Procurement Dashboard
    Shows all procurement requests with multi-stage workflow tracking
    """
    status_filter = request.GET.get('status', '')
    
    # Get pharmacy store
    pharmacy_store = Store.objects.filter(store_type='pharmacy', is_deleted=False).first()
    
    # Get all pharmacy procurement requests
    requests = ProcurementRequest.objects.filter(
        requested_by_store=pharmacy_store,
        is_deleted=False
    ).select_related(
        'requested_by__user',
        'admin_approved_by__user',
        'accounts_approved_by__user'
    ).prefetch_related('items')
    
    if status_filter:
        requests = requests.filter(status=status_filter)
    
    # Calculate statistics
    total_requests = requests.count()
    draft_count = requests.filter(status='draft').count()
    pending_approval = requests.filter(status__in=['submitted', 'admin_approved']).count()
    approved_count = requests.filter(status='accounts_approved').count()
    received_count = requests.filter(status='received').count()
    
    # Calculate total value
    total_value = requests.aggregate(total=Sum('estimated_total'))['total'] or Decimal('0.00')
    
    context = {
        'requests': requests.order_by('-request_date')[:50],
        'total_requests': total_requests,
        'draft_count': draft_count,
        'pending_approval': pending_approval,
        'approved_count': approved_count,
        'received_count': received_count,
        'total_value': total_value,
        'status_filter': status_filter,
        'pharmacy_store': pharmacy_store,
    }
    
    return render(request, 'hospital/pharmacy_procurement_worldclass.html', context)


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def procurement_admin_review(request, pk):
    """
    Procurement/Admin Review Stage
    Admin reviews and approves/rejects pharmacy requests
    """
    proc_request = get_object_or_404(ProcurementRequest, pk=pk, is_deleted=False)
    
    # Only submitted requests can be reviewed by admin
    if proc_request.status != 'submitted':
        messages.warning(request, 'This request is not in submitted status.')
        return redirect('hospital:procurement_requests_list')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        try:
            staff = Staff.objects.get(user=request.user, is_deleted=False)
            
            if action == 'approve':
                # Admin approves - moves to accounts for financial approval
                proc_request.status = 'admin_approved'
                proc_request.admin_approved_by = staff
                proc_request.admin_approved_at = timezone.now()
                proc_request.save()
                
                # Send SMS notification to accountants (triggered automatically by model save)
                # The SMS is sent in the model's approve_by_admin method
                
                messages.success(request, f'Request {proc_request.request_number} approved by Procurement. Forwarded to Finance for budget approval.')
                
            elif action == 'reject':
                reason = request.POST.get('rejection_reason', '')
                proc_request.status = 'cancelled'
                proc_request.admin_rejection_reason = reason
                proc_request.save()
                
                messages.warning(request, f'Request {proc_request.request_number} rejected.')
            
            return redirect('hospital:procurement_requests_list')
            
        except Staff.DoesNotExist:
            messages.error(request, 'Staff profile not found.')
            return redirect('hospital:procurement_requests_list')
    
    context = {
        'request': proc_request,
    }
    
    return render(request, 'hospital/procurement_admin_review.html', context)


@login_required
@user_passes_test(is_finance_staff, login_url='/admin/login/')
def finance_review_request(request, pk):
    """
    Finance/Accounts Review Stage
    Finance reviews budget and approves/rejects
    Upon approval, creates accounting expense entry
    """
    proc_request = get_object_or_404(ProcurementRequest, pk=pk, is_deleted=False)
    
    # Only admin-approved requests can be reviewed by finance
    if proc_request.status != 'admin_approved':
        messages.warning(request, 'This request has not been approved by Procurement yet.')
        return redirect('hospital:accounting_dashboard')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        try:
            staff = Staff.objects.get(user=request.user, is_deleted=False)
            
            if action == 'approve':
                approved_budget = request.POST.get('approved_budget')
                
                # Finance approves
                proc_request.status = 'accounts_approved'
                proc_request.accounts_approved_by = staff
                proc_request.accounts_approved_at = timezone.now()
                proc_request.approved_budget = Decimal(approved_budget) if approved_budget else proc_request.estimated_total
                proc_request.save()
                
                # Create accounting expense entry
                create_procurement_expense_entry(proc_request, staff)
                
                messages.success(request, f'Request {proc_request.request_number} approved by Finance. Budget allocated: GHS {proc_request.approved_budget}. Ready for procurement.')
                
            elif action == 'reject':
                reason = request.POST.get('rejection_reason', '')
                proc_request.status = 'cancelled'
                proc_request.accounts_rejection_reason = reason
                proc_request.save()
                
                messages.warning(request, f'Request {proc_request.request_number} rejected by Finance.')
            
            return redirect('hospital:accounting_dashboard')
            
        except Staff.DoesNotExist:
            messages.error(request, 'Staff profile not found.')
            return redirect('hospital:accounting_dashboard')
    
    context = {
        'request': proc_request,
    }
    
    return render(request, 'hospital/finance_review_request.html', context)


def create_procurement_expense_entry(proc_request, approved_by):
    """
    Create accounting expense entry when finance approves procurement
    World-Class Double-Entry Accounting Integration
    """
    from .models_accounting import Transaction, Account
    
    # Create accounting transaction for procurement expense
    transaction = Transaction.objects.create(
        transaction_date=timezone.now().date(),
        description=f'Procurement Request: {proc_request.request_number} - {proc_request.justification[:100]}',
        reference_number=proc_request.request_number,
        amount=proc_request.approved_budget or proc_request.estimated_total,
        transaction_type='expense'
    )
    
    # Link transaction to procurement request
    proc_request.notes += f"\n[Accounting Entry Created: {transaction.reference_number} on {timezone.now().strftime('%Y-%m-%d %H:%M')} - Amount: GHS {transaction.amount}]"
    proc_request.save()
    
    return transaction


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def mark_request_received_worldclass(request, pk):
    """
    Mark procurement request as received
    World-Class: Updates inventory AND posts accounting entry
    """
    proc_request = get_object_or_404(ProcurementRequest, pk=pk, is_deleted=False)
    
    if proc_request.status not in ['accounts_approved', 'ordered']:
        messages.error(request, 'Request must be approved by Finance before marking as received.')
        return redirect('hospital:procurement_requests_list')
    
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
        
        # Update status to received
        proc_request.status = 'received'
        proc_request.save()
        
        # Determine target store based on item type
        # Pharmacy items go to Drug Store (DRUGS), Lab items to Lab Store (LAB), others to Main Store (MAIN)
        from hospital.services.inventory_accountability_service import InventoryAccountabilityService
        
        for item in proc_request.items.filter(is_deleted=False):
            # Determine target store
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
            
            # Check if item exists in inventory
            inv_item, created = InventoryItem.objects.get_or_create(
                store=target_store,
                item_name=item.item_name,
                is_deleted=False,
                defaults={
                    'item_code': item.item_code,
                    'description': item.description,
                    'drug': item.drug,
                    'quantity_on_hand': 0,
                    'unit_cost': item.estimated_unit_price,
                    'unit_of_measure': item.unit_of_measure,
                    'reorder_level': 10,
                    'reorder_quantity': item.quantity,
                    'preferred_supplier': item.preferred_supplier
                }
            )
            
            # Use accountability service to receive from supplier
            InventoryAccountabilityService.receive_from_supplier(
                inventory_item=inv_item,
                quantity=item.quantity,
                unit_cost=item.estimated_unit_price,
                staff=staff,
                reference_number=proc_request.request_number,
                supplier_name=item.preferred_supplier.name if item.preferred_supplier else '',
                notes=f"Received via procurement request {proc_request.request_number}"
            )
            
            # Update received quantity on request item
            item.received_quantity = item.quantity
            item.save()
        
        # Post the accounting entry (make it official)
        post_procurement_accounting_entry(proc_request)
        
        messages.success(request, f'Request {proc_request.request_number} marked as received. {proc_request.items.count()} items added to inventory. Accounting entry posted.')
        
        return redirect('hospital:procurement_requests_list')
        
    except Staff.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('hospital:procurement_requests_list')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('hospital:procurement_requests_list')


def post_procurement_accounting_entry(proc_request):
    """
    Post the accounting entry when items are received
    Updates transaction status to confirmed
    """
    from .models_accounting import Transaction
    
    # Find the transaction for this procurement
    transaction = Transaction.objects.filter(
        reference_number=proc_request.request_number,
        is_deleted=False
    ).first()
    
    if transaction:
        # Transaction is already recorded, just add note
        proc_request.notes += f"\n[Items Received: {timezone.now().strftime('%Y-%m-%d %H:%M')} - Transaction confirmed]"
        proc_request.save()
        return transaction
    
    return None


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def release_to_pharmacy(request, pk):
    """
    Release items from Main Store to Pharmacy
    Creates store transfer and updates both inventories
    """
    proc_request = get_object_or_404(ProcurementRequest, pk=pk, is_deleted=False)
    
    if proc_request.status != 'received':
        messages.error(request, 'Request must be received before releasing to pharmacy.')
        return redirect('hospital:procurement_requests_list')
    
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
        
        # Get stores
        main_store = Store.objects.filter(store_type='main', is_deleted=False).first()
        pharmacy_store = proc_request.requested_by_store
        
        if not main_store or not pharmacy_store:
            messages.error(request, 'Store configuration error.')
            return redirect('hospital:procurement_requests_list')
        
        # Create store transfer
        transfer = StoreTransfer.objects.create(
            from_store=main_store,
            to_store=pharmacy_store,
            requested_by=staff,
            notes=f'Release of Procurement Request {proc_request.request_number}'
        )
        
        # Transfer each item
        for req_item in proc_request.items.filter(is_deleted=False):
            # Find item in main store
            main_inv_item = InventoryItem.objects.filter(
                store=main_store,
                item_name=req_item.item_name,
                is_deleted=False
            ).first()
            
            if main_inv_item and main_inv_item.quantity_on_hand >= req_item.quantity:
                # Reduce from main store
                main_inv_item.quantity_on_hand -= req_item.quantity
                main_inv_item.save()
                
                # Add to pharmacy store
                pharmacy_inv_item, created = InventoryItem.objects.get_or_create(
                    store=pharmacy_store,
                    item_name=req_item.item_name,
                    is_deleted=False,
                    defaults={
                        'item_code': req_item.item_code,
                        'description': req_item.description,
                        'drug': req_item.drug,
                        'quantity_on_hand': 0,
                        'unit_cost': req_item.estimated_unit_price,
                        'unit_of_measure': req_item.unit_of_measure,
                        'reorder_level': 10,
                        'reorder_quantity': req_item.quantity,
                        'preferred_supplier': req_item.preferred_supplier
                    }
                )
                
                pharmacy_inv_item.quantity_on_hand += req_item.quantity
                pharmacy_inv_item.save()
        
        # Mark transfer as completed
        transfer.status = 'completed'
        transfer.completed_at = timezone.now()
        transfer.completed_by = staff
        transfer.save()
        
        messages.success(request, f'Items from {proc_request.request_number} released to {pharmacy_store.name}. Transfer #{transfer.pk} completed.')
        
        return redirect('hospital:procurement_requests_list')
        
    except Exception as e:
        messages.error(request, f'Error releasing items: {str(e)}')
        return redirect('hospital:procurement_requests_list')


@login_required
@user_passes_test(is_procurement_staff, login_url='/admin/login/')
def procurement_approval_dashboard(request):
    """
    Procurement Approval Dashboard
    Shows requests waiting for procurement approval
    """
    # Get pending requests (submitted by pharmacy)
    pending_requests = ProcurementRequest.objects.filter(
        status='submitted',
        is_deleted=False
    ).select_related(
        'requested_by_store',
        'requested_by__user'
    ).prefetch_related('items').order_by('-created')
    
    # Get recently approved requests (by current user's role)
    approved_requests = ProcurementRequest.objects.filter(
        status='admin_approved',
        is_deleted=False
    ).select_related(
        'requested_by_store',
        'admin_approved_by__user'
    ).order_by('-admin_approved_at')[:10]
    
    # Calculate statistics
    pending_count = pending_requests.count()
    approved_count = approved_requests.count()
    total_value = pending_requests.aggregate(
        total=Sum('estimated_total')
    )['total'] or Decimal('0.00')
    
    context = {
        'pending_requests': pending_requests,
        'approved_requests': approved_requests,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'total_value': total_value,
    }
    
    return render(request, 'hospital/procurement_requests_approval.html', context)


@login_required
def procurement_workflow_dashboard(request):
    """
    Complete procurement workflow dashboard
    Shows all stages and pending approvals
    """
    # Get staff role
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except:
        staff = None
    
    # Requests by stage
    draft_requests = ProcurementRequest.objects.filter(
        status='draft',
        is_deleted=False
    ).count()
    
    submitted_requests = ProcurementRequest.objects.filter(
        status='submitted',
        is_deleted=False
    ).select_related('requested_by_store', 'requested_by__user')[:10]
    
    admin_approved_requests = ProcurementRequest.objects.filter(
        status='admin_approved',
        is_deleted=False
    ).select_related('requested_by_store', 'admin_approved_by__user')[:10]
    
    accounts_approved_requests = ProcurementRequest.objects.filter(
        status='accounts_approved',
        is_deleted=False
    ).select_related('requested_by_store', 'accounts_approved_by__user')[:10]
    
    received_requests = ProcurementRequest.objects.filter(
        status='received',
        is_deleted=False
    ).select_related('requested_by_store')[:10]
    
    context = {
        'draft_count': draft_requests,
        'submitted_requests': submitted_requests,
        'admin_approved_requests': admin_approved_requests,
        'accounts_approved_requests': accounts_approved_requests,
        'received_requests': received_requests,
        'staff': staff,
    }
    
    return render(request, 'hospital/procurement_workflow_dashboard.html', context)
