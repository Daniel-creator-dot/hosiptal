"""
Procurement Approval Workflow Views
Complete P2P (Procure-to-Pay) system with role-based approvals
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum
from django.http import JsonResponse
from decimal import Decimal

from .models_procurement import ProcurementRequest, ProcurementRequestItem
from .procurement_accounting_integration import auto_create_accounting_on_approval


# ==================== PROCUREMENT STAFF VIEWS ====================

@login_required
def procurement_dashboard(request):
    """
    Dashboard for procurement staff
    Shows all requests and their status
    """
    # Get all procurement requests
    my_requests = ProcurementRequest.objects.filter(
        requested_by=request.user.staff if hasattr(request.user, 'staff') else None,
        is_deleted=False
    ).order_by('-created')
    
    # Get summary counts
    draft_count = my_requests.filter(status='draft').count()
    submitted_count = my_requests.filter(status='submitted').count()
    approved_count = my_requests.filter(status__in=['admin_approved', 'accounts_approved']).count()
    rejected_count = my_requests.filter(status='cancelled').count()
    
    # Get pending approvals (if user is approver)
    pending_approvals = ProcurementRequest.objects.filter(
        is_deleted=False
    ).exclude(
        status__in=['draft', 'cancelled', 'received']
    ).order_by('-created')[:10]
    
    context = {
        'my_requests': my_requests[:20],
        'draft_count': draft_count,
        'submitted_count': submitted_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'pending_approvals': pending_approvals,
    }
    
    return render(request, 'hospital/procurement/dashboard.html', context)


@login_required
def create_procurement_request(request):
    """
    Create new procurement request
    Anyone can create a request
    """
    if request.method == 'POST':
        try:
            # Create the request
            pr = ProcurementRequest.objects.create(
                requested_by_store=request.user.staff.store if hasattr(request.user, 'staff') and hasattr(request.user.staff, 'store') else None,
                requested_by=request.user.staff if hasattr(request.user, 'staff') else None,
                priority=request.POST.get('priority', 'normal'),
                justification=request.POST.get('justification', ''),
                notes=request.POST.get('notes', ''),
                status='draft'
            )
            
            # Add items
            item_count = int(request.POST.get('item_count', 0))
            for i in range(item_count):
                item_name = request.POST.get(f'item_name_{i}')
                quantity = request.POST.get(f'quantity_{i}')
                unit_price = request.POST.get(f'unit_price_{i}')
                
                if item_name and quantity:
                    ProcurementRequestItem.objects.create(
                        request=pr,
                        item_name=item_name,
                        quantity=int(quantity),
                        estimated_unit_price=Decimal(unit_price or 0),
                        line_total=int(quantity) * Decimal(unit_price or 0)
                    )
            
            messages.success(request, f'Procurement request {pr.request_number} created successfully!')
            return redirect('hospital:procurement_detail', pr_id=pr.id)
        
        except Exception as e:
            messages.error(request, f'Error creating request: {e}')
    
    return render(request, 'hospital/procurement/create_request.html')


@login_required
def submit_procurement_request(request, pr_id):
    """
    Submit procurement request for approval
    Changes status from 'draft' to 'submitted'
    """
    pr = get_object_or_404(ProcurementRequest, id=pr_id, is_deleted=False)
    
    # Check permission
    if hasattr(request.user, 'staff') and pr.requested_by != request.user.staff:
        messages.error(request, 'You can only submit your own requests')
        return redirect('hospital:procurement_dashboard')
    
    if pr.status != 'draft':
        messages.error(request, 'Only draft requests can be submitted')
        return redirect('hospital:procurement_detail', pr_id=pr.id)
    
    # Check if has items
    if not pr.items.exists():
        messages.error(request, 'Please add at least one item before submitting')
        return redirect('hospital:procurement_detail', pr_id=pr.id)
    
    # Submit
    pr.status = 'submitted'
    pr.submitted_date = timezone.now()
    pr.save()
    
    messages.success(request, f'Request {pr.request_number} submitted for approval!')
    return redirect('hospital:procurement_detail', pr_id=pr.id)


# ==================== ADMINISTRATOR APPROVAL ====================

@login_required
@permission_required('hospital.can_approve_procurement_admin', raise_exception=True)
def admin_approval_list(request):
    """
    List of procurement requests pending admin approval
    Only administrators can access
    """
    pending_requests = ProcurementRequest.objects.filter(
        status='submitted',
        is_deleted=False
    ).order_by('-created')
    
    context = {
        'pending_requests': pending_requests,
        'approval_type': 'Administrator',
    }
    
    return render(request, 'hospital/procurement/approval_list.html', context)


@login_required
@permission_required('hospital.can_approve_procurement_admin', raise_exception=True)
def approve_admin(request, pr_id):
    """
    Administrator approves procurement request
    Changes status from 'submitted' to 'admin_approved'
    """
    pr = get_object_or_404(ProcurementRequest, id=pr_id, is_deleted=False)
    
    if pr.status != 'submitted':
        messages.error(request, 'This request is not pending admin approval')
        return redirect('hospital:admin_approval_list')
    
    if request.method == 'POST':
        comments = request.POST.get('comments', '')
        
        # Approve
        pr.status = 'admin_approved'
        pr.admin_approved_by = request.user.staff if hasattr(request.user, 'staff') else None
        pr.admin_approved_at = timezone.now()
        pr.admin_notes = comments
        pr.save()
        
        messages.success(request, f'Request {pr.request_number} approved! Now pending accounts approval.')
        return redirect('hospital:admin_approval_list')
    
    context = {
        'procurement_request': pr,
        'approval_type': 'Administrator',
    }
    
    return render(request, 'hospital/procurement/approve_request.html', context)


@login_required
@permission_required('hospital.can_approve_procurement_admin', raise_exception=True)
def reject_admin(request, pr_id):
    """
    Administrator rejects procurement request
    """
    pr = get_object_or_404(ProcurementRequest, id=pr_id, is_deleted=False)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        
        if not reason:
            messages.error(request, 'Please provide a rejection reason')
            return redirect('hospital:approve_admin', pr_id=pr.id)
        
        # Reject
        pr.status = 'cancelled'
        pr.admin_rejection_reason = reason
        pr.save()
        
        messages.warning(request, f'Request {pr.request_number} rejected.')
        return redirect('hospital:admin_approval_list')
    
    return redirect('hospital:approve_admin', pr_id=pr.id)


# ==================== ACCOUNTS APPROVAL & ACCOUNTING INTEGRATION ====================

@login_required
@permission_required('hospital.can_approve_procurement_accounts', raise_exception=True)
def accounts_approval_list(request):
    """
    List of procurement requests pending accounts approval
    Only accounts staff can access
    """
    pending_requests = ProcurementRequest.objects.filter(
        status='admin_approved',
        is_deleted=False
    ).order_by('-created')
    
    context = {
        'pending_requests': pending_requests,
        'approval_type': 'Accounts',
    }
    
    return render(request, 'hospital/procurement/approval_list.html', context)


@login_required
@permission_required('hospital.can_approve_procurement_accounts', raise_exception=True)
def approve_accounts(request, pr_id):
    """
    Accounts approves procurement request
    THIS IS WHERE THE MAGIC HAPPENS!
    - Changes status from 'admin_approved' to 'accounts_approved'
    - Automatically creates accounting entries (AP, Expense, Payment Voucher)
    """
    pr = get_object_or_404(ProcurementRequest, id=pr_id, is_deleted=False)
    
    if pr.status != 'admin_approved':
        messages.error(request, 'This request is not pending accounts approval')
        return redirect('hospital:accounts_approval_list')
    
    if request.method == 'POST':
        comments = request.POST.get('comments', '')
        
        # Approve
        pr.status = 'accounts_approved'
        pr.accounts_approved_by = request.user.staff if hasattr(request.user, 'staff') else None
        pr.accounts_approved_at = timezone.now()
        pr.accounts_notes = comments
        pr.save()
        
        # ✨ AUTOMATIC ACCOUNTING ENTRY CREATION ✨
        try:
            result = auto_create_accounting_on_approval(pr)
            
            if result:
                messages.success(
                    request, 
                    f'✅ Request {pr.request_number} approved! '
                    f'Accounting entries created automatically: '
                    f'AP ({result["accounts_payable"].vendor_name}), '
                    f'Expense ({result["expense"].expense_number}), '
                    f'Payment Voucher ({result["payment_voucher"].voucher_number})'
                )
            else:
                messages.warning(
                    request,
                    f'Request approved but accounting entries could not be created. Please create manually.'
                )
        
        except Exception as e:
            messages.warning(
                request,
                f'Request approved but error creating accounting entries: {e}. Please create manually.'
            )
        
        return redirect('hospital:accounts_approval_list')
    
    context = {
        'procurement_request': pr,
        'approval_type': 'Accounts',
    }
    
    return render(request, 'hospital/procurement/approve_request.html', context)


@login_required
@permission_required('hospital.can_approve_procurement_accounts', raise_exception=True)
def reject_accounts(request, pr_id):
    """
    Accounts rejects procurement request
    """
    pr = get_object_or_404(ProcurementRequest, id=pr_id, is_deleted=False)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        
        if not reason:
            messages.error(request, 'Please provide a rejection reason')
            return redirect('hospital:approve_accounts', pr_id=pr.id)
        
        # Reject
        pr.status = 'cancelled'
        pr.accounts_rejection_reason = reason
        pr.save()
        
        messages.warning(request, f'Request {pr.request_number} rejected.')
        return redirect('hospital:accounts_approval_list')
    
    return redirect('hospital:approve_accounts', pr_id=pr.id)


# ==================== COMMON VIEWS ====================

@login_required
def procurement_detail(request, pr_id):
    """
    View details of a procurement request
    Shows items, approval chain, and accounting status
    """
    pr = get_object_or_404(ProcurementRequest, id=pr_id, is_deleted=False)
    
    # Get accounting summary
    from .procurement_accounting_integration import ProcurementAccountingIntegration
    accounting_summary = ProcurementAccountingIntegration.get_procurement_accounting_summary(pr)
    
    context = {
        'procurement_request': pr,
        'items': pr.items.all(),
        'accounting_summary': accounting_summary,
    }
    
    return render(request, 'hospital/procurement/detail.html', context)


@login_required
def procurement_list(request):
    """
    List all procurement requests with filters
    """
    # Get filter parameters
    status = request.GET.get('status', 'all')
    priority = request.GET.get('priority', 'all')
    
    # Base queryset
    requests = ProcurementRequest.objects.filter(is_deleted=False)
    
    # Apply filters
    if status != 'all':
        requests = requests.filter(status=status)
    
    if priority != 'all':
        requests = requests.filter(priority=priority)
    
    # Order by date
    requests = requests.order_by('-created')
    
    context = {
        'requests': requests[:50],
        'status_filter': status,
        'priority_filter': priority,
    }
    
    return render(request, 'hospital/procurement/list.html', context)


# ==================== API ENDPOINTS ====================

@login_required
def procurement_stats_api(request):
    """
    API endpoint for procurement statistics
    """
    stats = {
        'total': ProcurementRequest.objects.filter(is_deleted=False).count(),
        'draft': ProcurementRequest.objects.filter(status='draft', is_deleted=False).count(),
        'submitted': ProcurementRequest.objects.filter(status='submitted', is_deleted=False).count(),
        'admin_approved': ProcurementRequest.objects.filter(status='admin_approved', is_deleted=False).count(),
        'accounts_approved': ProcurementRequest.objects.filter(status='accounts_approved', is_deleted=False).count(),
        'payment_processed': ProcurementRequest.objects.filter(status='payment_processed', is_deleted=False).count(),
        'cancelled': ProcurementRequest.objects.filter(status='cancelled', is_deleted=False).count(),
    }
    
    # Get total amounts
    total_amount = ProcurementRequest.objects.filter(
        is_deleted=False
    ).aggregate(total=Sum('estimated_total'))['total'] or Decimal('0.00')
    
    approved_amount = ProcurementRequest.objects.filter(
        status__in=['accounts_approved', 'payment_processed', 'ordered', 'received'],
        is_deleted=False
    ).aggregate(total=Sum('estimated_total'))['total'] or Decimal('0.00')
    
    stats['total_amount'] = float(total_amount)
    stats['approved_amount'] = float(approved_amount)
    
    return JsonResponse(stats)

