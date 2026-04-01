"""
Comprehensive Accountant Views - All Accounting Features
Provides access to all accounting features for accountants.
Sensitive data entry (Insurance Receivable, Bank Reconciliation, etc.) requires
re-entry of password within HMS interface so users never need Django admin.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Q, Count, Avg, F, DecimalField, Case, When, Value
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import transaction
from django.urls import reverse
from django.utils.http import urlencode
from django.core.cache import cache
from datetime import datetime, timedelta, date
from decimal import Decimal, InvalidOperation
from uuid import UUID
from functools import wraps
import json

# Session key and expiry (minutes) for finance-sensitive re-auth
FINANCE_SENSITIVE_SESSION_KEY = 'finance_sensitive_verified_at'
FINANCE_SENSITIVE_EXPIRY_MINUTES = 15

# Dashboard aggregates many queries; short TTL keeps numbers fresh while making repeat loads instant.
ACCOUNTANT_COMPREHENSIVE_DASH_CACHE_TTL = 120

from .models_accounting import Account, CostCenter, PaymentReceipt, Transaction
from .models_accounting_advanced import (
    # Existing models
    FiscalYear, AccountingPeriod, Journal, AdvancedJournalEntry, AdvancedJournalEntryLine,
    AdvancedGeneralLedger, PaymentVoucher, ReceiptVoucher, Cheque,
    Revenue, RevenueCategory, Expense, ExpenseCategory,
    AdvancedAccountsReceivable, AccountsPayable,
    BankAccount, BankTransaction, Budget, BudgetLine,
    # New models
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
from .utils_account_linking import sync_all_accounts, link_cashbook_to_accounts
from collections import defaultdict
from .models import PharmacyStock, Drug


def is_accountant(user):
    """Check if user is accountant or senior account officer"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role = get_user_role(user)
    return role in ('accountant', 'senior_account_officer')


def require_finance_reauth(view_func):
    """Require re-entry of password for sensitive accountant actions (Insurance Receivable, Bank Reconciliation, etc.)."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(reverse('hospital:login') + '?next=' + request.get_full_path())
        verified_at = request.session.get(FINANCE_SENSITIVE_SESSION_KEY)
        if verified_at:
            try:
                elapsed = (timezone.now().timestamp() - float(verified_at)) if isinstance(verified_at, (int, float)) else FINANCE_SENSITIVE_EXPIRY_MINUTES * 60
                if elapsed < FINANCE_SENSITIVE_EXPIRY_MINUTES * 60:
                    return view_func(request, *args, **kwargs)
            except (TypeError, ValueError):
                pass
        next_url = request.get_full_path()
        return redirect(reverse('hospital:finance_sensitive_confirm_password') + '?' + urlencode({'next': next_url}))
    return _wrapped


@login_required
@role_required('accountant', 'senior_account_officer')
def finance_sensitive_confirm_password(request):
    """Confirm password before accessing Insurance Receivable add/edit, Bank Reconciliation add/edit, etc."""
    next_url = request.GET.get('next', reverse('hospital:accountant_comprehensive_dashboard'))
    if request.method == 'POST':
        password = request.POST.get('password', '').strip()
        if not password:
            messages.error(request, 'Please enter your password.')
            return render(request, 'hospital/accountant/finance_sensitive_confirm_password.html', {'next_url': next_url})
        if request.user.check_password(password):
            request.session[FINANCE_SENSITIVE_SESSION_KEY] = timezone.now().timestamp()
            request.session.set_expiry(60 * 60 * 8)  # 8 hours session
            messages.success(request, 'Access granted. You can now enter or edit sensitive records.')
            return redirect(next_url)
        messages.error(request, 'Incorrect password. Please try again.')
    return render(request, 'hospital/accountant/finance_sensitive_confirm_password.html', {
        'next_url': next_url,
        'expiry_minutes': FINANCE_SENSITIVE_EXPIRY_MINUTES,
    })


@login_required
@role_required('accountant', 'senior_account_officer')
def accountant_comprehensive_dashboard(request):
    """Comprehensive accountant dashboard with all accounting features"""
    today = timezone.now().date()
    start_of_month = today.replace(day=1)

    dash_cache_key = f'hms:acct_comprehensive_dash:v1:{today.isoformat()}'
    cached_context = cache.get(dash_cache_key)
    if cached_context is not None:
        return render(request, 'hospital/accountant/comprehensive_dashboard.html', cached_context)
    
    # Safe query wrapper
    def safe_query(query_func, default=0):
        try:
            return query_func()
        except Exception:
            return default
    
    # Financial Summary
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
    
    # Accounts Payable: Use General Ledger first, then fall back to model
    def get_ap_total():
        from hospital.models_accounting import Account
        from hospital.models_accounting_advanced import AdvancedGeneralLedger
        total = Decimal('0.00')
        try:
            # Check General Ledger for AP accounts (Excel imported balances)
            ap_accounts = Account.objects.filter(
                account_type='liability',
                account_name__icontains='payable',
                is_deleted=False
            )
            ap_ids = list(ap_accounts.values_list('pk', flat=True))
            if ap_ids:
                ap_gl_total = AdvancedGeneralLedger.objects.filter(
                    account_id__in=ap_ids,
                    is_voided=False,
                    is_deleted=False
                ).aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
                total += ap_gl_total
            # If GL has no data, use AccountsPayable model
            if total == 0:
                total = AccountsPayable.objects.filter(
                    balance_due__gt=0,
                    is_deleted=False
                ).aggregate(total=Sum('balance_due'))['total'] or Decimal('0.00')
        except:
            total = AccountsPayable.objects.filter(
                balance_due__gt=0,
                is_deleted=False
            ).aggregate(total=Sum('balance_due'))['total'] or Decimal('0.00')
        return float(total) if total else 0.0
    
    total_ap = safe_query(get_ap_total)
    
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
    
    # Additional Financial Metrics
    # Accounts Payable
    overdue_ap = safe_query(lambda: AccountsPayable.objects.filter(
        balance_due__gt=0,
        due_date__lt=today
    ).aggregate(total=Sum('balance_due'))['total'] or 0)
    
    # Accounts Receivable - Overdue
    overdue_ar = safe_query(lambda: AdvancedAccountsReceivable.objects.filter(
        balance_due__gt=0,
        due_date__lt=today
    ).aggregate(total=Sum('balance_due'))['total'] or 0)
    
    # Total Bank Balance
    total_bank_balance = safe_query(lambda: BankAccount.objects.aggregate(
        total=Sum('current_balance')
    )['total'] or 0)
    
    # Today's Revenue
    today_revenue = safe_query(lambda: Revenue.objects.filter(
        revenue_date=today
    ).aggregate(total=Sum('amount'))['total'] or 0)
    
    # Today's Expenses
    today_expenses = safe_query(lambda: Expense.objects.filter(
        expense_date=today,
        status='paid'
    ).aggregate(total=Sum('amount'))['total'] or 0)
    
    # Pending Accounts Approval (requests that are admin_approved and waiting for accounts approval)
    pending_accounts_approval = 0
    try:
        from .models_procurement import ProcurementRequest
        pending_accounts_approval = safe_query(lambda: ProcurementRequest.objects.filter(
            status='admin_approved',
            is_deleted=False
        ).count())
    except (ImportError, AttributeError):
        try:
            from .models_workflow import ProcurementRequest
            pending_accounts_approval = safe_query(lambda: ProcurementRequest.objects.filter(
                status='admin_approved',
                is_deleted=False
            ).count())
        except (ImportError, AttributeError):
            pending_accounts_approval = 0
    
    # Procurement expenses (this month) - from approved procurement posted to ledger
    procurement_expense_total_month = safe_query(lambda: Expense.objects.filter(
        is_deleted=False,
        expense_date__gte=start_of_month,
        expense_date__lte=today,
    ).filter(
        Q(description__icontains='Procurement') | Q(vendor_invoice_number__istartswith='REQ')
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'))
    procurement_expense_count_month = safe_query(lambda: Expense.objects.filter(
        is_deleted=False,
        expense_date__gte=start_of_month,
        expense_date__lte=today,
    ).filter(
        Q(description__icontains='Procurement') | Q(vendor_invoice_number__istartswith='REQ')
    ).count())
    
    # Optional: Stock Management & Monitoring – only show link if URL is registered (avoids NoReverseMatch on old deploys)
    show_stock_management_link = False
    try:
        reverse('hospital:stock_management_monitoring')
        show_stock_management_link = True
    except Exception:
        pass

    context = {
        'today': today,
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'net_income': total_revenue - total_expenses,
        'today_revenue': today_revenue,
        'today_expenses': today_expenses,
        'pending_cashbook': pending_cashbook,
        'ready_to_classify': ready_to_classify,
        'unreconciled_transactions': unreconciled_transactions,
        'total_insurance_receivable': total_insurance_receivable,
        'pending_procurement': pending_procurement,
        'pending_payroll': pending_payroll,
        'unpaid_commissions': unpaid_commissions,
        'total_ar': total_ar,
        'total_ap': total_ap,
        'overdue_ar': overdue_ar,
        'overdue_ap': overdue_ap,
        'draft_journals': draft_journals,
        'pending_vouchers': pending_vouchers,
        'outstanding_cheques': outstanding_cheques,
        'total_bank_balance': total_bank_balance,
        'pending_accounts_approval': pending_accounts_approval,
        'procurement_expense_total_month': procurement_expense_total_month,
        'procurement_expense_count_month': procurement_expense_count_month,
        'show_stock_management_link': show_stock_management_link,
    }
    
    cache.set(dash_cache_key, context, ACCOUNTANT_COMPREHENSIVE_DASH_CACHE_TTL)
    return render(request, 'hospital/accountant/comprehensive_dashboard.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def stock_management_monitoring(request):
    """
    Stock Management & Monitoring – view all pharmacy stock added by store managers.
    Read-only for account to monitor what store manager is doing.
    Includes full audit trail (Added By, Added On, Last modified) and
    "All drugs as in pharmacy" view (drug-centric with batches).
    """
    stock_list = (
        PharmacyStock.objects.filter(is_deleted=False)
        .select_related('drug', 'created_by')
        .order_by('-created')
    )
    query = request.GET.get('q', '')
    filter_type = request.GET.get('filter', 'all')
    category_filter = request.GET.get('category', '')
    location_filter = request.GET.get('location', '').strip()
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if query:
        stock_list = stock_list.filter(
            Q(drug__name__icontains=query)
            | Q(drug__generic_name__icontains=query)
            | Q(batch_number__icontains=query)
        )
    if category_filter:
        stock_list = stock_list.filter(drug__category=category_filter)
    if location_filter:
        stock_list = stock_list.filter(location__iexact=location_filter)
    if filter_type == 'low_stock':
        stock_list = stock_list.filter(quantity_on_hand__lte=F('reorder_level'))
    elif filter_type == 'expiring':
        expiring_soon = date.today() + timedelta(days=90)
        stock_list = stock_list.filter(
            expiry_date__gte=date.today(),
            expiry_date__lte=expiring_soon,
            quantity_on_hand__gt=0,
        )
    if date_from:
        stock_list = stock_list.filter(created__date__gte=date_from)
    if date_to:
        stock_list = stock_list.filter(created__date__lte=date_to)

    # Build Location/Store dropdown: system stores (procurement) + any distinct location from stock
    try:
        from .models_procurement import Store
        system_stores = list(
            Store.objects.filter(is_deleted=False, is_active=True)
            .values_list('name', flat=True)
            .order_by('name')
        )
    except Exception:
        system_stores = []
    from_stock = list(
        PharmacyStock.objects.filter(is_deleted=False)
        .values_list('location', flat=True)
        .distinct()
    )
    from_stock = [loc for loc in from_stock if loc and str(loc).strip()]
    # Merge: system stores first, then any stock location not already in the list
    seen = set()
    stock_locations = []
    for name in system_stores:
        name = (name or '').strip()
        if name and name not in seen:
            seen.add(name)
            stock_locations.append(name)
    for loc in sorted(from_stock, key=lambda x: (x or '').lower()):
        loc = (loc or '').strip()
        if loc and loc not in seen:
            seen.add(loc)
            stock_locations.append(loc)

    expiry_threshold = (date.today() + timedelta(days=90)).isoformat()
    paginator = Paginator(stock_list, 50)
    page = request.GET.get('page')
    stock_page = paginator.get_page(page)

    # Summary stats (respect location filter)
    summary_qs = PharmacyStock.objects.filter(is_deleted=False)
    if location_filter:
        summary_qs = summary_qs.filter(location__iexact=location_filter)
    total_value = (
        summary_qs.aggregate(
            total=Sum(F('quantity_on_hand') * F('unit_cost'), output_field=DecimalField(max_digits=14, decimal_places=2))
        )
    )['total'] or Decimal('0.00')
    low_stock_count = summary_qs.filter(quantity_on_hand__lte=F('reorder_level')).count()
    total_batch_count = summary_qs.count()
    total_drug_count = summary_qs.values('drug').distinct().count()

    # All drugs as in pharmacy: same filters, grouped by drug. Newest stock first so newly added batches come up.
    stock_for_pharmacy_view = (
        stock_list.order_by('-created', 'drug__name', 'batch_number')[:500]
    )
    stock_list_pharmacy = list(stock_for_pharmacy_view)
    drugs_with_batches = []
    if stock_list_pharmacy:
        from itertools import groupby
        # Group by drug (preserve order: newest batches first within each drug)
        sorted_stock = sorted(stock_list_pharmacy, key=lambda s: (s.drug_id, -s.created.timestamp() if s.created else 0))
        for _drug_id, batch_iter in groupby(sorted_stock, key=lambda s: s.drug_id):
            batches = list(batch_iter)
            drug = batches[0].drug
            drugs_with_batches.append({'drug': drug, 'batches': batches})
        # Sort drugs so the one with the most recently added batch comes first
        _min_dt = timezone.now() - timedelta(days=365 * 50)
        drugs_with_batches.sort(
            key=lambda x: max((b.created for b in x['batches'] if b.created), default=_min_dt),
            reverse=True
        )

    context = {
        'stock_list': stock_page,
        'query': query,
        'filter_type': filter_type,
        'category_filter': category_filter,
        'location_filter': location_filter,
        'stock_locations': stock_locations,
        'date_from': date_from,
        'date_to': date_to,
        'drug_categories': Drug.CATEGORIES,
        'expiry_threshold': expiry_threshold,
        'total_value': total_value,
        'low_stock_count': low_stock_count,
        'total_batch_count': total_batch_count,
        'total_drug_count': total_drug_count,
        'drugs_with_batches': drugs_with_batches,
    }
    return render(request, 'hospital/accountant/stock_management_monitoring.html', context)


# ==================== CASHBOOK VIEWS ====================

def _cashbook_payment_method_labels():
    return dict(PaymentVoucher.PAYMENT_METHODS)


def _cashbook_status_labels():
    return dict(Cashbook.STATUS_CHOICES)


def _cashbook_entry_type_labels():
    return dict(Cashbook.ENTRY_TYPES)


def _cashbook_dec(value, default=Decimal('0')):
    """Coerce DB aggregate (often None) to Decimal for display and math."""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _cashbook_fmt_ghs(value):
    """Format GHS amounts in Python so templates never show blank from None/Decimal quirks."""
    d = _cashbook_dec(value)
    return f'{d:,.2f}'


def _cashbook_fmt_int(value):
    if value is None:
        return '0'
    return f'{int(value):,}'


@login_required
@role_required('accountant', 'senior_account_officer')
def cashbook_list(request):
    """List all cashbook entries with analytics for the current filter set."""
    base = Cashbook.objects.filter(is_deleted=False).order_by('-entry_date', '-entry_number')

    status_filter = request.GET.get('status', '')
    entry_type_filter = request.GET.get('entry_type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    filtered = base
    if status_filter:
        filtered = filtered.filter(status=status_filter)
    if entry_type_filter:
        filtered = filtered.filter(entry_type=entry_type_filter)
    if date_from:
        filtered = filtered.filter(entry_date__gte=date_from)
    if date_to:
        filtered = filtered.filter(entry_date__lte=date_to)

    qs = filtered.order_by()

    today = timezone.now().date()
    dec = DecimalField(max_digits=15, decimal_places=2)

    receipt_total = _cashbook_dec(qs.filter(entry_type='receipt').aggregate(t=Sum('amount'))['t'])
    payment_total = _cashbook_dec(qs.filter(entry_type='payment').aggregate(t=Sum('amount'))['t'])
    net_flow = receipt_total - payment_total

    agg = qs.aggregate(
        total_count=Count('id'),
        total_amount=Sum('amount'),
        pending_amount=Sum(Case(When(status='pending', then=F('amount')), default=Value(0), output_field=dec)),
        classified_amount=Sum(Case(When(status='classified', then=F('amount')), default=Value(0), output_field=dec)),
        void_amount=Sum(Case(When(status='void', then=F('amount')), default=Value(0), output_field=dec)),
        pending_count=Count('id', filter=Q(status='pending')),
        classified_count=Count('id', filter=Q(status='classified')),
        receipt_count=Count('id', filter=Q(entry_type='receipt')),
        payment_count=Count('id', filter=Q(entry_type='payment')),
    )

    total_count = int(agg['total_count'] or 0)
    total_amount = _cashbook_dec(agg['total_amount'])
    pending_amount = _cashbook_dec(agg['pending_amount'])
    classified_amount = _cashbook_dec(agg['classified_amount'])
    void_amount = _cashbook_dec(agg['void_amount'])
    pending_count = int(agg['pending_count'] or 0)
    classified_count = int(agg['classified_count'] or 0)
    receipt_count = int(agg['receipt_count'] or 0)
    payment_count = int(agg['payment_count'] or 0)
    avg_amount = (total_amount / total_count) if total_count else Decimal('0')

    ready_qs = qs.filter(status='pending', held_until__lte=today)
    ready_to_classify = ready_qs.count()
    ready_amount = _cashbook_dec(ready_qs.aggregate(t=Sum('amount'))['t'])

    method_labels = _cashbook_payment_method_labels()
    status_labels = _cashbook_status_labels()
    type_labels = _cashbook_entry_type_labels()

    status_breakdown = []
    for row in qs.values('status').annotate(cnt=Count('id'), amt=Sum('amount')).order_by('status'):
        st = row['status']
        status_breakdown.append({
            'key': st,
            'label': status_labels.get(st, st or 'Unknown'),
            'count': row['cnt'],
            'amount': str(row['amt'] or '0'),
        })

    type_breakdown = []
    for row in qs.values('entry_type').annotate(cnt=Count('id'), amt=Sum('amount')).order_by('entry_type'):
        et = row['entry_type']
        type_breakdown.append({
            'key': et,
            'label': type_labels.get(et, et or 'Unknown'),
            'count': row['cnt'],
            'amount': str(row['amt'] or '0'),
        })

    method_breakdown = []
    for row in qs.values('payment_method').annotate(cnt=Count('id'), amt=Sum('amount')).order_by('-amt'):
        pm = row['payment_method']
        method_breakdown.append({
            'key': pm or 'other',
            'label': method_labels.get(pm, pm or 'Other'),
            'count': row['cnt'],
            'amount': str(row['amt'] or '0'),
        })

    daily_rows = list(
        qs.values('entry_date')
        .annotate(
            receipts=Sum(
                Case(
                    When(entry_type='receipt', then=F('amount')),
                    default=Value(0),
                    output_field=dec,
                )
            ),
            payments=Sum(
                Case(
                    When(entry_type='payment', then=F('amount')),
                    default=Value(0),
                    output_field=dec,
                )
            ),
        )
        .order_by('entry_date')
    )
    daily_chart = [
        {
            'date': r['entry_date'].isoformat() if r['entry_date'] else '',
            'receipts': float(r['receipts'] or 0),
            'payments': float(r['payments'] or 0),
            'net': float((r['receipts'] or 0) - (r['payments'] or 0)),
        }
        for r in daily_rows
    ]

    chart_payload = {
        'daily': daily_chart,
        'status': [{'label': x['label'], 'count': x['count'], 'amount': float(Decimal(x['amount']))} for x in status_breakdown],
        'entryType': [{'label': x['label'], 'count': x['count'], 'amount': float(Decimal(x['amount']))} for x in type_breakdown],
        'paymentMethod': [{'label': x['label'], 'count': x['count'], 'amount': float(Decimal(x['amount']))} for x in method_breakdown],
    }

    get_params = request.GET.copy()
    get_params.pop('page', None)
    filter_query = get_params.urlencode()

    paginator = Paginator(filtered, 50)
    page = request.GET.get('page')
    entries_page = paginator.get_page(page)

    context = {
        'entries': entries_page,
        'status_filter': status_filter,
        'entry_type_filter': entry_type_filter,
        'date_from': date_from,
        'date_to': date_to,
        'filter_query': filter_query,
        'analytics': {
            'total_count': total_count,
            'receipt_total': receipt_total,
            'payment_total': payment_total,
            'net_flow': net_flow,
            'total_amount': total_amount,
            'pending_amount': pending_amount,
            'classified_amount': classified_amount,
            'void_amount': void_amount,
            'pending_count': pending_count,
            'classified_count': classified_count,
            'receipt_count': receipt_count,
            'payment_count': payment_count,
            'avg_amount': avg_amount,
            'ready_to_classify': ready_to_classify,
            'ready_amount': ready_amount,
            # Pre-formatted for reliable display (avoids empty cells from None / theme / filter edge cases)
            'total_count_fmt': _cashbook_fmt_int(total_count),
            'receipt_count_fmt': _cashbook_fmt_int(receipt_count),
            'payment_count_fmt': _cashbook_fmt_int(payment_count),
            'pending_count_fmt': _cashbook_fmt_int(pending_count),
            'classified_count_fmt': _cashbook_fmt_int(classified_count),
            'ready_to_classify_fmt': _cashbook_fmt_int(ready_to_classify),
            'receipt_total_fmt': _cashbook_fmt_ghs(receipt_total),
            'payment_total_fmt': _cashbook_fmt_ghs(payment_total),
            'net_flow_fmt': _cashbook_fmt_ghs(net_flow),
            'avg_amount_fmt': _cashbook_fmt_ghs(avg_amount),
            'pending_amount_fmt': _cashbook_fmt_ghs(pending_amount),
            'ready_amount_fmt': _cashbook_fmt_ghs(ready_amount),
            'classified_amount_fmt': _cashbook_fmt_ghs(classified_amount),
            'void_amount_fmt': _cashbook_fmt_ghs(void_amount),
            'total_amount_fmt': _cashbook_fmt_ghs(total_amount),
        },
        'chart_payload': chart_payload,
    }

    return render(request, 'hospital/accountant/cashbook_list.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def cashbook_detail(request, entry_id):
    """View cashbook entry details"""
    entry = get_object_or_404(Cashbook, pk=entry_id)
    
    context = {
        'entry': entry,
        'can_classify': entry.can_classify(),
    }
    
    return render(request, 'hospital/accountant/cashbook_detail.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def cashbook_classify(request, entry_id):
    """Classify cashbook entry to revenue/expense"""
    entry = get_object_or_404(Cashbook, pk=entry_id)
    
    if request.method == 'POST':
        try:
            revenue_account_id = request.POST.get('revenue_account')
            expense_account_id = request.POST.get('expense_account')
            
            revenue_account = None
            expense_account = None
            
            if revenue_account_id:
                revenue_account = get_object_or_404(Account, pk=revenue_account_id)
            if expense_account_id:
                expense_account = get_object_or_404(Account, pk=expense_account_id)
            
            entry.classify_to_revenue(
                user=request.user,
                revenue_account=revenue_account,
                expense_account=expense_account
            )
            
            messages.success(request, f'Cashbook entry {entry.entry_number} classified successfully.')
            return redirect('hospital:cashbook_detail', entry_id=entry.id)
            
        except Exception as e:
            messages.error(request, f'Error classifying entry: {str(e)}')
    
    # Get accounts for dropdown
    revenue_accounts = Account.objects.filter(account_type='revenue', is_active=True)
    expense_accounts = Account.objects.filter(account_type='expense', is_active=True)
    
    context = {
        'entry': entry,
        'revenue_accounts': revenue_accounts,
        'expense_accounts': expense_accounts,
    }
    
    return render(request, 'hospital/accountant/cashbook_classify.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def cashbook_bulk_classify(request):
    """Bulk classify ready cashbook entries"""
    if request.method == 'POST':
        entry_ids = request.POST.getlist('entry_ids')
        count = 0
        errors = []
        
        for entry_id in entry_ids:
            try:
                entry = Cashbook.objects.get(pk=entry_id, status='pending')
                if entry.can_classify():
                    if entry.entry_type == 'receipt' and entry.revenue_account:
                        entry.classify_to_revenue(request.user, entry.revenue_account)
                        count += 1
                    elif entry.entry_type == 'payment' and entry.expense_account:
                        entry.classify_to_revenue(request.user, expense_account=entry.expense_account)
                        count += 1
            except Exception as e:
                errors.append(f"Entry {entry_id}: {str(e)}")
        
        if count > 0:
            messages.success(request, f'Successfully classified {count} entries.')
        if errors:
            messages.warning(request, f'Some errors occurred: {"; ".join(errors)}')
    
    return redirect('hospital:cashbook_list')


# ==================== BANK RECONCILIATION VIEWS ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def bank_reconciliation_list(request):
    """List all bank reconciliations"""
    reconciliations = BankReconciliation.objects.all().order_by('-statement_date')
    
    paginator = Paginator(reconciliations, 20)
    page = request.GET.get('page')
    reconciliations_page = paginator.get_page(page)
    
    return render(request, 'hospital/accountant/bank_reconciliation_list.html', {
        'reconciliations': reconciliations_page,
    })


@login_required
@role_required('accountant', 'senior_account_officer')
def bank_reconciliation_detail(request, recon_id):
    """View bank reconciliation details"""
    reconciliation = get_object_or_404(BankReconciliation, pk=recon_id)
    items = reconciliation.items.all()
    
    return render(request, 'hospital/accountant/bank_reconciliation_detail.html', {
        'reconciliation': reconciliation,
        'items': items,
    })


# ==================== INSURANCE RECEIVABLE VIEWS ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def insurance_receivable_list(request):
    """List all insurance receivables - includes both InsuranceReceivable and InsuranceReceivableEntry"""
    from .models_primecare_accounting import InsuranceReceivableEntry
    from .models_accounting_advanced import InsuranceReceivable
    from django.utils import timezone
    
    # Get both types of receivables
    receivables_list = []
    
    # Add InsuranceReceivable records
    for rec in InsuranceReceivable.objects.all():
        receivables_list.append(rec)
    
    # Add InsuranceReceivableEntry records - EXCLUDE CORPORATE PAYERS
    # Handle case where table doesn't exist (migration not run)
    try:
        receivable_entries = InsuranceReceivableEntry.objects.filter(
            is_deleted=False
        ).exclude(payer__payer_type='corporate')  # Only insurance, not corporate
    except Exception:
        # Table doesn't exist or other database error - use empty queryset
        receivable_entries = InsuranceReceivableEntry.objects.none()
    
    try:
        for entry in receivable_entries:
            # Create a simple object-like dict for template compatibility
            class ReceivableEntryWrapper:
                def __init__(self, entry):
                    self.id = entry.id
                    self.receivable_number = entry.entry_number
                    self.insurance_company = entry.payer
                    self.patient = None
                    self.claim_number = ''
                    self.total_amount = entry.total_amount
                    self.amount_paid = entry.amount_received
                    self.balance_due = entry.outstanding_amount
                    self.status = entry.status
                    self.due_date = entry.entry_date
                    self.claim_date = entry.entry_date
                    self.is_entry = True
                    self.entry = entry
                
                def get_status_display(self):
                    return dict(InsuranceReceivableEntry.STATUS_CHOICES).get(self.status, self.status)
            
            receivables_list.append(ReceivableEntryWrapper(entry))
    except Exception:
        # Table doesn't exist or error accessing it - skip processing
        pass
    
    # Sort by date (newest first)
    receivables_list.sort(key=lambda x: getattr(x, 'claim_date', getattr(x, 'due_date', timezone.now().date())), reverse=True)
    
    # Filters
    status_filter = request.GET.get('status', '')
    insurance_filter = request.GET.get('insurance', '')
    
    if status_filter:
        receivables_list = [r for r in receivables_list if getattr(r, 'status', None) == status_filter]
    
    if insurance_filter:
        receivables_list = [r for r in receivables_list if str(getattr(r, 'insurance_company', None).id if hasattr(r, 'insurance_company') and r.insurance_company else '') == insurance_filter]
    
    paginator = Paginator(receivables_list, 50)
    page = request.GET.get('page')
    receivables_page = paginator.get_page(page)
    
    # Get insurance companies for filter (include both 'private' and 'nhis' payer types)
    from .models import Payer
    insurance_companies = Payer.objects.filter(payer_type__in=['private', 'nhis'], is_active=True)
    
    return render(request, 'hospital/accountant/insurance_receivable_list.html', {
        'receivables': receivables_page,
        'status_filter': status_filter,
        'insurance_companies': insurance_companies,
    })


@login_required
@role_required('accountant', 'senior_account_officer')
@require_finance_reauth
def insurance_receivable_create(request):
    """Create Insurance Receivable from HMS interface (password already confirmed)."""
    from .models import Payer, Patient, Invoice
    insurance_payers = Payer.objects.filter(payer_type__in=['private', 'nhis'], is_active=True, is_deleted=False).order_by('name')
    receivable_accounts = Account.objects.filter(account_type='asset', is_active=True, is_deleted=False).order_by('account_code')
    patients = Patient.objects.filter(is_deleted=False).order_by('first_name', 'last_name')[:500]
    invoices = Invoice.objects.filter(is_deleted=False).order_by('-issued_at')[:500]
    if request.method == 'POST':
        try:
            insurance_company_id = request.POST.get('insurance_company')
            patient_id = request.POST.get('patient')
            invoice_id = request.POST.get('invoice')
            claim_number = request.POST.get('claim_number', '').strip()
            claim_date = request.POST.get('claim_date')
            total_amount = request.POST.get('total_amount')
            amount_paid = request.POST.get('amount_paid') or '0'
            due_date = request.POST.get('due_date')
            payment_date = request.POST.get('payment_date') or None
            status = request.POST.get('status', 'pending')
            receivable_account_id = request.POST.get('receivable_account')
            notes = request.POST.get('notes', '').strip()
            if not all([insurance_company_id, patient_id, invoice_id, claim_date, total_amount, due_date, receivable_account_id]):
                messages.error(request, 'Please fill all required fields: Insurance Company, Patient, Invoice, Claim Date, Total Amount, Due Date, Receivable Account.')
                return render(request, 'hospital/accountant/insurance_receivable_form.html', {
                    'form_type': 'create',
                    'insurance_payers': insurance_payers,
                    'receivable_accounts': receivable_accounts,
                    'patients': patients,
                    'invoices': invoices,
                })
            insurance_company = get_object_or_404(Payer, pk=insurance_company_id)
            patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
            invoice = get_object_or_404(Invoice, pk=invoice_id, is_deleted=False)
            receivable_account = get_object_or_404(Account, pk=receivable_account_id, is_active=True)
            total_amount = Decimal(total_amount)
            amount_paid = Decimal(amount_paid)
            balance_due = total_amount - amount_paid
            with transaction.atomic():
                rec = InsuranceReceivable.objects.create(
                    insurance_company=insurance_company,
                    patient=patient,
                    invoice=invoice,
                    claim_number=claim_number,
                    claim_date=claim_date,
                    total_amount=total_amount,
                    amount_paid=amount_paid,
                    balance_due=balance_due,
                    due_date=due_date,
                    payment_date=payment_date if payment_date else None,
                    status=status,
                    receivable_account=receivable_account,
                    notes=notes,
                )
            messages.success(request, f'Insurance Receivable {rec.receivable_number} created successfully.')
            return redirect('hospital:insurance_receivable_list')
        except Exception as e:
            messages.error(request, f'Error saving: {str(e)}')
    return render(request, 'hospital/accountant/insurance_receivable_form.html', {
        'form_type': 'create',
        'insurance_payers': insurance_payers,
        'receivable_accounts': receivable_accounts,
        'patients': patients,
        'invoices': invoices,
    })


@login_required
@role_required('accountant', 'senior_account_officer')
@require_finance_reauth
def insurance_receivable_edit(request, receivable_id):
    """Edit Insurance Receivable from HMS interface."""
    from .models import Payer, Patient, Invoice
    rec = get_object_or_404(InsuranceReceivable, pk=receivable_id, is_deleted=False)
    insurance_payers = Payer.objects.filter(payer_type__in=['private', 'nhis'], is_active=True, is_deleted=False).order_by('name')
    receivable_accounts = Account.objects.filter(account_type='asset', is_active=True, is_deleted=False).order_by('account_code')
    if request.method == 'POST':
        try:
            rec.insurance_company = get_object_or_404(Payer, pk=request.POST.get('insurance_company'))
            rec.patient = get_object_or_404(Patient, pk=request.POST.get('patient'), is_deleted=False)
            rec.invoice = get_object_or_404(Invoice, pk=request.POST.get('invoice'), is_deleted=False)
            rec.claim_number = request.POST.get('claim_number', '').strip()
            rec.claim_date = request.POST.get('claim_date')
            rec.total_amount = Decimal(request.POST.get('total_amount'))
            rec.amount_paid = Decimal(request.POST.get('amount_paid') or '0')
            rec.due_date = request.POST.get('due_date')
            rec.payment_date = request.POST.get('payment_date') or None
            rec.status = request.POST.get('status', 'pending')
            rec.receivable_account = get_object_or_404(Account, pk=request.POST.get('receivable_account'), is_active=True)
            rec.notes = request.POST.get('notes', '').strip()
            rec.save()
            messages.success(request, f'Insurance Receivable {rec.receivable_number} updated successfully.')
            return redirect('hospital:insurance_receivable_list')
        except Exception as e:
            messages.error(request, f'Error saving: {str(e)}')
    return render(request, 'hospital/accountant/insurance_receivable_form.html', {
        'form_type': 'edit',
        'receivable': rec,
        'insurance_payers': insurance_payers,
        'receivable_accounts': receivable_accounts,
        'patients': Patient.objects.filter(is_deleted=False).order_by('first_name', 'last_name')[:500],
        'invoices': Invoice.objects.filter(is_deleted=False).order_by('-issued_at')[:500],
    })


@login_required
@role_required('accountant', 'senior_account_officer')
@require_finance_reauth
def bank_reconciliation_create(request):
    """Create Bank Reconciliation from HMS interface."""
    bank_accounts = BankAccount.objects.filter(is_active=True, is_deleted=False).order_by('account_name')
    if request.method == 'POST':
        try:
            bank_account_id = request.POST.get('bank_account')
            statement_date = request.POST.get('statement_date')
            statement_balance = request.POST.get('statement_balance')
            book_balance = request.POST.get('book_balance')
            deposits_in_transit = request.POST.get('deposits_in_transit') or '0'
            outstanding_cheques = request.POST.get('outstanding_cheques') or '0'
            bank_charges = request.POST.get('bank_charges') or '0'
            interest_earned = request.POST.get('interest_earned') or '0'
            other_adjustments = request.POST.get('other_adjustments') or '0'
            status = request.POST.get('status', 'draft')
            notes = request.POST.get('notes', '').strip()
            if not all([bank_account_id, statement_date, statement_balance, book_balance]):
                messages.error(request, 'Please fill Bank Account, Statement Date, Statement Balance, and Book Balance.')
                return render(request, 'hospital/accountant/bank_reconciliation_form.html', {
                    'form_type': 'create',
                    'bank_accounts': bank_accounts,
                })
            bank_account = get_object_or_404(BankAccount, pk=bank_account_id, is_active=True)
            with transaction.atomic():
                recon = BankReconciliation.objects.create(
                    bank_account=bank_account,
                    statement_date=statement_date,
                    statement_balance=Decimal(statement_balance),
                    book_balance=Decimal(book_balance),
                    deposits_in_transit=Decimal(deposits_in_transit),
                    outstanding_cheques=Decimal(outstanding_cheques),
                    bank_charges=Decimal(bank_charges),
                    interest_earned=Decimal(interest_earned),
                    other_adjustments=Decimal(other_adjustments),
                    status=status,
                    notes=notes,
                )
            messages.success(request, f'Bank Reconciliation {recon.reconciliation_number} created successfully.')
            return redirect('hospital:bank_reconciliation_list')
        except Exception as e:
            messages.error(request, f'Error saving: {str(e)}')
    return render(request, 'hospital/accountant/bank_reconciliation_form.html', {
        'form_type': 'create',
        'bank_accounts': bank_accounts,
    })


@login_required
@role_required('accountant', 'senior_account_officer')
@require_finance_reauth
def bank_reconciliation_edit(request, recon_id):
    """Edit Bank Reconciliation from HMS interface."""
    recon = get_object_or_404(BankReconciliation, pk=recon_id, is_deleted=False)
    bank_accounts = BankAccount.objects.filter(is_active=True, is_deleted=False).order_by('account_name')
    if request.method == 'POST':
        try:
            recon.bank_account = get_object_or_404(BankAccount, pk=request.POST.get('bank_account'), is_active=True)
            recon.statement_date = request.POST.get('statement_date')
            recon.statement_balance = Decimal(request.POST.get('statement_balance'))
            recon.book_balance = Decimal(request.POST.get('book_balance'))
            recon.deposits_in_transit = Decimal(request.POST.get('deposits_in_transit') or '0')
            recon.outstanding_cheques = Decimal(request.POST.get('outstanding_cheques') or '0')
            recon.bank_charges = Decimal(request.POST.get('bank_charges') or '0')
            recon.interest_earned = Decimal(request.POST.get('interest_earned') or '0')
            recon.other_adjustments = Decimal(request.POST.get('other_adjustments') or '0')
            recon.status = request.POST.get('status', 'draft')
            recon.notes = request.POST.get('notes', '').strip()
            recon.save()
            messages.success(request, f'Bank Reconciliation {recon.reconciliation_number} updated successfully.')
            return redirect('hospital:bank_reconciliation_list')
        except Exception as e:
            messages.error(request, f'Error saving: {str(e)}')
    return render(request, 'hospital/accountant/bank_reconciliation_form.html', {
        'form_type': 'edit',
        'reconciliation': recon,
        'bank_accounts': bank_accounts,
    })


# ==================== PROCUREMENT PURCHASE VIEWS ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def procurement_purchase_list(request):
    """List all procurement purchases and link to post-to-ledger for approved procurements."""
    purchases = ProcurementPurchase.objects.all().order_by('-purchase_date')
    
    # Filters
    purchase_type_filter = request.GET.get('purchase_type', '')
    status_filter = request.GET.get('status', '')
    
    if purchase_type_filter:
        purchases = purchases.filter(purchase_type=purchase_type_filter)
    if status_filter:
        purchases = purchases.filter(status=status_filter)
    
    paginator = Paginator(purchases, 50)
    page = request.GET.get('page')
    purchases_page = paginator.get_page(page)
    
    # Count approved procurements not yet posted to ledger (for accountant prompt)
    pending_post_count = 0
    if request.user.has_perm('hospital.can_approve_procurement_accounts') or request.user.is_superuser:
        from .models_procurement import ProcurementRequest
        from .procurement_accounting_integration import ProcurementAccountingIntegration
        approved = ProcurementRequest.objects.filter(status='accounts_approved', is_deleted=False)
        for pr in approved:
            summary = ProcurementAccountingIntegration.get_procurement_accounting_summary(pr)
            if not summary.get('has_accounting_entries'):
                pending_post_count += 1
                if pending_post_count > 10:
                    break
    
    return render(request, 'hospital/accountant/procurement_purchase_list.html', {
        'purchases': purchases_page,
        'purchase_type_filter': purchase_type_filter,
        'status_filter': status_filter,
        'pending_post_to_ledger_count': min(pending_post_count, 99),
    })


@login_required
@role_required('accountant', 'senior_account_officer')
def procurement_expenses_report(request):
    """Dedicated report: expenses created from approved procurement (posted to ledger)."""
    # Procurement-related expenses: created by procurement_accounting_integration
    base_qs = Expense.objects.filter(
        is_deleted=False
    ).filter(
        Q(description__icontains='Procurement') | Q(vendor_invoice_number__istartswith='REQ')
    ).select_related('category').order_by('-expense_date')
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        base_qs = base_qs.filter(expense_date__gte=date_from)
    if date_to:
        base_qs = base_qs.filter(expense_date__lte=date_to)
    
    # Default: current month
    if not date_from and not date_to:
        start_of_month = timezone.now().date().replace(day=1)
        base_qs = base_qs.filter(expense_date__gte=start_of_month)
    
    totals = base_qs.aggregate(
        total=Sum('amount'),
        count=Count('id'),
    )
    total_amount = totals.get('total') or Decimal('0.00')
    total_count = totals.get('count') or 0
    
    paginator = Paginator(base_qs, 30)
    page = request.GET.get('page')
    expenses_page = paginator.get_page(page)
    
    return render(request, 'hospital/accountant/procurement_expenses_report.html', {
        'expenses': expenses_page,
        'total_amount': total_amount,
        'total_count': total_count,
        'date_from': date_from,
        'date_to': date_to,
    })


# ==================== PAYROLL VIEWS (RMC salary template) ====================

def _staff_summaries_for_payroll_ids(payroll_ids):
    """Map payroll PK -> {names, emp_codes} strings for list view (batched query)."""
    if not payroll_ids:
        return {}
    from collections import defaultdict

    def _fmt(items, max_show=5):
        if not items:
            return '—'
        if len(items) <= max_show:
            return ', '.join(items)
        return ', '.join(items[:max_show]) + f' +{len(items) - max_show} more'

    qs = (
        AccountingPayrollEntry.objects.filter(
            payroll_id__in=payroll_ids,
            is_deleted=False,
        )
        .select_related('staff__user')
        .order_by('payroll_id', 'staff__user__last_name', 'staff__user__first_name')
    )
    by_payroll = defaultdict(lambda: {'names': [], 'codes': []})
    for e in qs:
        if not e.staff_id:
            continue
        name = e.staff.user.get_full_name() or e.staff.user.username
        emp = (e.staff.employee_id or '').strip() or '—'
        by_payroll[e.payroll_id]['names'].append(name)
        by_payroll[e.payroll_id]['codes'].append(emp)
    out = {}
    for pid in payroll_ids:
        bucket = by_payroll.get(pid) or {}
        names = bucket.get('names') or []
        codes = bucket.get('codes') or []
        if not names:
            out[pid] = {'names': '—', 'emp_codes': '—'}
        else:
            out[pid] = {'names': _fmt(names), 'emp_codes': _fmt(codes)}
    return out


def _payroll_list_rows_expanded(payrolls_page):
    """
    One list row per staff line (not one row per run with comma-joined names).
    Payrolls with no lines still produce a single placeholder row using run totals.
    """
    from collections import defaultdict

    page_ids = [p.pk for p in payrolls_page]
    if not page_ids:
        return []

    def _pid_key(pid):
        if pid is None:
            return None
        return str(pid)

    entries_by_payroll = defaultdict(list)
    qs = (
        AccountingPayrollEntry.objects.filter(
            payroll_id__in=page_ids,
            is_deleted=False,
        )
        .select_related('staff__user')
        .order_by('payroll_id', 'staff__user__last_name', 'staff__user__first_name', 'id')
    )
    for e in qs:
        if e.staff_id is None:
            continue
        k = _pid_key(e.payroll_id)
        entries_by_payroll[k].append(e)
    rows = []
    for p in payrolls_page:
        n = getattr(p, 'active_entry_count', 0) or 0
        label_display = _payroll_label_display(p, n)
        source_display = _payroll_source_display(p, n)
        elist = entries_by_payroll.get(_pid_key(p.pk)) or []
        if not elist:
            rows.append({
                'payroll': p,
                'staff_name': '—',
                'staff_emp_code': '—',
                'row_gross': p.total_gross_pay,
                'row_deductions': p.total_deductions,
                'row_net': p.total_net_pay,
                'label_display': label_display,
                'source_display': source_display,
            })
            continue
        for e in elist:
            name = e.staff.user.get_full_name() or e.staff.user.username
            emp = (e.staff.employee_id or '').strip() or '—'
            rows.append({
                'payroll': p,
                'staff_name': name,
                'staff_emp_code': emp,
                'row_gross': e.gross_pay,
                'row_deductions': e.deductions,
                'row_net': e.net_pay,
                'label_display': label_display,
                'source_display': source_display,
            })
    return rows


def _payroll_label_display(payroll, active_entry_count=0):
    """List-column label: saved period_label, else month/year + staff count from period."""
    pl = (getattr(payroll, 'period_label', None) or '').strip()
    if pl and pl not in {'—', '–', '-'}:
        return pl
    month_y = payroll.payroll_period_start.strftime('%B %Y')
    if active_entry_count > 0:
        return f'{month_y}, {active_entry_count} staff'
    return f'{month_y}, no lines yet'


def _payroll_source_display(payroll, active_entry_count=0):
    """List-column source: Excel filename when stored, else short HMS hint."""
    fn = (getattr(payroll, 'import_source_filename', None) or '').strip()
    if fn and fn not in {'—', '–', '-'}:
        return fn
    if active_entry_count > 0:
        return 'Entered in HMS'
    return '—'


@login_required
@role_required('accountant', 'senior_account_officer')
def payroll_list(request):
    """Accounting payroll hub — matches Sample Salary-RMC.xlsx (Raphal Medical Centre layout)."""
    payrolls = (
        AccountingPayroll.objects.filter(is_deleted=False)
        .annotate(
            active_entry_count=Count('entries', filter=Q(entries__is_deleted=False)),
        )
        .order_by('-payroll_period_end')
    )
    agg = payrolls.aggregate(
        cnt=Count('id'),
        sum_net=Sum('total_net_pay'),
        sum_gross=Sum('total_gross_pay'),
    )
    paginator = Paginator(payrolls, 20)
    payrolls_page = paginator.get_page(request.GET.get('page'))
    payroll_rows = _payroll_list_rows_expanded(payrolls_page)
    return render(request, 'hospital/accountant/payroll_list.html', {
        'payroll_rows': payroll_rows,
        'payrolls': payrolls_page,
        'total_payroll_runs': agg['cnt'] or 0,
        'sum_net_all': agg['sum_net'] or Decimal('0'),
        'sum_gross_all': agg['sum_gross'] or Decimal('0'),
    })


@login_required
@role_required('accountant', 'senior_account_officer')
def accountant_payroll_create(request):
    if request.method == 'POST':
        try:
            ps = date.fromisoformat(request.POST.get('payroll_period_start', '').strip())
            pe = date.fromisoformat(request.POST.get('payroll_period_end', '').strip())
            pd = date.fromisoformat(request.POST.get('pay_date', '').strip())
        except ValueError:
            messages.error(request, 'Enter valid dates (YYYY-MM-DD).')
            today = timezone.now().date()
            st = today.replace(day=1)
            return render(request, 'hospital/accountant/payroll_create.html', {
                'default_start': request.POST.get('payroll_period_start') or st.isoformat(),
                'default_end': request.POST.get('payroll_period_end') or today.isoformat(),
                'default_pay': request.POST.get('pay_date') or today.isoformat(),
                'period_label_value': (request.POST.get('period_label') or '')[:120],
                'deduction_apply_percentages': request.POST.get('deduction_apply_percentages') == '1',
                'deduction_ssnit_employee_pct': (request.POST.get('deduction_ssnit_employee_pct') or '5.5').strip(),
                'deduction_pension_employee_pct': (request.POST.get('deduction_pension_employee_pct') or '5.0').strip(),
                'deduction_paye_pct': (request.POST.get('deduction_paye_pct') or '0').strip(),
                'deduction_other_deduction_pct': (request.POST.get('deduction_other_deduction_pct') or '0').strip(),
                **_staff_pick_payroll_create_context(_staff_uuid_list_from_post(request)),
            })
        label = (request.POST.get('period_label') or '').strip()[:120]
        pf = _accounting_payroll_field_names()
        create_kw = dict(
            payroll_period_start=ps,
            payroll_period_end=pe,
            pay_date=pd,
            status='draft',
            created_by=request.user,
            total_gross_pay=Decimal('0'),
            total_deductions=Decimal('0'),
            total_net_pay=Decimal('0'),
        )
        if 'period_label' in pf:
            create_kw['period_label'] = label or f'{ps.strftime("%B %Y")} — Payroll'
        if 'deduction_apply_percentages' in pf:
            create_kw['deduction_apply_percentages'] = request.POST.get('deduction_apply_percentages') == '1'
        if 'deduction_ssnit_employee_pct' in pf:
            create_kw['deduction_ssnit_employee_pct'] = _clamp_percentage_field(
                _payroll_decimal_from_post(request, 'deduction_ssnit_employee_pct', '5.5')
            )
        if 'deduction_pension_employee_pct' in pf:
            create_kw['deduction_pension_employee_pct'] = _clamp_percentage_field(
                _payroll_decimal_from_post(request, 'deduction_pension_employee_pct', '5.0')
            )
        if 'deduction_paye_pct' in pf:
            create_kw['deduction_paye_pct'] = _clamp_percentage_field(
                _payroll_decimal_from_post(request, 'deduction_paye_pct', '0')
            )
        if 'deduction_other_deduction_pct' in pf:
            create_kw['deduction_other_deduction_pct'] = _clamp_percentage_field(
                _payroll_decimal_from_post(request, 'deduction_other_deduction_pct', '0')
            )
        p = AccountingPayroll(**create_kw)
        p.save()
        staff_uuids = _staff_uuid_list_from_post(request)
        created_lines = 0
        if staff_uuids:
            from .models import Staff

            z = Decimal('0')
            staff_found = list(
                Staff.objects.filter(pk__in=staff_uuids, is_deleted=False).select_related('user')
            )
            with transaction.atomic():
                for st in staff_found:
                    obj, created = AccountingPayrollEntry.objects.get_or_create(
                        payroll=p,
                        staff=st,
                        defaults={
                            'gross_pay': z,
                            'deductions': z,
                            'net_pay': z,
                        },
                    )
                    if created:
                        created_lines += 1
                    elif obj.is_deleted:
                        obj.is_deleted = False
                        obj.gross_pay = z
                        obj.deductions = z
                        obj.net_pay = z
                        obj.save()
                        created_lines += 1
            p.recalculate_totals_from_entries()
        if created_lines:
            messages.success(
                request,
                f'Payroll run created with {created_lines} staff line(s). Import Excel to fill pay amounts, or add more staff from admin.',
            )
        elif staff_uuids and not created_lines:
            messages.warning(
                request,
                'Payroll run created, but no matching active staff were found for the ticked names. Import Excel or pick staff again.',
            )
        else:
            messages.success(request, 'Payroll run created. Import the RMC Excel file on the next screen.')
        return redirect('accountant_payroll_detail', pk=p.pk)
    today = timezone.now().date()
    start = today.replace(day=1)
    return render(request, 'hospital/accountant/payroll_create.html', {
        'default_start': start.isoformat(),
        'default_end': today.isoformat(),
        'default_pay': today.isoformat(),
        'deduction_apply_percentages': False,
        'deduction_ssnit_employee_pct': '5.5',
        'deduction_pension_employee_pct': '5.0',
        'deduction_paye_pct': '0',
        'deduction_other_deduction_pct': '0',
        'period_label_value': '',
        **_staff_pick_payroll_create_context([]),
    })


@login_required
@require_POST
@role_required('accountant', 'senior_account_officer')
def accountant_payroll_deduction_rates(request, pk):
    payroll = get_object_or_404(AccountingPayroll, pk=pk, is_deleted=False)
    if payroll.status not in ('draft', 'calculated'):
        messages.error(request, 'Only draft or calculated payrolls can change deduction settings.')
        return redirect('accountant_payroll_detail', pk=pk)
    pf = _accounting_payroll_field_names()
    if 'deduction_apply_percentages' not in pf:
        messages.error(
            request,
            'This server needs the payroll migration for automatic percentages. Run: python manage.py migrate hospital',
        )
        return redirect('accountant_payroll_detail', pk=pk)
    payroll.deduction_apply_percentages = request.POST.get('deduction_apply_percentages') == '1'
    payroll.deduction_ssnit_employee_pct = _clamp_percentage_field(
        _payroll_decimal_from_post(request, 'deduction_ssnit_employee_pct', '5.5')
    )
    payroll.deduction_pension_employee_pct = _clamp_percentage_field(
        _payroll_decimal_from_post(request, 'deduction_pension_employee_pct', '5.0')
    )
    payroll.deduction_paye_pct = _clamp_percentage_field(
        _payroll_decimal_from_post(request, 'deduction_paye_pct', '0')
    )
    payroll.deduction_other_deduction_pct = _clamp_percentage_field(
        _payroll_decimal_from_post(request, 'deduction_other_deduction_pct', '0')
    )
    payroll.save()
    if payroll.deduction_apply_percentages:
        payroll.apply_percentage_deductions_to_all_entries()
        messages.success(request, 'Deduction rates saved. All staff lines were recalculated from earnings.')
    else:
        messages.success(
            request,
            'Settings saved. Automatic percentage deductions are off — imported or manual amounts are kept until you edit lines.',
        )
    return redirect('accountant_payroll_detail', pk=pk)


def _payroll_entry_field_names():
    return {f.name for f in AccountingPayrollEntry._meta.local_concrete_fields}


def _accounting_payroll_field_names():
    return {f.name for f in AccountingPayroll._meta.local_concrete_fields}


def _payroll_decimal_from_post(request, key, default='0'):
    raw = (request.POST.get(key) or '').strip().replace(',', '')
    if not raw:
        try:
            return Decimal(default)
        except InvalidOperation:
            return Decimal('0')
    try:
        return Decimal(raw)
    except InvalidOperation:
        try:
            return Decimal(default)
        except InvalidOperation:
            return Decimal('0')


def _clamp_percentage_field(value: Decimal) -> Decimal:
    if value < Decimal('0'):
        return Decimal('0')
    if value > Decimal('100'):
        return Decimal('100')
    return value


def _staff_uuid_list_from_post(request):
    """Deduped valid UUIDs from POST staff_ids checkboxes."""
    out = []
    seen = set()
    for x in request.POST.getlist('staff_ids'):
        x = (x or '').strip()
        if not x or x in seen:
            continue
        seen.add(x)
        try:
            out.append(UUID(x))
        except ValueError:
            continue
    return out


def _staff_pick_payroll_create_context(selected_staff_uuid):
    pick_qs, pick_relaxed = _staff_pick_list_for_payroll_create()
    return {
        'staff_pick_list': pick_qs,
        'staff_pick_relaxed': pick_relaxed,
        'staff_pick_count': pick_qs.count(),
        'selected_staff_uuid': selected_staff_uuid,
    }


def _staff_pick_list_for_payroll_create():
    """
    Prefer active, employable staff; widen the filter if that returns nobody (common on
    sites where is_active / employment_status were never maintained).
    """
    from .models import Staff

    base = (
        Staff.objects.filter(is_deleted=False)
        .select_related('user', 'department')
    )
    strict = (
        base.filter(user__is_active=True, is_active=True)
        .exclude(employment_status__in=('terminated', 'retired'))
        .order_by('user__last_name', 'user__first_name', 'id')
    )
    if strict.exists():
        return strict, False
    loose = (
        base.filter(user__is_active=True)
        .order_by('user__last_name', 'user__first_name', 'id')
    )
    if loose.exists():
        return loose, True
    any_staff = base.order_by('user__last_name', 'user__first_name', 'id')
    return any_staff, True


@login_required
@role_required('accountant', 'senior_account_officer')
def accountant_payroll_detail(request, pk):
    payroll = get_object_or_404(AccountingPayroll, pk=pk, is_deleted=False)
    entry_fields = _payroll_entry_field_names()
    # RMC breakdown (migration 1108+). Do not require sheet_serial — some DBs lag migrations.
    has_rmc_columns = 'basic_salary' in entry_fields
    show_sheet_serial = 'sheet_serial' in entry_fields

    # Never order_by('sheet_serial') in SQL: older deployed models omit that field → FieldError.
    entries_qs = (
        payroll.entries.filter(is_deleted=False)
        .select_related('staff', 'staff__user', 'staff__department')
        .order_by('staff__user__last_name', 'staff__user__first_name', 'id')
    )
    entries_list = list(entries_qs)
    if show_sheet_serial:
        entries_list.sort(
            key=lambda e: (
                getattr(e, 'sheet_serial', None) is None,
                getattr(e, 'sheet_serial', None) or 0,
            )
        )

    by_dept = defaultdict(lambda: Decimal('0'))
    for e in entries_list:
        if has_rmc_columns and 'department_snapshot' in entry_fields:
            d = (getattr(e, 'department_snapshot', None) or 'Unassigned')
            d = (d or '').strip() or 'Unassigned'
        else:
            dept = getattr(e.staff, 'department', None)
            d = dept.name if dept else 'Unassigned'
        by_dept[d] += e.net_pay
    chart_pairs = sorted(by_dept.items(), key=lambda x: float(x[1]), reverse=True)[:12]
    n_lines = len(entries_list)
    ur = get_user_role(request.user)
    can_edit_payroll = payroll.status in ('draft', 'calculated')
    accountant_like = ur in ('accountant', 'senior_account_officer', 'admin')
    can_submit_payroll = (
        accountant_like
        and can_edit_payroll
        and n_lines > 0
    )
    can_withdraw_payroll = (
        ur in ('accountant', 'senior_account_officer')
        and payroll.status == 'pending_approval'
    )
    can_approve_payroll = ur == 'admin' and payroll.status == 'pending_approval'
    return render(request, 'hospital/accountant/payroll_detail.html', {
        'payroll': payroll,
        'entries': entries_list,
        'has_rmc_columns': has_rmc_columns,
        'show_sheet_serial': show_sheet_serial,
        'payroll_heading': _payroll_label_display(payroll, n_lines),
        'source_banner': _payroll_source_display(payroll, n_lines),
        'chart_labels_json': json.dumps([p[0] for p in chart_pairs]),
        'chart_values_json': json.dumps([float(p[1]) for p in chart_pairs]),
        'can_edit_payroll': can_edit_payroll,
        'can_submit_payroll': can_submit_payroll,
        'can_withdraw_payroll': can_withdraw_payroll,
        'can_approve_payroll': can_approve_payroll,
    })


@login_required
@require_POST
@role_required('accountant', 'senior_account_officer')
def accountant_payroll_submit_approval(request, pk):
    payroll = get_object_or_404(AccountingPayroll, pk=pk, is_deleted=False)
    if payroll.status not in ('draft', 'calculated'):
        messages.error(request, 'Only draft payrolls can be submitted for approval.')
        return redirect('accountant_payroll_detail', pk=pk)
    n = payroll.entries.filter(is_deleted=False).count()
    if n == 0:
        messages.error(request, 'Import or add at least one staff line before submitting.')
        return redirect('accountant_payroll_detail', pk=pk)
    payroll.recalculate_totals_from_entries()
    payroll.status = 'pending_approval'
    payroll.save(update_fields=['status', 'total_gross_pay', 'total_deductions', 'total_net_pay', 'modified'])
    messages.success(
        request,
        'Payroll submitted for administrator approval. An admin can approve it from this same page.',
    )
    return redirect('accountant_payroll_detail', pk=pk)


@login_required
@require_POST
@role_required('accountant', 'senior_account_officer')
def accountant_payroll_withdraw_submission(request, pk):
    if get_user_role(request.user) not in ('accountant', 'senior_account_officer'):
        messages.error(request, 'Only accounting staff can withdraw a payroll submission.')
        return redirect('accountant_payroll_list')
    payroll = get_object_or_404(AccountingPayroll, pk=pk, is_deleted=False)
    if payroll.status != 'pending_approval':
        messages.error(request, 'Only payrolls awaiting approval can be withdrawn.')
        return redirect('accountant_payroll_detail', pk=pk)
    payroll.status = 'draft'
    payroll.approved_by = None
    payroll.save(update_fields=['status', 'approved_by', 'modified'])
    messages.info(request, 'Submission withdrawn. You can edit and submit again when ready.')
    return redirect('accountant_payroll_detail', pk=pk)


@login_required
@require_POST
@role_required('admin')
def accountant_payroll_approve(request, pk):
    payroll = get_object_or_404(AccountingPayroll, pk=pk, is_deleted=False)
    if payroll.status != 'pending_approval':
        messages.error(request, 'This payroll is not waiting for approval.')
        return redirect('accountant_payroll_detail', pk=pk)
    payroll.status = 'approved'
    payroll.approved_by = request.user
    payroll.save(update_fields=['status', 'approved_by', 'modified'])
    messages.success(request, 'Payroll approved.')
    return redirect('accountant_payroll_detail', pk=pk)


@login_required
@require_POST
@role_required('admin')
def accountant_payroll_reject(request, pk):
    payroll = get_object_or_404(AccountingPayroll, pk=pk, is_deleted=False)
    if payroll.status != 'pending_approval':
        messages.error(request, 'This payroll is not waiting for approval.')
        return redirect('accountant_payroll_detail', pk=pk)
    payroll.status = 'draft'
    payroll.approved_by = None
    payroll.save(update_fields=['status', 'approved_by', 'modified'])
    messages.warning(request, 'Payroll returned to draft for revision.')
    return redirect('accountant_payroll_detail', pk=pk)


@login_required
@role_required('accountant', 'senior_account_officer')
def accountant_payroll_import(request):
    if request.method != 'POST':
        return redirect('accountant_payroll_list')
    from io import BytesIO
    from .utils_salary_rmc_import import parse_rmc_workbook, apply_rmc_rows_to_payroll

    payroll = get_object_or_404(AccountingPayroll, pk=request.POST.get('payroll_id', ''), is_deleted=False)
    if payroll.status not in ('draft', 'calculated'):
        messages.error(request, 'This payroll status cannot be modified from Excel.')
        return redirect('accountant_payroll_detail', pk=payroll.pk)

    if 'basic_salary' not in _payroll_entry_field_names():
        messages.error(
            request,
            'RMC Excel import requires payroll migrations on this server. Run: python manage.py migrate hospital',
        )
        return redirect('accountant_payroll_detail', pk=payroll.pk)

    upload = request.FILES.get('excel_file')
    if not upload:
        messages.error(request, 'Choose an Excel file (.xlsx).')
        return redirect('accountant_payroll_detail', pk=payroll.pk)

    raw = BytesIO(upload.read())
    period_label, ymd, rows, warnings = parse_rmc_workbook(raw)
    for w in warnings:
        messages.warning(request, w)
    if not rows:
        messages.error(request, 'No salary rows found. Use the official RMC template layout.')
        return redirect('accountant_payroll_detail', pk=payroll.pk)

    pf = _accounting_payroll_field_names()
    if request.POST.get('sync_dates') == '1' and ymd:
        y, m, last = ymd
        payroll.payroll_period_start = date(y, m, 1)
        payroll.payroll_period_end = date(y, m, last)
        payroll.pay_date = date(y, m, last)
    if period_label and 'period_label' in pf:
        current = getattr(payroll, 'period_label', '') or ''
        if not current or request.POST.get('overwrite_label') == '1':
            payroll.period_label = period_label[:120]
    if 'import_source_filename' in pf:
        payroll.import_source_filename = upload.name[:255]
    payroll.save()

    replace = request.POST.get('replace_existing') == '1'
    errors, count = apply_rmc_rows_to_payroll(payroll, rows, replace=replace)
    for e in errors[:30]:
        messages.warning(request, e)
    if len(errors) > 30:
        messages.warning(request, f'…and {len(errors) - 30} more row messages.')
    if count:
        messages.success(request, f'Successfully imported {count} staff line(s).')
    elif not errors:
        messages.info(request, 'No new lines were created.')
    return redirect('accountant_payroll_detail', pk=payroll.pk)


@login_required
@role_required('accountant', 'senior_account_officer')
def accountant_payroll_template_download(request):
    from .utils_salary_rmc_import import build_rmc_template_workbook_bytes

    data = build_rmc_template_workbook_bytes()
    resp = HttpResponse(
        data,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    resp['Content-Disposition'] = 'attachment; filename="Sample_Salary-RMC_template.xlsx"'
    return resp


@login_required
@role_required('accountant', 'senior_account_officer')
def accountant_payroll_export_runs(request):
    """Download all payroll runs (summary table) as .xlsx — not limited to the current list page."""
    from .utils_accountant_payroll_export import payroll_runs_summary_to_xlsx_bytes

    payrolls = list(
        AccountingPayroll.objects.filter(is_deleted=False)
        .annotate(active_entry_count=Count('entries', filter=Q(entries__is_deleted=False)))
        .order_by('-payroll_period_end', '-payroll_number')
    )
    ids = [p.pk for p in payrolls]
    staff_bits = _staff_summaries_for_payroll_ids(ids)
    rows = []
    for p in payrolls:
        n = getattr(p, 'active_entry_count', 0) or 0
        s = staff_bits.get(p.pk) or {'names': '—', 'emp_codes': '—'}
        rows.append({
            'payroll_number': p.payroll_number,
            'staff_names': s['names'],
            'emp_codes': s['emp_codes'],
            'period_start': p.payroll_period_start,
            'period_end': p.payroll_period_end,
            'label': _payroll_label_display(p, n),
            'pay_date': p.pay_date,
            'gross': p.total_gross_pay,
            'deductions': p.total_deductions,
            'net': p.total_net_pay,
            'status': p.get_status_display(),
            'source': _payroll_source_display(p, n),
        })
    try:
        raw = payroll_runs_summary_to_xlsx_bytes(rows)
    except RuntimeError as e:
        messages.error(request, str(e))
        return redirect('accountant_payroll_list')
    fn = f'payroll_runs_{timezone.now().strftime("%Y%m%d_%H%M")}.xlsx'
    resp = HttpResponse(
        raw,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    resp['Content-Disposition'] = f'attachment; filename="{fn}"'
    return resp


@login_required
@role_required('accountant', 'senior_account_officer')
def accountant_payroll_export_lines(request, pk):
    """Download one payroll run’s staff lines as .xlsx (RMC-style columns when available)."""
    from .utils_accountant_payroll_export import payroll_run_lines_to_xlsx_bytes

    payroll = get_object_or_404(AccountingPayroll, pk=pk, is_deleted=False)
    entry_fields = _payroll_entry_field_names()
    has_rmc = 'basic_salary' in entry_fields
    show_sheet_serial = 'sheet_serial' in entry_fields
    entries_qs = (
        payroll.entries.filter(is_deleted=False)
        .select_related('staff', 'staff__user', 'staff__department')
        .order_by('staff__user__last_name', 'staff__user__first_name', 'id')
    )
    entries_list = list(entries_qs)
    if show_sheet_serial:
        entries_list.sort(
            key=lambda e: (
                getattr(e, 'sheet_serial', None) is None,
                getattr(e, 'sheet_serial', None) or 0,
            )
        )
    n = len(entries_list)
    try:
        raw = payroll_run_lines_to_xlsx_bytes(
            payroll.payroll_number,
            _payroll_label_display(payroll, n),
            payroll.pay_date,
            payroll.get_status_display(),
            entries_list,
            has_rmc,
        )
    except RuntimeError as e:
        messages.error(request, str(e))
        return redirect('accountant_payroll_detail', pk=payroll.pk)
    safe_num = ''.join(c if c.isalnum() or c in '-_' else '_' for c in payroll.payroll_number)
    fn = f'{safe_num}_staff_lines.xlsx'
    resp = HttpResponse(
        raw,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    resp['Content-Disposition'] = f'attachment; filename="{fn}"'
    return resp


@login_required
@role_required('accountant', 'senior_account_officer')
def doctor_commission_list(request):
    """List all doctor commissions"""
    commissions = DoctorCommission.objects.all().order_by('-service_date')
    
    # Filters
    is_paid_filter = request.GET.get('is_paid', '')
    doctor_filter = request.GET.get('doctor', '')
    
    if is_paid_filter != '':
        commissions = commissions.filter(is_paid=is_paid_filter == 'true')
    if doctor_filter:
        commissions = commissions.filter(doctor_id=doctor_filter)
    
    # Calculate summary statistics BEFORE pagination
    total_commissions = commissions.count()
    paid_count = commissions.filter(is_paid=True).count()
    unpaid_count = commissions.filter(is_paid=False).count()
    unpaid_total = commissions.filter(is_paid=False).aggregate(
        total=Sum('doctor_share')
    )['total'] or 0
    
    # Paginate after calculating stats
    paginator = Paginator(commissions, 50)
    page = request.GET.get('page')
    commissions_page = paginator.get_page(page)
    
    # Get doctors for filter
    from .models import Staff
    doctors = Staff.objects.filter(profession='doctor', is_deleted=False)
    
    return render(request, 'hospital/accountant/doctor_commission_list.html', {
        'commissions': commissions_page,
        'is_paid_filter': is_paid_filter,
        'doctors': doctors,
        'total_commissions': total_commissions,
        'paid_count': paid_count,
        'unpaid_count': unpaid_count,
        'unpaid_total': unpaid_total,
    })


# ==================== PROFIT & LOSS VIEWS ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def profit_loss_list(request):
    """List all profit & loss reports with aggregates and chart payload."""
    reports_qs = ProfitLossReport.objects.all().order_by('-period_end')

    period_filter = request.GET.get('period', '').strip()
    fiscal_year_filter = request.GET.get('fiscal_year', '').strip()

    if period_filter:
        reports_qs = reports_qs.filter(report_period=period_filter)
    if fiscal_year_filter:
        try:
            reports_qs = reports_qs.filter(fiscal_year_id=int(fiscal_year_filter))
        except (ValueError, TypeError):
            fiscal_year_filter = ''

    aggregates = reports_qs.aggregate(
        n=Count('id'),
        sum_rev=Sum('total_revenue'),
        sum_exp=Sum('total_expenses'),
        sum_net=Sum('net_profit'),
        avg_margin=Avg('profit_percentage'),
    )
    profitable_count = reports_qs.filter(net_profit__gte=0).count()
    loss_count = reports_qs.filter(net_profit__lt=0).count()

    period_labels = {'monthly': 'Monthly', 'quarterly': 'Quarterly', 'yearly': 'Yearly'}
    period_mix_rows = list(
        reports_qs.values('report_period').annotate(c=Count('id')).order_by('report_period')
    )
    period_mix = [
        {'label': period_labels.get(row['report_period'], row['report_period'] or '—'), 'count': row['c']}
        for row in period_mix_rows
    ]

    chron = list(
        reports_qs.order_by('period_end', 'period_start', 'report_number')[:48]
    )
    trend_labels = []
    trend_rev = []
    trend_exp = []
    trend_net = []
    for r in chron:
        if r.period_end:
            trend_labels.append(r.period_end.strftime('%b %Y'))
        else:
            trend_labels.append(r.report_number or '—')
        trend_rev.append(float(r.total_revenue or 0))
        trend_exp.append(float(r.total_expenses or 0))
        trend_net.append(float(r.net_profit or 0))

    rev_merged = defaultdict(lambda: Decimal('0'))
    exp_merged = defaultdict(lambda: Decimal('0'))
    for r in reports_qs.iterator(chunk_size=200):
        rc = r.revenue_by_category
        if isinstance(rc, dict):
            for k, v in rc.items():
                try:
                    rev_merged[str(k)] += Decimal(str(v))
                except (InvalidOperation, ValueError, TypeError):
                    pass
        ec = r.expenses_by_category
        if isinstance(ec, dict):
            for k, v in ec.items():
                try:
                    exp_merged[str(k)] += Decimal(str(v))
                except (InvalidOperation, ValueError, TypeError):
                    pass

    def _top_category_rows(merged, limit=12):
        items = sorted(merged.items(), key=lambda x: abs(x[1]), reverse=True)[:limit]
        return [{'label': (k[:100] if k else '—'), 'amount': float(v)} for k, v in items]

    chart_payload = {
        'trend': {
            'labels': trend_labels,
            'revenue': trend_rev,
            'expenses': trend_exp,
            'net': trend_net,
        },
        'periodMix': period_mix,
        'revenueCats': _top_category_rows(rev_merged),
        'expenseCats': _top_category_rows(exp_merged),
    }

    sum_rev = aggregates['sum_rev'] or Decimal('0')
    sum_exp = aggregates['sum_exp'] or Decimal('0')
    sum_net = aggregates['sum_net'] or Decimal('0')
    avg_margin = aggregates['avg_margin']
    if avg_margin is not None:
        avg_margin_f = float(avg_margin)
    else:
        avg_margin_f = 0.0

    analytics = {
        'report_count': aggregates['n'] or 0,
        'profitable_count': profitable_count,
        'loss_count': loss_count,
        'sum_revenue': sum_rev,
        'sum_expenses': sum_exp,
        'sum_net': sum_net,
        'avg_margin_pct': avg_margin_f,
    }

    paginator = Paginator(reports_qs, 20)
    page = request.GET.get('page')
    reports_page = paginator.get_page(page)

    fiscal_years = FiscalYear.objects.all().order_by('-start_date')

    filter_q = {}
    if period_filter:
        filter_q['period'] = period_filter
    if fiscal_year_filter:
        filter_q['fiscal_year'] = fiscal_year_filter
    filter_query = urlencode(filter_q)

    return render(request, 'hospital/accountant/profit_loss_list.html', {
        'reports': reports_page,
        'period_filter': period_filter,
        'fiscal_year_filter': fiscal_year_filter,
        'fiscal_years': fiscal_years,
        'analytics': analytics,
        'chart_payload': chart_payload,
        'filter_query': filter_query,
    })


@login_required
@role_required('accountant', 'senior_account_officer')
def profit_loss_create(request):
    """Create a new profit & loss report"""
    if request.method == 'POST':
        try:
            report = ProfitLossReport(
                report_period=request.POST.get('report_period'),
                period_start=request.POST.get('period_start'),
                period_end=request.POST.get('period_end'),
                fiscal_year_id=request.POST.get('fiscal_year'),
                total_revenue=Decimal(request.POST.get('total_revenue', 0)),
                total_expenses=Decimal(request.POST.get('total_expenses', 0)),
                generated_by=request.user
            )
            
            # Parse JSON fields if provided
            revenue_by_category = request.POST.get('revenue_by_category', '{}')
            expenses_by_category = request.POST.get('expenses_by_category', '{}')
            try:
                import json
                report.revenue_by_category = json.loads(revenue_by_category) if revenue_by_category else {}
                report.expenses_by_category = json.loads(expenses_by_category) if expenses_by_category else {}
            except:
                report.revenue_by_category = {}
                report.expenses_by_category = {}
            
            report.save()
            messages.success(request, f'Profit & Loss report {report.report_number} created successfully.')
            return redirect('hospital:profit_loss_list')
        except Exception as e:
            messages.error(request, f'Error creating report: {str(e)}')
    
    fiscal_years = FiscalYear.objects.all().order_by('-start_date')
    return render(request, 'hospital/accountant/profit_loss_form.html', {
        'fiscal_years': fiscal_years,
        'form_action': 'create',
    })


@login_required
@role_required('accountant', 'senior_account_officer')
def profit_loss_edit(request, report_id):
    """Edit a profit & loss report"""
    report = get_object_or_404(ProfitLossReport, id=report_id)
    
    if request.method == 'POST':
        try:
            report.report_period = request.POST.get('report_period')
            report.period_start = request.POST.get('period_start')
            report.period_end = request.POST.get('period_end')
            report.fiscal_year_id = request.POST.get('fiscal_year')
            report.total_revenue = Decimal(request.POST.get('total_revenue', 0))
            report.total_expenses = Decimal(request.POST.get('total_expenses', 0))
            
            # Parse JSON fields if provided
            revenue_by_category = request.POST.get('revenue_by_category', '{}')
            expenses_by_category = request.POST.get('expenses_by_category', '{}')
            try:
                import json
                report.revenue_by_category = json.loads(revenue_by_category) if revenue_by_category else {}
                report.expenses_by_category = json.loads(expenses_by_category) if expenses_by_category else {}
            except:
                pass
            
            report.save()
            messages.success(request, f'Profit & Loss report {report.report_number} updated successfully.')
            return redirect('hospital:profit_loss_list')
        except Exception as e:
            messages.error(request, f'Error updating report: {str(e)}')
    
    fiscal_years = FiscalYear.objects.all().order_by('-start_date')
    return render(request, 'hospital/accountant/profit_loss_form.html', {
        'report': report,
        'fiscal_years': fiscal_years,
        'form_action': 'edit',
    })


# ==================== REGISTRATION FEE VIEWS ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def registration_fee_list(request):
    """List all registration fees"""
    fees = RegistrationFee.objects.filter(is_deleted=False).order_by('-registration_date')
    
    # Optional filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    patient_search = request.GET.get('patient_search', '').strip()
    
    if date_from:
        fees = fees.filter(registration_date__gte=date_from)
    if date_to:
        fees = fees.filter(registration_date__lte=date_to)
    if patient_search:
        fees = fees.filter(
            Q(patient__first_name__icontains=patient_search) |
            Q(patient__last_name__icontains=patient_search) |
            Q(patient__mrn__icontains=patient_search)
        )
    
    paginator = Paginator(fees, 50)
    page = request.GET.get('page')
    fees_page = paginator.get_page(page)
    
    return render(request, 'hospital/accountant/registration_fee_list.html', {
        'fees': fees_page,
    })


# ==================== CASH SALES VIEWS ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def cash_sale_list(request):
    """List all cash sales"""
    sales = CashSale.objects.filter(is_deleted=False).order_by('-sale_date')
    
    # Optional filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    customer_search = request.GET.get('customer_search', '').strip()
    
    if date_from:
        sales = sales.filter(sale_date__gte=date_from)
    if date_to:
        sales = sales.filter(sale_date__lte=date_to)
    if customer_search:
        sales = sales.filter(customer_name__icontains=customer_search)
    
    paginator = Paginator(sales, 50)
    page = request.GET.get('page')
    sales_page = paginator.get_page(page)
    
    return render(request, 'hospital/accountant/cash_sale_list.html', {
        'sales': sales_page,
    })


# ==================== CORPORATE ACCOUNT VIEWS ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def corporate_account_list(request):
    """List all accounting corporate accounts"""
    from hospital.models_flexible_pricing import PricingCategory, ServicePrice
    
    accounts = AccountingCorporateAccount.objects.filter(is_deleted=False).order_by('company_name')
    
    # Enhance accounts with pricing information
    accounts_with_pricing = []
    for account in accounts:
        # Find associated pricing category
        pricing_category = None
        service_count = 0
        
        # Try to find pricing category by company name
        pricing_category = PricingCategory.objects.filter(
            name__icontains=account.company_name,
            is_deleted=False
        ).first()
        
        if pricing_category:
            service_count = ServicePrice.objects.filter(
                pricing_category=pricing_category,
                is_deleted=False
            ).count()
        
        accounts_with_pricing.append({
            'account': account,
            'pricing_category': pricing_category,
            'service_count': service_count,
        })
    
    return render(request, 'hospital/accountant/corporate_account_list.html', {
        'accounts': accounts,
        'accounts_with_pricing': accounts_with_pricing,
    })


# ==================== WITHHOLDING RECEIVABLE VIEWS ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def withholding_receivable_list(request):
    """List all withholding receivables"""
    receivables = WithholdingReceivable.objects.all().order_by('-withholding_date')
    
    paginator = Paginator(receivables, 50)
    page = request.GET.get('page')
    receivables_page = paginator.get_page(page)
    
    return render(request, 'hospital/accountant/withholding_receivable_list.html', {
        'receivables': receivables_page,
    })


# ==================== DEPOSIT VIEWS ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def deposit_list(request):
    """List all deposits"""
    deposits = Deposit.objects.all().order_by('-deposit_date')
    
    # Filters
    deposit_type_filter = request.GET.get('deposit_type', '')
    
    if deposit_type_filter:
        deposits = deposits.filter(deposit_type=deposit_type_filter)
    
    paginator = Paginator(deposits, 50)
    page = request.GET.get('page')
    deposits_page = paginator.get_page(page)
    
    return render(request, 'hospital/accountant/deposit_list.html', {
        'deposits': deposits_page,
        'deposit_type_filter': deposit_type_filter,
    })


# ==================== INITIAL REVALUATION VIEWS ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def initial_revaluation_list(request):
    """List all initial revaluations"""
    revaluations = InitialRevaluation.objects.all().order_by('-revaluation_date')
    
    paginator = Paginator(revaluations, 50)
    page = request.GET.get('page')
    revaluations_page = paginator.get_page(page)
    
    return render(request, 'hospital/accountant/initial_revaluation_list.html', {
        'revaluations': revaluations_page,
    })


# ==================== CHART OF ACCOUNTS VIEWS ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def chart_of_accounts(request):
    """View chart of accounts with balances"""
    from .models_accounting import GeneralLedger
    from django.db.models import Sum, Q
    
    account_type_filter = request.GET.get('type', '')
    search_query = request.GET.get('search', '')
    
    accounts = Account.objects.filter(is_deleted=False).select_related('parent_account')
    
    if account_type_filter:
        accounts = accounts.filter(account_type=account_type_filter)
    
    if search_query:
        accounts = accounts.filter(
            Q(account_code__icontains=search_query) |
            Q(account_name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Calculate balances for each account
    account_list = []
    for account in accounts.order_by('account_code'):
        # Get all GL entries for this account
        gl_entries = GeneralLedger.objects.filter(
            account=account,
            is_deleted=False
        ).aggregate(
            total_debits=Sum('debit_amount'),
            total_credits=Sum('credit_amount')
        )
        
        total_debits = gl_entries['total_debits'] or Decimal('0.00')
        total_credits = gl_entries['total_credits'] or Decimal('0.00')
        
        # Calculate balance based on account type
        if account.account_type in ['asset', 'expense']:
            balance = total_debits - total_credits
        else:
            balance = total_credits - total_debits
        
        account_list.append({
            'account': account,
            'balance': balance,
            'total_debits': total_debits,
            'total_credits': total_credits,
        })
    
    # Group by account type for display
    accounts_by_type = {}
    for item in account_list:
        account_type = item['account'].get_account_type_display()
        if account_type not in accounts_by_type:
            accounts_by_type[account_type] = []
        accounts_by_type[account_type].append(item)
    
    return render(request, 'hospital/accountant/chart_of_accounts.html', {
        'accounts_by_type': accounts_by_type,
        'account_list': account_list,
        'account_types': Account.ACCOUNT_TYPES,
        'selected_type': account_type_filter,
        'search_query': search_query,
    })


@login_required
@role_required('accountant', 'senior_account_officer')
def account_edit(request, account_id):
    """Edit account - Accountant-friendly view"""
    account = get_object_or_404(Account, id=account_id, is_deleted=False)
    
    if request.method == 'POST':
        # Update account fields
        account.account_code = request.POST.get('account_code', account.account_code)
        account.account_name = request.POST.get('account_name', account.account_name)
        account.description = request.POST.get('description', account.description)
        account.account_type = request.POST.get('account_type', account.account_type)
        account.is_active = request.POST.get('is_active') == 'on'
        
        # Handle parent account
        parent_id = request.POST.get('parent_account')
        if parent_id:
            try:
                account.parent_account = Account.objects.get(id=parent_id, is_deleted=False)
            except Account.DoesNotExist:
                pass
        else:
            account.parent_account = None
        
        account.save()
        messages.success(request, f'Account {account.account_code} updated successfully')
        return redirect('hospital:accountant_account_detail', account_id=account.id)
    
    # Get all accounts for parent account dropdown
    parent_accounts = Account.objects.filter(
        is_deleted=False,
        account_type=account.account_type
    ).exclude(id=account.id).order_by('account_code')
    
    context = {
        'account': account,
        'parent_accounts': parent_accounts,
        'account_types': Account.ACCOUNT_TYPES,
    }
    
    return render(request, 'hospital/accountant/account_edit.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def account_create(request):
    """Create new account - Accountant-friendly view"""
    from django.db import IntegrityError

    if request.method == 'POST':
        account_code = (request.POST.get('account_code') or '').strip()
        if not account_code:
            messages.error(request, 'Account code is required.')
        elif Account.objects.filter(account_code=account_code).exists():
            messages.error(
                request,
                f'An account with code "{account_code}" already exists. Please choose a different account code.',
            )
        else:
            try:
                account = Account.objects.create(
                    account_code=account_code,
                    account_name=request.POST.get('account_name', ''),
                    description=request.POST.get('description', ''),
                    account_type=request.POST.get('account_type', 'asset'),
                    is_active=request.POST.get('is_active') == 'on',
                )
                parent_id = request.POST.get('parent_account')
                if parent_id:
                    try:
                        account.parent_account = Account.objects.get(id=parent_id, is_deleted=False)
                        account.save()
                    except Account.DoesNotExist:
                        pass
                messages.success(request, f'Account {account.account_code} created successfully')
                return redirect('hospital:accountant_account_detail', account_id=account.id)
            except IntegrityError as e:
                if 'account_code' in str(e).lower() or 'unique' in str(e).lower():
                    messages.error(
                        request,
                        f'An account with code "{account_code}" already exists. Please choose a different account code.',
                    )
                else:
                    messages.error(request, 'Could not create account. Please try again.')

    # Get all accounts for parent account dropdown
    parent_accounts = Account.objects.filter(is_deleted=False).order_by('account_code')
    context = {
        'parent_accounts': parent_accounts,
        'account_types': Account.ACCOUNT_TYPES,
        'form_data': request.POST if request.method == 'POST' else None,
    }
    return render(request, 'hospital/accountant/account_create.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def account_detail(request, account_id):
    """View account details with transactions - Accountant-friendly view"""
    from .models_accounting import GeneralLedger
    from .models_accounting_advanced import AdvancedGeneralLedger
    from django.core.paginator import Paginator
    
    account = get_object_or_404(Account, id=account_id, is_deleted=False)
    
    # Get date range from query params
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    if not start_date or not end_date:
        # Default to current month
        today = timezone.now().date()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
    
    # Get transactions - try AdvancedGeneralLedger first, fallback to GeneralLedger
    transactions = []
    opening_balance = Decimal('0.00')
    total_debits = Decimal('0.00')
    total_credits = Decimal('0.00')
    
    try:
        # Try AdvancedGeneralLedger
        ledger_query = AdvancedGeneralLedger.objects.filter(
            account=account,
            is_voided=False
        )
        
        if start_date_obj:
            # Calculate opening balance
            opening_query = ledger_query.filter(transaction_date__lt=start_date_obj)
            opening_debits = opening_query.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
            opening_credits = opening_query.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')
            
            if account.account_type in ['asset', 'expense']:
                opening_balance = opening_debits - opening_credits
            else:
                opening_balance = opening_credits - opening_debits
            
            ledger_query = ledger_query.filter(transaction_date__gte=start_date_obj)
        
        if end_date_obj:
            ledger_query = ledger_query.filter(transaction_date__lte=end_date_obj)
        
        ledger_entries = ledger_query.order_by('-transaction_date', '-id')
        
        for entry in ledger_entries:
            transactions.append({
                'date': entry.transaction_date,
                'description': entry.description or '',
                'debit': entry.debit_amount or Decimal('0.00'),
                'credit': entry.credit_amount or Decimal('0.00'),
                'journal_entry': entry.journal_entry,
                'reference': entry.journal_entry.entry_number if entry.journal_entry else '',
            })
            total_debits += entry.debit_amount or Decimal('0.00')
            total_credits += entry.credit_amount or Decimal('0.00')
            
    except:
        # Fallback to GeneralLedger
        ledger_query = GeneralLedger.objects.filter(
            account=account,
            is_deleted=False
        )
        
        if start_date_obj:
            opening_query = ledger_query.filter(transaction_date__lt=start_date_obj)
            opening_debits = opening_query.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
            opening_credits = opening_query.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')
            
            if account.account_type in ['asset', 'expense']:
                opening_balance = opening_debits - opening_credits
            else:
                opening_balance = opening_credits - opening_debits
            
            ledger_query = ledger_query.filter(transaction_date__gte=start_date_obj)
        
        if end_date_obj:
            ledger_query = ledger_query.filter(transaction_date__lte=end_date_obj)
        
        ledger_entries = ledger_query.order_by('-transaction_date', '-id')
        
        for entry in ledger_entries:
            transactions.append({
                'date': entry.transaction_date,
                'description': entry.description or '',
                'debit': entry.debit_amount or Decimal('0.00'),
                'credit': entry.credit_amount or Decimal('0.00'),
                'journal_entry': entry.journal_entry if hasattr(entry, 'journal_entry') else None,
                'reference': '',
            })
            total_debits += entry.debit_amount or Decimal('0.00')
            total_credits += entry.credit_amount or Decimal('0.00')
    
    # Calculate closing balance
    if account.account_type in ['asset', 'expense']:
        closing_balance = opening_balance + total_debits - total_credits
    else:
        closing_balance = opening_balance + total_credits - total_debits
    
    # Calculate running balance for each transaction
    running_balance = opening_balance
    transactions_with_balance = []
    
    for trans in transactions:
        if account.account_type in ['asset', 'expense']:
            running_balance = running_balance + trans['debit'] - trans['credit']
        else:
            running_balance = running_balance + trans['credit'] - trans['debit']
        
        trans['running_balance'] = running_balance
        transactions_with_balance.append(trans)
    
    # Paginate transactions
    paginator = Paginator(transactions_with_balance, 50)
    page_number = request.GET.get('page', 1)
    transactions_page = paginator.get_page(page_number)
    
    context = {
        'account': account,
        'opening_balance': opening_balance,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'closing_balance': closing_balance,
        'transactions': transactions_page,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'hospital/accountant/account_detail.html', context)


# ==================== ACCOUNT SYNC VIEWS ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def sync_accounts(request):
    """Sync and link all accounting accounts"""
    if request.method == 'POST':
        try:
            sync_type = request.POST.get('sync_type', 'all')
            
            if sync_type == 'cashbook':
                results = link_cashbook_to_accounts()
                messages.success(
                    request,
                    f'Successfully linked {results["linked"]} cashbook entries to accounts.'
                )
            else:
                results = sync_all_accounts()
                messages.success(
                    request,
                    f'Account sync completed! Checked {results["accounts_checked"]} accounts, '
                    f'linked {results["accounts_linked"]} accounts, '
                    f'synced {results["bank_accounts_synced"]} bank accounts.'
                )
            
            if results.get('errors'):
                for error in results['errors']:
                    messages.error(request, f'Sync error: {error}')
            
            return redirect('hospital:accountant_comprehensive_dashboard')
            
        except Exception as e:
            messages.error(request, f'Error syncing accounts: {str(e)}')
            return redirect('hospital:accountant_comprehensive_dashboard')
    
    return redirect('hospital:accountant_comprehensive_dashboard')


# ==================== DETAILED FINANCIAL REPORT ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def detailed_financial_report(request):
    """Comprehensive detailed financial report with account-level breakdowns"""
    
    # Get filter parameters
    account_id = request.GET.get('account', '')
    account_category_id = request.GET.get('account_category', '')
    account_type = request.GET.get('account_type', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    fiscal_year_id = request.GET.get('fiscal_year', '')
    include_all = request.GET.get('include_all', 'false') == 'true'
    
    # Default to current month if no dates provided
    if not start_date or not end_date:
        today = timezone.now().date()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
    
    # Build base query for accounts
    accounts_query = Account.objects.filter(is_active=True)
    
    if account_id:
        accounts_query = accounts_query.filter(id=account_id)
    if account_category_id:
        # Note: Account model may not have account_category field, check if it exists
        try:
            accounts_query = accounts_query.filter(account_category_id=account_category_id)
        except:
            pass
    if account_type:
        accounts_query = accounts_query.filter(account_type=account_type)
    
    accounts = accounts_query.order_by('account_code')
    
    # If include_all is false and no specific account selected, show summary only
    if not include_all and not account_id:
        accounts = accounts[:50]  # Limit to first 50 for performance
    
    # Prepare comprehensive report data
    report_data = {
        'accounts': [],
        'summary': {
            'total_assets': Decimal('0.00'),
            'total_liabilities': Decimal('0.00'),
            'total_equity': Decimal('0.00'),
            'total_revenue': Decimal('0.00'),
            'total_expenses': Decimal('0.00'),
            'net_income': Decimal('0.00'),
        },
        'by_category': defaultdict(lambda: {
            'accounts': [],
            'total_debit': Decimal('0.00'),
            'total_credit': Decimal('0.00'),
            'balance': Decimal('0.00'),
        }),
    }
    
    # Process each account
    for account in accounts:
        account_data = {
            'account': account,
            'transactions': [],
            'opening_balance': Decimal('0.00'),
            'total_debit': Decimal('0.00'),
            'total_credit': Decimal('0.00'),
            'closing_balance': Decimal('0.00'),
            'related_data': {
                'cashbook_entries': [],
                'journal_entries': [],
                'receivables': [],
                'payables': [],
                'bank_transactions': [],
            }
        }
        
        # Get General Ledger transactions
        ledger_query = AdvancedGeneralLedger.objects.filter(account=account)
        if start_date_obj:
            ledger_query = ledger_query.filter(transaction_date__gte=start_date_obj)
        if end_date_obj:
            ledger_query = ledger_query.filter(transaction_date__lte=end_date_obj)
        
        ledger_transactions = ledger_query.order_by('transaction_date', 'id')
        
        # Calculate opening balance (transactions before start date)
        if start_date_obj:
            opening_query = AdvancedGeneralLedger.objects.filter(
                account=account,
                transaction_date__lt=start_date_obj
            )
            opening_debits = opening_query.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
            opening_credits = opening_query.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')
            
            if account.account_type in ['asset', 'expense']:
                account_data['opening_balance'] = opening_debits - opening_credits
            else:
                account_data['opening_balance'] = opening_credits - opening_debits
        
        # Process ledger transactions
        for trans in ledger_transactions:
            account_data['transactions'].append({
                'date': trans.transaction_date,
                'description': trans.description or '',
                'debit': trans.debit_amount,
                'credit': trans.credit_amount,
                'journal_entry': trans.journal_entry,
                'reference': trans.journal_entry.entry_number if trans.journal_entry else '',
            })
            account_data['total_debit'] += trans.debit_amount or Decimal('0.00')
            account_data['total_credit'] += trans.credit_amount or Decimal('0.00')
        
        # Calculate closing balance
        if account.account_type in ['asset', 'expense']:
            account_data['closing_balance'] = (
                account_data['opening_balance'] + 
                account_data['total_debit'] - 
                account_data['total_credit']
            )
        else:
            account_data['closing_balance'] = (
                account_data['opening_balance'] + 
                account_data['total_credit'] - 
                account_data['total_debit']
            )
        
        # Get related cashbook entries
        if account.account_type == 'revenue':
            cashbook_query = Cashbook.objects.filter(
                revenue_account=account,
                entry_date__gte=start_date_obj if start_date_obj else date(2000, 1, 1),
                entry_date__lte=end_date_obj if end_date_obj else date.today()
            )
            account_data['related_data']['cashbook_entries'] = list(cashbook_query[:20])
        
        # Get related journal entries
        journal_entries = AdvancedJournalEntry.objects.filter(
            lines__account=account,
            entry_date__gte=start_date_obj if start_date_obj else date(2000, 1, 1),
            entry_date__lte=end_date_obj if end_date_obj else date.today()
        ).distinct()[:20]
        account_data['related_data']['journal_entries'] = list(journal_entries)
        
        # Get receivables for AR accounts
        # Note: AdvancedAccountsReceivable doesn't have receivable_account field
        # It's linked via invoice, so we'll show receivables based on account type match
        if account.account_type == 'asset' and 'receivable' in account.account_name.lower():
            receivables = AdvancedAccountsReceivable.objects.filter(
                due_date__gte=start_date_obj if start_date_obj else date(2000, 1, 1),
                due_date__lte=end_date_obj if end_date_obj else date.today()
            )[:20]
            account_data['related_data']['receivables'] = list(receivables)
        
        # Get payables for AP accounts
        # Note: AccountsPayable may not have payable_account field, check model structure
        if account.account_type == 'liability' and 'payable' in account.account_name.lower():
            try:
                payables = AccountsPayable.objects.filter(
                    due_date__gte=start_date_obj if start_date_obj else date(2000, 1, 1),
                    due_date__lte=end_date_obj if end_date_obj else date.today()
                )[:20]
                account_data['related_data']['payables'] = list(payables)
            except:
                # If payable_account field doesn't exist, skip
                pass
        
        # Update summary totals
        if account.account_type == 'asset':
            report_data['summary']['total_assets'] += account_data['closing_balance']
        elif account.account_type == 'liability':
            report_data['summary']['total_liabilities'] += account_data['closing_balance']
        elif account.account_type == 'equity':
            report_data['summary']['total_equity'] += account_data['closing_balance']
        elif account.account_type == 'revenue':
            report_data['summary']['total_revenue'] += account_data['total_credit']
        elif account.account_type == 'expense':
            report_data['summary']['total_expenses'] += account_data['total_debit']
        
        # Group by category
        category_key = account.account_type
        if hasattr(account, 'account_category') and account.account_category:
            category_key = f"{account.account_type}_{account.account_category.code}"
        
        report_data['by_category'][category_key]['accounts'].append(account_data)
        report_data['by_category'][category_key]['total_debit'] += account_data['total_debit']
        report_data['by_category'][category_key]['total_credit'] += account_data['total_credit']
        # Use closing balance (includes opening balance) to match balance sheet calculation
        # This shows the actual account balance as of the end date, not just period transactions
        report_data['by_category'][category_key]['balance'] += account_data['closing_balance']
        
        report_data['accounts'].append(account_data)
    
    # Calculate net income
    report_data['summary']['net_income'] = (
        report_data['summary']['total_revenue'] - 
        report_data['summary']['total_expenses']
    )
    
    # Convert defaultdict to list of tuples for template iteration
    # Django templates have issues with dict.items() unpacking, so convert to list
    report_data['by_category'] = list(report_data['by_category'].items())
    
    # Get filter options
    all_accounts = Account.objects.filter(is_active=True).order_by('account_code')
    account_categories = AccountCategory.objects.filter(is_active=True).order_by('code')
    fiscal_years = FiscalYear.objects.all().order_by('-start_date')
    
    context = {
        'report_data': report_data,
        'all_accounts': all_accounts,
        'account_categories': account_categories,
        'fiscal_years': fiscal_years,
        'filters': {
            'account_id': account_id,
            'account_category_id': account_category_id,
            'account_type': account_type,
            'start_date': start_date,
            'end_date': end_date,
            'fiscal_year_id': fiscal_year_id,
            'include_all': include_all,
        },
        'account_types': Account.ACCOUNT_TYPES,
    }
    
    return render(request, 'hospital/accountant/detailed_financial_report.html', context)

