"""
Shared utilities for reducing pharmacy stock when drugs are dispensed.
Used by prescription dispensing, walk-in sales, and quick dispense flows.
Allows negative stock when insufficient - for accountability until restocked.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import F, Sum

logger = logging.getLogger(__name__)

_ZERO = Decimal('0.00')


def _quantize_money(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _empty_reduction():
    return {'shortfall': 0, 'cogs_amount': _ZERO, 'batch_lines': []}


def reduce_pharmacy_stock(drug, quantity):
    """
    Reduce PharmacyStock when drugs are dispensed (FIFO - first expiring first).
    Syncs linked pharmacy InventoryItem rows. When insufficient positive batches,
    records a SHORTFALL batch (negative qty) for accountability.

    Returns:
        dict with keys:
            shortfall (int): units not covered by positive batches
            cogs_amount (Decimal): FIFO cost of units taken from positive batches
            batch_lines (list): per-batch cost breakdown
    """
    if not drug or quantity <= 0:
        return _empty_reduction()

    qty_to_dispense = int(quantity)

    try:
        from .models import PharmacyStock
        from django.db import OperationalError

        shortfall = 0
        cogs_amount = _ZERO
        batch_lines = []

        with transaction.atomic():
            base_qs = PharmacyStock.objects.filter(
                drug=drug,
                quantity_on_hand__gt=0,
                is_deleted=False,
            ).order_by('expiry_date')

            try:
                stocks = list(base_qs.select_for_update())
            except (OperationalError, NotImplementedError):
                stocks = list(base_qs)

            remaining = qty_to_dispense
            for stock in stocks:
                if remaining <= 0:
                    break
                stock.refresh_from_db()
                on_hand = int(stock.quantity_on_hand or 0)
                if on_hand <= 0:
                    continue
                take = min(on_hand, remaining)
                unit_cost = _quantize_money(stock.unit_cost)
                line_cost = _quantize_money(Decimal(take) * unit_cost)

                updated = PharmacyStock.objects.filter(
                    pk=stock.pk,
                    quantity_on_hand__gte=take,
                ).update(quantity_on_hand=F('quantity_on_hand') - take)
                if updated:
                    cogs_amount += line_cost
                    batch_lines.append({
                        'batch_id': str(stock.pk),
                        'batch_number': stock.batch_number,
                        'qty': take,
                        'unit_cost': unit_cost,
                        'line_cost': line_cost,
                    })
                    remaining -= take
                    continue
                stock.refresh_from_db()
                on_hand = int(stock.quantity_on_hand or 0)
                if on_hand <= 0:
                    continue
                take = min(on_hand, remaining)
                unit_cost = _quantize_money(stock.unit_cost)
                line_cost = _quantize_money(Decimal(take) * unit_cost)
                updated = PharmacyStock.objects.filter(
                    pk=stock.pk,
                    quantity_on_hand__gte=take,
                ).update(quantity_on_hand=F('quantity_on_hand') - take)
                if updated:
                    cogs_amount += line_cost
                    batch_lines.append({
                        'batch_id': str(stock.pk),
                        'batch_number': stock.batch_number,
                        'qty': take,
                        'unit_cost': unit_cost,
                        'line_cost': line_cost,
                    })
                    remaining -= take

            shortfall = remaining

            if shortfall > 0:
                logger.warning(
                    "Insufficient positive batches for %s. Requested: %s, shortfall: %s.",
                    getattr(drug, 'name', drug),
                    qty_to_dispense,
                    shortfall,
                )
                shortfall_expiry = date.today() + timedelta(days=365 * 2)
                shortfall_batch = PharmacyStock.objects.filter(
                    drug=drug,
                    batch_number__istartswith='SHORTFALL',
                    is_deleted=False,
                ).order_by('-created').first()

                if shortfall_batch:
                    PharmacyStock.objects.filter(pk=shortfall_batch.pk).update(
                        quantity_on_hand=F('quantity_on_hand') - shortfall
                    )
                else:
                    PharmacyStock.objects.create(
                        drug=drug,
                        batch_number=f'SHORTFALL-{date.today().isoformat()}',
                        expiry_date=shortfall_expiry,
                        location='Main Pharmacy',
                        quantity_on_hand=-shortfall,
                        reorder_level=0,
                        unit_cost=0,
                    )

            _reduce_inventory_items_for_pharmacy(drug, qty_to_dispense)

        return {
            'shortfall': shortfall,
            'cogs_amount': _quantize_money(cogs_amount),
            'batch_lines': batch_lines,
        }
    except Exception as e:
        logger.error(
            "Error reducing pharmacy stock for %s: %s",
            getattr(drug, 'name', drug),
            e,
            exc_info=True,
        )
        raise


def _reduce_inventory_items_for_pharmacy(drug, quantity):
    """
    Reduce linked pharmacy InventoryItem quantities (procurement / store screens)
    in the canonical Main Pharmacy store for prescription workflows.
    """
    if not drug or quantity <= 0:
        return 0

    try:
        from .models_procurement import Store, InventoryItem

        pharmacy_store = Store.get_main_pharmacy_store()
        if not pharmacy_store:
            logger.warning(
                "Main Pharmacy store not found; skipping InventoryItem sync for %s",
                getattr(drug, 'name', str(drug)),
            )
            return quantity

        items = list(
            InventoryItem.objects.filter(
                store_id=pharmacy_store.id,
                drug=drug,
                is_deleted=False,
                is_active=True,
                store__is_deleted=False,
            )
            .order_by('created')
            .distinct()
        )

        remaining = int(quantity)
        for item in items:
            if remaining <= 0:
                break
            item.refresh_from_db(fields=['quantity_on_hand'])
            on_hand = int(item.quantity_on_hand or 0)
            if on_hand <= 0:
                continue
            take = min(on_hand, remaining)
            updated = InventoryItem.objects.filter(
                pk=item.pk,
                quantity_on_hand__gte=take,
            ).update(quantity_on_hand=F('quantity_on_hand') - take)
            if updated:
                remaining -= take
                continue
            item.refresh_from_db(fields=['quantity_on_hand'])
            on_hand = int(item.quantity_on_hand or 0)
            if on_hand <= 0:
                continue
            take = min(on_hand, remaining)
            updated = InventoryItem.objects.filter(
                pk=item.pk,
                quantity_on_hand__gte=take,
            ).update(quantity_on_hand=F('quantity_on_hand') - take)
            if updated:
                remaining -= take

        if remaining > 0:
            logger.warning(
                "InventoryItem sync shortfall for %s: requested=%s, units not matched in pharmacy items=%s",
                getattr(drug, 'name', str(drug)),
                quantity,
                remaining,
            )
        return remaining
    except Exception as exc:
        logger.warning(
            "InventoryItem sync failed for %s: %s",
            getattr(drug, 'name', str(drug)),
            exc,
        )
        return quantity


def _post_pharmacy_cogs_if_enabled(deduction_log, cogs_amount, user=None):
    if not cogs_amount or cogs_amount <= 0:
        return None
    try:
        from hospital.services.inventory_gl_service import post_inventory_cogs_gl
        return post_inventory_cogs_gl(
            category_key='pharmacy',
            amount=cogs_amount,
            reference=f'COGS-PHARM-{deduction_log.pk}',
            description=(
                f'Pharmacy COGS — {getattr(deduction_log.drug, "name", "drug")} '
                f'×{deduction_log.quantity} ({deduction_log.source_type})'
            ),
            user=user,
            deduction_log=deduction_log,
        )
    except Exception as exc:
        logger.warning('Pharmacy COGS GL posting failed: %s', exc, exc_info=True)
        return None


def reduce_pharmacy_stock_once(drug, quantity, source_type, source_id, user=None):
    """
    Apply reduce_pharmacy_stock at most once per (source_type, source_id).
    Use the PK of PharmacyDispenseHistory, PharmacyDispensing, or WalkInPharmacySaleItem.

    Returns:
        tuple: (shortfall, applied) where ``applied`` is True only when a new deduction log
        row was created and ``reduce_pharmacy_stock`` completed.
    """
    from django.db import IntegrityError

    from .models_payment_verification import PharmacyStockDeductionLog

    if not drug or quantity <= 0:
        logger.info(
            "Skipping stock deduction due to invalid payload: drug=%s quantity=%s source=%s source_id=%s",
            getattr(drug, 'id', None) if drug else None,
            quantity,
            source_type,
            source_id,
        )
        return 0, False
    if source_id is None:
        result = reduce_pharmacy_stock(drug, int(quantity))
        return result['shortfall'], True

    qty = int(quantity)

    try:
        with transaction.atomic():
            log, created = PharmacyStockDeductionLog.objects.get_or_create(
                source_type=source_type,
                source_id=source_id,
                defaults={'quantity': 0, 'drug': drug},
            )
            if not created:
                logger.info(
                    "Stock deduction already recorded for %s %s — skipping",
                    source_type,
                    source_id,
                )
                return 0, False
            try:
                result = reduce_pharmacy_stock(drug, qty)
            except Exception:
                log.delete()
                raise
            log.quantity = qty
            log.drug = drug
            log.cogs_amount = result['cogs_amount']
            log.save(update_fields=['quantity', 'drug', 'cogs_amount', 'modified'])

            _post_pharmacy_cogs_if_enabled(log, result['cogs_amount'], user=user)

            return result['shortfall'], True
    except IntegrityError:
        logger.warning(
            "Concurrent stock deduction log create for %s %s — treating as already done",
            source_type,
            source_id,
        )
        return 0, False


def add_or_increase_pharmacy_stock(
    drug,
    quantity,
    *,
    unit_cost=None,
    batch_number=None,
    expiry_date=None,
    location='Main Pharmacy',
    supplier=None,
    created_by=None,
    reference=None,
):
    """
    Add quantity into PharmacyStock so pharmacy dispense/served stock reflects
    procurement receiving and inventory edits linked to a formulary drug.

    Prefer increasing an existing non-expired batch with matching unit_cost;
    otherwise create a new batch.
    Returns PharmacyStock instance or None.
    """
    if not drug or quantity is None:
        return None
    try:
        qty = int(quantity)
    except (TypeError, ValueError):
        return None
    if qty <= 0:
        return None

    from datetime import timedelta

    from django.utils import timezone

    from .models import PharmacyStock

    unit_cost_dec = _quantize_money(unit_cost)
    today = timezone.localdate()
    if expiry_date is None:
        expiry_date = today + timedelta(days=365 * 2)
    if not batch_number:
        prefix = f"RECV-{today.strftime('%Y%m%d')}"
        if reference:
            safe_ref = ''.join(c for c in str(reference) if c.isalnum())[:10].upper()
            prefix = f"RECV-{safe_ref}" if safe_ref else prefix
        same = PharmacyStock.objects.filter(
            batch_number__startswith=prefix, is_deleted=False
        ).count()
        batch_number = f"{prefix}-{same + 1:04d}"

    try:
        with transaction.atomic():
            existing = (
                PharmacyStock.objects.filter(
                    drug=drug,
                    is_deleted=False,
                    expiry_date__gte=today,
                    quantity_on_hand__gte=0,
                )
                .order_by('expiry_date', 'created')
                .first()
            )
            if existing and (
                unit_cost is None
                or _quantize_money(existing.unit_cost) == unit_cost_dec
                or unit_cost_dec == _ZERO
            ):
                PharmacyStock.objects.filter(pk=existing.pk).update(
                    quantity_on_hand=F('quantity_on_hand') + qty,
                )
                if unit_cost is not None and unit_cost_dec > _ZERO:
                    if not existing.unit_cost or existing.unit_cost == 0:
                        PharmacyStock.objects.filter(pk=existing.pk).update(
                            unit_cost=unit_cost_dec
                        )
                existing.refresh_from_db()
                logger.info(
                    "Increased PharmacyStock %s for %s by %s (now %s)",
                    existing.pk,
                    getattr(drug, 'name', drug),
                    qty,
                    existing.quantity_on_hand,
                )
                return existing

            stock = PharmacyStock.objects.create(
                drug=drug,
                batch_number=batch_number,
                expiry_date=expiry_date,
                location=location or 'Main Pharmacy',
                initial_quantity=qty,
                quantity_on_hand=qty,
                unit_cost=unit_cost_dec,
                supplier=supplier,
                created_by=created_by,
            )
            logger.info(
                "Created PharmacyStock %s for %s qty=%s batch=%s",
                stock.pk,
                getattr(drug, 'name', drug),
                qty,
                batch_number,
            )
            return stock
    except Exception as exc:
        logger.warning(
            "add_or_increase_pharmacy_stock failed for drug %s: %s",
            getattr(drug, 'pk', drug),
            exc,
            exc_info=True,
        )
        return None


def sync_inventory_item_quantity_to_pharmacy_stock(inventory_item, previous_quantity=None):
    """
    When procurement edits an InventoryItem linked to a Drug, mirror the quantity
    delta into PharmacyStock so pharmacy sees the updated on-hand.
    """
    if not inventory_item or not getattr(inventory_item, 'drug_id', None):
        return None
    try:
        new_qty = int(inventory_item.quantity_on_hand or 0)
    except (TypeError, ValueError):
        return None
    try:
        old_qty = int(previous_quantity) if previous_quantity is not None else None
    except (TypeError, ValueError):
        old_qty = None

    if old_qty is None:
        from .models import PharmacyStock

        total = (
            PharmacyStock.objects.filter(drug_id=inventory_item.drug_id, is_deleted=False).aggregate(
                t=Sum('quantity_on_hand')
            )['t']
            or 0
        )
        # Set absolute: add delta between desired inventory qty and current pharmacy total
        delta = new_qty - int(total)
    else:
        delta = new_qty - old_qty

    if delta == 0:
        return None
    if delta > 0:
        return add_or_increase_pharmacy_stock(
            inventory_item.drug,
            delta,
            unit_cost=getattr(inventory_item, 'unit_cost', None),
            supplier=getattr(inventory_item, 'preferred_supplier', None),
            reference=getattr(inventory_item, 'item_code', None)
            or getattr(inventory_item, 'item_name', None),
        )

    # Quantity reduced — reduce PharmacyStock FIFO
    result = reduce_pharmacy_stock(inventory_item.drug, abs(delta))
    return result


def drug_is_sold_per_tablet(drug) -> bool:
    """True when drug dosage form indicates individual tablet unit-of-sale."""
    form = (getattr(drug, 'form', None) or '').strip().lower()
    return form.startswith('tab') or 'tablet' in form
