"""
Primecare chart-of-accounts mapping for perpetual inventory GL posting.
"""
import json

from django.conf import settings

from hospital.services.service_account_mapping import TRADE_PAYABLES_CODE

INVENTORY_ASSET_CODE = '1400'
ACCOUNTS_PAYABLE_CODE = TRADE_PAYABLES_CODE
CLOSING_INVENTORY_CODE = '5120'
MEDICAL_SUPPLIES_PURCHASES_CODE = '5600'

# Categories that post receipts to Closing Inventory (5120) and issues to Purchases 5600 / Cr 5120
CLOSING_INVENTORY_CATEGORIES = frozenset({'lab', 'consumables'})

INVENTORY_CATEGORY_MAP = {
    'pharmacy': {
        'asset': INVENTORY_ASSET_CODE,
        'receipt_debit': INVENTORY_ASSET_CODE,
        'receipt_credit': ACCOUNTS_PAYABLE_CODE,
        'cogs': '5110',
        'cogs_credit': INVENTORY_ASSET_CODE,
        'ap': ACCOUNTS_PAYABLE_CODE,
        'label': 'Pharmacy / Drugs',
    },
    'lab': {
        'asset': CLOSING_INVENTORY_CODE,
        'receipt_debit': CLOSING_INVENTORY_CODE,
        'receipt_credit': ACCOUNTS_PAYABLE_CODE,
        'cogs': MEDICAL_SUPPLIES_PURCHASES_CODE,
        'cogs_credit': CLOSING_INVENTORY_CODE,
        'ap': ACCOUNTS_PAYABLE_CODE,
        'label': 'Laboratory Reagents',
    },
    'dental': {
        'asset': INVENTORY_ASSET_CODE,
        'receipt_debit': INVENTORY_ASSET_CODE,
        'receipt_credit': ACCOUNTS_PAYABLE_CODE,
        'cogs': '5112',
        'cogs_credit': INVENTORY_ASSET_CODE,
        'ap': ACCOUNTS_PAYABLE_CODE,
        'label': 'Dental',
    },
    'radiology': {
        'asset': INVENTORY_ASSET_CODE,
        'receipt_debit': INVENTORY_ASSET_CODE,
        'receipt_credit': ACCOUNTS_PAYABLE_CODE,
        'cogs': '5113',
        'cogs_credit': INVENTORY_ASSET_CODE,
        'ap': ACCOUNTS_PAYABLE_CODE,
        'label': 'Radiology',
    },
    'consumables': {
        'asset': CLOSING_INVENTORY_CODE,
        'receipt_debit': CLOSING_INVENTORY_CODE,
        'receipt_credit': ACCOUNTS_PAYABLE_CODE,
        'cogs': MEDICAL_SUPPLIES_PURCHASES_CODE,
        'cogs_credit': CLOSING_INVENTORY_CODE,
        'ap': ACCOUNTS_PAYABLE_CODE,
        'label': 'Medical Supplies and Consumables',
    },
    'physiotherapy': {
        'asset': INVENTORY_ASSET_CODE,
        'receipt_debit': INVENTORY_ASSET_CODE,
        'receipt_credit': ACCOUNTS_PAYABLE_CODE,
        'cogs': '5115',
        'cogs_credit': INVENTORY_ASSET_CODE,
        'ap': ACCOUNTS_PAYABLE_CODE,
        'label': 'Physiotherapy',
    },
    'other': {
        'asset': INVENTORY_ASSET_CODE,
        'receipt_debit': INVENTORY_ASSET_CODE,
        'receipt_credit': ACCOUNTS_PAYABLE_CODE,
        'cogs': '5116',
        'cogs_credit': INVENTORY_ASSET_CODE,
        'ap': ACCOUNTS_PAYABLE_CODE,
        'label': 'Other inventory',
    },
}

COGS_ACCOUNT_CODES = tuple(
    sorted({cfg['cogs'] for cfg in INVENTORY_CATEGORY_MAP.values()})
)

ACCOUNT_NAMES = {
    INVENTORY_ASSET_CODE: ('Inventories (Closing Stock)', 'asset'),
    ACCOUNTS_PAYABLE_CODE: ('Trade Payables', 'liability'),
    CLOSING_INVENTORY_CODE: ('Closing Inventory', 'expense'),
    MEDICAL_SUPPLIES_PURCHASES_CODE: ('Purchases - Medical Supplies and Consumables', 'expense'),
    '5110': ('Purchases - Drugs', 'expense'),
    '5111': ('Purchases - Laboratory Reagents', 'expense'),
    '5112': ('Purchases - Dental', 'expense'),
    '5113': ('Purchases - Radiology', 'expense'),
    '5114': ('Purchases - Consumables', 'expense'),
    '5115': ('Purchases - Physiotherapy', 'expense'),
    '5116': ('Purchases - Others', 'expense'),
}


def uses_closing_inventory_posting(category_key):
    """True when receipts/issues use 5120 Closing Inventory and 5600 purchases."""
    key = (category_key or '').lower().strip()
    return key in CLOSING_INVENTORY_CATEGORIES


def inventory_gl_enabled():
    return getattr(settings, 'INVENTORY_GL_ENABLED', True)


def get_inventory_accounts(category_key='pharmacy'):
    key = (category_key or 'pharmacy').lower().strip()
    return INVENTORY_CATEGORY_MAP.get(key, INVENTORY_CATEGORY_MAP['other'])


def _category_key_from_inventory_category(category):
    if not category:
        return None
    if getattr(category, 'is_for_pharmacy', False):
        return 'pharmacy'
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
    return None


def _category_key_from_store(store, *, has_drug=False):
    if has_drug:
        return None
    if not store:
        return None
    store_type = (getattr(store, 'store_type', '') or '').lower()
    if store_type == 'lab':
        return 'lab'
    if store_type in ('main', 'general', 'ward', 'ot'):
        return 'consumables'
    return None


def procurement_item_is_lab_reagent(proc_item):
    """True when procurement line metadata flags a lab reagent."""
    try:
        if proc_item and proc_item.specifications:
            metadata = json.loads(proc_item.specifications)
            return bool(metadata.get('is_lab_reagent', False))
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
        pass
    return False


def get_default_inventory_category(*, store=None, drug=None, is_lab_reagent=False):
    """Return InventoryCategory FK for new items based on store/item type."""
    from hospital.models_procurement import InventoryCategory

    if drug or (store and getattr(store, 'store_type', None) == 'pharmacy'):
        return InventoryCategory.objects.filter(code='PHARM', is_deleted=False).first()
    if is_lab_reagent or (store and getattr(store, 'store_type', None) == 'lab'):
        return InventoryCategory.objects.filter(code='LAB', is_deleted=False).first()
    return InventoryCategory.objects.filter(code='SUPPLY', is_deleted=False).first()


def ensure_inventory_item_category(inventory_item, *, store=None, drug=None, is_lab_reagent=False):
    """Assign default InventoryCategory when missing."""
    if not inventory_item or inventory_item.category_id:
        return inventory_item
    category = get_default_inventory_category(
        store=store or getattr(inventory_item, 'store', None),
        drug=drug or getattr(inventory_item, 'drug', None),
        is_lab_reagent=is_lab_reagent,
    )
    if category:
        inventory_item.category = category
        inventory_item.save(update_fields=['category', 'modified'])
    return inventory_item


def resolve_procurement_target_store(proc_request, item, staff=None):
    """Same target-store routing used by modern procurement receive."""
    from hospital.models_procurement import Store

    if item.drug or (
        proc_request.requested_by_store
        and proc_request.requested_by_store.store_type == 'pharmacy'
    ):
        target_store = Store.objects.filter(code='DRUGS', is_deleted=False).first()
        if not target_store:
            target_store = Store.objects.filter(store_type='pharmacy', is_deleted=False).first()
    elif proc_request.requested_by_store and proc_request.requested_by_store.store_type == 'lab':
        target_store = Store.objects.filter(code='LAB', is_deleted=False).first()
        if not target_store:
            target_store = Store.objects.filter(store_type='lab', is_deleted=False).first()
    else:
        target_store = Store.objects.filter(code='MAIN', is_deleted=False).first()
        if not target_store:
            target_store = Store.objects.filter(store_type='main', is_deleted=False).first()

    if not target_store and staff:
        target_store = Store.objects.create(
            name='Main Store',
            code='MAIN',
            store_type='main',
            manager=staff,
        )
    return target_store


def find_procurement_inventory_item(proc_request, item, staff=None):
    """Locate InventoryItem after receive (LAB/MAIN/DRUGS store, not only requested_by_store)."""
    from hospital.models_procurement import InventoryItem

    target_store = resolve_procurement_target_store(proc_request, item, staff=staff)
    if not target_store:
        return None

    item_code = item.item_code if item.item_code else item.item_name
    qs = InventoryItem.objects.filter(store=target_store, is_deleted=False)
    inventory_item = qs.filter(item_code=item_code).first()
    if inventory_item:
        return inventory_item
    return qs.filter(item_name__iexact=item.item_name.strip()).first()


def resolve_inventory_category_from_item(inventory_item):
    """Map procurement InventoryItem to an inventory GL category key."""
    if not inventory_item:
        return 'other'
    if getattr(inventory_item, 'drug_id', None):
        return 'pharmacy'

    category = getattr(inventory_item, 'category', None)
    key = _category_key_from_inventory_category(category)
    if key:
        return key

    store = getattr(inventory_item, 'store', None)
    store_key = _category_key_from_store(store, has_drug=bool(getattr(inventory_item, 'drug_id', None)))
    if store_key:
        return store_key

    return 'other'
