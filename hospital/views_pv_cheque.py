"""
Payment Voucher and Cheque Management Views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Q, Count
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import datetime, timedelta
import json

from .models_accounting import Account, CostCenter
from .models_accounting_advanced import (
    PaymentVoucher, Cheque, BankAccount, Journal, AdvancedJournalEntry,
    AdvancedJournalEntryLine, FiscalYear, AccountingPeriod
)
from .models import BaseModel
from .utils_pv_account_setup import (
    setup_pv_cheque_accounts, get_pv_expense_accounts, get_pv_payment_accounts
)


def is_accountant(user):
    """Check if user has accounting permissions"""
    return user.is_superuser or user.is_staff or user.groups.filter(name__in=['Accountant', 'Finance']).exists()


@login_required
@user_passes_test(is_accountant)
def pv_account_setup(request):
    """Setup default accounts for PV and cheque operations"""
    if request.method == 'POST':
        result = setup_pv_cheque_accounts()
        if result['total_created'] > 0:
            messages.success(request, f"Created {result['total_created']} new accounts for PV and cheque operations")
        else:
            messages.info(request, "All required accounts already exist")
        return redirect('hospital:chart_of_accounts')
    
    # Check which accounts exist
    expense_accounts = get_pv_expense_accounts()
    payment_accounts = get_pv_payment_accounts()
    
    # Check for default accounts
    default_expense_codes = ['5010', '5020', '5030', '5040', '5050']
    default_payment_codes = ['1010', '1020', '1030']
    
    missing_expense = []
    missing_payment = []
    
    for code in default_expense_codes:
        if not Account.objects.filter(account_code=code, is_active=True).exists():
            missing_expense.append(code)
    
    for code in default_payment_codes:
        if not Account.objects.filter(account_code=code, is_active=True).exists():
            missing_payment.append(code)
    
    context = {
        'expense_accounts': expense_accounts,
        'payment_accounts': payment_accounts,
        'missing_expense': missing_expense,
        'missing_payment': missing_payment,
        'needs_setup': len(missing_expense) > 0 or len(missing_payment) > 0,
    }
    
    return render(request, 'hospital/pv/pv_account_setup.html', context)


@login_required
@user_passes_test(is_accountant)
def pv_list(request):
    """List all payment vouchers"""
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    vouchers = PaymentVoucher.objects.filter(is_deleted=False)
    
    if status_filter:
        vouchers = vouchers.filter(status=status_filter)
    
    if search:
        vouchers = vouchers.filter(
            Q(voucher_number__icontains=search) |
            Q(payee_name__icontains=search) |
            Q(description__icontains=search)
        )
    
    vouchers = vouchers.select_related('requested_by', 'approved_by', 'paid_by', 'expense_account', 'payment_account').order_by('-voucher_date', '-voucher_number')
    
    # Statistics
    stats = {
        'total': vouchers.count(),
        'draft': vouchers.filter(status='draft').count(),
        'pending': vouchers.filter(status='pending_approval').count(),
        'approved': vouchers.filter(status='approved').count(),
        'paid': vouchers.filter(status='paid').count(),
        'total_amount': vouchers.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
    }
    
    context = {
        'vouchers': vouchers,
        'stats': stats,
        'status_filter': status_filter,
        'search': search,
    }
    
    return render(request, 'hospital/pv/pv_list.html', context)


@login_required
@user_passes_test(is_accountant)
def pv_create(request):
    """Create a new payment voucher"""
    from django import forms
    
    class PaymentVoucherForm(forms.ModelForm):
        class Meta:
            model = PaymentVoucher
            fields = [
                'voucher_date', 'payment_type', 'payee_name', 'payee_type',
                'description', 'amount', 'payment_method', 'bank_account',
                'bank_name', 'account_number', 'expense_account', 'payment_account',
                'invoice_number', 'po_number', 'memo', 'notes'
            ]
            widgets = {
                'voucher_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
                'payment_type': forms.Select(attrs={'class': 'form-select'}),
                'payee_name': forms.TextInput(attrs={'class': 'form-control'}),
                'payee_type': forms.TextInput(attrs={'class': 'form-control'}),
                'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
                'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
                'payment_method': forms.Select(attrs={'class': 'form-select'}),
                'bank_account': forms.Select(attrs={'class': 'form-select', 'onchange': 'updateBankBalance()'}),
                'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
                'account_number': forms.TextInput(attrs={'class': 'form-control'}),
                'expense_account': forms.Select(attrs={'class': 'form-select'}),
                'payment_account': forms.Select(attrs={'class': 'form-select'}),
                'invoice_number': forms.TextInput(attrs={'class': 'form-control'}),
                'po_number': forms.TextInput(attrs={'class': 'form-control'}),
                'memo': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Enter payment details/memo'}),
                'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            }
    
    if request.method == 'POST':
        form = PaymentVoucherForm(request.POST)
        if form.is_valid():
            voucher = form.save(commit=False)
            voucher.requested_by = request.user
            voucher.status = 'draft'
            voucher.save()
            
            # If payment method is cheque, create cheque
            if voucher.payment_method == 'cheque' and request.POST.get('create_cheque') == 'yes':
                cheque_number = request.POST.get('cheque_number')
                cheque_date = request.POST.get('cheque_date')
                bank_account_id = request.POST.get('bank_account')
                
                if cheque_number and cheque_date and bank_account_id:
                    try:
                        bank_account = BankAccount.objects.get(id=bank_account_id)
                        cheque = Cheque.objects.create(
                            cheque_number=cheque_number,
                            bank_account=bank_account,
                            payee_name=voucher.payee_name,
                            amount=voucher.amount,
                            issue_date=timezone.now().date(),
                            cheque_date=datetime.strptime(cheque_date, '%Y-%m-%d').date(),
                            description=voucher.description,
                            memo=voucher.description[:200],
                            payment_voucher=voucher,
                            issued_by=request.user,
                            status='issued'
                        )
                        voucher.cheque = cheque
                        voucher.cheque_number = cheque_number
                        voucher.save()
                        messages.success(request, f'Payment Voucher {voucher.voucher_number} created with Cheque #{cheque_number}')
                    except Exception as e:
                        messages.error(request, f'Error creating cheque: {str(e)}')
                else:
                    messages.warning(request, 'Cheque details incomplete. PV created without cheque.')
            
            messages.success(request, f'Payment Voucher {voucher.voucher_number} created successfully')
            return redirect('hospital:pv_detail', voucher_id=voucher.id)
    else:
        form = PaymentVoucherForm()
    
    # Get accounts for dropdowns - use utility functions
    expense_accounts = get_pv_expense_accounts()
    payment_accounts = get_pv_payment_accounts()
    bank_accounts = BankAccount.objects.filter(is_active=True).order_by('account_name')
    
    # Auto-setup accounts if none exist
    if not expense_accounts.exists() or not payment_accounts.exists():
        setup_pv_cheque_accounts()
        expense_accounts = get_pv_expense_accounts()
        payment_accounts = get_pv_payment_accounts()
    
    # Calculate ending balances for bank accounts
    bank_accounts_with_balance = []
    for bank in bank_accounts:
        # Get current balance from GL
        from .models_accounting_advanced import AdvancedGeneralLedger
        from django.db.models import Sum
        
        gl_balance = AdvancedGeneralLedger.objects.filter(
            account=bank.gl_account,
            is_voided=False
        ).aggregate(
            total_debit=Sum('debit_amount'),
            total_credit=Sum('credit_amount')
        )
        
        debit_total = gl_balance['total_debit'] or Decimal('0.00')
        credit_total = gl_balance['total_credit'] or Decimal('0.00')
        current_balance = bank.opening_balance + debit_total - credit_total
        
        bank_accounts_with_balance.append({
            'bank': bank,
            'current_balance': current_balance,
        })
    
    context = {
        'form': form,
        'expense_accounts': expense_accounts,
        'payment_accounts': payment_accounts,
        'bank_accounts': bank_accounts,
        'bank_accounts_with_balance': bank_accounts_with_balance,
    }
    
    return render(request, 'hospital/pv/pv_create.html', context)


@login_required
@user_passes_test(is_accountant)
def pv_detail(request, voucher_id):
    """View payment voucher details"""
    voucher = get_object_or_404(PaymentVoucher, id=voucher_id, is_deleted=False)
    
    context = {
        'voucher': voucher,
    }
    
    return render(request, 'hospital/pv/pv_detail.html', context)


@login_required
@user_passes_test(is_accountant)
def pv_approve(request, voucher_id):
    """Approve a payment voucher"""
    voucher = get_object_or_404(PaymentVoucher, id=voucher_id, is_deleted=False)
    
    if voucher.status == 'draft':
        # Submit for approval
        voucher.status = 'pending_approval'
        voucher.save()
        messages.success(request, f'Payment Voucher {voucher.voucher_number} submitted for approval')
    elif voucher.status == 'pending_approval':
        # Approve
        try:
            voucher.approve(request.user)
            messages.success(request, f'Payment Voucher {voucher.voucher_number} approved')
        except Exception as e:
            messages.error(request, f'Error approving voucher: {str(e)}')
    else:
        messages.error(request, f'Voucher {voucher.voucher_number} cannot be approved in current status')
    
    return redirect('hospital:pv_detail', voucher_id=voucher.id)


@login_required
@user_passes_test(is_accountant)
def pv_mark_paid(request, voucher_id):
    """Mark payment voucher as paid"""
    voucher = get_object_or_404(PaymentVoucher, id=voucher_id, is_deleted=False)
    
    if voucher.status != 'approved':
        messages.error(request, f'Voucher {voucher.voucher_number} must be approved before payment')
        return redirect('hospital:pv_detail', voucher_id=voucher.id)
    
    try:
        payment_date = request.POST.get('payment_date') or timezone.now().date()
        if isinstance(payment_date, str):
            payment_date = datetime.strptime(payment_date, '%Y-%m-%d').date()
        
        voucher.mark_paid(request.user, payment_date)
        messages.success(request, f'Payment Voucher {voucher.voucher_number} marked as paid')
    except Exception as e:
        messages.error(request, f'Error marking voucher as paid: {str(e)}')
    
    return redirect('hospital:pv_detail', voucher_id=voucher.id)


@login_required
@user_passes_test(is_accountant)
def cheque_list(request):
    """List all cheques"""
    status_filter = request.GET.get('status', '')
    bank_filter = request.GET.get('bank', '')
    search = request.GET.get('search', '')
    
    cheques = Cheque.objects.filter(is_deleted=False)
    
    if status_filter:
        cheques = cheques.filter(status=status_filter)
    
    if bank_filter:
        cheques = cheques.filter(bank_account_id=bank_filter)
    
    if search:
        cheques = cheques.filter(
            Q(cheque_number__icontains=search) |
            Q(payee_name__icontains=search) |
            Q(description__icontains=search)
        )
    
    cheques = cheques.select_related('bank_account', 'payment_voucher', 'issued_by', 'cleared_by').order_by('-issue_date', '-cheque_number')
    
    # Statistics
    stats = {
        'total': cheques.count(),
        'issued': cheques.filter(status='issued').count(),
        'cleared': cheques.filter(status='cleared').count(),
        'bounced': cheques.filter(status='bounced').count(),
        'void': cheques.filter(status='void').count(),
        'total_amount': cheques.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        'outstanding_amount': cheques.filter(status='issued').aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
    }
    
    bank_accounts = BankAccount.objects.filter(is_active=True).order_by('account_name')
    
    context = {
        'cheques': cheques,
        'stats': stats,
        'status_filter': status_filter,
        'bank_filter': bank_filter,
        'search': search,
        'bank_accounts': bank_accounts,
    }
    
    return render(request, 'hospital/pv/cheque_list.html', context)


@login_required
@user_passes_test(is_accountant)
def cheque_create(request):
    """Create a new cheque"""
    from django import forms
    
    class ChequeForm(forms.ModelForm):
        class Meta:
            model = Cheque
            fields = [
                'cheque_number', 'bank_account', 'payee_name', 'amount',
                'cheque_date', 'description', 'memo', 'notes'
            ]
            widgets = {
                'cheque_number': forms.TextInput(attrs={'class': 'form-control'}),
                'bank_account': forms.Select(attrs={'class': 'form-select'}),
                'payee_name': forms.TextInput(attrs={'class': 'form-control'}),
                'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
                'cheque_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
                'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
                'memo': forms.TextInput(attrs={'class': 'form-control'}),
                'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            }
    
    if request.method == 'POST':
        form = ChequeForm(request.POST)
        if form.is_valid():
            cheque = form.save(commit=False)
            cheque.issue_date = timezone.now().date()
            cheque.issued_by = request.user
            cheque.status = 'issued'
            
            # Link to PV if provided
            pv_id = request.POST.get('payment_voucher_id')
            if pv_id:
                try:
                    pv = PaymentVoucher.objects.get(id=pv_id, is_deleted=False)
                    cheque.payment_voucher = pv
                    pv.cheque = cheque
                    pv.cheque_number = cheque.cheque_number
                    pv.save()
                except PaymentVoucher.DoesNotExist:
                    pass
            
            cheque.save()
            messages.success(request, f'Cheque #{cheque.cheque_number} created successfully')
            return redirect('hospital:cheque_detail', cheque_id=cheque.id)
    else:
        form = ChequeForm()
        pv_id = request.GET.get('pv_id')
        if pv_id:
            try:
                pv = PaymentVoucher.objects.get(id=pv_id, is_deleted=False)
                form.initial = {
                    'payee_name': pv.payee_name,
                    'amount': pv.amount,
                    'description': pv.description,
                }
            except PaymentVoucher.DoesNotExist:
                pass
    
    bank_accounts = BankAccount.objects.filter(is_active=True).order_by('account_name')
    
    context = {
        'form': form,
        'bank_accounts': bank_accounts,
        'pv_id': request.GET.get('pv_id'),
    }
    
    return render(request, 'hospital/pv/cheque_create.html', context)


@login_required
@user_passes_test(is_accountant)
def cheque_detail(request, cheque_id):
    """View cheque details"""
    cheque = get_object_or_404(Cheque, id=cheque_id, is_deleted=False)
    
    context = {
        'cheque': cheque,
    }
    
    return render(request, 'hospital/pv/cheque_detail.html', context)


@login_required
@user_passes_test(is_accountant)
def cheque_clear(request, cheque_id):
    """Mark cheque as cleared"""
    cheque = get_object_or_404(Cheque, id=cheque_id, is_deleted=False)
    
    if request.method == 'POST':
        clear_date = request.POST.get('clear_date')
        bank_reference = request.POST.get('bank_reference', '')
        
        if clear_date:
            clear_date = datetime.strptime(clear_date, '%Y-%m-%d').date()
        else:
            clear_date = timezone.now().date()
        
        try:
            cheque.clear(request.user, clear_date, bank_reference)
            messages.success(request, f'Cheque #{cheque.cheque_number} marked as cleared')
        except Exception as e:
            messages.error(request, f'Error clearing cheque: {str(e)}')
        
        return redirect('hospital:cheque_detail', cheque_id=cheque.id)
    
    return render(request, 'hospital/pv/cheque_clear.html', {'cheque': cheque})


@login_required
@user_passes_test(is_accountant)
def cheque_bounce(request, cheque_id):
    """Mark cheque as bounced"""
    cheque = get_object_or_404(Cheque, id=cheque_id, is_deleted=False)
    
    if request.method == 'POST':
        notes = request.POST.get('notes', '')
        try:
            cheque.bounce(request.user, notes)
            messages.success(request, f'Cheque #{cheque.cheque_number} marked as bounced')
        except Exception as e:
            messages.error(request, f'Error bouncing cheque: {str(e)}')
        
        return redirect('hospital:cheque_detail', cheque_id=cheque.id)
    
    return render(request, 'hospital/pv/cheque_bounce.html', {'cheque': cheque})


@login_required
@user_passes_test(is_accountant)
def cheque_void(request, cheque_id):
    """Void a cheque"""
    cheque = get_object_or_404(Cheque, id=cheque_id, is_deleted=False)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        try:
            cheque.void_cheque(request.user, reason)
            messages.success(request, f'Cheque #{cheque.cheque_number} voided')
        except Exception as e:
            messages.error(request, f'Error voiding cheque: {str(e)}')
        
        return redirect('hospital:cheque_detail', cheque_id=cheque.id)
    
    return render(request, 'hospital/pv/cheque_void.html', {'cheque': cheque})


@login_required
@user_passes_test(is_accountant)
def cheque_print(request, cheque_id):
    """Print cheque"""
    cheque = get_object_or_404(Cheque, id=cheque_id, is_deleted=False)
    
    context = {
        'cheque': cheque,
    }
    
    return render(request, 'hospital/pv/cheque_print.html', context)

