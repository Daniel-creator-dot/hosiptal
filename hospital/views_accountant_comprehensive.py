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
from django.http import JsonResponse, HttpResponse, Http404
from django.db.models import Sum, Q, Count, Avg, F, DecimalField, Case, When, Value
from django.db.models.functions import TruncMonth, ExtractYear
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import transaction
from django.urls import reverse
from django.utils.http import urlencode
from django.core.cache import cache
from datetime import datetime, timedelta, date, time
import calendar as calendar_mod
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
from .models_supplier_payables import SupplierPayableLine
from .models_missing_features import Supplier


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

    # GL balances (trial balance) for dashboard stat cards
    def get_gl_dashboard_balances():
        from hospital.services.trial_balance_service import (
            get_account_balance,
            get_account_by_code,
            sum_account_balances,
        )

        cash_account = get_account_by_code('1010')
        customer_deposits_account = get_account_by_code('2110')
        trade_receivables_account = get_account_by_code('1200')
        trade_payables_account = get_account_by_code('2100')
        return {
            'gl_cash_balance': float(get_account_balance('1010', today)),
            'gl_customer_deposits': float(get_account_balance('2110', today)),
            'gl_ar_balance': float(sum_account_balances(['1200', '1201', '1202'], today)),
            'gl_ap_balance': float(sum_account_balances(['2100', '2101'], today)),
            'gl_cash_account_id': str(cash_account.id) if cash_account else None,
            'gl_customer_deposits_account_id': (
                str(customer_deposits_account.id) if customer_deposits_account else None
            ),
            'gl_ar_account_id': (
                str(trade_receivables_account.id) if trade_receivables_account else None
            ),
            'gl_ap_account_id': (
                str(trade_payables_account.id) if trade_payables_account else None
            ),
        }

    gl_balances = safe_query(get_gl_dashboard_balances, default={})
    
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
        'total_ar': gl_balances.get('gl_ar_balance', total_ar),
        'total_ap': gl_balances.get('gl_ap_balance', total_ap),
        'gl_cash_balance': gl_balances.get('gl_cash_balance', 0),
        'gl_customer_deposits': gl_balances.get('gl_customer_deposits', 0),
        'gl_cash_account_id': gl_balances.get('gl_cash_account_id'),
        'gl_customer_deposits_account_id': gl_balances.get('gl_customer_deposits_account_id'),
        'gl_ar_account_id': gl_balances.get('gl_ar_account_id'),
        'gl_ap_account_id': gl_balances.get('gl_ap_account_id'),
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


def _supplier_balance_map():
    rows = (
        SupplierPayableLine.objects.filter(is_deleted=False)
        .values('supplier_id')
        .annotate(bal=Sum('amount'))
    )
    return {r['supplier_id']: r['bal'] or Decimal('0.00') for r in rows}


def _supplier_payables_month_datetime_bounds(year: int, month: int):
    """Inclusive start/end datetimes for a calendar month in the active timezone."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(date(year, month, 1), time.min), tz)
    last_day = calendar_mod.monthrange(year, month)[1]
    end = timezone.make_aware(datetime.combine(date(year, month, last_day), time.max), tz)
    return start, end


def _supplier_twelve_month_sequence_ending(year: int, month: int):
    """Twelve calendar months inclusive, chronological order ending at year-month."""
    pairs = []
    y, m = year, month
    for _ in range(12):
        pairs.append((y, m))
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    pairs.reverse()
    return pairs


def _supplier_pct_change_display(current: Decimal, previous: Decimal):
    """Return (label, direction) where direction is 'up','down','flat','new','na'."""
    if previous <= 0 and current <= 0:
        return ('—', 'na')
    if previous <= 0 < current:
        return ('New activity', 'new')
    if current <= 0 < previous:
        return ('Dropped to zero', 'down')
    try:
        diff = ((current - previous) / previous) * Decimal('100')
    except InvalidOperation:
        return ('—', 'na')
    lbl = f'{diff:+.1f}% vs prior month'
    if diff > Decimal('0.5'):
        return (lbl, 'up')
    if diff < Decimal('-0.5'):
        return (lbl, 'down')
    return ('~ Flat vs prior month', 'flat')


def _supplier_payables_month_local_bounds_display(year: int, month: int):
    """Human-readable inclusive datetimes for the month's ledger window (local TZ)."""
    start_dt, end_dt = _supplier_payables_month_datetime_bounds(year, month)
    return (
        timezone.localtime(start_dt).strftime('%d %b %Y %H:%M'),
        timezone.localtime(end_dt).strftime('%d %b %Y %H:%M'),
    )


def _supplier_total_payables_positive_only():
    """Sum of max(0, balance) per supplier — conservative headline for dashboard."""
    total = Decimal('0.00')
    for bal in _supplier_balance_map().values():
        if bal and bal > 0:
            total += bal
    return total


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
        .select_related('drug', 'created_by', 'supplier')
        .order_by('-created')
    )
    query = request.GET.get('q', '')
    filter_type = request.GET.get('filter', 'all')
    category_filter = request.GET.get('category', '')
    location_filter = request.GET.get('location', '').strip()
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    supplier_filter = (request.GET.get('supplier') or '').strip()

    if supplier_filter:
        try:
            UUID(supplier_filter)
            stock_list = stock_list.filter(supplier_id=supplier_filter)
        except (ValueError, TypeError):
            supplier_filter = ''

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
    if supplier_filter:
        summary_qs = summary_qs.filter(supplier_id=supplier_filter)
    total_value = (
        summary_qs.aggregate(
            total=Sum(F('quantity_on_hand') * F('unit_cost'), output_field=DecimalField(max_digits=14, decimal_places=2))
        )
    )['total'] or Decimal('0.00')
    low_stock_count = summary_qs.filter(quantity_on_hand__lte=F('reorder_level')).count()
    total_batch_count = summary_qs.count()
    total_drug_count = summary_qs.values('drug').distinct().count()

    supplier_choices = list(
        Supplier.objects.filter(is_deleted=False).order_by('name').values('id', 'name')
    )
    total_supplier_payables_positive = _supplier_total_payables_positive_only()

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
        'supplier_filter': supplier_filter,
        'supplier_choices': supplier_choices,
        'total_supplier_payables_positive': total_supplier_payables_positive,
    }
    return render(request, 'hospital/accountant/stock_management_monitoring.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def supplier_accounts_list(request):
    lt = SupplierPayableLine
    view_lifetime = (request.GET.get('view') or '').strip().lower() == 'lifetime'

    month_param = (request.GET.get('month') or '').strip()
    filter_year, filter_month = None, None
    month_bounds = None

    if view_lifetime:
        month_param = ''
    else:
        list_url = reverse('hospital:supplier_accounts_list')
        if not month_param:
            d0 = timezone.localdate()
            return redirect(f'{list_url}?{urlencode({"month": f"{d0.year}-{d0.month:02d}"})}')
        parts = month_param.split('-')
        if len(parts) == 2:
            try:
                fy, fm = int(parts[0]), int(parts[1])
                if 2000 <= fy <= 2100 and 1 <= fm <= 12:
                    filter_year, filter_month = fy, fm
                    month_bounds = _supplier_payables_month_datetime_bounds(fy, fm)
            except (ValueError, TypeError):
                filter_year = filter_month = None
                month_bounds = None
        if not month_bounds:
            messages.warning(
                request,
                'Choose a valid month (YYYY-MM), or use Lifetime view for all-time KPIs.',
            )
            d0 = timezone.localdate()
            return redirect(f'{list_url}?{urlencode({"month": f"{d0.year}-{d0.month:02d}"})}')

    balance_map = _supplier_balance_map()
    suppliers = Supplier.objects.filter(is_deleted=False).order_by('name')
    line_qs = SupplierPayableLine.objects.filter(is_deleted=False)
    line_qs_scope = (
        line_qs.filter(created__gte=month_bounds[0], created__lte=month_bounds[1])
        if month_bounds
        else line_qs
    )

    # Lifetime composition (always) — lines + amounts by entry type
    lifetime_type_stats = {
        r['entry_type']: {
            'lines': r['lines'],
            'total': r['total'] if r['total'] is not None else Decimal('0.00'),
        }
        for r in line_qs.values('entry_type').annotate(lines=Count('id'), total=Sum('amount'))
    }
    lifetime_totals_by_type = {k: v['total'] for k, v in lifetime_type_stats.items()}
    lifetime_line_count = line_qs.count()
    lifetime_abs_denom = sum(abs(v) for v in lifetime_totals_by_type.values()) or Decimal('1')
    lifetime_breakdown_rows = []
    for key, title in (
        (lt.ENTRY_STOCK_RECEIPT, 'Stock & lab receipts'),
        (lt.ENTRY_MANUAL_PAYABLE, 'Manual payables / invoices'),
        (lt.ENTRY_PAYMENT, 'Payments to suppliers'),
        (lt.ENTRY_ADJUSTMENT, 'Adjustments'),
    ):
        st = lifetime_type_stats.get(key, {'lines': 0, 'total': Decimal('0.00')})
        amt = st['total']
        lifetime_breakdown_rows.append(
            {
                'key': key,
                'title': title,
                'lines': st['lines'],
                'amount': amt,
                'amount_abs': abs(amt),
                'share_pct': float((abs(amt) / lifetime_abs_denom) * Decimal('100')),
            }
        )

    purchase_map = {}
    manual_map = {}
    payment_abs_map = {}
    if month_bounds:
        purchase_map = dict(
            line_qs_scope.filter(entry_type=lt.ENTRY_STOCK_RECEIPT)
            .values('supplier_id')
            .annotate(total=Sum('amount'))
            .values_list('supplier_id', 'total')
        )
        manual_map = dict(
            line_qs_scope.filter(entry_type=lt.ENTRY_MANUAL_PAYABLE)
            .values('supplier_id')
            .annotate(total=Sum('amount'))
            .values_list('supplier_id', 'total')
        )
        payment_abs_map = {}
        for sid, raw in (
            line_qs_scope.filter(entry_type=lt.ENTRY_PAYMENT)
            .values('supplier_id')
            .annotate(total=Sum('amount'))
            .values_list('supplier_id', 'total')
        ):
            payment_abs_map[sid] = abs(raw) if raw is not None else Decimal('0.00')

    rows = []
    for s in suppliers:
        bal = balance_map.get(s.id, Decimal('0.00'))
        period_purchase = (
            (purchase_map.get(s.id) or Decimal('0.00')) if month_bounds else Decimal('0.00')
        )
        period_manual = (
            (manual_map.get(s.id) or Decimal('0.00')) if month_bounds else Decimal('0.00')
        )
        period_pay_abs = (
            (payment_abs_map.get(s.id) or Decimal('0.00')) if month_bounds else Decimal('0.00')
        )
        rows.append(
            {
                'supplier': s,
                'balance': bal,
                'period_purchases': period_purchase,
                'period_manual': period_manual,
                'period_payments_abs': period_pay_abs,
            }
        )
    if month_bounds:
        rows.sort(
            key=lambda x: (
                -(x['period_purchases'] or Decimal('0')),
                -(x['period_manual'] or Decimal('0')),
                -(x['balance'] or Decimal('0')),
                x['supplier'].name.lower(),
            )
        )
    else:
        rows.sort(key=lambda x: (-(x['balance'] or 0), x['supplier'].name.lower()))

    type_rows = line_qs_scope.values('entry_type').annotate(total=Sum('amount'))
    totals_by_type = {
        (r['entry_type'] or ''): (r['total'] if r['total'] is not None else Decimal('0.00'))
        for r in type_rows
    }
    counts_by_type = {
        r['entry_type']: r['n']
        for r in line_qs_scope.values('entry_type').annotate(n=Count('id'))
    }
    stock_total = totals_by_type.get(lt.ENTRY_STOCK_RECEIPT, Decimal('0.00'))
    manual_total = totals_by_type.get(lt.ENTRY_MANUAL_PAYABLE, Decimal('0.00'))
    pay_total = totals_by_type.get(lt.ENTRY_PAYMENT, Decimal('0.00'))
    adj_total = totals_by_type.get(lt.ENTRY_ADJUSTMENT, Decimal('0.00'))
    suppliers_owing = sum(1 for r in rows if (r['balance'] or Decimal('0')) > 0)
    net_all = sum((r['balance'] or Decimal('0')) for r in rows)

    # Twelve rolling months ending at selected month or current local month — trend for charts
    local_today = timezone.localdate()
    trend_end_y = filter_year if month_bounds else local_today.year
    trend_end_m = filter_month if month_bounds else local_today.month
    trend_pairs = _supplier_twelve_month_sequence_ending(trend_end_y, trend_end_m)
    trend_start_dt, _ = _supplier_payables_month_datetime_bounds(trend_pairs[0][0], trend_pairs[0][1])
    _, trend_end_dt = _supplier_payables_month_datetime_bounds(trend_pairs[-1][0], trend_pairs[-1][1])
    trend_agg = (
        line_qs.filter(created__gte=trend_start_dt, created__lte=trend_end_dt)
        .annotate(mm=TruncMonth('created'))
        .values('mm', 'entry_type')
        .annotate(t=Sum('amount'))
    )
    trend_bucket = defaultdict(lambda: defaultdict(lambda: Decimal('0.00')))
    for r in trend_agg:
        mk = r['mm']
        if mk is None:
            continue
        loc = timezone.localtime(mk)
        yk = (loc.year, loc.month)
        et = r['entry_type']
        trend_bucket[yk][et] = r['t'] if r['t'] is not None else Decimal('0.00')

    trend_labels = []
    trend_stock, trend_manual, trend_pay_abs = [], [], []
    for y, m in trend_pairs:
        trend_labels.append(date(y, m, 1).strftime('%b %Y'))
        b = trend_bucket[(y, m)]
        trend_stock.append(float(b[lt.ENTRY_STOCK_RECEIPT]))
        trend_manual.append(float(b[lt.ENTRY_MANUAL_PAYABLE]))
        trend_pay_abs.append(float(abs(b[lt.ENTRY_PAYMENT])))
    trend_highlight_index = trend_pairs.index((trend_end_y, trend_end_m)) if trend_pairs else -1

    pharma_receipt_amt = lab_receipt_amt = other_receipt_amt = Decimal('0.00')
    pharma_receipt_n = lab_receipt_n = other_receipt_n = 0

    if month_bounds:
        period_stock_lines = line_qs_scope.filter(entry_type=lt.ENTRY_STOCK_RECEIPT)
        pharma_receipt_amt = (
            period_stock_lines.filter(pharmacy_stock__isnull=False).aggregate(x=Sum('amount'))['x']
            or Decimal('0.00')
        )
        lab_receipt_amt = (
            period_stock_lines.filter(
                pharmacy_stock__isnull=True, lab_reagent__isnull=False
            ).aggregate(x=Sum('amount'))['x']
            or Decimal('0.00')
        )
        other_receipt_amt = stock_total - pharma_receipt_amt - lab_receipt_amt
        pharma_receipt_n = period_stock_lines.filter(pharmacy_stock__isnull=False).count()
        lab_receipt_n = period_stock_lines.filter(
            pharmacy_stock__isnull=True, lab_reagent__isnull=False
        ).count()
        other_receipt_n = max(period_stock_lines.count() - pharma_receipt_n - lab_receipt_n, 0)

    period_range_start = period_range_end = ''
    period_analysis = None
    if month_bounds and filter_year and filter_month:
        period_range_start, period_range_end = _supplier_payables_month_local_bounds_display(
            filter_year, filter_month
        )
        suppliers_with_stock_receipts = sum(
            1 for r in rows if (r['period_purchases'] or Decimal('0')) > 0
        )
        distinct_suppliers_touched = line_qs_scope.values('supplier_id').distinct().count()
        top_sorted = sorted(
            [r for r in rows if (r['period_purchases'] or Decimal('0')) > 0],
            key=lambda r: -(r['period_purchases'] or Decimal('0')),
        )
        top3_sum = sum((r['period_purchases'] or Decimal('0')) for r in top_sorted[:3])
        concentration_pct = (
            float((top3_sum / stock_total) * Decimal('100')) if stock_total > 0 else None
        )
        avg_receipt = (
            (stock_total / Decimal(counts_by_type.get(lt.ENTRY_STOCK_RECEIPT, 1))).quantize(Decimal('0.01'))
            if counts_by_type.get(lt.ENTRY_STOCK_RECEIPT, 0)
            else None
        )
        net_cash_story = manual_total + stock_total + adj_total + pay_total
        pym = filter_month - 1
        pyear = filter_year
        if pym < 1:
            pym = 12
            pyear -= 1
        prev_bounds = _supplier_payables_month_datetime_bounds(pyear, pym)
        prev_stock = (
            line_qs.filter(
                entry_type=lt.ENTRY_STOCK_RECEIPT,
                created__gte=prev_bounds[0],
                created__lte=prev_bounds[1],
            ).aggregate(x=Sum('amount'))['x']
            or Decimal('0.00')
        )
        mom_label, mom_dir = _supplier_pct_change_display(stock_total, prev_stock)
        prev_month_label = date(pyear, pym, 1).strftime('%B %Y')
        gross_inflow_story = stock_total + manual_total
        period_analysis = {
            'period_range_start': period_range_start,
            'period_range_end': period_range_end,
            'distinct_suppliers_touched': distinct_suppliers_touched,
            'suppliers_with_receipts': suppliers_with_stock_receipts,
            'concentration_top3_pct': concentration_pct,
            'avg_stock_receipt': avg_receipt,
            'receipt_lines_pharmacy': pharma_receipt_n,
            'receipt_lines_lab': lab_receipt_n,
            'receipt_lines_other': other_receipt_n,
            'receipt_lines_total': counts_by_type.get(lt.ENTRY_STOCK_RECEIPT, 0),
            'receipt_amt_pharmacy': pharma_receipt_amt,
            'receipt_amt_lab': lab_receipt_amt,
            'receipt_amt_other': other_receipt_amt,
            'counts_by_type': counts_by_type,
            'mom_label': mom_label,
            'mom_direction': mom_dir,
            'prev_month_label': prev_month_label,
            'prev_month_stock_total': prev_stock,
            'gross_inflow': gross_inflow_story,
            'net_posted_delta': net_cash_story,
        }

    scoped_breakdown_rows = None
    if month_bounds:
        period_abs_denom = sum(abs(v) for v in totals_by_type.values()) or Decimal('1')
        scoped_breakdown_rows = []
        for key, title in (
            (lt.ENTRY_STOCK_RECEIPT, 'Stock & lab receipts'),
            (lt.ENTRY_MANUAL_PAYABLE, 'Manual payables'),
            (lt.ENTRY_PAYMENT, 'Payments (credit)'),
            (lt.ENTRY_ADJUSTMENT, 'Adjustments'),
        ):
            amt = totals_by_type.get(key, Decimal('0.00'))
            ln = counts_by_type.get(key, 0)
            scoped_breakdown_rows.append(
                {
                    'title': title,
                    'lines': ln,
                    'amount': amt,
                    'amount_display': abs(amt) if key == lt.ENTRY_PAYMENT else amt,
                    'share_pct': float((abs(amt) / period_abs_denom) * Decimal('100')),
                }
            )

    pie_labels, pie_data = [], []
    pie_triples = [
        (lt.ENTRY_STOCK_RECEIPT, 'Stock & lab receipts', False),
        (lt.ENTRY_MANUAL_PAYABLE, 'Manual payables', False),
        (lt.ENTRY_PAYMENT, 'Payments recorded', True),
        (lt.ENTRY_ADJUSTMENT, 'Adjustments', False),
    ]
    for key, label, use_abs in pie_triples:
        v = totals_by_type.get(key, Decimal('0.00'))
        if use_abs:
            v = abs(v)
        if v > 0:
            pie_labels.append(label)
            pie_data.append(float(v))

    if month_bounds:
        top_buyers = sorted(
            [r for r in rows if (r['period_purchases'] or Decimal('0')) > 0],
            key=lambda r: -(r['period_purchases'] or Decimal('0')),
        )[:10]
        bar_labels = [
            (r['supplier'].name[:26] + '…') if len(r['supplier'].name) > 27 else r['supplier'].name
            for r in top_buyers
        ]
        bar_data = [float(r['period_purchases']) for r in top_buyers]
    else:
        top_creditors = [r for r in rows if (r['balance'] or Decimal('0')) > 0][:10]
        bar_labels = [
            (r['supplier'].name[:26] + '…') if len(r['supplier'].name) > 27 else r['supplier'].name
            for r in top_creditors
        ]
        bar_data = [float(r['balance']) for r in top_creditors]

    chart_payload = {
        'monthLabels': trend_labels,
        'monthStock': trend_stock,
        'monthManual': trend_manual,
        'monthPayments': trend_pay_abs,
        'trendHighlightIndex': trend_highlight_index,
        'barLabels': bar_labels,
        'barData': bar_data,
        'pieLabels': pie_labels,
        'pieData': pie_data,
        'barChartPurchasesMode': bool(month_bounds),
    }

    period_label = ''
    if filter_year and filter_month:
        period_label = date(filter_year, filter_month, 1).strftime('%B %Y')

    context = {
        'supplier_rows': rows,
        'total_positive_payables': _supplier_total_payables_positive_only(),
        'month_filter': month_param if month_bounds else '',
        'month_filter_active': bool(month_bounds),
        'view_lifetime': view_lifetime,
        'period_label': period_label,
        'period_analysis': period_analysis,
        'lifetime_breakdown_rows': lifetime_breakdown_rows,
        'lifetime_line_count': lifetime_line_count,
        'scoped_breakdown_rows': scoped_breakdown_rows,
        'analytics': {
            'line_count': line_qs_scope.count(),
            'stock_receipts_total': stock_total,
            'manual_payables_total': manual_total,
            'payments_total': pay_total,
            'payments_total_abs': abs(pay_total),
            'adjustments_total': adj_total,
            'suppliers_owing': suppliers_owing,
            'net_all_suppliers': net_all,
        },
        'chart_payload': chart_payload,
    }
    return render(request, 'hospital/accountant/supplier_accounts_list.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def supplier_account_detail(request, supplier_id):
    supplier = get_object_or_404(Supplier, pk=supplier_id, is_deleted=False)
    lines_qs = (
        SupplierPayableLine.objects.filter(supplier=supplier, is_deleted=False)
        .select_related('created_by', 'pharmacy_stock', 'pharmacy_stock__drug', 'lab_reagent')
        .order_by('created', 'id')
    )
    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        try:
            if action == 'manual_payable':
                raw_amt = (request.POST.get('amount') or '').strip()
                amt = Decimal(raw_amt)
                if amt <= 0:
                    raise ValueError('Amount must be greater than zero.')
                desc = (request.POST.get('description') or '').strip()
                ref = (request.POST.get('reference') or '').strip()
                with transaction.atomic():
                    SupplierPayableLine.objects.create(
                        supplier=supplier,
                        entry_type=SupplierPayableLine.ENTRY_MANUAL_PAYABLE,
                        amount=amt,
                        description=desc or 'Manual payable',
                        reference=ref,
                        created_by=request.user,
                    )
                messages.success(request, 'Payable recorded.')
                return redirect(
                    reverse('hospital:supplier_account_detail', kwargs={'supplier_id': supplier.id})
                    + '#ledger'
                )
            if action == 'payment':
                raw_amt = (request.POST.get('amount') or '').strip()
                amt = Decimal(raw_amt)
                if amt <= 0:
                    raise ValueError('Amount must be greater than zero.')
                current_balance = (
                    SupplierPayableLine.objects.filter(supplier=supplier, is_deleted=False)
                    .aggregate(total=Sum('amount'))['total']
                    or Decimal('0.00')
                )
                if current_balance <= 0:
                    raise ValueError('No outstanding balance to pay for this supplier.')
                if amt > current_balance:
                    raise ValueError(
                        f'Payment GHS {amt:.2f} exceeds supplier balance GHS {current_balance:.2f}.'
                    )
                desc = (request.POST.get('description') or '').strip()
                ref = (request.POST.get('reference') or '').strip()
                with transaction.atomic():
                    SupplierPayableLine.objects.create(
                        supplier=supplier,
                        entry_type=SupplierPayableLine.ENTRY_PAYMENT,
                        amount=-amt,
                        description=desc or 'Payment to supplier',
                        reference=ref,
                        created_by=request.user,
                    )
                messages.success(request, 'Payment recorded.')
                return redirect(
                    reverse('hospital:supplier_account_detail', kwargs={'supplier_id': supplier.id})
                    + '#ledger'
                )
            messages.error(request, 'Unknown action.')
        except (InvalidOperation, ValueError, TypeError) as e:
            messages.error(request, str(e) or 'Invalid amount.')

    lines = list(lines_qs)
    running = Decimal('0.00')
    ledger_rows = []
    for line in lines:
        running += line.amount or Decimal('0.00')
        ledger_rows.append({'line': line, 'running': running})

    _et_labels = dict(SupplierPayableLine.ENTRY_TYPE_CHOICES)
    type_summary = []
    for row in (
        SupplierPayableLine.objects.filter(supplier=supplier, is_deleted=False)
        .values('entry_type')
        .annotate(cnt=Count('id'), tot=Sum('amount'))
        .order_by('entry_type')
    ):
        et = row['entry_type']
        type_summary.append(
            {
                'entry_type': et,
                'entry_label': _et_labels.get(et, et),
                'cnt': row['cnt'],
                'tot': row['tot'] if row['tot'] is not None else Decimal('0.00'),
            }
        )
    detail_chart = {'labels': [], 'data': []}
    for row in type_summary:
        et = row['entry_type']
        tot = row['tot'] or Decimal('0.00')
        if et == SupplierPayableLine.ENTRY_PAYMENT:
            mag = abs(tot)
            if mag > 0:
                detail_chart['labels'].append(row['entry_label'])
                detail_chart['data'].append(float(mag))
        elif tot > 0:
            detail_chart['labels'].append(row['entry_label'])
            detail_chart['data'].append(float(tot))

    context = {
        'supplier': supplier,
        'ledger_rows': ledger_rows,
        'current_balance': running,
        'type_summary': type_summary,
        'detail_chart_json': json.dumps(detail_chart),
    }
    return render(request, 'hospital/accountant/supplier_account_detail.html', context)


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
@role_required('accountant', 'senior_account_officer', 'account_officer')
def insurance_receivable_list(request):
    """Insurance receivables grouped by company + month (default) or individual lines."""
    from .models_primecare_accounting import InsuranceReceivableEntry
    from .models_accounting_advanced import InsuranceReceivable
    from .services.receivable_grouping_service import group_receivable_entries
    from django.db.models import Sum

    view_mode = request.GET.get('view', 'grouped')
    if view_mode not in ('grouped', 'detail'):
        view_mode = 'grouped'

    status_filter = request.GET.get('status', '')
    insurance_filter = request.GET.get('insurance', '')
    month_filter = request.GET.get('month', '')

    base_qs = InsuranceReceivableEntry.objects.filter(is_deleted=False).exclude(
        payer__payer_type='corporate'
    ).select_related('payer', 'invoice', 'invoice__patient')

    if status_filter:
        base_qs = base_qs.filter(status=status_filter)
    if insurance_filter:
        base_qs = base_qs.filter(payer_id=insurance_filter)
    if month_filter:
        try:
            from .services.receivable_grouping_service import month_bounds
            start, end = month_bounds(month_filter)
            base_qs = base_qs.filter(entry_date__gte=start, entry_date__lte=end)
        except (ValueError, IndexError):
            pass

    open_outstanding = base_qs.filter(outstanding_amount__gt=0).aggregate(
        t=Sum('outstanding_amount')
    )['t'] or Decimal('0.00')

    if view_mode == 'grouped':
        grouped_rows = group_receivable_entries(base_qs)
        paginator = Paginator(grouped_rows, 40)
        page = paginator.get_page(request.GET.get('page'))
        receivables = None
    else:
        receivables_list = []
        for rec in InsuranceReceivable.objects.all():
            receivables_list.append(rec)
        for entry in base_qs.order_by('-entry_date', '-created'):
            class ReceivableEntryWrapper:
                def __init__(self, entry):
                    self.id = entry.id
                    self.receivable_number = entry.entry_number
                    self.insurance_company = entry.payer
                    self.patient = entry.invoice.patient if entry.invoice_id and entry.invoice else None
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
        receivables_list.sort(
            key=lambda x: getattr(x, 'claim_date', getattr(x, 'due_date', timezone.now().date())),
            reverse=True,
        )
        paginator = Paginator(receivables_list, 50)
        page = paginator.get_page(request.GET.get('page'))
        receivables = page
        grouped_rows = None

    from .models import Payer
    insurance_companies = Payer.objects.filter(payer_type__in=['private', 'nhis'], is_active=True)

    return render(request, 'hospital/accountant/insurance_receivable_list.html', {
        'view_mode': view_mode,
        'grouped_receivables': page if view_mode == 'grouped' else None,
        'receivables': receivables,
        'status_filter': status_filter,
        'insurance_companies': insurance_companies,
        'open_outstanding': open_outstanding,
        'month_filter': month_filter,
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


def _payroll_calendar_months_for_year(year):
    """
    Roll up accounting payrolls by calendar month of payroll_period_start.
    staff_paid = distinct staff with at least one line in that month (any run).
    """
    y = max(2000, min(int(year), 2100))

    runs_rows = (
        AccountingPayroll.objects.filter(is_deleted=False, payroll_period_start__year=y)
        .annotate(m=TruncMonth('payroll_period_start'))
        .values('m')
        .annotate(
            run_count=Count('id'),
            sum_gross=Sum('total_gross_pay'),
            sum_net=Sum('total_net_pay'),
        )
    )
    runs_by_month = {}
    for row in runs_rows:
        key = row['m']
        if key is None:
            continue
        runs_by_month[key.month] = row

    staff_rows = (
        AccountingPayrollEntry.objects.filter(
            is_deleted=False,
            staff_id__isnull=False,
            payroll__is_deleted=False,
            payroll__payroll_period_start__year=y,
        )
        .annotate(m=TruncMonth('payroll__payroll_period_start'))
        .values('m')
        .annotate(staff_distinct=Count('staff', distinct=True))
    )
    staff_by_month = {}
    for row in staff_rows:
        key = row['m']
        if key is None:
            continue
        staff_by_month[key.month] = row['staff_distinct'] or 0

    abbr = list(calendar_mod.month_abbr)[1:]
    months_out = []
    for month in range(1, 13):
        r = runs_by_month.get(month)
        staff_n = staff_by_month.get(month, 0)
        run_count = r['run_count'] if r else 0
        sum_gross = r['sum_gross'] if r and r['sum_gross'] is not None else Decimal('0')
        sum_net = r['sum_net'] if r and r['sum_net'] is not None else Decimal('0')
        months_out.append({
            'month': month,
            'abbr': abbr[month - 1],
            'staff_paid': staff_n,
            'run_count': run_count,
            'sum_gross': sum_gross,
            'sum_net': sum_net,
            'has_data': bool(run_count or staff_n),
        })
    return y, months_out


@login_required
@role_required('accountant', 'senior_account_officer')
def payroll_list(request):
    """Accounting payroll hub — matches Sample Salary-RMC.xlsx (Raphal Medical Centre layout)."""
    payrolls = (
        AccountingPayroll.objects.filter(is_deleted=False)
        .annotate(
            active_entry_count=Count(
                'entries',
                filter=Q(entries__is_deleted=False, entries__staff_id__isnull=False),
            ),
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

    raw_year = (request.GET.get('year') or '').strip()
    try:
        calendar_year = int(raw_year) if raw_year else None
    except ValueError:
        calendar_year = None
    if calendar_year is None:
        latest_start = (
            AccountingPayroll.objects.filter(is_deleted=False)
            .order_by('-payroll_period_start')
            .values_list('payroll_period_start', flat=True)
            .first()
        )
        calendar_year = (latest_start.year if latest_start else timezone.now().year)
    calendar_year, payroll_calendar_months = _payroll_calendar_months_for_year(calendar_year)

    return render(request, 'hospital/accountant/payroll_list.html', {
        'payroll_rows': payroll_rows,
        'payrolls': payrolls_page,
        'total_payroll_runs': agg['cnt'] or 0,
        'sum_net_all': agg['sum_net'] or Decimal('0'),
        'sum_gross_all': agg['sum_gross'] or Decimal('0'),
        'payroll_calendar_year': calendar_year,
        'payroll_calendar_year_prev': calendar_year - 1,
        'payroll_calendar_year_next': calendar_year + 1,
        'payroll_calendar_months': payroll_calendar_months,
    })


def _payroll_analytics_resolve_year(request):
    raw_year = (request.GET.get('year') or '').strip()
    try:
        y = int(raw_year) if raw_year else None
    except ValueError:
        y = None
    if y is None:
        latest_start = (
            AccountingPayroll.objects.filter(is_deleted=False)
            .order_by('-payroll_period_start')
            .values_list('payroll_period_start', flat=True)
            .first()
        )
        y = (latest_start.year if latest_start else timezone.now().year)
    return max(2000, min(int(y), 2100))


def _payroll_years_with_data():
    rows = (
        AccountingPayroll.objects.filter(is_deleted=False)
        .annotate(y=ExtractYear('payroll_period_start'))
        .values('y')
        .distinct()
        .order_by('-y')
    )
    return [r['y'] for r in rows if r.get('y') is not None]


@login_required
@role_required('accountant', 'senior_account_officer')
def accountant_payroll_analytics(request):
    """Cross-run payroll analytics for a calendar year (period start)."""
    y = _payroll_analytics_resolve_year(request)
    abbr = list(calendar_mod.month_abbr)[1:]
    month_labels = [abbr[m - 1] for m in range(1, 13)]

    runs_rows = (
        AccountingPayroll.objects.filter(is_deleted=False, payroll_period_start__year=y)
        .annotate(m=TruncMonth('payroll_period_start'))
        .values('m')
        .annotate(
            run_count=Count('id'),
            sum_gross=Sum('total_gross_pay'),
            sum_net=Sum('total_net_pay'),
            sum_ded=Sum('total_deductions'),
        )
    )
    runs_by_month = {}
    for row in runs_rows:
        if row['m'] is None:
            continue
        runs_by_month[row['m'].month] = row

    staff_rows = (
        AccountingPayrollEntry.objects.filter(
            is_deleted=False,
            staff_id__isnull=False,
            payroll__is_deleted=False,
            payroll__payroll_period_start__year=y,
        )
        .annotate(m=TruncMonth('payroll__payroll_period_start'))
        .values('m')
        .annotate(staff_distinct=Count('staff', distinct=True))
    )
    staff_by_month = {}
    for row in staff_rows:
        if row['m'] is None:
            continue
        staff_by_month[row['m'].month] = row['staff_distinct'] or 0

    run_counts = []
    staff_paid = []
    net_series = []
    gross_series = []
    ded_series = []
    month_links = []
    for month in range(1, 13):
        r = runs_by_month.get(month)
        sn = staff_by_month.get(month, 0)
        run_counts.append(float(r['run_count'] if r else 0))
        staff_paid.append(int(sn))
        net_series.append(float(r['sum_net'] or 0) if r else 0.0)
        gross_series.append(float(r['sum_gross'] or 0) if r else 0.0)
        ded_series.append(float(r['sum_ded'] or 0) if r else 0.0)
        has_data = bool((r and r['run_count']) or sn)
        month_links.append({
            'month': month,
            'abbr': abbr[month - 1],
            'has_data': has_data,
        })

    status_rows = (
        AccountingPayroll.objects.filter(is_deleted=False, payroll_period_start__year=y)
        .values('status')
        .annotate(cnt=Count('id'), sum_net=Sum('total_net_pay'))
    )
    status_labels = []
    status_counts = []
    status_net = []
    status_lookup = dict(AccountingPayroll.STATUS_CHOICES)
    for row in sorted(status_rows, key=lambda x: x['status'] or ''):
        st = row['status'] or ''
        status_labels.append(status_lookup.get(st, st.replace('_', ' ').title()))
        status_counts.append(int(row['cnt'] or 0))
        status_net.append(float(row['sum_net'] or 0))

    by_dept = defaultdict(lambda: {'net': Decimal('0'), 'gross': Decimal('0')})
    entry_qs = (
        AccountingPayrollEntry.objects.filter(
            is_deleted=False,
            payroll__is_deleted=False,
            payroll__payroll_period_start__year=y,
            staff_id__isnull=False,
        )
        .select_related('staff', 'staff__department')
    )
    for e in entry_qs.iterator(chunk_size=500):
        snap = (getattr(e, 'department_snapshot', None) or '').strip()
        if snap:
            dname = snap
        elif e.staff_id and e.staff:
            dept = getattr(e.staff, 'department', None)
            dname = dept.name if dept else 'Unassigned'
        else:
            dname = 'Unassigned'
        by_dept[dname]['net'] += e.net_pay
        by_dept[dname]['gross'] += e.gross_pay

    dept_pairs = sorted(by_dept.items(), key=lambda x: float(x[1]['net']), reverse=True)
    top_n = 15
    dept_table = []
    other_net = Decimal('0')
    other_gross = Decimal('0')
    for i, (name, vals) in enumerate(dept_pairs):
        if i < top_n:
            dept_table.append({
                'name': name,
                'net': vals['net'],
                'gross': vals['gross'],
            })
        else:
            other_net += vals['net']
            other_gross += vals['gross']
    if len(dept_pairs) > top_n:
        dept_table.append({
            'name': f'Other ({len(dept_pairs) - top_n} departments)',
            'net': other_net,
            'gross': other_gross,
        })

    year_totals = (
        AccountingPayroll.objects.filter(is_deleted=False, payroll_period_start__year=y).aggregate(
            runs=Count('id'),
            net=Sum('total_net_pay'),
            gross=Sum('total_gross_pay'),
        )
    )
    staff_year = (
        AccountingPayrollEntry.objects.filter(
            is_deleted=False,
            staff_id__isnull=False,
            payroll__is_deleted=False,
            payroll__payroll_period_start__year=y,
        )
        .aggregate(n=Count('staff', distinct=True))
    )

    years_with_data = _payroll_years_with_data()
    years_for_select = sorted(set(years_with_data) | {y}, reverse=True)

    return render(request, 'hospital/accountant/payroll_analytics.html', {
        'analytics_year': y,
        'analytics_year_prev': y - 1,
        'analytics_year_next': y + 1,
        'years_for_select': years_for_select,
        'month_labels_json': json.dumps(month_labels),
        'run_counts_json': json.dumps(run_counts),
        'staff_paid_json': json.dumps(staff_paid),
        'net_series_json': json.dumps(net_series),
        'gross_series_json': json.dumps(gross_series),
        'ded_series_json': json.dumps(ded_series),
        'status_labels_json': json.dumps(status_labels),
        'status_counts_json': json.dumps(status_counts),
        'status_net_json': json.dumps(status_net),
        'dept_table': dept_table,
        'month_links': month_links,
        'year_total_runs': year_totals['runs'] or 0,
        'year_total_net': year_totals['net'] or Decimal('0'),
        'year_total_gross': year_totals['gross'] or Decimal('0'),
        'year_distinct_staff': staff_year['n'] or 0,
    })


@login_required
@role_required('accountant', 'senior_account_officer')
def accountant_payroll_analytics_month(request, year, month):
    """Runs and staff rollups for payrolls whose period starts in a calendar month."""
    y = max(2000, min(int(year), 2100))
    m = int(month)
    if m < 1 or m > 12:
        raise Http404('Invalid month')
    start = date(y, m, 1)
    last_day = calendar_mod.monthrange(y, m)[1]
    end = date(y, m, last_day)

    payrolls = (
        AccountingPayroll.objects.filter(
            is_deleted=False,
            payroll_period_start__gte=start,
            payroll_period_start__lte=end,
        )
        .annotate(line_count=Count('entries', filter=Q(entries__is_deleted=False)))
        .order_by('-pay_date', '-payroll_number')
    )
    payroll_list_m = list(payrolls.select_related('created_by'))

    staff_buckets = defaultdict(
        lambda: {'staff': None, 'run_ids': set(), 'net': Decimal('0'), 'gross': Decimal('0')}
    )
    if payroll_list_m:
        pids = [p.pk for p in payroll_list_m]
        for e in (
            AccountingPayrollEntry.objects.filter(
                payroll_id__in=pids,
                is_deleted=False,
                staff_id__isnull=False,
            )
            .select_related('staff__user')
            .iterator(chunk_size=500)
        ):
            b = staff_buckets[e.staff_id]
            b['staff'] = e.staff
            b['run_ids'].add(e.payroll_id)
            b['net'] += e.net_pay
            b['gross'] += e.gross_pay

    staff_rows = []
    for _, b in staff_buckets.items():
        st = b['staff']
        if not st:
            continue
        name = st.user.get_full_name() or st.user.username
        emp = (st.employee_id or '').strip() or '—'
        staff_rows.append({
            'name': name,
            'emp_code': emp,
            'run_count': len(b['run_ids']),
            'net': b['net'],
            'gross': b['gross'],
        })
    staff_rows.sort(key=lambda r: (r['name'].lower(), r['emp_code']))

    month_label = start.strftime('%B %Y')
    return render(request, 'hospital/accountant/payroll_analytics_month.html', {
        'bucket_year': y,
        'bucket_month': m,
        'bucket_start': start,
        'bucket_end': end,
        'month_label': month_label,
        'payrolls': payroll_list_m,
        'staff_rows': staff_rows,
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
        payroll.entries.filter(is_deleted=False, staff_id__isnull=False)
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
    payroll_footer_rmc = None
    if has_rmc_columns and entries_list:
        Z = Decimal('0')
        payroll_footer_rmc = {
            'basic': sum((e.basic_salary for e in entries_list), Z),
            'other_allowances': sum((e.other_allowances for e in entries_list), Z),
            'medical_allowance': sum((e.medical_allowance for e in entries_list), Z),
            'risk_emergency_allowance': sum((e.risk_emergency_allowance for e in entries_list), Z),
            'gross': sum((e.gross_pay for e in entries_list), Z),
            'ssnit': sum((e.ssnit_employee for e in entries_list), Z),
            'pension': sum((e.pension_employee for e in entries_list), Z),
            'paye': sum((e.paye_tax for e in entries_list), Z),
            'net': sum((e.net_pay for e in entries_list), Z),
        }
    entry_stats = payroll.entries.filter(is_deleted=False).aggregate(
        sum_net=Sum('net_pay'),
        sum_gross=Sum('gross_pay'),
        sum_ded=Sum('deductions'),
    )
    sum_net_e = entry_stats['sum_net'] or Decimal('0')
    sum_gross_e = entry_stats['sum_gross'] or Decimal('0')
    sum_ded_e = entry_stats['sum_ded'] or Decimal('0')
    avg_net_e = (sum_net_e / n_lines) if n_lines else Decimal('0')

    ded_labels = []
    ded_values = []
    if has_rmc_columns:
        ded_agg = payroll.entries.filter(is_deleted=False).aggregate(
            ssnit=Sum('ssnit_employee'),
            pf=Sum('pension_employee'),
            paye=Sum('paye_tax'),
            loan=Sum('loan_deduction'),
            other=Sum('other_deductions_detail'),
        )
        breakdown = [
            ('SSF (employee)', ded_agg.get('ssnit') or Decimal('0')),
            ('PF (employee)', ded_agg.get('pf') or Decimal('0')),
            ('PAYE', ded_agg.get('paye') or Decimal('0')),
            ('Loan', ded_agg.get('loan') or Decimal('0')),
            ('Other deductions', ded_agg.get('other') or Decimal('0')),
        ]
        for label, val in breakdown:
            if val > Decimal('0'):
                ded_labels.append(label)
                ded_values.append(float(val))
        if not ded_labels and sum_ded_e > Decimal('0'):
            ded_labels = ['Total deductions']
            ded_values = [float(sum_ded_e)]
    else:
        if sum_ded_e > Decimal('0') or sum_net_e > Decimal('0'):
            ded_labels = ['Total deductions', 'Net pay']
            ded_values = [float(sum_ded_e), float(sum_net_e)]

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
        'deduction_chart_labels_json': json.dumps(ded_labels),
        'deduction_chart_values_json': json.dumps(ded_values),
        'entry_line_count': n_lines,
        'entry_sum_net': sum_net_e,
        'entry_sum_gross': sum_gross_e,
        'entry_sum_deductions': sum_ded_e,
        'entry_avg_net': avg_net_e,
        'payroll_footer_rmc': payroll_footer_rmc,
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
    """List doctor commissions; default scope is specialist doctors (Staff with SpecialistProfile)."""
    scope = (request.GET.get('scope') or 'specialists').strip().lower()
    if scope not in ('specialists', 'all'):
        scope = 'specialists'

    commissions = (
        DoctorCommission.objects.all()
        .select_related(
            'doctor',
            'doctor__user',
            'doctor__specialist_profile',
            'doctor__specialist_profile__specialty',
        )
        .order_by('-service_date')
    )
    if scope == 'specialists':
        commissions = commissions.filter(doctor__specialist_profile__isnull=False)

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

    from .models import Staff

    doctors_qs = Staff.objects.filter(profession='doctor', is_deleted=False).select_related('user')
    if scope == 'specialists':
        doctors_qs = doctors_qs.filter(specialist_profile__isnull=False).select_related(
            'specialist_profile__specialty'
        )
    doctors = doctors_qs.order_by('user__last_name', 'user__first_name')

    pq = request.GET.copy()
    pq.pop('page', None)
    pagination_query = pq.urlencode()

    return render(request, 'hospital/accountant/doctor_commission_list.html', {
        'commissions': commissions_page,
        'is_paid_filter': is_paid_filter,
        'doctors': doctors,
        'commission_scope': scope,
        'pagination_query': pagination_query,
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
    from hospital.utils_bills_go_live import get_bills_go_live_date, resolve_date_from_for_listing

    fees = RegistrationFee.objects.filter(is_deleted=False).order_by('-registration_date')

    include_legacy = request.GET.get('include_legacy') == '1'
    date_from_raw = (request.GET.get('date_from') or '').strip()
    date_from_effective, date_from = resolve_date_from_for_listing(date_from_raw, include_legacy)
    date_to = (request.GET.get('date_to') or '').strip()
    patient_search = request.GET.get('patient_search', '').strip()

    if date_from_effective:
        fees = fees.filter(registration_date__gte=date_from_effective)
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
        'date_from': date_from,
        'date_to': date_to,
        'patient_search': patient_search,
        'include_legacy': include_legacy,
        'bills_go_live_date': get_bills_go_live_date().isoformat(),
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
    """View chart of accounts with balances grouped by financial statement sections."""
    from hospital.services.trial_balance_service import get_account_ledger_totals, _account_balance_from_totals
    from hospital.services.chart_of_accounts_grouping import build_chart_of_accounts_sections
    from hospital.services.account_delete_service import can_delete_account, get_account_delete_blockers
    from django.db.models import Q
    
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
    
    account_list = []
    for account in accounts.order_by('account_code'):
        total_debits, total_credits, _ = get_account_ledger_totals(account, timezone.now().date())
        balance = _account_balance_from_totals(account.account_type, total_debits, total_credits)
        blockers = get_account_delete_blockers(account)
        
        account_list.append({
            'account': account,
            'balance': balance,
            'total_debits': total_debits,
            'total_credits': total_credits,
            'can_delete': can_delete_account(account),
            'delete_block_reason': '; '.join(blockers) if blockers else '',
        })
    
    chart_sections = build_chart_of_accounts_sections(account_list)
    
    return render(request, 'hospital/accountant/chart_of_accounts.html', {
        'chart_sections': chart_sections,
        'account_list': account_list,
        'account_types': Account.ACCOUNT_TYPES,
        'account_subgroups': Account.ACCOUNT_SUBGROUPS,
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
        account.account_subgroup = request.POST.get('account_subgroup', '') or ''
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
    
    from hospital.services.chart_of_accounts_grouping import subgroup_choices_for_type

    context = {
        'account': account,
        'parent_accounts': parent_accounts,
        'account_types': Account.ACCOUNT_TYPES,
        'account_subgroups': subgroup_choices_for_type(account.account_type),
        'all_subgroups': Account.ACCOUNT_SUBGROUPS,
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
                    account_subgroup=request.POST.get('account_subgroup', '') or '',
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
    from hospital.services.chart_of_accounts_grouping import subgroup_choices_for_type

    parent_accounts = Account.objects.filter(is_deleted=False).order_by('account_code')
    form_data = request.POST if request.method == 'POST' else None
    selected_type = (form_data.get('account_type') if form_data else None) or 'asset'
    context = {
        'parent_accounts': parent_accounts,
        'account_types': Account.ACCOUNT_TYPES,
        'account_subgroups': subgroup_choices_for_type(selected_type),
        'all_subgroups': Account.ACCOUNT_SUBGROUPS,
        'form_data': form_data,
    }
    return render(request, 'hospital/accountant/account_create.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def account_delete(request, account_id):
    """Soft-delete an unused chart-of-accounts row."""
    from hospital.services.account_delete_service import get_account_delete_blockers

    account = get_object_or_404(Account, id=account_id, is_deleted=False)

    if request.method != 'POST':
        return redirect('hospital:accountant_chart_of_accounts')

    blockers = get_account_delete_blockers(account)
    if blockers:
        messages.error(
            request,
            f'Cannot delete {account.account_code} — {blockers[0]}'
            + (f' (+{len(blockers) - 1} more)' if len(blockers) > 1 else ''),
        )
        return redirect('hospital:accountant_chart_of_accounts')

    code = account.account_code
    account.is_deleted = True
    account.is_active = False
    account.save(update_fields=['is_deleted', 'is_active', 'modified'])
    messages.success(request, f'Account {code} deleted successfully.')
    return redirect('hospital:accountant_chart_of_accounts')


@login_required
@role_required('accountant', 'senior_account_officer')
def account_detail(request, account_id):
    """View account details with transactions - Accountant-friendly view"""
    from hospital.services.trial_balance_service import (
        DEBIT_NORMAL_TYPES,
        get_account_ledger_totals,
        _account_balance_from_totals,
    )
    from django.core.paginator import Paginator

    account = get_object_or_404(Account, id=account_id, is_deleted=False)

    as_of_date = request.GET.get('as_of_date', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    if as_of_date:
        end_date = as_of_date
        if not start_date:
            start_date = '1900-01-01'

    if not start_date or not end_date:
        today = timezone.now().date()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')

    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None

    _, _, all_entries = get_account_ledger_totals(account, end_date_obj or timezone.now().date())

    opening_debits = Decimal('0.00')
    opening_credits = Decimal('0.00')
    for entry in all_entries:
        entry_date = entry['date']
        if start_date_obj and entry_date and entry_date < start_date_obj:
            opening_debits += entry['debit'] or Decimal('0.00')
            opening_credits += entry['credit'] or Decimal('0.00')

    opening_balance = _account_balance_from_totals(
        account.account_type, opening_debits, opening_credits
    )

    transactions = []
    total_debits = Decimal('0.00')
    total_credits = Decimal('0.00')

    for entry in all_entries:
        entry_date = entry['date']
        if start_date_obj and entry_date and entry_date < start_date_obj:
            continue
        if end_date_obj and entry_date and entry_date > end_date_obj:
            continue

        journal_entry = None
        if entry.get('journal_entry_id'):
            try:
                from .models_accounting_advanced import AdvancedJournalEntry
                journal_entry = AdvancedJournalEntry.objects.filter(
                    pk=entry['journal_entry_id']
                ).first()
            except Exception:
                journal_entry = None

        transactions.append({
            'date': entry_date,
            'description': entry.get('description') or '',
            'debit': entry.get('debit') or Decimal('0.00'),
            'credit': entry.get('credit') or Decimal('0.00'),
            'journal_entry': journal_entry,
            'reference': entry.get('reference_number') or entry.get('entry_number') or '',
        })
        total_debits += entry.get('debit') or Decimal('0.00')
        total_credits += entry.get('credit') or Decimal('0.00')

    transactions.sort(key=lambda x: (x['date'] or date(1900, 1, 1), x['reference']), reverse=True)

    if account.account_type in DEBIT_NORMAL_TYPES:
        closing_balance = opening_balance + total_debits - total_credits
    else:
        closing_balance = opening_balance + total_credits - total_debits

    running_balance = opening_balance
    transactions_with_balance = []

    for trans in transactions:
        if account.account_type in DEBIT_NORMAL_TYPES:
            running_balance = running_balance + trans['debit'] - trans['credit']
        else:
            running_balance = running_balance + trans['credit'] - trans['debit']

        trans['running_balance'] = running_balance
        transactions_with_balance.append(trans)

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
        'as_of_date': as_of_date,
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

