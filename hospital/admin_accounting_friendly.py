"""
Accounting-Friendly Admin Interface
Customizes admin to show only accounting-related models for accountants
"""
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

# Accounting models that should be visible to accountants
ACCOUNTING_MODEL_NAMES = {
    # Core Accounting
    'account', 'costcenter', 'transaction', 'paymentreceipt', 'paymentallocation',
    'accountsreceivable', 'generalledger', 'journalentry', 'journalentryline',
    
    # Advanced Accounting
    'accountcategory', 'fiscalyear', 'accountingperiod', 'journal',
    'advancedjournalentry', 'advancedjournalentryline', 'advancedgeneralledger',
    'paymentvoucher', 'receiptvoucher', 'cheque',
    'revenuecategory', 'revenue', 'expensecategory', 'expense',
    'advancedaccountsreceivable', 'accountspayable',
    'bankaccount', 'banktransaction',
    'budget', 'budgetline', 'taxrate',
    'accountingauditlog',
    'cashbook',
    'bankreconciliation', 'bankreconciliationitem',
    'insurancereceivable',
    'procurementpurchase',
    'accountingpayroll', 'accountingpayrollentry', 'doctorcommission',
    'incomegroup', 'profitlossreport',
    'registrationfee', 'cashsale', 'accountingcorporateaccount',
    'withholdingreceivable', 'withholdingtaxpayable', 'deposit', 'initialrevaluation',
    'pettycashtransaction',
    
    # Related Financial
    'invoice', 'invoiceline',
    'cashiersession',
    'revenuestream', 'departmentrevenue',
    'procurementrequest', 'procurementrequestitem',
    'corporateaccount',
}

# Group accounting models by category
ACCOUNTING_MODEL_GROUPS = {
    'Chart of Accounts': [
        'account', 'accountcategory', 'costcenter',
    ],
    'Journal Entries & Ledger': [
        'journal', 'advancedjournalentry', 'advancedjournalentryline',
        'advancedgeneralledger', 'generalledger', 'journalentry', 'journalentryline',
    ],
    'Transactions & Payments': [
        'transaction', 'paymentreceipt', 'paymentallocation',
        'cashiersession', 'invoice', 'invoiceline',
    ],
    'Vouchers & Cashbook': [
        'paymentvoucher', 'receiptvoucher', 'cheque', 'cashbook',
        'pettycashtransaction',
    ],
    'Revenue & Expenses': [
        'revenuecategory', 'revenue', 'expensecategory', 'expense',
        'revenuestream', 'departmentrevenue',
    ],
    'Accounts Receivable & Payable': [
        'accountsreceivable', 'advancedaccountsreceivable',
        'accountspayable', 'insurancereceivable',
    ],
    'Banking & Reconciliation': [
        'bankaccount', 'banktransaction',
        'bankreconciliation', 'bankreconciliationitem',
    ],
    'Budget & Planning': [
        'budget', 'budgetline', 'fiscalyear', 'accountingperiod',
    ],
    'Payroll & Commissions': [
        'accountingpayroll', 'accountingpayrollentry', 'doctorcommission',
    ],
    'Reports & Analytics': [
        'profitlossreport', 'accountingauditlog',
        'incomegroup',
    ],
    'Other Financial': [
        'taxrate', 'procurementpurchase',
        'registrationfee', 'cashsale', 'accountingcorporateaccount',
        'withholdingreceivable', 'withholdingtaxpayable', 'deposit', 'initialrevaluation',
        'corporateaccount',
    ],
}


def is_accounting_model(model):
    """Check if a model is accounting-related"""
    model_name = model.__name__.lower()
    return model_name in ACCOUNTING_MODEL_NAMES or any(
        model_name.startswith(prefix) for prefix in ['account', 'payment', 'receipt', 'revenue', 'expense', 'invoice', 'journal', 'ledger', 'cashbook', 'budget', 'bank', 'voucher']
    )


def get_accounting_model_groups():
    """Get accounting models grouped by category"""
    from django.apps import apps
    from django.contrib.admin.sites import site
    
    groups = {}
    for group_name, model_names in ACCOUNTING_MODEL_GROUPS.items():
        models_in_group = []
        for model_name in model_names:
            try:
                model = apps.get_model('hospital', model_name)
                if model in site._registry:
                    models_in_group.append({
                        'name': model._meta.verbose_name_plural.title(),
                        'model_name': model_name,
                        'url': reverse(f'admin:hospital_{model_name}_changelist'),
                    })
            except:
                continue
        if models_in_group:
            groups[group_name] = models_in_group
    
    return groups


@staff_member_required
def accounting_friendly_admin_index(request, extra_context=None):
    """Custom admin index that shows only accounting models for accountants"""
    from django.contrib.admin.sites import site
    
    # Get accounting model groups
    model_groups = get_accounting_model_groups()
    
    # Get accounting statistics
    try:
        from .models_accounting import Account, Transaction, PaymentReceipt
        from .models_accounting_advanced import (
            AdvancedJournalEntry, PaymentVoucher, Cashbook,
            Revenue, Expense, AccountsPayable, InsuranceReceivable,
            PettyCashTransaction
        )
        
        today = timezone.now().date()
        this_month_start = today.replace(day=1)
        
        stats = {
            'total_accounts': Account.objects.filter(is_active=True).count(),
            'pending_vouchers': PaymentVoucher.objects.filter(status='pending_approval', is_deleted=False).count(),
            'pending_petty_cash': PettyCashTransaction.objects.filter(status='pending_approval', is_deleted=False).count(),
            'month_revenue': Revenue.objects.filter(
                revenue_date__gte=this_month_start
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
            'month_expenses': Expense.objects.filter(
                expense_date__gte=this_month_start,
                status__in=['approved', 'paid']
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
            'pending_payables': AccountsPayable.objects.filter(is_overdue=False).count(),
            'overdue_payables': AccountsPayable.objects.filter(is_overdue=True).count(),
            'pending_receivables': InsuranceReceivable.objects.filter(
                status__in=['pending', 'submitted', 'approved']
            ).count(),
        }
    except Exception as e:
        # If models don't exist, use defaults
        stats = {
            'total_accounts': 0,
            'pending_vouchers': 0,
            'pending_petty_cash': 0,
            'month_revenue': Decimal('0.00'),
            'month_expenses': Decimal('0.00'),
            'pending_payables': 0,
            'overdue_payables': 0,
            'pending_receivables': 0,
        }
    
    extra_context = extra_context or {}
    extra_context.update({
        'accounting_mode': True,
        'model_groups': model_groups,
        'stats': stats,
    })
    
    # Use custom template
    return TemplateResponse(request, 'admin/accounting_admin_index.html', extra_context)


# We'll patch the existing custom_admin_index in admin.py
# This module provides the accounting_friendly_admin_index function
# The admin.py will check if user is accountant and call this function

