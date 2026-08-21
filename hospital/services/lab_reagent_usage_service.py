"""
Automatic lab reagent consumption when a lab test is completed.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone


AUTO_REFERENCE_PREFIX = "AUTO-LABRESULT"
EDTA_REFERENCE_PREFIX = "AUTO-EDTA"
RECEIVE_REFERENCE_PREFIX = "RECV-PACK"
DEFAULT_QTY_PER_TEST = Decimal("1.00")
DEFAULT_QTY_PER_VISIT = Decimal("1.00")


def consumption_qty_for_reagent(reagent):
    """Pieces or remaining tests to deduct when a linked lab test is completed."""
    raw = getattr(reagent, "qty_consumed_per_test", None)
    if raw is None:
        return DEFAULT_QTY_PER_TEST
    qty = Decimal(str(raw))
    return qty if qty > 0 else Decimal("0")


def _sync_inventory_item_from_reagent(reagent, quantity_used):
    """
    Keep a *lab store* InventoryItem in sync when reagent stock is consumed.

    Main-store SKUs are reduced when procurement issues to the lab, so completing
    a test must not decrease them again.
    """
    if not getattr(reagent, "inventory_item_id", None):
        return

    try:
        from hospital.models_procurement import InventoryItem
    except Exception:
        return

    item = InventoryItem.objects.select_related("store").filter(
        pk=reagent.inventory_item_id,
        is_deleted=False,
    ).first()
    if not item:
        return

    store_type = (getattr(getattr(item, "store", None), "store_type", "") or "").lower()
    if store_type not in ("lab", "laboratory"):
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
        qty = consumption_qty_for_reagent(reagent)
        if qty <= 0:
            summary["skipped"] += 1
            continue
        reference = f"{AUTO_REFERENCE_PREFIX}-{lab_result.id}-{reagent.id}"

        already_logged = ReagentTransaction.objects.filter(
            reagent=reagent,
            lab_result=lab_result,
            transaction_type="used",
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

            if locked_reagent.quantity_on_hand < qty:
                summary["skipped"] += 1
                continue

            locked_reagent.quantity_on_hand -= qty
            locked_reagent.total_used += qty
            locked_reagent.last_used_at = timezone.now()
            locked_reagent.save(update_fields=["quantity_on_hand", "total_used", "last_used_at", "modified"])

            txn = ReagentTransaction.objects.create(
                reagent=locked_reagent,
                transaction_type="used",
                quantity=qty,
                performed_by=performed_by,
                reference=reference,
                notes="Auto-deducted when lab result was completed.",
                patient=patient,
                lab_result=lab_result,
                purpose=f"Auto usage for completed test: {getattr(test, 'name', 'Lab Test')}",
                test_name=getattr(test, "name", "") or "",
            )

            unit_cost = locked_reagent.unit_cost or Decimal("0")
            cogs_amount = (qty * Decimal(str(unit_cost))).quantize(Decimal("0.01"))
            try:
                from hospital.services.inventory_gl_service import post_inventory_cogs_gl
                post_inventory_cogs_gl(
                    category_key="lab",
                    amount=cogs_amount,
                    reference=f"COGS-REAGENT-{txn.pk}",
                    description=f"Lab reagent COGS: {locked_reagent.name} ×{qty}",
                    reagent_transaction=txn,
                )
            except Exception:
                pass

            _sync_inventory_item_from_reagent(locked_reagent, qty)
            summary["consumed"] += 1

    return summary


def consume_visit_consumables_for_lab_result(lab_result, performed_by=None):
    """
    Deduct items marked deduct_per_lab_visit once for each completed lab test.
    EDTA tubes and similar items used on every completed lab.
    """
    if not lab_result or getattr(lab_result, "status", None) != "completed":
        return {"processed": 0, "consumed": 0, "skipped": 0}

    try:
        from hospital.models_lab_management import LabReagent, ReagentTransaction
    except Exception:
        return {"processed": 0, "consumed": 0, "skipped": 0}

    reagents = list(
        LabReagent.objects.filter(is_deleted=False, deduct_per_lab_visit=True)
    )
    summary = {"processed": len(reagents), "consumed": 0, "skipped": 0}
    patient = None
    try:
        patient = lab_result.order.encounter.patient
    except Exception:
        patient = None
    test = getattr(lab_result, "test", None)
    test_name = getattr(test, "name", "") or "Lab test"

    for reagent in reagents:
        qty = Decimal(str(reagent.qty_per_lab_visit or DEFAULT_QTY_PER_VISIT))
        if qty <= 0:
            summary["skipped"] += 1
            continue
        reference = f"{EDTA_REFERENCE_PREFIX}-{lab_result.id}-{reagent.id}"
        already_logged = ReagentTransaction.objects.filter(
            reagent=reagent,
            lab_result=lab_result,
            transaction_type="used",
            is_deleted=False,
        ).exists()
        if already_logged:
            summary["skipped"] += 1
            continue

        with transaction.atomic():
            locked_reagent = (
                LabReagent.objects.select_for_update()
                .filter(pk=reagent.pk, is_deleted=False)
                .first()
            )
            if not locked_reagent or locked_reagent.quantity_on_hand < qty:
                summary["skipped"] += 1
                continue

            locked_reagent.quantity_on_hand -= qty
            locked_reagent.total_used += qty
            locked_reagent.last_used_at = timezone.now()
            locked_reagent.save(
                update_fields=["quantity_on_hand", "total_used", "last_used_at", "modified"]
            )

            txn = ReagentTransaction.objects.create(
                reagent=locked_reagent,
                transaction_type="used",
                quantity=qty,
                performed_by=performed_by,
                reference=reference,
                notes="Auto-deducted for each completed lab test (EDTA / visit consumable).",
                patient=patient,
                lab_result=lab_result,
                purpose=f"Completed lab: {test_name}",
                test_name=test_name,
            )

            unit_cost = locked_reagent.unit_cost or Decimal("0")
            cogs_amount = (qty * Decimal(str(unit_cost))).quantize(Decimal("0.01"))
            try:
                from hospital.services.inventory_gl_service import post_inventory_cogs_gl

                post_inventory_cogs_gl(
                    category_key="lab",
                    amount=cogs_amount,
                    reference=f"COGS-REAGENT-{txn.pk}",
                    description=f"Lab EDTA COGS: {locked_reagent.name} ×{qty} ({test_name})",
                    reagent_transaction=txn,
                )
            except Exception:
                pass

            _sync_inventory_item_from_reagent(locked_reagent, qty)
            summary["consumed"] += 1

    return summary


def issue_reagent_to_staff(*, reagent, quantity, performed_by=None, recipient_staff=None, recipient_name="", notes=""):
    """Give lab stock to a staff member. Quantity leaves LabReagent (and linked inventory)."""
    from django.core.exceptions import ValidationError
    from hospital.models_lab_management import LabReagent, ReagentTransaction

    qty = Decimal(str(quantity or 0))
    if qty <= 0:
        raise ValidationError("Quantity must be positive.")

    recipient = (recipient_name or "").strip()
    if recipient_staff is not None and not recipient:
        user = getattr(recipient_staff, "user", None)
        recipient = (
            (user.get_full_name() if user else "") or (user.username if user else "") or str(recipient_staff)
        )
    if not recipient:
        raise ValidationError("Select or enter the staff member who received the item.")

    with transaction.atomic():
        locked = (
            LabReagent.objects.select_for_update()
            .filter(pk=reagent.pk, is_deleted=False)
            .first()
        )
        if not locked:
            raise ValidationError("Item not found.")
        if locked.quantity_on_hand < qty:
            raise ValidationError(
                f"Insufficient stock. Available: {locked.quantity_on_hand} {locked.unit}."
            )
        locked.quantity_on_hand -= qty
        locked.total_used += qty
        locked.last_used_at = timezone.now()
        locked.save(update_fields=["quantity_on_hand", "total_used", "last_used_at", "modified"])
        txn = ReagentTransaction.objects.create(
            reagent=locked,
            transaction_type="transferred",
            quantity=qty,
            performed_by=performed_by,
            reference=f"ISSUE-STAFF-{locked.id}",
            notes=(notes or "").strip(),
            purpose=f"Issued to lab staff: {recipient}",
            test_name="",
        )
        _sync_inventory_item_from_reagent(locked, qty)
    return txn


def receive_reagent_pack(*, reagent, packs, performed_by=None, notes=""):
    """
    Receive boxes (measurable kits) or chemistry kits (immeasurable).
    Measurable: packs × qty_per_box pieces.
    Immeasurable: packs × tests_per_kit remaining tests.
    """
    from django.core.exceptions import ValidationError
    from hospital.models_lab_management import LabReagent, ReagentTransaction

    pack_count = Decimal(str(packs or 0))
    if pack_count <= 0:
        raise ValidationError("Enter how many boxes or kits you received.")

    with transaction.atomic():
        locked = (
            LabReagent.objects.select_for_update()
            .filter(pk=reagent.pk, is_deleted=False)
            .first()
        )
        if not locked:
            raise ValidationError("Item not found.")

        tracking = locked.stock_tracking or "untracked"
        if tracking == "measurable" and locked.qty_per_box:
            qty = pack_count * Decimal(str(locked.qty_per_box))
            purpose = f"Received {pack_count} box(es) × {locked.qty_per_box} {locked.unit}"
        elif tracking == "immeasurable" and locked.tests_per_kit:
            qty = pack_count * Decimal(str(locked.tests_per_kit))
            purpose = f"Received {pack_count} kit(s) × {locked.tests_per_kit} tests"
        else:
            qty = pack_count
            purpose = f"Received {pack_count} {locked.unit}"

        locked.quantity_on_hand += qty
        locked.save(update_fields=["quantity_on_hand", "modified"])
        txn = ReagentTransaction.objects.create(
            reagent=locked,
            transaction_type="received",
            quantity=qty,
            performed_by=performed_by,
            reference=f"{RECEIVE_REFERENCE_PREFIX}-{locked.id}",
            notes=(notes or "").strip(),
            purpose=purpose,
        )
    return txn


BOX_UOM = frozenset({"box", "boxes", "pack", "packs", "kit", "kits", "bottle", "bottles"})


def lab_qty_from_store_issue(reagent, store_qty, store_uom=""):
    """Convert procurement issue quantity into lab pieces or remaining tests."""
    qty = Decimal(str(store_qty or 0))
    uom = (store_uom or "").strip().lower()
    tracking = getattr(reagent, "stock_tracking", "") or ""
    if tracking == "measurable" and reagent.qty_per_box and uom in BOX_UOM:
        return qty * Decimal(str(reagent.qty_per_box))
    if tracking == "immeasurable" and reagent.tests_per_kit and uom in BOX_UOM:
        return qty * Decimal(str(reagent.tests_per_kit))
    return qty


def ensure_procurement_item_for_reagent(reagent):
    """Create/link a main-store InventoryItem so procurement can issue this kit to the lab."""
    from hospital.models_procurement import InventoryCategory, InventoryItem, Store

    if getattr(reagent, "inventory_item_id", None):
        item = InventoryItem.objects.filter(pk=reagent.inventory_item_id, is_deleted=False).first()
        if item:
            return item

    store = (
        Store.objects.filter(store_type="main", is_deleted=False, is_active=True).first()
        or Store.objects.filter(store_type="general", is_deleted=False, is_active=True).first()
        or Store.objects.filter(is_deleted=False, is_active=True).exclude(store_type="pharmacy").first()
    )
    if not store:
        store, _ = Store.objects.get_or_create(
            code="MAIN",
            defaults={
                "name": "Main Store",
                "store_type": "main",
                "location": "Stores",
                "is_active": True,
            },
        )

    category, _ = InventoryCategory.objects.get_or_create(
        code="LAB",
        defaults={"name": "Laboratory", "description": "Lab kits and reagents", "is_active": True},
    )
    tracking = reagent.stock_tracking or "untracked"
    if tracking == "measurable":
        uom = "box"
    elif tracking == "immeasurable":
        uom = "kit"
    else:
        uom = reagent.unit or "pcs"

    item = None
    if reagent.item_code:
        item = InventoryItem.objects.filter(
            store=store, item_code=reagent.item_code, is_deleted=False
        ).first()
    if not item:
        item = InventoryItem.objects.create(
            store=store,
            category=category,
            item_name=reagent.name[:200],
            item_code=(reagent.item_code or "")[:50],
            quantity_on_hand=0,
            unit_cost=reagent.unit_cost or Decimal("0"),
            unit_of_measure=uom,
            is_active=True,
        )
    reagent.inventory_item_id = item.id
    reagent.save(update_fields=["inventory_item_id", "modified"])
    return item


def issue_store_stock_to_lab(*, inventory_item, quantity, performed_by=None, notes="", recipient_name=""):
    """
    Procurement issues store stock to the laboratory.
    Store quantity goes down; lab reagent on-hand goes up (with kit/box conversion).
    """
    from django.core.exceptions import ValidationError
    from hospital.models_lab_management import LabReagent, ReagentTransaction
    from hospital.services.inventory_accountability_service import InventoryAccountabilityService

    store_qty = int(quantity or 0)
    if store_qty <= 0:
        raise ValidationError("Quantity must be positive.")

    reagent = LabReagent.objects.filter(
        inventory_item_id=inventory_item.id, is_deleted=False
    ).first()
    if not reagent and getattr(inventory_item, "item_code", ""):
        reagent = LabReagent.objects.filter(
            item_code=inventory_item.item_code, is_deleted=False
        ).first()
        if reagent and not reagent.inventory_item_id:
            reagent.inventory_item_id = inventory_item.id
            reagent.save(update_fields=["inventory_item_id", "modified"])
    if not reagent:
        raise ValidationError(
            "This store item is not linked to a lab kit or reagent. "
            "Use Issue to staff for non-lab supplies, or link the item first."
        )

    lab_qty = lab_qty_from_store_issue(
        reagent, store_qty, getattr(inventory_item, "unit_of_measure", "") or ""
    )
    if lab_qty <= 0:
        raise ValidationError("Nothing to add to laboratory stock.")

    who = (recipient_name or "").strip() or "Laboratory"
    with transaction.atomic():
        txn = InventoryAccountabilityService.issue_to_department(
            inventory_item=inventory_item,
            quantity=store_qty,
            staff=performed_by,
            department_name="Laboratory",
            recipient_name=who,
            notes=(notes or "").strip(),
            reason="Issue to laboratory",
        )

        locked = (
            LabReagent.objects.select_for_update()
            .filter(pk=reagent.pk, is_deleted=False)
            .first()
        )
        if not locked:
            raise ValidationError("Lab item not found.")
        locked.quantity_on_hand += lab_qty
        locked.save(update_fields=["quantity_on_hand", "modified"])
        ReagentTransaction.objects.create(
            reagent=locked,
            transaction_type="received",
            quantity=lab_qty,
            performed_by=performed_by,
            reference=f"PROC-LAB-{getattr(txn, 'transaction_number', locked.id)}",
            notes=(notes or "").strip(),
            purpose=(
                f"Issued from {inventory_item.store.name} to laboratory: "
                f"{store_qty} {inventory_item.unit_of_measure} → {lab_qty} {locked.unit}"
            ),
        )
    return txn, lab_qty
