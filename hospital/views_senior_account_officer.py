"""
Senior Account Officer Views
Oversees all accounting operations and account-related staff
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q, Count, F
from django.utils import timezone
from datetime import datetime, timedelta, date
from decimal import Decimal

from .models import Staff, Department
from .models_accounting import Account, CostCenter, PaymentReceipt, Transaction
from .models_accounting_advanced import (
    FiscalYear, AccountingPeriod, Journal, AdvancedJournalEntry, AdvancedJournalEntryLine,
    AdvancedGeneralLedger, PaymentVoucher, ReceiptVoucher, Cheque,
    Revenue, RevenueCategory, Expense, ExpenseCategory,
    AdvancedAccountsReceivable, AccountsPayable,
    BankAccount, BankTransaction, Budget, BudgetLine,
    Cashbook, BankReconciliation, BankReconciliationItem,
    InsuranceReceivable, ProcurementPurchase,
    AccountingPayroll, AccountingPayrollEntry, DoctorCommission,
    IncomeGroup, ProfitLossReport,
    RegistrationFee, CashSale, AccountingCorporateAccount,
    WithholdingReceivable, Deposit, InitialRevaluation,
    AccountCategory
)
from .utils_roles import get_user_role
from .decorators import role_required

import logging
logger = logging.getLogger(__name__)


@login_required
@role_required('senior_account_officer')
def senior_account_officer_dashboard(request):
    """
    Senior Account Officer Dashboard
    Shows accounting overview and account-related staff management
    """
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    
    # Safe query wrapper
    def safe_query(query_func, default=0):
        try:
            return query_func()
        except Exception:
            return default
    
    # ===== ACCOUNTING METRICS =====
    total_revenue = safe_query(lambda: Revenue.objects.filter(
        revenue_date__gte=start_of_month
    ).aggregate(total=Sum('amount'))['total'] or 0)
    
    total_expenses = safe_query(lambda: Expense.objects.filter(
        expense_date__gte=start_of_month,
        status='paid'
    ).aggregate(total=Sum('amount'))['total'] or 0)
    
    # Cashbook Statistics
    pending_cashbook = safe_query(lambda: Cashbook.objects.filter(status='pending').count())
    ready_to_classify = safe_query(lambda: Cashbook.objects.filter(
        status='pending',
        held_until__lte=today
    ).count())
    
    # Bank Reconciliation
    unreconciled_transactions = safe_query(lambda: BankTransaction.objects.filter(
        is_reconciled=False
    ).count())
    
    # Insurance Receivable
    total_insurance_receivable = safe_query(lambda: InsuranceReceivable.objects.filter(
        balance_due__gt=0
    ).aggregate(total=Sum('balance_due'))['total'] or 0)
    
    # Procurement
    pending_procurement = safe_query(lambda: ProcurementPurchase.objects.filter(
        status='draft'
    ).count())
    
    # Payroll
    pending_payroll = safe_query(lambda: AccountingPayroll.objects.filter(
        status='draft'
    ).count())
    
    # Doctor Commissions
    unpaid_commissions = safe_query(lambda: DoctorCommission.objects.filter(
        is_paid=False
    ).aggregate(total=Sum('doctor_share'))['total'] or 0)
    
    # Accounts Receivable/Payable
    total_ar = safe_query(lambda: AdvancedAccountsReceivable.objects.filter(
        balance_due__gt=0
    ).aggregate(total=Sum('balance_due'))['total'] or 0)
    
    total_ap = safe_query(lambda: AccountsPayable.objects.filter(
        balance_due__gt=0
    ).aggregate(total=Sum('balance_due'))['total'] or 0)
    
    # Journal Entries
    draft_journals = safe_query(lambda: AdvancedJournalEntry.objects.filter(
        status='draft'
    ).count())
    
    # Payment Vouchers
    pending_vouchers = safe_query(lambda: PaymentVoucher.objects.filter(
        status='pending_approval'
    ).count())
    
    # Cheques
    outstanding_cheques = safe_query(lambda: Cheque.objects.filter(
        status='issued'
    ).aggregate(total=Sum('amount'))['total'] or 0)
    
    # ===== ACCOUNT STAFF MANAGEMENT =====
    # Get account-related staff only (accountants, account officers, account personnel)
    account_professions = ['accountant', 'account_officer', 'account_personnel', 'senior_account_officer']
    
    # Get account staff
    account_staff = Staff.objects.filter(
        profession__in=account_professions,
        is_deleted=False
    ).select_related('user', 'department').order_by('user__last_name', 'user__first_name')
    
    # Staff statistics
    total_account_staff = account_staff.count()
    active_account_staff = account_staff.filter(is_active=True).count()
    
    # Group by profession - always include all professions with count (even if 0)
    staff_by_profession = {}
    for profession in account_professions:
        count = account_staff.filter(profession=profession, is_active=True).count()
        staff_by_profession[profession] = count  # Always set, even if 0
    
    # Recent account staff activity (last 30 days)
    thirty_days_ago = today - timedelta(days=30)
    # This would require activity tracking - for now, just show staff list
    
    context = {
        'title': 'Senior Account Officer Dashboard',
        'today': today,
        
        # Accounting metrics
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'net_income': total_revenue - total_expenses,
        'pending_cashbook': pending_cashbook,
        'ready_to_classify': ready_to_classify,
        'unreconciled_transactions': unreconciled_transactions,
        'total_insurance_receivable': total_insurance_receivable,
        'pending_procurement': pending_procurement,
        'pending_payroll': pending_payroll,
        'unpaid_commissions': unpaid_commissions,
        'total_ar': total_ar,
        'total_ap': total_ap,
        'draft_journals': draft_journals,
        'pending_vouchers': pending_vouchers,
        'outstanding_cheques': outstanding_cheques,
        
        # Account staff management
        'account_staff': account_staff[:20],  # Limit to 20 for display
        'total_account_staff': total_account_staff,
        'active_account_staff': active_account_staff,
        'staff_by_profession': staff_by_profession,
    }
    
    return render(request, 'hospital/senior_account_officer/dashboard.html', context)


@login_required
@role_required('senior_account_officer')
def account_staff_list(request):
    """
    List all account-related staff (accountants, account officers, account personnel)
    Senior Account Officer can view and manage account staff only
    """
    # Get account-related staff only
    account_professions = ['accountant', 'account_officer', 'account_personnel', 'senior_account_officer']
    
    query = request.GET.get('q', '')
    profession_filter = request.GET.get('profession', '')
    status_filter = request.GET.get('status', 'active')
    
    # Base queryset - account staff only
    account_staff = Staff.objects.filter(
        profession__in=account_professions,
        is_deleted=False
    ).select_related('user', 'department')
    
    # Apply filters
    if status_filter == 'active':
        account_staff = account_staff.filter(is_active=True)
    elif status_filter == 'inactive':
        account_staff = account_staff.filter(is_active=False)
    
    if profession_filter:
        account_staff = account_staff.filter(profession=profession_filter)
    
    if query:
        account_staff = account_staff.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query) |
            Q(employee_id__icontains=query) |
            Q(phone_number__icontains=query)
        )
    
    # Get profession choices for filter
    profession_choices = [
        ('accountant', 'Accountant'),
        ('account_officer', 'Account Officer'),
        ('account_personnel', 'Account Personnel'),
        ('senior_account_officer', 'Senior Account Officer'),
    ]
    
    context = {
        'title': 'Account Staff Management',
        'account_staff': account_staff.order_by('user__last_name', 'user__first_name'),
        'profession_choices': profession_choices,
        'query': query,
        'profession_filter': profession_filter,
        'status_filter': status_filter,
        'total_count': account_staff.count(),
    }
    
    return render(request, 'hospital/senior_account_officer/account_staff_list.html', context)


@login_required
@role_required('senior_account_officer')
def account_staff_detail(request, pk):
    """
    View details of account-related staff member
    Senior Account Officer can view account staff details only
    """
    # Get account-related staff only
    account_professions = ['accountant', 'account_officer', 'account_personnel', 'senior_account_officer']
    
    staff = get_object_or_404(
        Staff.objects.select_related('user', 'department'),
        pk=pk,
        is_deleted=False,
        profession__in=account_professions  # Restrict to account staff only
    )
    
    context = {
        'title': f'{staff.user.get_full_name()} - Account Staff Detail',
        'staff': staff,
    }
    
    return render(request, 'hospital/senior_account_officer/account_staff_detail.html', context)

