"""
Automatic lab reagent consumption when a lab test is completed.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone


AUTO_REFERENCE_PREFIX = "AUTO-LABRESULT"
DEFAULT_QTY_PER_TEST = Decimal("1.00")


def _sync_inventory_item_from_reagent(reagent, quantity_used):
    """
    Keep linked InventoryItem in sync when reagent stock is auto-consumed.
    InventoryItem uses positive integers, so we clamp to zero.
    """
    if not getattr(reagent, "inventory_item_id", None):
        return

    try:
        from hospital.models_procurement import InventoryItem
    except Exception:
        return

    item = InventoryItem.objects.filter(
        pk=reagent.inventory_item_id,
        is_deleted=False,
    ).first()
    if not item:
        return

    decrement = int(quantity_used)
    if decrement <= 0:
        return

    item.quantity_on_hand = max(0, int(item.quantity_on_hand or 0) - decrement)
    item.save(update_fields=["quantity_on_hand", "modified"])


def consume_reagents_for_completed_lab_result(lab_result, performed_by=None):
    """
    Deduct linked reagents for a completed LabResult exactly once.
    Returns a small summary dict for logging/diagnostics.
    """
    if not lab_result or getattr(lab_result, "status", None) != "completed":
        return {"processed": 0, "consumed": 0, "skipped": 0}

    test = getattr(lab_result, "test", None)
    if not test:
        return {"processed": 0, "consumed": 0, "skipped": 0}

    try:
        from hospital.models_lab_management import ReagentTransaction
    except Exception:
        return {"processed": 0, "consumed": 0, "skipped": 0}

    patient = None
    try:
        patient = lab_result.order.encounter.patient
    except Exception:
        patient = None

    reagents = list(test.required_reagents.filter(is_deleted=False))
    summary = {"processed": len(reagents), "consumed": 0, "skipped": 0}

    for reagent in reagents:
        reference = f"{AUTO_REFERENCE_PREFIX}-{lab_result.id}-{reagent.id}"

        already_logged = ReagentTransaction.objects.filter(
            reagent=reagent,
            lab_result=lab_result,
            transaction_type="used",
            reference=reference,
            is_deleted=False,
        ).exists()
        if already_logged:
            summary["skipped"] += 1
            continue

        with transaction.atomic():
            locked_reagent = (
                type(reagent).objects.select_for_update().filter(pk=reagent.pk, is_deleted=False).first()
            )
            if not locked_reagent:
                summary["skipped"] += 1
                continue

            if locked_reagent.quantity_on_hand < DEFAULT_QTY_PER_TEST:
                summary["skipped"] += 1
                continue

            locked_reagent.quantity_on_hand -= DEFAULT_QTY_PER_TEST
            locked_reagent.total_used += DEFAULT_QTY_PER_TEST
            locked_reagent.last_used_at = timezone.now()
            locked_reagent.save(update_fields=["quantity_on_hand", "total_used", "last_used_at", "modified"])

            ReagentTransaction.objects.create(
                reagent=locked_reagent,
                transaction_type="used",
                quantity=DEFAULT_QTY_PER_TEST,
                performed_by=performed_by,
                reference=reference,
                notes="Auto-deducted when lab result was completed.",
                patient=patient,
                lab_result=lab_result,
                purpose=f"Auto usage for completed test: {getattr(test, 'name', 'Lab Test')}",
                test_name=getattr(test, "name", "") or "",
            )

            _sync_inventory_item_from_reagent(locked_reagent, DEFAULT_QTY_PER_TEST)
            summary["consumed"] += 1

    return summary
