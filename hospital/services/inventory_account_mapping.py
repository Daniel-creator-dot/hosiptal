"""
Primecare chart-of-accounts mapping for perpetual inventory GL posting.
"""
from django.conf import settings

from hospital.services.service_account_mapping import TRADE_PAYABLES_CODE

INVENTORY_ASSET_CODE = '1400'
ACCOUNTS_PAYABLE_CODE = TRADE_PAYABLES_CODE
CLOSING_INVENTORY_CODE = '5120'

INVENTORY_CATEGORY_MAP = {
    'pharmacy': {
        'asset': INVENTORY_ASSET_CODE,
        'cogs': '5110',
        'ap': ACCOUNTS_PAYABLE_CODE,
        'label': 'Pharmacy / Drugs',
    },
    'lab': {
        'asset': INVENTORY_ASSET_CODE,
        'cogs': '5111',
        'ap': ACCOUNTS_PAYABLE_CODE,
        'label': 'Laboratory Reagents',
    },
    'dental': {
        'asset': INVENTORY_ASSET_CODE,
        'cogs': '5112',
        'ap': ACCOUNTS_PAYABLE_CODE,
        'label': 'Dental',
    },
    'radiology': {
        'asset': INVENTORY_ASSET_CODE,
        'cogs': '5113',
        'ap': ACCOUNTS_PAYABLE_CODE,
        'label': 'Radiology',
    },
    'consumables': {
        'asset': INVENTORY_ASSET_CODE,
        'cogs': '5114',
        'ap': ACCOUNTS_PAYABLE_CODE,
        'label': 'Consumables',
    },
    'physiotherapy': {
        'asset': INVENTORY_ASSET_CODE,
        'cogs': '5115',
        'ap': ACCOUNTS_PAYABLE_CODE,
        'label': 'Physiotherapy',
    },
    'other': {
        'asset': INVENTORY_ASSET_CODE,
        'cogs': '5116',
        'ap': ACCOUNTS_PAYABLE_CODE,
        'label': 'Other inventory',
    },
}

COGS_ACCOUNT_CODES = tuple(
    sorted({cfg['cogs'] for cfg in INVENTORY_CATEGORY_MAP.values()})
)

ACCOUNT_NAMES = {
    INVENTORY_ASSET_CODE: ('Inventories (Closing Stock)', 'asset'),
    ACCOUNTS_PAYABLE_CODE: ('Accounts Payable', 'liability'),
    CLOSING_INVENTORY_CODE: ('Closing Inventory', 'expense'),
    '5110': ('Purchases - Drugs', 'expense'),
    '5111': ('Purchases - Laboratory Reagents', 'expense'),
    '5112': ('Purchases - Dental', 'expense'),
    '5113': ('Purchases - Radiology', 'expense'),
    '5114': ('Purchases - Consumables', 'expense'),
    '5115': ('Purchases - Physiotherapy', 'expense'),
    '5116': ('Purchases - Others', 'expense'),
}


def inventory_gl_enabled():
    return getattr(settings, 'INVENTORY_GL_ENABLED', True)


def get_inventory_accounts(category_key='pharmacy'):
    key = (category_key or 'pharmacy').lower().strip()
    return INVENTORY_CATEGORY_MAP.get(key, INVENTORY_CATEGORY_MAP['other'])


def resolve_inventory_category_from_item(inventory_item):
    """Map procurement InventoryItem to an inventory GL category key."""
    if not inventory_item:
        return 'other'
    if getattr(inventory_item, 'drug_id', None):
        return 'pharmacy'
    category = getattr(inventory_item, 'category', None)
    if category and getattr(category, 'is_for_pharmacy', False):
        return 'pharmacy'
    if category:
        name = (getattr(category, 'name', '') or '').lower()
        code = (getattr(category, 'code', '') or '').lower()
        blob = f'{name} {code}'
        if 'lab' in blob or 'reagent' in blob:
            return 'lab'
        if 'dental' in blob:
            return 'dental'
        if 'radiolog' in blob or 'imaging' in blob:
            return 'radiology'
        if 'physio' in blob:
            return 'physiotherapy'
        if 'consum' in blob or 'suppl' in blob:
            return 'consumables'
    return 'other'
