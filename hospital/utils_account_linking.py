"""
Account Linking and Synchronization Utilities
Links all accounting accounts to the right places and syncs them
"""
from django.db import transaction
from django.db.models import Q
from .models_accounting import Account
from .models_accounting_advanced import (
    BankAccount, Cashbook, BankReconciliation, InsuranceReceivable,
    ProcurementPurchase, AccountingPayroll, DoctorCommission, 
    RegistrationFee, CashSale, AccountingCorporateAccount,
    WithholdingReceivable, Deposit, InitialRevaluation
)


@transaction.atomic
def sync_all_accounts():
    """
    Sync and link all accounts to ensure proper relationships
    Returns dict with sync results
    """
    results = {
        'accounts_checked': 0,
        'accounts_linked': 0,
        'bank_accounts_synced': 0,
        'errors': []
    }
    
    try:
        # 1. Ensure all BankAccounts have corresponding Account records
        bank_accounts = BankAccount.objects.filter(is_active=True)
        for bank_acc in bank_accounts:
            results['bank_accounts_synced'] += 1
            # Try to find or create corresponding Account
            account, created = Account.objects.get_or_create(
                account_code=f"BANK-{bank_acc.account_number}",
                defaults={
                    'account_name': f"{bank_acc.bank_name} - {bank_acc.account_name}",
                    'account_type': 'asset',
                    'description': f"Bank account: {bank_acc.account_name}",
                    'is_active': True,
                }
            )
            if created:
                results['accounts_linked'] += 1
        
        # 2. Link Cashbook entries to accounts if not linked
        cashbook_entries = Cashbook.objects.filter(
            status='pending',
            revenue_account__isnull=True,
            expense_account__isnull=True
        )
        for entry in cashbook_entries:
            if entry.entry_type == 'receipt':
                # Try to find revenue account
                revenue_acc = Account.objects.filter(
                    account_type='revenue',
                    is_active=True
                ).first()
                if revenue_acc:
                    entry.revenue_account = revenue_acc
                    entry.save(update_fields=['revenue_account'])
                    results['accounts_linked'] += 1
            else:
                # Try to find expense account
                expense_acc = Account.objects.filter(
                    account_type='expense',
                    is_active=True
                ).first()
                if expense_acc:
                    entry.expense_account = expense_acc
                    entry.save(update_fields=['expense_account'])
                    results['accounts_linked'] += 1
        
        # 3. Ensure default accounts exist
        default_accounts = [
            {'code': '4000', 'name': 'Service Revenue', 'type': 'revenue'},
            {'code': '4010', 'name': 'Consultation Revenue', 'type': 'revenue'},
            {'code': '4020', 'name': 'Surgery Revenue', 'type': 'revenue'},
            {'code': '4030', 'name': 'Pharmacy Revenue', 'type': 'revenue'},
            {'code': '4040', 'name': 'Lab Revenue', 'type': 'revenue'},
            {'code': '5000', 'name': 'Operating Expenses', 'type': 'expense'},
            {'code': '5010', 'name': 'Salaries & Wages', 'type': 'expense'},
            {'code': '5020', 'name': 'Supplies Expense', 'type': 'expense'},
            {'code': '5030', 'name': 'Utility Expenses', 'type': 'expense'},
            {'code': '2000', 'name': 'Accounts Receivable', 'type': 'asset'},
            {'code': '2010', 'name': 'Insurance Receivable', 'type': 'asset'},
            {'code': '2020', 'name': 'Corporate Receivable', 'type': 'asset'},
            {'code': '3000', 'name': 'Accounts Payable', 'type': 'liability'},
            {'code': '3010', 'name': 'Accrued Expenses', 'type': 'liability'},
            {'code': '1000', 'name': 'Cash', 'type': 'asset'},
            {'code': '1010', 'name': 'Bank Account', 'type': 'asset'},
        ]
        
        for acc_data in default_accounts:
            account, created = Account.objects.get_or_create(
                account_code=acc_data['code'],
                defaults={
                    'account_name': acc_data['name'],
                    'account_type': acc_data['type'],
                    'is_active': True,
                }
            )
            results['accounts_checked'] += 1
            if created:
                results['accounts_linked'] += 1
        
        # 4. Link Insurance Receivables to accounts
        insurance_receivables = InsuranceReceivable.objects.filter(
            receivable_account__isnull=True
        )
        ar_account = Account.objects.filter(
            account_code='2010'
        ).first()
        if ar_account:
            for receivable in insurance_receivables:
                receivable.receivable_account = ar_account
                receivable.save(update_fields=['receivable_account'])
                results['accounts_linked'] += 1
        
        # 5. Link Corporate Accounts to accounts (if field exists)
        try:
            corporate_accounts = AccountingCorporateAccount.objects.filter(
                account__isnull=True
            )
            corp_ar_account = Account.objects.filter(
                account_code='2020'
            ).first()
            if corp_ar_account:
                for corp_acc in corporate_accounts:
                    if hasattr(corp_acc, 'account'):
                        corp_acc.account = corp_ar_account
                        corp_acc.save(update_fields=['account'])
                        results['accounts_linked'] += 1
        except Exception:
            pass  # Field might not exist
        
        # 6. Link Procurement Purchases to accounts (if field exists)
        try:
            procurement_purchases = ProcurementPurchase.objects.filter(
                account__isnull=True,
                purchase_type='credit'
            )
            ap_account = Account.objects.filter(
                account_code='3000'
            ).first()
            if ap_account:
                for purchase in procurement_purchases:
                    if hasattr(purchase, 'account'):
                        purchase.account = ap_account
                        purchase.save(update_fields=['account'])
                        results['accounts_linked'] += 1
        except Exception:
            pass  # Field might not exist
        
    except Exception as e:
        results['errors'].append(str(e))
    
    return results


def get_default_revenue_account():
    """Get default revenue account"""
    return Account.objects.filter(
        account_type='revenue',
        is_active=True
    ).first()


def get_default_expense_account():
    """Get default expense account"""
    return Account.objects.filter(
        account_type='expense',
        is_active=True
    ).first()


def get_default_ar_account():
    """Get default accounts receivable account"""
    return Account.objects.filter(
        Q(account_code='2000') | Q(account_code='2010'),
        is_active=True
    ).first()


def get_default_ap_account():
    """Get default accounts payable account"""
    return Account.objects.filter(
        account_code='3000',
        is_active=True
    ).first()


def get_default_cash_account():
    """Get default cash account"""
    return Account.objects.filter(
        Q(account_code='1000') | Q(account_type='asset', account_name__icontains='cash'),
        is_active=True
    ).first()


def get_default_bank_account():
    """Get default bank account"""
    return Account.objects.filter(
        Q(account_code='1010') | Q(account_type='asset', account_name__icontains='bank'),
        is_active=True
    ).first()


def link_cashbook_to_accounts():
    """Link all cashbook entries to appropriate accounts"""
    results = {
        'linked': 0,
        'errors': []
    }
    
    try:
        revenue_acc = get_default_revenue_account()
        expense_acc = get_default_expense_account()
        
        # Link receipts to revenue
        receipts = Cashbook.objects.filter(
            entry_type='receipt',
            revenue_account__isnull=True,
            status='pending'
        )
        if revenue_acc:
            for receipt in receipts:
                receipt.revenue_account = revenue_acc
                receipt.save(update_fields=['revenue_account'])
                results['linked'] += 1
        
        # Link payments to expense
        payments = Cashbook.objects.filter(
            entry_type='payment',
            expense_account__isnull=True,
            status='pending'
        )
        if expense_acc:
            for payment in payments:
                payment.expense_account = expense_acc
                payment.save(update_fields=['expense_account'])
                results['linked'] += 1
                
    except Exception as e:
        results['errors'].append(str(e))
    
    return results

