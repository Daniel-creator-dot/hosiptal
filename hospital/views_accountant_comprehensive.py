"""
Comprehensive Accountant Views - All Accounting Features
Provides access to all accounting features for accountants
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Q, Count, F
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import transaction
from datetime import datetime, timedelta, date
from decimal import Decimal
import json

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


def is_accountant(user):
    """Check if user is accountant"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role = get_user_role(user)
    return role == 'accountant'


@login_required
@role_required('accountant')
def accountant_comprehensive_dashboard(request):
    """Comprehensive accountant dashboard with all accounting features"""
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    
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
    
    context = {
        'today': today,
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
    }
    
    return render(request, 'hospital/accountant/comprehensive_dashboard.html', context)


# ==================== CASHBOOK VIEWS ====================

@login_required
@role_required('accountant')
def cashbook_list(request):
    """List all cashbook entries"""
    entries = Cashbook.objects.all().order_by('-entry_date', '-entry_number')
    
    # Filters
    status_filter = request.GET.get('status', '')
    entry_type_filter = request.GET.get('entry_type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if status_filter:
        entries = entries.filter(status=status_filter)
    if entry_type_filter:
        entries = entries.filter(entry_type=entry_type_filter)
    if date_from:
        entries = entries.filter(entry_date__gte=date_from)
    if date_to:
        entries = entries.filter(entry_date__lte=date_to)
    
    paginator = Paginator(entries, 50)
    page = request.GET.get('page')
    entries_page = paginator.get_page(page)
    
    context = {
        'entries': entries_page,
        'status_filter': status_filter,
        'entry_type_filter': entry_type_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'hospital/accountant/cashbook_list.html', context)


@login_required
@role_required('accountant')
def cashbook_detail(request, entry_id):
    """View cashbook entry details"""
    entry = get_object_or_404(Cashbook, pk=entry_id)
    
    context = {
        'entry': entry,
        'can_classify': entry.can_classify(),
    }
    
    return render(request, 'hospital/accountant/cashbook_detail.html', context)


@login_required
@role_required('accountant')
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
@role_required('accountant')
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
@role_required('accountant')
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
@role_required('accountant')
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
@role_required('accountant')
def insurance_receivable_list(request):
    """List all insurance receivables"""
    receivables = InsuranceReceivable.objects.all().order_by('-claim_date')
    
    # Filters
    status_filter = request.GET.get('status', '')
    insurance_filter = request.GET.get('insurance', '')
    
    if status_filter:
        receivables = receivables.filter(status=status_filter)
    if insurance_filter:
        receivables = receivables.filter(insurance_company_id=insurance_filter)
    
    paginator = Paginator(receivables, 50)
    page = request.GET.get('page')
    receivables_page = paginator.get_page(page)
    
    # Get insurance companies for filter
    from .models import Payer
    insurance_companies = Payer.objects.filter(payer_type='insurance', is_active=True)
    
    return render(request, 'hospital/accountant/insurance_receivable_list.html', {
        'receivables': receivables_page,
        'status_filter': status_filter,
        'insurance_companies': insurance_companies,
    })


# ==================== PROCUREMENT PURCHASE VIEWS ====================

@login_required
@role_required('accountant')
def procurement_purchase_list(request):
    """List all procurement purchases"""
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
    
    return render(request, 'hospital/accountant/procurement_purchase_list.html', {
        'purchases': purchases_page,
        'purchase_type_filter': purchase_type_filter,
        'status_filter': status_filter,
    })


# ==================== PAYROLL VIEWS ====================

@login_required
@role_required('accountant')
def payroll_list(request):
    """List all accounting payrolls"""
    payrolls = AccountingPayroll.objects.all().order_by('-payroll_period_end')
    
    paginator = Paginator(payrolls, 20)
    page = request.GET.get('page')
    payrolls_page = paginator.get_page(page)
    
    return render(request, 'hospital/accountant/payroll_list.html', {
        'payrolls': payrolls_page,
    })


@login_required
@role_required('accountant')
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
@role_required('accountant')
def profit_loss_list(request):
    """List all profit & loss reports"""
    reports = ProfitLossReport.objects.all().order_by('-period_end')
    
    # Filters
    period_filter = request.GET.get('period', '')
    fiscal_year_filter = request.GET.get('fiscal_year', '')
    
    if period_filter:
        reports = reports.filter(report_period=period_filter)
    if fiscal_year_filter:
        reports = reports.filter(fiscal_year_id=fiscal_year_filter)
    
    paginator = Paginator(reports, 20)
    page = request.GET.get('page')
    reports_page = paginator.get_page(page)
    
    fiscal_years = FiscalYear.objects.all().order_by('-start_date')
    
    return render(request, 'hospital/accountant/profit_loss_list.html', {
        'reports': reports_page,
        'period_filter': period_filter,
        'fiscal_year_filter': fiscal_year_filter,
        'fiscal_years': fiscal_years,
    })


@login_required
@role_required('accountant')
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
@role_required('accountant')
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
@role_required('accountant')
def registration_fee_list(request):
    """List all registration fees"""
    fees = RegistrationFee.objects.all().order_by('-registration_date')
    
    paginator = Paginator(fees, 50)
    page = request.GET.get('page')
    fees_page = paginator.get_page(page)
    
    return render(request, 'hospital/accountant/registration_fee_list.html', {
        'fees': fees_page,
    })


# ==================== CASH SALES VIEWS ====================

@login_required
@role_required('accountant')
def cash_sale_list(request):
    """List all cash sales"""
    sales = CashSale.objects.all().order_by('-sale_date')
    
    paginator = Paginator(sales, 50)
    page = request.GET.get('page')
    sales_page = paginator.get_page(page)
    
    return render(request, 'hospital/accountant/cash_sale_list.html', {
        'sales': sales_page,
    })


# ==================== CORPORATE ACCOUNT VIEWS ====================

@login_required
@role_required('accountant')
def corporate_account_list(request):
    """List all accounting corporate accounts"""
    accounts = AccountingCorporateAccount.objects.all().order_by('company_name')
    
    return render(request, 'hospital/accountant/corporate_account_list.html', {
        'accounts': accounts,
    })


# ==================== WITHHOLDING RECEIVABLE VIEWS ====================

@login_required
@role_required('accountant')
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
@role_required('accountant')
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
@role_required('accountant')
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
@role_required('accountant')
def chart_of_accounts(request):
    """View chart of accounts"""
    accounts = Account.objects.filter(is_active=True).order_by('account_code')
    
    # Group by account type
    accounts_by_type = {}
    for account in accounts:
        account_type = account.get_account_type_display()
        if account_type not in accounts_by_type:
            accounts_by_type[account_type] = []
        accounts_by_type[account_type].append(account)
    
    return render(request, 'hospital/accountant/chart_of_accounts.html', {
        'accounts_by_type': accounts_by_type,
    })


# ==================== ACCOUNT SYNC VIEWS ====================

@login_required
@role_required('accountant')
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
@role_required('accountant')
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

