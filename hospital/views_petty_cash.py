"""
Petty Cash Transaction Management Views
With Account Personnel and Account Officer approval workflow
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Q, Count
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import datetime

from .models_accounting import Account, CostCenter
from .models_accounting_advanced import PettyCashTransaction
from .utils_roles import get_user_role
from .decorators import role_required


def is_account_personnel(user):
    """Check if user is account personnel, officer, or senior account officer"""
    if user.is_superuser:
        return True
    return (user.groups.filter(name__in=['Account Personnel', 'Account Officer', 'Accountant', 'Senior Account Officer']).exists() or
            get_user_role(user) in ['account_personnel', 'account_officer', 'accountant', 'senior_account_officer'])


def is_account_officer(user):
    """Check if user is account officer or senior account officer"""
    if user.is_superuser:
        return True
    return (user.groups.filter(name__in=['Account Officer', 'Accountant', 'Senior Account Officer']).exists() or
            get_user_role(user) in ['account_officer', 'accountant', 'senior_account_officer'])


@login_required
@role_required('account_personnel', 'account_officer', 'accountant', 'senior_account_officer', 'admin')
def petty_cash_list(request):
    """List all petty cash transactions"""
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    user_role = get_user_role(request.user)
    
    transactions = PettyCashTransaction.objects.filter(is_deleted=False)
    
    # Account Personnel can only see their own transactions
    if user_role == 'account_personnel':
        transactions = transactions.filter(created_by=request.user)
    
    if status_filter:
        transactions = transactions.filter(status=status_filter)
    
    if search:
        transactions = transactions.filter(
            Q(transaction_number__icontains=search) |
            Q(payee_name__icontains=search) |
            Q(description__icontains=search)
        )
    
    transactions = transactions.select_related(
        'created_by', 'approved_by', 'rejected_by', 'expense_account', 'cost_center'
    ).order_by('-transaction_date', '-created')
    
    # Statistics
    stats = {
        'total': transactions.count(),
        'draft': transactions.filter(status='draft').count(),
        'pending': transactions.filter(status='pending_approval').count(),
        'approved': transactions.filter(status='approved').count(),
        'paid': transactions.filter(status='paid').count(),
        'rejected': transactions.filter(status='rejected').count(),
        'total_amount': transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        'pending_amount': transactions.filter(status='pending_approval').aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
    }
    
    context = {
        'transactions': transactions,
        'stats': stats,
        'status_filter': status_filter,
        'search': search,
        'user_role': user_role,
    }
    
    return render(request, 'hospital/petty_cash/petty_cash_list.html', context)


@login_required
@role_required('account_personnel', 'account_officer', 'accountant', 'senior_account_officer', 'admin')
def petty_cash_create(request):
    """Create a new petty cash transaction"""
    from django import forms
    
    class PettyCashTransactionForm(forms.ModelForm):
        class Meta:
            model = PettyCashTransaction
            fields = [
                'transaction_date', 'description', 'amount', 'payee_name', 'payee_type',
                'expense_account', 'cost_center', 'invoice_number', 'notes'
            ]
            widgets = {
                'transaction_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
                'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'required': True}),
                'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'required': True}),
                'payee_name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
                'payee_type': forms.TextInput(attrs={'class': 'form-control'}),
                'expense_account': forms.Select(attrs={'class': 'form-select', 'required': True}),
                'cost_center': forms.Select(attrs={'class': 'form-select'}),
                'invoice_number': forms.TextInput(attrs={'class': 'form-control'}),
                'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            }
    
    if request.method == 'POST':
        form = PettyCashTransactionForm(request.POST)
        if form.is_valid():
            pc_transaction = form.save(commit=False)
            pc_transaction.created_by = request.user
            pc_transaction.status = 'draft'
            pc_transaction.save()
            
            # Check if amount > 500 GHC requires approval
            if pc_transaction.amount > Decimal('500.00'):
                messages.warning(
                    request, 
                    f"Transaction created. Amount (GHS {pc_transaction.amount:,.2f}) exceeds GHS 500.00 and requires Account Officer approval."
                )
            else:
                messages.info(
                    request,
                    f"Transaction created. Amount (GHS {pc_transaction.amount:,.2f}) is within approval limit, but still requires Account Officer approval."
                )
            
            return redirect('hospital:petty_cash_detail', transaction_id=pc_transaction.id)
    else:
        form = PettyCashTransactionForm()
    
    # Get expense accounts
    expense_accounts = Account.objects.filter(account_type='expense', is_active=True).order_by('account_code')
    cost_centers = CostCenter.objects.filter(is_active=True).order_by('code')
    
    context = {
        'form': form,
        'expense_accounts': expense_accounts,
        'cost_centers': cost_centers,
    }
    
    return render(request, 'hospital/petty_cash/petty_cash_create.html', context)


@login_required
@role_required('account_personnel', 'account_officer', 'accountant', 'senior_account_officer', 'admin')
def petty_cash_detail(request, transaction_id):
    """View petty cash transaction details"""
    pc_transaction = get_object_or_404(PettyCashTransaction, id=transaction_id, is_deleted=False)
    user_role = get_user_role(request.user)
    
    # Account Personnel can only view their own transactions
    if user_role == 'account_personnel' and pc_transaction.created_by != request.user:
        messages.error(request, "You don't have permission to view this transaction.")
        return redirect('hospital:petty_cash_list')
    
    context = {
        'transaction': pc_transaction,
        'user_role': user_role,
        'can_approve': user_role in ['account_officer', 'accountant'] and pc_transaction.status == 'pending_approval',
        'can_reject': user_role in ['account_officer', 'accountant'] and pc_transaction.status == 'pending_approval',
        'can_submit': user_role in ['account_personnel', 'account_officer', 'accountant'] and pc_transaction.status == 'draft',
    }
    
    return render(request, 'hospital/petty_cash/petty_cash_detail.html', context)


@login_required
@role_required('account_personnel', 'account_officer', 'accountant', 'senior_account_officer', 'admin')
def petty_cash_submit(request, transaction_id):
    """Submit transaction for approval"""
    pc_transaction = get_object_or_404(PettyCashTransaction, id=transaction_id, is_deleted=False)
    user_role = get_user_role(request.user)
    
    # Only creator can submit
    if pc_transaction.created_by != request.user and user_role != 'account_officer':
        messages.error(request, "You don't have permission to submit this transaction.")
        return redirect('hospital:petty_cash_list')
    
    if pc_transaction.status != 'draft':
        messages.error(request, "Only draft transactions can be submitted for approval.")
        return redirect('hospital:petty_cash_detail', transaction_id=pc_transaction.id)
    
    try:
        pc_transaction.submit_for_approval(request.user)
        messages.success(
            request, 
            f"Transaction {pc_transaction.transaction_number} submitted for Account Officer approval."
        )
    except ValueError as e:
        messages.error(request, str(e))
    
    return redirect('hospital:petty_cash_detail', transaction_id=pc_transaction.id)


@login_required
@role_required('account_officer', 'accountant', 'senior_account_officer', 'admin')
def petty_cash_approve(request, transaction_id):
    """Approve petty cash transaction"""
    pc_transaction = get_object_or_404(PettyCashTransaction, id=transaction_id, is_deleted=False)
    
    if pc_transaction.status != 'pending_approval':
        messages.error(request, "Only pending transactions can be approved.")
        return redirect('hospital:petty_cash_detail', transaction_id=pc_transaction.id)
    
    try:
        with transaction.atomic():
            pc_transaction.approve(request.user)
            messages.success(
                request, 
                f"Transaction {pc_transaction.transaction_number} approved. Journal entry created automatically."
            )
    except Exception as e:
        messages.error(request, f"Error approving transaction: {str(e)}")
    
    return redirect('hospital:petty_cash_detail', transaction_id=pc_transaction.id)


@login_required
@role_required('account_officer', 'accountant', 'senior_account_officer', 'admin')
def petty_cash_reject(request, transaction_id):
    """Reject petty cash transaction"""
    pc_transaction = get_object_or_404(PettyCashTransaction, id=transaction_id, is_deleted=False)
    
    if pc_transaction.status != 'pending_approval':
        messages.error(request, "Only pending transactions can be rejected.")
        return redirect('hospital:petty_cash_detail', transaction_id=pc_transaction.id)
    
    if request.method == 'POST':
        reason = request.POST.get('rejection_reason', '')
        try:
            pc_transaction.reject(request.user, reason)
            messages.warning(
                request, 
                f"Transaction {pc_transaction.transaction_number} rejected."
            )
            return redirect('hospital:petty_cash_detail', transaction_id=pc_transaction.id)
        except Exception as e:
            messages.error(request, f"Error rejecting transaction: {str(e)}")
    
    context = {
        'transaction': pc_transaction,
    }
    
    return render(request, 'hospital/petty_cash/petty_cash_reject.html', context)


@login_required
@role_required('account_officer', 'accountant', 'senior_account_officer', 'admin')
def petty_cash_approval_list(request):
    """List transactions pending approval (for Account Officers)"""
    transactions = PettyCashTransaction.objects.filter(
        is_deleted=False,
        status='pending_approval'
    ).select_related(
        'created_by', 'expense_account', 'cost_center'
    ).order_by('transaction_date', 'created')
    
    # Highlight transactions over 500 GHC
    high_amount_transactions = [t for t in transactions if t.amount > Decimal('500.00')]
    
    stats = {
        'total': transactions.count(),
        'over_500': len(high_amount_transactions),
        'total_amount': transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        'over_500_amount': sum(t.amount for t in high_amount_transactions),
    }
    
    context = {
        'transactions': transactions,
        'stats': stats,
        'high_amount_threshold': Decimal('500.00'),
    }
    
    return render(request, 'hospital/petty_cash/petty_cash_approval_list.html', context)


@login_required
@role_required('account_officer', 'accountant', 'senior_account_officer', 'admin')
def petty_cash_mark_paid(request, transaction_id):
    """Mark transaction as paid"""
    pc_transaction = get_object_or_404(PettyCashTransaction, id=transaction_id, is_deleted=False)
    user_role = get_user_role(request.user)
    
    # Only account officers can mark as paid
    if user_role not in ['account_officer', 'accountant']:
        messages.error(request, "You don't have permission to mark transactions as paid.")
        return redirect('hospital:petty_cash_detail', transaction_id=pc_transaction.id)
    
    if pc_transaction.status != 'approved':
        messages.error(request, "Only approved transactions can be marked as paid.")
        return redirect('hospital:petty_cash_detail', transaction_id=pc_transaction.id)
    
    if request.method == 'POST':
        payment_date = request.POST.get('payment_date')
        receipt_number = request.POST.get('receipt_number', '')
        
        try:
            pc_transaction.payment_date = payment_date or timezone.now().date()
            pc_transaction.receipt_number = receipt_number
            pc_transaction.mark_paid(request.user)
            messages.success(
                request, 
                f"Transaction {pc_transaction.transaction_number} marked as paid."
            )
        except Exception as e:
            messages.error(request, f"Error marking as paid: {str(e)}")
        
        return redirect('hospital:petty_cash_detail', transaction_id=pc_transaction.id)
    
    context = {
        'transaction': pc_transaction,
    }
    
    return render(request, 'hospital/petty_cash/petty_cash_mark_paid.html', context)

