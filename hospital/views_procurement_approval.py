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
import logging

from .models_procurement import ProcurementRequest, ProcurementRequestItem
from .procurement_accounting_integration import auto_create_accounting_on_approval
from .models import Staff
from .models_accounting import Account
from .services.sms_service import SMSService

logger = logging.getLogger(__name__)


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
    # Use the primary procurement request creation flow (inline formset with 20 item rows).
    return redirect('hospital:procurement_request_create')


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
        return redirect('hospital:procurement_approval_detail', pr_id=pr.id)
    
    # Check if has items
    if not pr.items.exists():
        messages.error(request, 'Please add at least one item before submitting')
        return redirect('hospital:procurement_approval_detail', pr_id=pr.id)
    
    # Submit
    pr.status = 'submitted'
    pr.submitted_date = timezone.now()
    pr.save()
    
    messages.success(request, f'Request {pr.request_number} submitted for approval!')
    return redirect('hospital:procurement_approval_detail', pr_id=pr.id)


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
        
        # Send SMS notification to accountants
        try:
            _send_procurement_approval_sms_to_accountants(pr)
        except Exception as e:
            logger.error(f"Error sending SMS notification to accountants for procurement request {pr.request_number}: {str(e)}", exc_info=True)
            # Don't fail the approval if SMS fails
        
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
        
        # Optional: accounts for debit/credit (finance selection)
        expense_account_id = request.POST.get('expense_account') or None
        liability_account_id = request.POST.get('liability_account') or None
        payment_account_id = request.POST.get('payment_account') or None
        
        # Approve
        pr.status = 'accounts_approved'
        pr.accounts_approved_by = request.user.staff if hasattr(request.user, 'staff') else None
        pr.accounts_approved_at = timezone.now()
        pr.accounts_notes = comments
        pr.save()
        
        # Create accounting entries (with selected debit/credit accounts if provided)
        try:
            result = auto_create_accounting_on_approval(
                pr,
                expense_account=expense_account_id,
                liability_account=liability_account_id,
                payment_account=payment_account_id,
            )
            
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
    
    # For Accounts approval: pass chart of accounts so they can select debit/credit
    expense_accounts = []
    liability_accounts = []
    payment_accounts = []
    if pr.status == 'admin_approved':
        expense_accounts = Account.objects.filter(
            account_type='expense', is_active=True, is_deleted=False
        ).order_by('account_code')
        liability_accounts = Account.objects.filter(
            account_type='liability', is_active=True, is_deleted=False
        ).order_by('account_code')
        payment_accounts = Account.objects.filter(
            account_type='asset', is_active=True, is_deleted=False
        ).filter(account_code__startswith='10').order_by('account_code')
        if not payment_accounts.exists():
            payment_accounts = Account.objects.filter(
                account_type='asset', is_active=True, is_deleted=False
            ).order_by('account_code')[:20]
    
    context = {
        'procurement_request': pr,
        'approval_type': 'Accounts',
        'expense_accounts': expense_accounts,
        'liability_accounts': liability_accounts,
        'payment_accounts': payment_accounts,
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


# ==================== POST TO LEDGER (Accountant: record approved procurements) ====================

@login_required
@permission_required('hospital.can_approve_procurement_accounts', raise_exception=True)
def procurement_post_to_ledger_list(request):
    """
    List approved procurement requests that do not yet have accounting entries.
    Accountant can open each and select debit/credit accounts to post to finance.
    """
    from .procurement_accounting_integration import ProcurementAccountingIntegration
    approved = ProcurementRequest.objects.filter(
        status='accounts_approved', is_deleted=False
    ).order_by('-accounts_approved_at')
    pending_post = []
    for pr in approved:
        summary = ProcurementAccountingIntegration.get_procurement_accounting_summary(pr)
        if not summary.get('has_accounting_entries'):
            pending_post.append({'request': pr, 'summary': summary})
    context = {'pending_post': pending_post}
    return render(request, 'hospital/procurement/post_to_ledger_list.html', context)


@login_required
@permission_required('hospital.can_approve_procurement_accounts', raise_exception=True)
def procurement_post_to_ledger(request, pr_id):
    """
    Post an approved procurement to the ledger: select expense (debit), liability (credit AP), payment (credit bank).
    Creates AP, Expense, Payment Voucher and posts to General Ledger; updates finance reports.
    """
    pr = get_object_or_404(ProcurementRequest, id=pr_id, is_deleted=False)
    from .procurement_accounting_integration import (
        ProcurementAccountingIntegration,
        auto_create_accounting_on_approval,
    )
    summary = ProcurementAccountingIntegration.get_procurement_accounting_summary(pr)
    if summary.get('has_accounting_entries'):
        messages.info(request, f'{pr.request_number} already has accounting entries.')
        return redirect('hospital:procurement_post_to_ledger_list')
    if pr.status != 'accounts_approved':
        messages.error(request, 'Only approved procurements can be posted to the ledger.')
        return redirect('hospital:procurement_post_to_ledger_list')

    if request.method == 'POST':
        expense_account_id = request.POST.get('expense_account') or None
        liability_account_id = request.POST.get('liability_account') or None
        payment_account_id = request.POST.get('payment_account') or None
        try:
            result = auto_create_accounting_on_approval(
                pr,
                expense_account=expense_account_id,
                liability_account=liability_account_id,
                payment_account=payment_account_id,
            )
            if result:
                messages.success(
                    request,
                    f'Posted to ledger: AP {result["accounts_payable"].bill_number}, '
                    f'Expense {result["expense"].expense_number}, '
                    f'Voucher {result["payment_voucher"].voucher_number}.'
                )
            else:
                messages.warning(request, 'Accounting entries could not be created. Try again or create manually.')
        except Exception as e:
            messages.error(request, str(e))
        return redirect('hospital:procurement_post_to_ledger_list')

    expense_accounts = Account.objects.filter(
        account_type='expense', is_active=True, is_deleted=False
    ).order_by('account_code')
    liability_accounts = Account.objects.filter(
        account_type='liability', is_active=True, is_deleted=False
    ).order_by('account_code')
    payment_accounts = Account.objects.filter(
        account_type='asset', is_active=True, is_deleted=False
    ).filter(account_code__startswith='10').order_by('account_code')
    if not payment_accounts.exists():
        payment_accounts = Account.objects.filter(
            account_type='asset', is_active=True, is_deleted=False
        ).order_by('account_code')[:20]
    context = {
        'procurement_request': pr,
        'expense_accounts': expense_accounts,
        'liability_accounts': liability_accounts,
        'payment_accounts': payment_accounts,
    }
    return render(request, 'hospital/procurement/post_to_ledger.html', context)


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


def _send_procurement_approval_sms_to_accountants(procurement_request):
    """
    Send SMS notification to all accountants when a procurement request is approved by admin
    and ready for accounts approval.
    """
    try:
        # Get all accountant staff (accountants, account officers, senior account officers)
        accountant_professions = ['accountant', 'account_officer', 'account_personnel', 'senior_account_officer']
        accountant_staff = Staff.objects.filter(
            profession__in=accountant_professions,
            is_active=True,
            is_deleted=False
        ).select_related('user').exclude(phone_number__isnull=True).exclude(phone_number='')
        
        if not accountant_staff.exists():
            logger.info(f"No accountant staff found with phone numbers for procurement request {procurement_request.request_number}")
            return
        
        # Prepare SMS message
        request_number = procurement_request.request_number
        estimated_total = procurement_request.estimated_total
        requested_by = procurement_request.requested_by.full_name if procurement_request.requested_by else "Unknown"
        
        message = (
            f"🔔 Procurement Approval Required\n\n"
            f"Request: {request_number}\n"
            f"Amount: GHS {estimated_total:,.2f}\n"
            f"Requested by: {requested_by}\n"
            f"Status: Pending Accounts Approval\n\n"
            f"Please review and approve at:\n"
            f"/hms/procurement/accounts/pending/\n\n"
            f"PrimeCare Hospital"
        )
        
        # Send SMS to each accountant
        sms_service = SMSService()
        sent_count = 0
        failed_count = 0
        
        for staff in accountant_staff:
            if not staff.phone_number:
                continue
                
            try:
                phone = staff.phone_number.strip()
                # Ensure phone number starts with +233 or 0
                if phone.startswith('0'):
                    phone = '+233' + phone[1:]
                elif not phone.startswith('+'):
                    phone = '+233' + phone
                
                recipient_name = staff.full_name or (staff.user.get_full_name() if staff.user else "Accountant")
                
                sms_log = sms_service.send_sms(
                    phone_number=phone,
                    message=message,
                    message_type='procurement_approval',
                    recipient_name=recipient_name,
                    related_object_id=str(procurement_request.id),
                    related_object_type='ProcurementRequest'
                )
                
                if sms_log and sms_log.status == 'sent':
                    sent_count += 1
                    logger.info(f"SMS sent to accountant {recipient_name} ({phone}) for procurement request {request_number}")
                else:
                    failed_count += 1
                    logger.warning(f"Failed to send SMS to accountant {recipient_name} ({phone}) for procurement request {request_number}")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"Error sending SMS to accountant {staff.full_name} for procurement request {request_number}: {str(e)}", exc_info=True)
                continue
        
        logger.info(f"Procurement approval SMS notifications: {sent_count} sent, {failed_count} failed for request {request_number}")
        
    except Exception as e:
        logger.error(f"Error in _send_procurement_approval_sms_to_accountants for request {procurement_request.request_number}: {str(e)}", exc_info=True)
        raise

