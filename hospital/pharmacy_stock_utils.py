"""
Shared utilities for reducing pharmacy stock when drugs are dispensed.
Used by prescription dispensing, walk-in sales, and quick dispense flows.
Allows negative stock when insufficient - for accountability until restocked.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import F

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


def drug_is_sold_per_tablet(drug) -> bool:
    """True when drug dosage form indicates individual tablet unit-of-sale."""
    form = (getattr(drug, 'form', None) or '').strip().lower()
    return form.startswith('tab') or 'tablet' in form
