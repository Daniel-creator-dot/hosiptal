"""
Inventory GL integration — operational stock valuation, receipt/COGS posting,
and closing stock adjustment.
Posts Dr 1400 Inventories / Cr 5120 Closing Inventory (or reverse) to align GL with physical stock.
Perpetual inventory: receipt Dr 1400 / Cr AP; dispense Dr 511x / Cr 1400.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, F, DecimalField, Count, Q
from django.utils import timezone

from hospital.models import PharmacyStock
from hospital.models_accounting import Account
from hospital.models_accounting_advanced import (
    AdvancedJournalEntry,
    AdvancedJournalEntryLine,
    Journal,
)
from hospital.models_procurement import InventoryItem
from hospital.services.inventory_account_mapping import (
    ACCOUNT_NAMES,
    CLOSING_INVENTORY_CODE,
    COGS_ACCOUNT_CODES,
    INVENTORY_ASSET_CODE,
    get_inventory_accounts,
    inventory_gl_enabled,
)
from hospital.services.trial_balance_service import get_account_balance

logger = logging.getLogger(__name__)

CLOSING_STOCK_REF_PREFIX = 'CLOSE-STOCK-'
RECEIPT_REF_PREFIX = 'STOCK-RCV-'
COGS_REF_PREFIX = 'COGS-'
ADJUST_REF_PREFIX = 'STOCK-ADJ-'


def _gl_reference_lock(reference: str) -> bool:
    """Cross-process lock for GL posting idempotency (requires shared cache in production)."""
    from django.core.cache import cache

    return cache.add(f'hms:gl:ref:{reference}', '1', timeout=120)


def _gl_reference_unlock(reference: str) -> None:
    from django.core.cache import cache

    cache.delete(f'hms:gl:ref:{reference}')


def _ensure_account(code, name=None, account_type=None):
    defaults_name, defaults_type = ACCOUNT_NAMES.get(code, (name or code, account_type or 'expense'))
    account, _ = Account.objects.get_or_create(
        account_code=code,
        defaults={
            'account_name': name or defaults_name,
            'account_type': account_type or defaults_type,
            'is_active': True,
        },
    )
    return account


def _get_journal():
    journal, _ = Journal.objects.get_or_create(
        code='GJ',
        defaults={'name': 'General Journal', 'journal_type': 'general'},
    )
    return journal


def _existing_posted_entry(reference):
    return AdvancedJournalEntry.objects.filter(
        reference=reference,
        status='posted',
        is_deleted=False,
    ).first()


def _post_balanced_journal(
    *,
    reference,
    description,
    debit_account,
    credit_account,
    amount,
    debit_desc,
    credit_desc,
    user=None,
    entry_date=None,
):
    amount = Decimal(str(amount)).quantize(Decimal('0.01'))
    if amount <= 0:
        return None

    existing = _existing_posted_entry(reference)
    if existing:
        return existing

    entry_date = entry_date or timezone.now().date()
    journal = _get_journal()

    je = AdvancedJournalEntry.objects.create(
        journal=journal,
        entry_date=entry_date,
        description=description,
        reference=reference,
        created_by=user,
        status='draft',
        total_debit=amount,
        total_credit=amount,
    )
    AdvancedJournalEntryLine.objects.create(
        journal_entry=je,
        line_number=1,
        account=debit_account,
        description=debit_desc,
        debit_amount=amount,
        credit_amount=Decimal('0.00'),
    )
    AdvancedJournalEntryLine.objects.create(
        journal_entry=je,
        line_number=2,
        account=credit_account,
        description=credit_desc,
        debit_amount=Decimal('0.00'),
        credit_amount=amount,
    )
    je.post(user)
    return je


def post_inventory_receipt_gl(
    *,
    category_key='pharmacy',
    amount,
    reference,
    description,
    user=None,
    entry_date=None,
):
    """
    Post stock receipt: Dr 1400 Inventories / Cr 2100 Accounts Payable.
    Idempotent by reference.
    """
    if not inventory_gl_enabled():
        return {'success': True, 'posted': False, 'message': 'Inventory GL disabled'}

    amount = Decimal(str(amount or 0)).quantize(Decimal('0.01'))
    if amount <= 0:
        return {'success': True, 'posted': False, 'message': 'Zero amount — skipped'}

    accounts = get_inventory_accounts(category_key)
    asset = _ensure_account(accounts['asset'])
    ap = _ensure_account(accounts['ap'])

    existing = _existing_posted_entry(reference)
    if existing:
        return {
            'success': True,
            'posted': False,
            'already_posted': True,
            'journal_entry': existing,
            'message': f'Receipt already posted ({reference})',
        }

    if not _gl_reference_lock(reference):
        for _ in range(30):
            import time
            time.sleep(0.05)
            existing = _existing_posted_entry(reference)
            if existing:
                return {
                    'success': True,
                    'posted': False,
                    'already_posted': True,
                    'journal_entry': existing,
                    'message': f'Receipt already posted ({reference})',
                }
        return {'success': False, 'posted': False, 'message': f'GL posting busy ({reference})'}

    try:
        with transaction.atomic():
            existing = _existing_posted_entry(reference)
            if existing:
                return {
                    'success': True,
                    'posted': False,
                    'already_posted': True,
                    'journal_entry': existing,
                    'message': f'Receipt already posted ({reference})',
                }
            je = _post_balanced_journal(
                reference=reference,
                description=description,
                debit_account=asset,
                credit_account=ap,
                amount=amount,
                debit_desc=f'Inventory receipt — {accounts["label"]}',
                credit_desc=f'AP — inventory receipt ({accounts["label"]})',
                user=user,
                entry_date=entry_date,
            )
    finally:
        _gl_reference_unlock(reference)

    return {
        'success': True,
        'posted': True,
        'journal_entry': je,
        'message': f'Posted inventory receipt GHS {amount:.2f} ({reference})',
    }


def post_inventory_cogs_gl(
    *,
    category_key='pharmacy',
    amount,
    reference,
    description,
    user=None,
    entry_date=None,
    deduction_log=None,
    reagent_transaction=None,
):
    """
    Post cost of goods issued: Dr 511x / Cr 1400 Inventories.
    Idempotent by reference.
    """
    if not inventory_gl_enabled():
        return {'success': True, 'posted': False, 'message': 'Inventory GL disabled'}

    amount = Decimal(str(amount or 0)).quantize(Decimal('0.01'))
    if amount <= 0:
        return {'success': True, 'posted': False, 'message': 'Zero COGS — skipped'}

    accounts = get_inventory_accounts(category_key)
    cogs = _ensure_account(accounts['cogs'])
    asset = _ensure_account(accounts['asset'])

    existing = _existing_posted_entry(reference)
    if existing:
        return {
            'success': True,
            'posted': False,
            'already_posted': True,
            'journal_entry': existing,
            'message': f'COGS already posted ({reference})',
        }

    if not _gl_reference_lock(reference):
        for _ in range(30):
            import time
            time.sleep(0.05)
            existing = _existing_posted_entry(reference)
            if existing:
                return {
                    'success': True,
                    'posted': False,
                    'already_posted': True,
                    'journal_entry': existing,
                    'message': f'COGS already posted ({reference})',
                }
        return {'success': False, 'posted': False, 'message': f'GL posting busy ({reference})'}

    try:
        with transaction.atomic():
            existing = _existing_posted_entry(reference)
            if existing:
                return {
                    'success': True,
                    'posted': False,
                    'already_posted': True,
                    'journal_entry': existing,
                    'message': f'COGS already posted ({reference})',
                }
            je = _post_balanced_journal(
                reference=reference,
                description=description,
                debit_account=cogs,
                credit_account=asset,
                amount=amount,
                debit_desc=f'COGS — {accounts["label"]}',
                credit_desc=f'Inventory issued — {accounts["label"]}',
                user=user,
                entry_date=entry_date,
            )
            if deduction_log is not None and je:
                deduction_log.gl_journal_entry = je
                deduction_log.cogs_posted_at = timezone.now()
                deduction_log.save(update_fields=['gl_journal_entry', 'cogs_posted_at', 'modified'])
            if reagent_transaction is not None and je:
                reagent_transaction.gl_journal_entry = je
                reagent_transaction.cogs_posted_at = timezone.now()
                reagent_transaction.cogs_amount = amount
                reagent_transaction.save(
                    update_fields=['gl_journal_entry', 'cogs_posted_at', 'cogs_amount', 'modified']
                )
    finally:
        _gl_reference_unlock(reference)

    return {
        'success': True,
        'posted': True,
        'journal_entry': je,
        'message': f'Posted COGS GHS {amount:.2f} ({reference})',
    }


def post_pharmacy_stock_adjustment_gl(stock, old_qty, old_unit_cost, new_qty, new_unit_cost, user=None):
    """Post GL adjustment when pharmacy stock quantity or unit cost changes on edit."""
    from decimal import Decimal as D

    old_val = (D(int(old_qty or 0)) * D(str(old_unit_cost or 0))).quantize(D('0.01'))
    new_val = (D(int(new_qty or 0)) * D(str(new_unit_cost or 0))).quantize(D('0.01'))
    delta = (new_val - old_val).quantize(D('0.01'))
    if abs(delta) <= D('0.01'):
        return {'success': True, 'posted': False, 'message': 'No inventory value change'}

    drug_name = getattr(getattr(stock, 'drug', None), 'name', '') or 'Drug'
    batch = getattr(stock, 'batch_number', '') or ''
    ts = timezone.now().strftime('%Y%m%d%H%M%S')
    reference = f'{ADJUST_REF_PREFIX}{stock.pk}-{ts}'

    if delta > 0:
        return post_inventory_receipt_gl(
            category_key='pharmacy',
            amount=delta,
            reference=reference,
            description=(
                f'Pharmacy stock adjustment (increase): {drug_name} batch {batch} '
                f'qty {old_qty}->{new_qty}'
            ),
            user=user,
        )

    accounts = get_inventory_accounts('pharmacy')
    cogs = _ensure_account(accounts['cogs'])
    asset = _ensure_account(accounts['asset'])
    amount = abs(delta)
    if not _gl_reference_lock(reference):
        return {'success': False, 'posted': False, 'message': f'GL posting busy ({reference})'}
    try:
        with transaction.atomic():
            je = _post_balanced_journal(
                reference=reference,
                description=(
                    f'Pharmacy stock adjustment (decrease): {drug_name} batch {batch} '
                    f'qty {old_qty}->{new_qty}'
                ),
                debit_account=cogs,
                credit_account=asset,
                amount=amount,
                debit_desc='Inventory adjustment — decrease',
                credit_desc='Reduce inventory (1400)',
                user=user,
            )
    finally:
        _gl_reference_unlock(reference)
    return {
        'success': True,
        'posted': True,
        'journal_entry': je,
        'message': f'Posted inventory decrease adjustment GHS {amount:.2f}',
    }


def post_pharmacy_stock_receipt_gl(stock, quantity_added, unit_cost, user=None):
    """Convenience wrapper for PharmacyStock batch receipt."""
    from decimal import Decimal as D

    qty = int(quantity_added or 0)
    unit = D(str(unit_cost or 0))
    total = (D(qty) * unit).quantize(D('0.01'))
    drug_name = getattr(getattr(stock, 'drug', None), 'name', '') or 'Drug'
    batch = getattr(stock, 'batch_number', '') or ''
    return post_inventory_receipt_gl(
        category_key='pharmacy',
        amount=total,
        reference=f'{RECEIPT_REF_PREFIX}{stock.pk}',
        description=f'Pharmacy stock receipt: {drug_name} batch {batch} qty {qty}',
        user=user,
        entry_date=getattr(stock, 'created', timezone.now()).date()
        if getattr(stock, 'created', None)
        else timezone.now().date(),
    )


def get_inventory_gl_activity_summary(as_of_date):
    """Summarize 1400 receipts, COGS credits, and closing adjustments for trial balance UI."""
    asset_code = INVENTORY_ASSET_CODE
    receipts = Decimal('0.00')
    cogs_credits = Decimal('0.00')
    closing_adj = Decimal('0.00')

    receipt_refs = Q(reference__startswith=RECEIPT_REF_PREFIX) | Q(
        reference__startswith='LAB-RCV-'
    )
    cogs_refs = Q(reference__startswith=COGS_REF_PREFIX)
    closing_refs = Q(reference__startswith=CLOSING_STOCK_REF_PREFIX)

    asset_account_ids = list(
        Account.objects.filter(account_code=asset_code, is_deleted=False).values_list('pk', flat=True)
    )
    if not asset_account_ids:
        return {
            'receipts_debit_1400': receipts,
            'cogs_credit_1400': cogs_credits,
            'closing_adjustment_net': closing_adj,
        }

    lines = AdvancedJournalEntryLine.objects.filter(
        account_id__in=asset_account_ids,
        journal_entry__status='posted',
        journal_entry__is_deleted=False,
        journal_entry__entry_date__lte=as_of_date,
    ).select_related('journal_entry')

    for line in lines:
        ref = line.journal_entry.reference or ''
        if ref.startswith(RECEIPT_REF_PREFIX) or ref.startswith('LAB-RCV-'):
            receipts += line.debit_amount or Decimal('0.00')
        elif ref.startswith(COGS_REF_PREFIX):
            cogs_credits += line.credit_amount or Decimal('0.00')
        elif ref.startswith(CLOSING_STOCK_REF_PREFIX):
            closing_adj += (line.debit_amount or Decimal('0.00')) - (
                line.credit_amount or Decimal('0.00')
            )

    return {
        'receipts_debit_1400': receipts,
        'cogs_credit_1400': cogs_credits,
        'closing_adjustment_net': closing_adj,
        'cogs_accounts': COGS_ACCOUNT_CODES,
    }


def get_operational_stock_summary(as_of_date=None):
    """
    Operational stock value from PharmacyStock and procurement InventoryItem.
    as_of_date is reserved for future date-filtered snapshots; currently uses live qty.
    """
    pharmacy_qs = PharmacyStock.objects.filter(is_deleted=False)
    pharmacy_value = (
        pharmacy_qs.aggregate(
            total=Sum(
                F('quantity_on_hand') * F('unit_cost'),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )['total']
        or Decimal('0.00')
    )
    pharmacy_batch_count = pharmacy_qs.count()
    pharmacy_drug_count = pharmacy_qs.values('drug').distinct().count()

    store_qs = InventoryItem.objects.filter(is_deleted=False, is_active=True)
    store_value = (
        store_qs.aggregate(
            total=Sum(
                F('quantity_on_hand') * F('unit_cost'),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )['total']
        or Decimal('0.00')
    )
    store_item_count = store_qs.count()

    location_breakdown = list(
        pharmacy_qs.values('location')
        .annotate(
            value=Sum(
                F('quantity_on_hand') * F('unit_cost'),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
            batches=Count('id'),
        )
        .order_by('-value')
    )

    total_value = pharmacy_value + store_value

    return {
        'total_value': total_value,
        'pharmacy_value': pharmacy_value,
        'store_value': store_value,
        'pharmacy_batch_count': pharmacy_batch_count,
        'pharmacy_drug_count': pharmacy_drug_count,
        'store_item_count': store_item_count,
        'location_breakdown': location_breakdown,
        'as_of_date': as_of_date,
    }


def get_gl_inventory_balance(as_of_date):
    """GL balance on account 1400 from both ledgers."""
    return get_account_balance(INVENTORY_ASSET_CODE, as_of_date, account_type='asset')


def compute_closing_stock_adjustment(as_of_date):
    """
    Compare operational stock to GL 1400 balance.
    Returns adjustment details without posting.
    """
    today = timezone.now().date()
    live_only = as_of_date != today
    summary = get_operational_stock_summary(as_of_date)
    operational_value = summary['total_value']
    gl_balance = get_gl_inventory_balance(as_of_date)
    variance = operational_value - gl_balance

    if live_only:
        direction = 'none'
        debit_code, credit_code = None, None
    elif variance > Decimal('0.01'):
        direction = 'increase'
        debit_code, credit_code = INVENTORY_ASSET_CODE, CLOSING_INVENTORY_CODE
    elif variance < Decimal('-0.01'):
        direction = 'decrease'
        debit_code, credit_code = CLOSING_INVENTORY_CODE, INVENTORY_ASSET_CODE
    else:
        direction = 'none'
        debit_code, credit_code = None, None

    return {
        'operational_value': operational_value,
        'gl_balance': gl_balance,
        'variance': variance,
        'adjustment_amount': abs(variance),
        'direction': direction,
        'debit_account_code': debit_code,
        'credit_account_code': credit_code,
        'summary': summary,
        'live_only': live_only,
        'can_post': not live_only and direction != 'none',
    }


def _existing_closing_stock_entry(as_of_date):
    ref = f"{CLOSING_STOCK_REF_PREFIX}{as_of_date.isoformat()}"
    return AdvancedJournalEntry.objects.filter(
        reference=ref,
        status='posted',
        is_deleted=False,
    ).first()


def post_closing_stock_adjustment(as_of_date, user, force=False):
    """
    Post closing stock adjustment journal to align GL 1400 with operational stock.

    Idempotent per date unless force=True (voids prior posted entry for same date first).
    Returns result dict with success flag and details.
    """
    today = timezone.now().date()
    if as_of_date != today:
        adjustment = compute_closing_stock_adjustment(as_of_date)
        return {
            'success': False,
            'posted': False,
            'message': (
                f'Closing stock sync is only allowed for today ({today}). '
                f'Operational stock is live-only; historical dates show informational variance only.'
            ),
            **adjustment,
        }

    adjustment = compute_closing_stock_adjustment(as_of_date)

    if adjustment['direction'] == 'none':
        return {
            'success': True,
            'posted': False,
            'message': 'GL inventory balance already matches operational stock.',
            **adjustment,
        }

    existing = _existing_closing_stock_entry(as_of_date)
    if existing and not force:
        return {
            'success': True,
            'posted': False,
            'already_posted': True,
            'journal_entry': existing,
            'message': (
                f'Closing stock already synced for {as_of_date} '
                f'(entry {existing.entry_number}). Use force to re-sync.'
            ),
            **adjustment,
        }

    amount = adjustment['adjustment_amount']
    inventory_account = _ensure_account(INVENTORY_ASSET_CODE)
    closing_account = _ensure_account(CLOSING_INVENTORY_CODE)

    if adjustment['direction'] == 'increase':
        debit_account, credit_account = inventory_account, closing_account
        line1_desc = 'Increase closing stock — align GL inventory (1400) with physical count'
        line2_desc = 'Closing inventory offset (5120)'
    else:
        debit_account, credit_account = closing_account, inventory_account
        line1_desc = 'Decrease closing inventory offset (5120)'
        line2_desc = 'Reduce GL inventory (1400) to match physical count'

    ref = f"{CLOSING_STOCK_REF_PREFIX}{as_of_date.isoformat()}"
    description = (
        f'Closing stock adjustment as of {as_of_date}: '
        f'operational GHS {adjustment["operational_value"]:.2f}, '
        f'prior GL GHS {adjustment["gl_balance"]:.2f}, '
        f'adjustment GHS {amount:.2f}'
    )

    if not _gl_reference_lock(ref):
        for _ in range(30):
            import time
            time.sleep(0.05)
            existing = _existing_closing_stock_entry(as_of_date)
            if existing:
                return {
                    'success': True,
                    'posted': False,
                    'already_posted': True,
                    'journal_entry': existing,
                    'message': (
                        f'Closing stock already synced for {as_of_date} '
                        f'(entry {existing.entry_number}). Use force to re-sync.'
                    ),
                    **adjustment,
                }
        return {
            'success': False,
            'posted': False,
            'message': f'Closing stock posting busy for {as_of_date}.',
            **adjustment,
        }

    try:
        with transaction.atomic():
            if existing and force:
                existing.void()

            journal, _ = Journal.objects.get_or_create(
                code='GJ',
                defaults={'name': 'General Journal', 'journal_type': 'general'},
            )

            je = AdvancedJournalEntry.objects.create(
                journal=journal,
                entry_date=as_of_date,
                description=description,
                reference=ref,
                created_by=user,
                status='draft',
                total_debit=amount,
                total_credit=amount,
            )

            AdvancedJournalEntryLine.objects.create(
                journal_entry=je,
                line_number=1,
                account=debit_account,
                description=line1_desc,
                debit_amount=amount,
                credit_amount=Decimal('0.00'),
            )
            AdvancedJournalEntryLine.objects.create(
                journal_entry=je,
                line_number=2,
                account=credit_account,
                description=line2_desc,
                debit_amount=Decimal('0.00'),
                credit_amount=amount,
            )

            je.post(user)
    finally:
        _gl_reference_unlock(ref)

    return {
        'success': True,
        'posted': True,
        'journal_entry': je,
        'message': (
            f'Posted closing stock adjustment of GHS {amount:.2f} '
            f'({adjustment["direction"]} inventory). Entry {je.entry_number}.'
        ),
        **adjustment,
    }
