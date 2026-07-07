"""
Trial Balance builder — merges legacy GeneralLedger and AdvancedGeneralLedger
with account-type-aware balances and per-account transaction drill-down.
"""
from datetime import date
from decimal import Decimal
import logging

from django.db.models import Sum

from hospital.models_accounting import Account, GeneralLedger
from hospital.models_accounting_advanced import AdvancedGeneralLedger

logger = logging.getLogger(__name__)

ACCOUNT_TYPES = ('asset', 'liability', 'equity', 'revenue', 'expense')
DEBIT_NORMAL_TYPES = frozenset({'asset', 'expense'})


def _account_balance_from_totals(account_type, debits, credits):
    """Return signed balance using normal balance rules."""
    debits = debits or Decimal('0.00')
    credits = credits or Decimal('0.00')
    if account_type in DEBIT_NORMAL_TYPES:
        return debits - credits
    return credits - debits


def _tb_column_amounts(account_type, balance):
    """Map signed balance to trial-balance debit/credit columns."""
    if account_type in DEBIT_NORMAL_TYPES:
        if balance >= 0:
            return balance, Decimal('0.00')
        return Decimal('0.00'), abs(balance)
    if balance >= 0:
        return Decimal('0.00'), balance
    return abs(balance), Decimal('0.00')


def get_account_ledger_totals(account, as_of_date):
    """
    Sum debits/credits for one account from both ledgers up to as_of_date.
    Returns (debits, credits, entries_list).
    """
    gl_entries = GeneralLedger.objects.filter(
        account=account,
        transaction_date__lte=as_of_date,
        is_deleted=False,
    ).order_by('transaction_date', 'created')

    gl_debits = gl_entries.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
    gl_credits = gl_entries.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')

    adv_entries = AdvancedGeneralLedger.objects.filter(
        account=account,
        transaction_date__lte=as_of_date,
        is_voided=False,
        is_deleted=False,
    ).select_related('journal_entry').order_by('transaction_date', 'created')

    adv_debits = adv_entries.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
    adv_credits = adv_entries.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')

    debits = gl_debits + adv_debits
    credits = gl_credits + adv_credits

    all_entries = []

    for entry in gl_entries:
        all_entries.append({
            'date': entry.transaction_date,
            'entry_number': entry.entry_number or 'N/A',
            'description': entry.description or '',
            'reference_number': entry.reference_number or '',
            'reference_type': entry.reference_type or '',
            'debit': entry.debit_amount or Decimal('0.00'),
            'credit': entry.credit_amount or Decimal('0.00'),
            'source': 'GeneralLedger',
            'journal_entry_id': None,
        })

    for entry in adv_entries:
        ref_number = ''
        entry_number = 'N/A'
        journal_entry_id = None
        try:
            if entry.journal_entry_id:
                journal_entry_id = entry.journal_entry_id
                je = entry.journal_entry
                entry_number = je.entry_number or 'N/A'
                ref_number = je.reference or ''
        except Exception:
            pass

        all_entries.append({
            'date': entry.transaction_date,
            'entry_number': entry_number,
            'description': getattr(entry, 'description', '') or '',
            'reference_number': ref_number,
            'reference_type': '',
            'debit': entry.debit_amount or Decimal('0.00'),
            'credit': entry.credit_amount or Decimal('0.00'),
            'source': 'AdvancedGeneralLedger',
            'journal_entry_id': journal_entry_id,
        })

    all_entries.sort(
        key=lambda x: (x['date'] if x['date'] else date(1900, 1, 1), x['entry_number'])
    )

    return debits, credits, all_entries


def get_account_balance(account_code, as_of_date, account_type=None):
    """Balance for a single account code from both ledgers."""
    try:
        account = Account.objects.get(account_code=account_code, is_deleted=False)
    except Account.DoesNotExist:
        return Decimal('0.00')

    if account_type is None:
        account_type = account.account_type

    debits, credits, _ = get_account_ledger_totals(account, as_of_date)
    return _account_balance_from_totals(account_type, debits, credits)


def get_account_by_code(account_code):
    """Return active Account for a chart code, or None."""
    return Account.objects.filter(account_code=account_code, is_deleted=False).first()


def sum_account_balances(account_codes, as_of_date):
    """Sum signed balances for multiple account codes."""
    total = Decimal('0.00')
    for code in account_codes:
        total += get_account_balance(code, as_of_date)
    return total


def build_trial_balance(as_of_date):
    """
    Build trial balance data merging both general ledgers.

    Returns dict with accounts (annotated Account objects), totals, section subtotals,
    and balance check fields.
    """
    accounts_list = Account.objects.filter(is_active=True, is_deleted=False).order_by('account_code')

    accounts_with_balance = []
    total_debits = Decimal('0.00')
    total_credits = Decimal('0.00')
    section_totals = {t: {'debit': Decimal('0.00'), 'credit': Decimal('0.00')} for t in ACCOUNT_TYPES}

    for account in accounts_list:
        debits, credits, all_entries = get_account_ledger_totals(account, as_of_date)

        if debits == 0 and credits == 0:
            continue

        balance = _account_balance_from_totals(account.account_type, debits, credits)
        tb_debit, tb_credit = _tb_column_amounts(account.account_type, balance)

        account.balance = balance
        account.total_debits = debits
        account.total_credits = credits
        account.tb_debit = tb_debit
        account.tb_credit = tb_credit
        account.entries = all_entries
        account.entry_count = len(all_entries)
        accounts_with_balance.append(account)

        total_debits += tb_debit
        total_credits += tb_credit
        if account.account_type in section_totals:
            section_totals[account.account_type]['debit'] += tb_debit
            section_totals[account.account_type]['credit'] += tb_credit

    balance_difference = total_debits - total_credits
    is_balanced = abs(balance_difference) < Decimal('0.01')

    accounts_by_type = {t: [] for t in ACCOUNT_TYPES}
    for account in accounts_with_balance:
        if account.account_type in accounts_by_type:
            accounts_by_type[account.account_type].append(account)

    return {
        'accounts': accounts_with_balance,
        'accounts_by_type': accounts_by_type,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'balance_difference': balance_difference,
        'is_balanced': is_balanced,
        'section_totals': section_totals,
        'as_of_date': as_of_date,
    }
