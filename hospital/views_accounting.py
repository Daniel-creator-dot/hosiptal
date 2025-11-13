"""
Accounting and Financial Management Views
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.http import JsonResponse, HttpResponse
from datetime import date, timedelta
from decimal import Decimal
from .models import Patient, Invoice
from .models_accounting import (
    Account, Transaction, PaymentReceipt, AccountsReceivable,
    GeneralLedger, JournalEntry, JournalEntryLine
)
from .models_workflow import Bill, CashierSession


def is_accountant(user):
    """Check if user is an accountant"""
    return user.groups.filter(name__in=['Cashier', 'Admin']).exists() or user.is_staff


@login_required
@user_passes_test(is_accountant, login_url='/admin/login/')
def accounting_dashboard(request):
    """Accounting main dashboard with FULL SYNC"""
    today = timezone.now().date()
    
    # Accounts Receivable Summary
    ar_total = AccountsReceivable.objects.filter(
        outstanding_amount__gt=0,
        is_deleted=False
    ).aggregate(Sum('outstanding_amount'))['outstanding_amount__sum'] or Decimal('0.00')
    
    ar_by_aging = {
        'current': AccountsReceivable.objects.filter(aging_bucket='current', is_deleted=False).aggregate(Sum('outstanding_amount'))['outstanding_amount__sum'] or Decimal('0.00'),
        'aging_31_60': AccountsReceivable.objects.filter(aging_bucket='31-60', is_deleted=False).aggregate(Sum('outstanding_amount'))['outstanding_amount__sum'] or Decimal('0.00'),
        'aging_61_90': AccountsReceivable.objects.filter(aging_bucket='61-90', is_deleted=False).aggregate(Sum('outstanding_amount'))['outstanding_amount__sum'] or Decimal('0.00'),
        'aging_90_plus': AccountsReceivable.objects.filter(aging_bucket='90+', is_deleted=False).aggregate(Sum('outstanding_amount'))['outstanding_amount__sum'] or Decimal('0.00'),
    }
    
    # Today's revenue from GENERAL LEDGER (source of truth)
    # Note: transaction_date is a DateField, so we don't use __date lookup
    today_revenue_gl = GeneralLedger.objects.filter(
        account__account_type='revenue',
        transaction_date=today,
        is_deleted=False
    ).aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
    
    # Today's revenue from PaymentReceipts (for comparison)
    # Note: receipt_date is a DateTimeField, so we use __date lookup
    today_revenue_receipts = PaymentReceipt.objects.filter(
        receipt_date__date=today,
        is_deleted=False
    ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
    
    # Use GL as primary, fallback to receipts if GL is empty
    today_revenue = today_revenue_gl if today_revenue_gl > 0 else today_revenue_receipts
    
    # Calculate sync variance (absolute difference)
    sync_variance = abs(today_revenue_gl - today_revenue_receipts)
    is_synced = today_revenue_gl == today_revenue_receipts
    
    # Recent journal entries (proper accounting view)
    recent_journal_entries = JournalEntry.objects.filter(
        is_deleted=False
    ).select_related('entered_by', 'posted_by').prefetch_related('lines__account').order_by('-entry_date', '-created')[:15]
    
    # Recent transactions (old view, for compatibility)
    recent_transactions = Transaction.objects.filter(
        is_deleted=False
    ).select_related('patient', 'invoice').order_by('-transaction_date')[:20]
    
    # Open cashier sessions
    open_sessions = CashierSession.objects.filter(
        status='open',
        is_deleted=False
    ).select_related('cashier')[:5]
    
    # Get account balances for quick view
    from .models_accounting import Account
    key_accounts = Account.objects.filter(
        account_code__in=['1010', '4010', '4020', '4030', '4040', '4060'],  # Cash, Lab Rev, Pharmacy Rev, Imaging Rev, Consult Rev, Admission Rev
        is_deleted=False
    )
    
    account_balances = {}
    for account in key_accounts:
        # Calculate balance from all GL entries for this account
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
            # Assets and Expenses: Debit increases, Credit decreases
            balance = total_debits - total_credits
        else:
            # Liabilities, Equity, Revenue: Credit increases, Debit decreases
            balance = total_credits - total_debits
        
        account_balances[account.account_code] = {
            'name': account.account_name,
            'balance': balance
        }
    
    context = {
        'ar_total': ar_total,
        'ar_by_aging': ar_by_aging,
        'today_revenue': today_revenue,
        'today_revenue_gl': today_revenue_gl,
        'today_revenue_receipts': today_revenue_receipts,
        'sync_variance': sync_variance,
        'is_synced': is_synced,
        'recent_journal_entries': recent_journal_entries,
        'recent_transactions': recent_transactions,
        'open_sessions': open_sessions,
        'account_balances': account_balances,
        'today': today,
    }
    return render(request, 'hospital/accounting_dashboard.html', context)


@login_required
@user_passes_test(is_accountant, login_url='/admin/login/')
def accounts_receivable(request):
    """Accounts Receivable aging report"""
    aging_filter = request.GET.get('aging', '')
    
    ar_entries = AccountsReceivable.objects.filter(
        outstanding_amount__gt=0,
        is_deleted=False
    ).select_related('invoice', 'patient').order_by('due_date')
    
    if aging_filter:
        ar_entries = ar_entries.filter(aging_bucket=aging_filter)
    
    # Update aging for all entries
    for entry in ar_entries:
        entry.update_aging()
    
    context = {
        'ar_entries': ar_entries,
        'aging_filter': aging_filter,
    }
    return render(request, 'hospital/accounts_receivable.html', context)


@login_required
@user_passes_test(is_accountant, login_url='/admin/login/')
def general_ledger(request):
    """General Ledger view"""
    account_filter = request.GET.get('account')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    entries = GeneralLedger.objects.filter(is_deleted=False).select_related('account')
    
    if account_filter:
        entries = entries.filter(account_id=account_filter)
    
    if start_date:
        try:
            entries = entries.filter(transaction_date__gte=date.fromisoformat(start_date))
        except ValueError:
            pass
    
    if end_date:
        try:
            entries = entries.filter(transaction_date__lte=date.fromisoformat(end_date))
        except ValueError:
            pass
    
    # Get account balances
    accounts = Account.objects.filter(is_active=True, is_deleted=False)
    
    context = {
        'entries': entries.order_by('-transaction_date')[:500],
        'accounts': accounts,
        'selected_account': account_filter,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'hospital/general_ledger.html', context)


@login_required
@user_passes_test(is_accountant, login_url='/admin/login/')
def trial_balance(request):
    """Trial Balance report"""
    report_date = request.GET.get('date')
    
    if report_date:
        try:
            report_date = date.fromisoformat(report_date)
        except ValueError:
            report_date = timezone.now().date()
    else:
        report_date = timezone.now().date()
    
    accounts = Account.objects.filter(is_active=True, is_deleted=False)
    
    trial_balance_data = []
    total_debits = Decimal('0.00')
    total_credits = Decimal('0.00')
    
    for account in accounts:
        entries = GeneralLedger.objects.filter(
            account=account,
            transaction_date__lte=report_date,
            is_deleted=False
        )
        
        debits = entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
        credits = entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
        balance = debits - credits
        
        if debits > 0 or credits > 0:
            trial_balance_data.append({
                'account': account,
                'debits': debits,
                'credits': credits,
                'balance': balance,
            })
            total_debits += debits
            total_credits += credits
    
    context = {
        'trial_balance': trial_balance_data,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'report_date': report_date,
    }
    return render(request, 'hospital/trial_balance.html', context)


@login_required
@user_passes_test(is_accountant, login_url='/admin/login/')
def financial_statement(request):
    """Financial statements (P&L, Balance Sheet)"""
    statement_type = request.GET.get('type', 'profit_loss')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    today = timezone.now().date()
    if not start_date:
        start_date = today.replace(month=1, day=1)
    else:
        try:
            start_date = date.fromisoformat(start_date)
        except ValueError:
            start_date = today.replace(month=1, day=1)
    
    if not end_date:
        end_date = today
    else:
        try:
            end_date = date.fromisoformat(end_date)
        except ValueError:
            end_date = today
    
    context = {
        'statement_type': statement_type,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    if statement_type == 'profit_loss':
        # P&L Statement
        revenue = GeneralLedger.objects.filter(
            account__account_type='revenue',
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            is_deleted=False
        ).aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
        
        expenses = GeneralLedger.objects.filter(
            account__account_type='expense',
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            is_deleted=False
        ).aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
        
        context.update({
            'revenue': revenue,
            'expenses': expenses,
            'net_income': revenue - expenses,
        })
    
    elif statement_type == 'balance_sheet':
        # Balance Sheet
        # Assets = Debit balance (debits - credits)
        assets_data = GeneralLedger.objects.filter(
            account__account_type='asset',
            transaction_date__lte=end_date,
            is_deleted=False
        ).aggregate(
            total_debits=Sum('debit_amount'),
            total_credits=Sum('credit_amount')
        )
        
        total_assets = (
            (assets_data['total_debits'] or Decimal('0.00')) - 
            (assets_data['total_credits'] or Decimal('0.00'))
        )
        
        # Liabilities = Credit balance (credits - debits)
        liabilities_data = GeneralLedger.objects.filter(
            account__account_type='liability',
            transaction_date__lte=end_date,
            is_deleted=False
        ).aggregate(
            total_debits=Sum('debit_amount'),
            total_credits=Sum('credit_amount')
        )
        
        total_liabilities = (
            (liabilities_data['total_credits'] or Decimal('0.00')) - 
            (liabilities_data['total_debits'] or Decimal('0.00'))
        )
        
        # Equity = Credit balance (credits - debits)
        equity_data = GeneralLedger.objects.filter(
            account__account_type='equity',
            transaction_date__lte=end_date,
            is_deleted=False
        ).aggregate(
            total_debits=Sum('debit_amount'),
            total_credits=Sum('credit_amount')
        )
        
        total_equity = (
            (equity_data['total_credits'] or Decimal('0.00')) - 
            (equity_data['total_debits'] or Decimal('0.00'))
        )
        
        # Calculate Net Income (Revenue - Expenses) to add to Retained Earnings
        revenue = GeneralLedger.objects.filter(
            account__account_type='revenue',
            transaction_date__lte=end_date,
            is_deleted=False
        ).aggregate(
            total_credits=Sum('credit_amount'),
            total_debits=Sum('debit_amount')
        )
        
        expenses = GeneralLedger.objects.filter(
            account__account_type='expense',
            transaction_date__lte=end_date,
            is_deleted=False
        ).aggregate(
            total_debits=Sum('debit_amount'),
            total_credits=Sum('credit_amount')
        )
        
        total_revenue = (
            (revenue['total_credits'] or Decimal('0.00')) - 
            (revenue['total_debits'] or Decimal('0.00'))
        )
        total_expenses = (
            (expenses['total_debits'] or Decimal('0.00')) - 
            (expenses['total_credits'] or Decimal('0.00'))
        )
        net_income = total_revenue - total_expenses
        
        # Add Net Income to Equity (Retained Earnings)
        total_equity_with_income = total_equity + net_income
        
        # Calculate asset breakdown
        cash_data = GeneralLedger.objects.filter(
            account__account_code__in=['1010', '1020', '1030', '1040'],
            transaction_date__lte=end_date,
            is_deleted=False
        ).aggregate(
            total_debits=Sum('debit_amount'),
            total_credits=Sum('credit_amount')
        )
        
        total_cash = (
            (cash_data['total_debits'] or Decimal('0.00')) - 
            (cash_data['total_credits'] or Decimal('0.00'))
        )
        
        ar_data = GeneralLedger.objects.filter(
            account__account_code='1200',
            transaction_date__lte=end_date,
            is_deleted=False
        ).aggregate(
            total_debits=Sum('debit_amount'),
            total_credits=Sum('credit_amount')
        )
        
        total_ar = (
            (ar_data['total_debits'] or Decimal('0.00')) - 
            (ar_data['total_credits'] or Decimal('0.00'))
        )
        
        context.update({
            'total_assets': total_assets,
            'total_cash': total_cash,
            'total_ar': total_ar,
            'total_liabilities': total_liabilities,
            'total_equity': total_equity,
            'net_income': net_income,
            'total_equity_with_income': total_equity_with_income,
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
        })
    
    elif statement_type == 'cashflow':
        # Cash Flow Statement
        # Get cash account codes (1010, 1020, 1030, 1040)
        cash_account_codes = ['1010', '1020', '1030', '1040']  # Cash, Card, Mobile, Bank
        
        # Operating Activities - Cash received from revenue
        cash_from_operations = GeneralLedger.objects.filter(
            account__account_code__in=cash_account_codes,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            is_deleted=False
        ).aggregate(
            cash_in=Sum('debit_amount'),
            cash_out=Sum('credit_amount')
        )
        
        cash_receipts = cash_from_operations['cash_in'] or Decimal('0.00')
        cash_payments = cash_from_operations['cash_out'] or Decimal('0.00')
        net_operating_cash = cash_receipts - cash_payments
        
        # Get beginning cash balance (before start_date)
        beginning_cash_entries = GeneralLedger.objects.filter(
            account__account_code__in=cash_account_codes,
            transaction_date__lt=start_date,
            is_deleted=False
        ).aggregate(
            total_debits=Sum('debit_amount'),
            total_credits=Sum('credit_amount')
        )
        
        beginning_cash = (
            (beginning_cash_entries['total_debits'] or Decimal('0.00')) - 
            (beginning_cash_entries['total_credits'] or Decimal('0.00'))
        )
        
        # Ending cash balance
        ending_cash = beginning_cash + net_operating_cash
        
        context.update({
            'cash_receipts': cash_receipts,
            'cash_payments': cash_payments,
            'net_operating_cash': net_operating_cash,
            'beginning_cash': beginning_cash,
            'ending_cash': ending_cash,
            'net_cash_flow': net_operating_cash,
        })
    
    return render(request, 'hospital/financial_statement.html', context)

