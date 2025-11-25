"""
Payment Voucher and Cheque Account Setup Utilities
Creates default accounts for PV and cheque operations if they don't exist
"""

from django.db import transaction
from .models_accounting import Account
from .models_accounting_advanced import BankAccount


@transaction.atomic
def setup_pv_cheque_accounts():
    """
    Setup default accounts for Payment Vouchers and Cheque operations
    Returns dict with created accounts and status
    """
    from decimal import Decimal
    
    accounts_created = []
    accounts_existing = []
    
    # Default Expense Accounts for PVs
    expense_accounts = [
        {
            'code': '5010',
            'name': 'Operating Expenses',
            'type': 'expense',
            'description': 'General operating expenses paid via payment vouchers'
        },
        {
            'code': '5020',
            'name': 'Supplier Payments',
            'type': 'expense',
            'description': 'Payments to suppliers and vendors'
        },
        {
            'code': '5030',
            'name': 'Utility Expenses',
            'type': 'expense',
            'description': 'Utility payments (electricity, water, etc.)'
        },
        {
            'code': '5040',
            'name': 'Salary Expenses',
            'type': 'expense',
            'description': 'Salary and wage payments'
        },
        {
            'code': '5050',
            'name': 'Tax Payments',
            'type': 'expense',
            'description': 'Tax payments and remittances'
        },
    ]
    
    # Default Payment Accounts (Assets - Cash/Bank)
    payment_accounts = [
        {
            'code': '1010',
            'name': 'Cash Account',
            'type': 'asset',
            'description': 'Main cash account for payments'
        },
        {
            'code': '1020',
            'name': 'Main Bank Account',
            'type': 'asset',
            'description': 'Primary bank account for cheque payments'
        },
        {
            'code': '1030',
            'name': 'Petty Cash',
            'type': 'asset',
            'description': 'Petty cash account for small payments'
        },
    ]
    
    # Create Expense Accounts
    for acc_data in expense_accounts:
        account, created = Account.objects.get_or_create(
            account_code=acc_data['code'],
            defaults={
                'account_name': acc_data['name'],
                'account_type': acc_data['type'],
                'description': acc_data['description'],
                'is_active': True,
            }
        )
        if created:
            accounts_created.append(account)
        else:
            accounts_existing.append(account)
    
    # Create Payment Accounts
    for acc_data in payment_accounts:
        account, created = Account.objects.get_or_create(
            account_code=acc_data['code'],
            defaults={
                'account_name': acc_data['name'],
                'account_type': acc_data['type'],
                'description': acc_data['description'],
                'is_active': True,
            }
        )
        if created:
            accounts_created.append(account)
        else:
            accounts_existing.append(account)
    
    return {
        'created': accounts_created,
        'existing': accounts_existing,
        'total_created': len(accounts_created),
        'total_existing': len(accounts_existing),
    }


def get_pv_expense_accounts():
    """Get expense accounts suitable for payment vouchers"""
    return Account.objects.filter(
        account_type='expense',
        is_active=True
    ).order_by('account_code')


def get_pv_payment_accounts():
    """Get payment accounts (cash/bank) suitable for payment vouchers"""
    return Account.objects.filter(
        account_type__in=['asset', 'current_asset'],
        is_active=True
    ).order_by('account_code')


def ensure_bank_account_exists(account_name, account_number, bank_name=''):
    """
    Ensure a bank account exists, create if it doesn't
    Returns the BankAccount instance
    """
    from .models_accounting_advanced import BankAccount
    
    bank_account, created = BankAccount.objects.get_or_create(
        account_number=account_number,
        defaults={
            'account_name': account_name,
            'bank_name': bank_name,
            'is_active': True,
        }
    )
    
    return bank_account, created

