"""
Chart of Accounts display grouping — balance-sheet order with sub-sections.
"""
from decimal import Decimal

from hospital.models_accounting import Account

UNCLASSIFIED_KEY = 'unclassified'

SECTION_ORDER = [
    ('equity', 'Equity', None),
    ('assets', 'Assets', [
        ('non_current_asset', 'Non-Current Assets'),
        ('current_asset', 'Current Assets'),
        (UNCLASSIFIED_KEY, 'Unclassified Assets'),
    ]),
    ('liabilities', 'Liabilities', [
        ('non_current_liability', 'Non-Current Liabilities'),
        ('current_liability', 'Current Liabilities'),
        (UNCLASSIFIED_KEY, 'Unclassified Liabilities'),
    ]),
    ('revenue', 'Revenue', None),
    ('expenses', 'Expenses', [
        ('direct_expense', 'Direct Expenses'),
        ('indirect_expense', 'Indirect Expenses'),
        (UNCLASSIFIED_KEY, 'Unclassified Expenses'),
    ]),
]

TYPE_TO_SECTION = {
    'equity': 'equity',
    'asset': 'assets',
    'liability': 'liabilities',
    'revenue': 'revenue',
    'expense': 'expenses',
}


def _numeric_code(account_code):
    digits = ''.join(c for c in (account_code or '') if c.isdigit())
    if not digits:
        return None
    try:
        return int(digits[:4])
    except ValueError:
        return None


def infer_account_subgroup_from_code_and_name(account):
    """Infer subgroup when account_subgroup is blank."""
    code = _numeric_code(account.account_code)
    name = (account.account_name or '').lower()
    acc_type = account.account_type

    if acc_type == 'asset':
        if code is not None:
            if 1800 <= code <= 1999:
                return 'non_current_asset'
            if 1000 <= code <= 1799:
                return 'current_asset'
        if any(k in name for k in ('depreciation', 'ppe', 'property', 'plant', 'equipment', 'land', 'building', 'intangible', 'long-term investment', 'deferred tax asset')):
            return 'non_current_asset'
        if any(k in name for k in ('cash', 'bank', 'receivable', 'inventory', 'prepayment', 'advance', 'undeposited')):
            return 'current_asset'
        return UNCLASSIFIED_KEY

    if acc_type == 'liability':
        if code is not None:
            if 2500 <= code <= 2999:
                return 'non_current_liability'
            if 2000 <= code <= 2499:
                return 'current_liability'
        if any(k in name for k in ('long-term', 'long term', 'deferred tax liab')):
            return 'non_current_liability'
        return UNCLASSIFIED_KEY

    if acc_type == 'expense':
        if code is not None:
            if 5100 <= code <= 5199:
                return 'direct_expense'
            if 5200 <= code <= 5999:
                return 'indirect_expense'
        if any(k in name for k in ('purchase', 'inventory', 'cost of sales', 'cogs', 'opening inventory', 'closing inventory')):
            return 'direct_expense'
        return UNCLASSIFIED_KEY

    return None


def resolve_account_subgroup(account):
    """Return subgroup key for grouping; uses stored field first, then inference."""
    if account.account_subgroup:
        return account.account_subgroup
    return infer_account_subgroup_from_code_and_name(account)


def subgroup_choices_for_type(account_type):
    """Valid subgroup choices for create/edit forms."""
    mapping = {
        'asset': [c for c in Account.ACCOUNT_SUBGROUPS if c[0].endswith('_asset')],
        'liability': [c for c in Account.ACCOUNT_SUBGROUPS if c[0].endswith('_liability')],
        'expense': [c for c in Account.ACCOUNT_SUBGROUPS if c[0].endswith('_expense')],
    }
    return mapping.get(account_type, [])


def build_chart_of_accounts_sections(account_items):
    """
    Build ordered chart sections from account_items list of dicts:
    {'account', 'balance', 'total_debits', 'total_credits', 'can_delete', 'delete_block_reason'}
    """
    buckets = {
        'equity': [],
        'assets': {
            'non_current_asset': [],
            'current_asset': [],
            UNCLASSIFIED_KEY: [],
        },
        'liabilities': {
            'non_current_liability': [],
            'current_liability': [],
            UNCLASSIFIED_KEY: [],
        },
        'revenue': [],
        'expenses': {
            'direct_expense': [],
            'indirect_expense': [],
            UNCLASSIFIED_KEY: [],
        },
    }

    for item in account_items:
        account = item['account']
        section_key = TYPE_TO_SECTION.get(account.account_type)
        if not section_key:
            continue

        if section_key in ('equity', 'revenue'):
            buckets[section_key].append(item)
            continue

        subgroup = resolve_account_subgroup(account) or UNCLASSIFIED_KEY
        if subgroup not in buckets[section_key]:
            subgroup = UNCLASSIFIED_KEY
        buckets[section_key][subgroup].append(item)

    def _subsection_total(items):
        return sum((i['balance'] for i in items), Decimal('0.00'))

    sections = []
    for section_key, section_title, subsections in SECTION_ORDER:
        if subsections is None:
            items = buckets[section_key]
            if not items:
                continue
            sections.append({
                'key': section_key,
                'title': section_title,
                'subsections': None,
                'items': sorted(items, key=lambda x: x['account'].account_code),
                'total': _subsection_total(items),
            })
            continue

        built_subsections = []
        section_total = Decimal('0.00')
        for sub_key, sub_title in subsections:
            items = buckets[section_key].get(sub_key, [])
            if not items:
                continue
            sub_total = _subsection_total(items)
            section_total += sub_total
            built_subsections.append({
                'key': sub_key,
                'title': sub_title,
                'items': sorted(items, key=lambda x: x['account'].account_code),
                'total': sub_total,
            })

        if not built_subsections:
            continue

        sections.append({
            'key': section_key,
            'title': section_title,
            'subsections': built_subsections,
            'items': None,
            'total': section_total,
        })

    return sections
