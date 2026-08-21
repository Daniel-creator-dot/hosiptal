"""
Supplier payable sub-ledger: stock receipts (pharmacy / lab), manual payables, payments.
Positive amount = increased amount owed to supplier; negative = payment reducing balance.
"""
import logging

from django.conf import settings
from django.db import models

from .models import BaseModel

logger = logging.getLogger(__name__)


class SupplierPayableLine(BaseModel):
    ENTRY_STOCK_RECEIPT = 'stock_receipt'
    ENTRY_MANUAL_PAYABLE = 'manual_payable'
    ENTRY_PAYMENT = 'payment'
    ENTRY_ADJUSTMENT = 'adjustment'

    ENTRY_TYPE_CHOICES = [
        (ENTRY_STOCK_RECEIPT, 'Stock receipt'),
        (ENTRY_MANUAL_PAYABLE, 'Manual payable / invoice'),
        (ENTRY_PAYMENT, 'Payment'),
        (ENTRY_ADJUSTMENT, 'Adjustment'),
    ]

    supplier = models.ForeignKey(
        'hospital.Supplier',
        on_delete=models.PROTECT,
        related_name='payable_lines',
    )
    entry_type = models.CharField(max_length=32, choices=ENTRY_TYPE_CHOICES, db_index=True)
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text='Positive increases balance owed; negative records payment.',
    )
    description = models.TextField(blank=True)
    reference = models.CharField(
        max_length=120,
        blank=True,
        help_text='Invoice #, cheque #, or other reference',
    )
    pharmacy_stock = models.OneToOneField(
        'hospital.PharmacyStock',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='supplier_payable_line',
    )
    lab_reagent = models.OneToOneField(
        'hospital.LabReagent',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='supplier_payable_line',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplier_payable_lines_created',
    )

    class Meta:
        ordering = ['-created']
        indexes = [
            models.Index(fields=['supplier', 'is_deleted']),
        ]

    def __str__(self):
        return f'{self.supplier_id} {self.entry_type} {self.amount}'


class SupplierStockReceiptCorrectionRequest(BaseModel):
    """
    Pending edit to a procurement stock-receipt on the supplier ledger.
    Ledger / stock / GL change only after admin approval.
    """

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending approval'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    payable_line = models.ForeignKey(
        SupplierPayableLine,
        on_delete=models.PROTECT,
        related_name='correction_requests',
    )
    supplier = models.ForeignKey(
        'hospital.Supplier',
        on_delete=models.PROTECT,
        related_name='stock_receipt_correction_requests',
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    proposed_quantity = models.PositiveIntegerField()
    proposed_unit_cost = models.DecimalField(max_digits=15, decimal_places=4)
    proposed_amount = models.DecimalField(max_digits=15, decimal_places=2)
    current_quantity = models.PositiveIntegerField()
    current_unit_cost = models.DecimalField(max_digits=15, decimal_places=4)
    current_amount = models.DecimalField(max_digits=15, decimal_places=2)
    reason = models.CharField(max_length=200, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_receipt_corrections_requested',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_receipt_corrections_reviewed',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-created']
        indexes = [
            models.Index(fields=['supplier', 'status', 'is_deleted']),
            models.Index(fields=['payable_line', 'status', 'is_deleted']),
        ]

    def __str__(self):
        return (
            f'Correction {self.status} line={self.payable_line_id} '
            f'{self.current_amount}→{self.proposed_amount}'
        )


def post_pharmacy_stock_supplier_payable(*, stock, quantity_added, unit_cost, supplier, user):
    """
    Create a stock_receipt line for a new pharmacy batch. Caller must be inside transaction.atomic().
    Idempotent: skips if a line already exists for this stock.
    Stores supplier invoice # on the payable line reference so accounts can look it up when paying.
    """
    if not supplier or quantity_added is None:
        return None
    from decimal import Decimal as D
    import re

    unit = D(str(unit_cost or 0))
    qty = int(quantity_added or 0)
    total = (D(qty) * unit).quantize(D('0.01'))
    if total <= 0:
        return None
    existing = SupplierPayableLine.objects.filter(pharmacy_stock=stock, is_deleted=False).first()
    if existing:
        # Keep invoice reference in sync if stock was updated before first payment.
        inv = re.sub(r'\s+', ' ', (getattr(stock, 'supplier_invoice_number', None) or '').strip())
        if inv and (existing.reference or '').strip().casefold() != inv.casefold():
            existing.reference = inv
            existing.save(update_fields=['reference', 'modified'])
        return existing
    drug_name = getattr(getattr(stock, 'drug', None), 'name', '') or 'Drug'
    batch = getattr(stock, 'batch_number', '') or ''
    inv = re.sub(r'\s+', ' ', (getattr(stock, 'supplier_invoice_number', None) or '').strip())
    return SupplierPayableLine.objects.create(
        supplier=supplier,
        entry_type=SupplierPayableLine.ENTRY_STOCK_RECEIPT,
        amount=total,
        description=f'Pharmacy stock: {drug_name} batch {batch} qty {qty}',
        reference=inv,
        pharmacy_stock=stock,
        created_by=user,
    )


def post_pharmacy_stock_accounting(*, stock, quantity_added, unit_cost, supplier=None, user=None):
    """
    Post GL receipt (Dr 1400 / Cr 2100) and optional supplier payable for pharmacy stock.
    Idempotent via STOCK-RCV-{stock.pk} for new batches.
    """
    from decimal import Decimal as D

    qty = int(quantity_added or 0)
    unit = D(str(unit_cost or 0))
    total = (D(qty) * unit).quantize(D('0.01'))
    if total <= 0:
        return {'gl': None, 'payable': None}

    gl_result = None
    try:
        from hospital.services.inventory_gl_service import post_pharmacy_stock_receipt_gl

        gl_result = post_pharmacy_stock_receipt_gl(
            stock,
            qty,
            unit,
            user=user,
        )
    except Exception:
        logger.exception('Pharmacy stock receipt GL failed for stock pk=%s', getattr(stock, 'pk', None))

    payable_line = None
    if supplier and not getattr(supplier, 'is_deleted', False):
        try:
            payable_line = post_pharmacy_stock_supplier_payable(
                stock=stock,
                quantity_added=qty,
                unit_cost=unit,
                supplier=supplier,
                user=user,
            )
        except Exception:
            logger.exception(
                'Pharmacy stock supplier payable failed for stock pk=%s',
                getattr(stock, 'pk', None),
            )

    return {'gl': gl_result, 'payable': payable_line}


def _resolve_stock_receipt_correction_values(
    *,
    line,
    new_quantity=None,
    new_unit_cost=None,
    new_amount=None,
):
    """
    Validate proposed supplier-ledger correction values without mutating anything.

    Qty/unit on the form are invoice/commercial figures for the payable amount.
    They are NOT applied to pharmacy/lab stock (items may already be sold).
    """
    from decimal import Decimal as D

    if not line or getattr(line, 'is_deleted', False):
        raise ValueError('Payable line not found.')
    if line.entry_type != SupplierPayableLine.ENTRY_STOCK_RECEIPT:
        raise ValueError('Only stock receipt lines can be corrected here.')

    stock = getattr(line, 'pharmacy_stock', None)
    reagent = getattr(line, 'lab_reagent', None)
    if not stock and not reagent:
        raise ValueError('This stock receipt is not linked to pharmacy or lab stock.')

    old_amount = D(str(line.amount or 0)).quantize(D('0.01'))
    if stock:
        stock_qty = int(
            getattr(stock, 'initial_quantity', None) or getattr(stock, 'quantity_on_hand', 0) or 0
        )
        stock_unit = D(str(getattr(stock, 'unit_cost', 0) or 0))
        category_key = 'pharmacy'
        item_label = getattr(getattr(stock, 'drug', None), 'name', '') or 'Drug'
        batch = getattr(stock, 'batch_number', '') or ''
    else:
        stock_qty = int(D(str(getattr(reagent, 'quantity_on_hand', 0) or 0)))
        stock_unit = D(str(getattr(reagent, 'unit_cost', 0) or 0))
        category_key = 'lab'
        item_label = getattr(reagent, 'name', '') or 'Reagent'
        batch = getattr(reagent, 'batch_number', '') or ''

    # Baseline for the payable edit: prior correction qty if description was updated,
    # else current stock snapshot (display only — stock is never written).
    old_qty = stock_qty
    old_unit = stock_unit

    if new_quantity is not None and str(new_quantity).strip() != '':
        new_qty = int(D(str(new_quantity)))
    else:
        new_qty = old_qty
    if new_qty < 0:
        raise ValueError('Quantity cannot be negative.')

    if new_unit_cost is not None and str(new_unit_cost).strip() != '':
        new_unit = D(str(new_unit_cost)).quantize(D('0.01'))
    elif new_amount is not None and str(new_amount).strip() != '' and new_qty > 0:
        new_unit = (D(str(new_amount)) / D(new_qty)).quantize(D('0.0001'))
    else:
        new_unit = old_unit
    if new_unit < 0:
        raise ValueError('Unit cost cannot be negative.')

    if new_amount is not None and str(new_amount).strip() != '':
        corrected_amount = D(str(new_amount)).quantize(D('0.01'))
    else:
        corrected_amount = (D(new_qty) * new_unit).quantize(D('0.01'))
    if corrected_amount < 0:
        raise ValueError('Amount cannot be negative.')
    if corrected_amount == 0 and new_qty == 0:
        raise ValueError('Corrected quantity and amount cannot both be zero.')

    if corrected_amount == old_amount and new_qty == old_qty and new_unit == old_unit:
        raise ValueError('No changes to save.')

    return {
        'stock': stock,
        'reagent': reagent,
        'category_key': category_key,
        'item_label': item_label,
        'batch': batch,
        'stock_qty': stock_qty,
        'stock_unit': stock_unit,
        'old_amount': old_amount,
        'old_qty': old_qty,
        'old_unit': old_unit,
        'new_qty': new_qty,
        'new_unit': new_unit,
        'new_amount': corrected_amount,
    }


def submit_supplier_stock_receipt_correction(
    *,
    line,
    new_quantity=None,
    new_unit_cost=None,
    new_amount=None,
    user=None,
    reason='',
):
    """
    Queue a stock-receipt correction for admin approval.
    Does not change ledger, stock, or GL until approved.
    """
    from django.db import transaction as db_transaction

    resolved = _resolve_stock_receipt_correction_values(
        line=line,
        new_quantity=new_quantity,
        new_unit_cost=new_unit_cost,
        new_amount=new_amount,
    )
    pending = (
        SupplierStockReceiptCorrectionRequest.objects.filter(
            payable_line=line,
            status=SupplierStockReceiptCorrectionRequest.STATUS_PENDING,
            is_deleted=False,
        )
        .order_by('-created')
        .first()
    )
    if pending:
        raise ValueError(
            'A correction for this stock receipt is already pending admin approval. '
            'Wait for approval/rejection, or ask an admin to reject the pending request first.'
        )

    with db_transaction.atomic():
        req = SupplierStockReceiptCorrectionRequest.objects.create(
            payable_line=line,
            supplier=line.supplier,
            status=SupplierStockReceiptCorrectionRequest.STATUS_PENDING,
            proposed_quantity=resolved['new_qty'],
            proposed_unit_cost=resolved['new_unit'],
            proposed_amount=resolved['new_amount'],
            current_quantity=resolved['old_qty'],
            current_unit_cost=resolved['old_unit'],
            current_amount=resolved['old_amount'],
            reason=(reason or '').strip()[:200],
            requested_by=user,
        )
    return {
        'request': req,
        'old_amount': resolved['old_amount'],
        'new_amount': resolved['new_amount'],
        'old_qty': resolved['old_qty'],
        'new_qty': resolved['new_qty'],
    }


def approve_supplier_stock_receipt_correction(*, correction_request, user=None, review_note=''):
    """Admin approval: apply ledger/stock/GL via correct_supplier_stock_receipt_line."""
    from django.db import transaction as db_transaction
    from django.utils import timezone

    req = correction_request
    if not req or getattr(req, 'is_deleted', False):
        raise ValueError('Correction request not found.')
    if req.status != SupplierStockReceiptCorrectionRequest.STATUS_PENDING:
        raise ValueError(f'This correction is already {req.get_status_display().lower()}.')

    line = req.payable_line
    reason_parts = []
    if (req.reason or '').strip():
        reason_parts.append(req.reason.strip())
    if (review_note or '').strip():
        reason_parts.append(f'Approved: {(review_note or "").strip()}')
    else:
        reason_parts.append('Approved by admin')
    apply_reason = '; '.join(reason_parts)[:200]

    with db_transaction.atomic():
        locked = (
            SupplierStockReceiptCorrectionRequest.objects.select_for_update()
            .filter(pk=req.pk, is_deleted=False)
            .first()
        )
        if not locked or locked.status != SupplierStockReceiptCorrectionRequest.STATUS_PENDING:
            raise ValueError('Correction request is no longer pending.')
        result = correct_supplier_stock_receipt_line(
            line=line,
            new_quantity=locked.proposed_quantity,
            new_unit_cost=locked.proposed_unit_cost,
            new_amount=locked.proposed_amount,
            user=user,
            reason=apply_reason,
        )
        locked.status = SupplierStockReceiptCorrectionRequest.STATUS_APPROVED
        locked.reviewed_by = user
        locked.reviewed_at = timezone.now()
        locked.review_note = (review_note or '').strip()[:200]
        locked.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_note', 'modified'])
        result['request'] = locked
        return result


def reject_supplier_stock_receipt_correction(*, correction_request, user=None, review_note=''):
    """Admin rejection: leave ledger/stock/GL unchanged."""
    from django.utils import timezone

    req = correction_request
    if not req or getattr(req, 'is_deleted', False):
        raise ValueError('Correction request not found.')
    if req.status != SupplierStockReceiptCorrectionRequest.STATUS_PENDING:
        raise ValueError(f'This correction is already {req.get_status_display().lower()}.')

    req.status = SupplierStockReceiptCorrectionRequest.STATUS_REJECTED
    req.reviewed_by = user
    req.reviewed_at = timezone.now()
    req.review_note = (review_note or '').strip()[:200]
    req.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_note', 'modified'])
    return {'request': req}


def correct_supplier_stock_receipt_line(
    *,
    line,
    new_quantity=None,
    new_unit_cost=None,
    new_amount=None,
    user=None,
    reason='',
):
    """
    Apply a supplier-ledger correction after admin approval.

    Valve behaviour:
      - Procurement receipt: stock + supplier account (unchanged path elsewhere)
      - Account correction: supplier payable amount + AP GL only
      - Does NOT change PharmacyStock / LabReagent qty or unit cost
        (stock may already be sold / dispensed)

    GL: Purchases (expense) ↔ Trade Payables so inventory on-hand is untouched.
    """
    from django.db import transaction as db_transaction
    from django.utils import timezone

    resolved = _resolve_stock_receipt_correction_values(
        line=line,
        new_quantity=new_quantity,
        new_unit_cost=new_unit_cost,
        new_amount=new_amount,
    )
    stock = resolved['stock']
    category_key = resolved['category_key']
    item_label = resolved['item_label']
    batch = resolved['batch']
    old_amount = resolved['old_amount']
    old_qty = resolved['old_qty']
    old_unit = resolved['old_unit']
    new_qty = resolved['new_qty']
    new_unit = resolved['new_unit']
    corrected_amount = resolved['new_amount']
    stock_qty = resolved['stock_qty']

    reason_txt = (reason or '').strip()
    stamp = timezone.now().strftime('%d/%m/%Y %H:%M')
    who = ''
    if user is not None:
        who = getattr(user, 'get_full_name', lambda: '')() or getattr(user, 'username', '') or ''
    audit = f' [Supplier amount corrected {stamp}'
    if who:
        audit += f' by {who}'
    audit += (
        f': was invoice qty {old_qty} @ {old_unit} = {old_amount:.2f} '
        f'→ qty {new_qty} @ {new_unit} = {corrected_amount:.2f}'
        f'; pharmacy/lab stock unchanged (on hand {stock_qty})'
    )
    if reason_txt:
        audit += f'; {reason_txt}'
    audit += ']'

    base_desc = (
        f'{"Pharmacy stock" if stock else "Lab reagent"}: {item_label} batch {batch}'
        f' (supplier invoice qty {new_qty})'
    )
    new_desc = base_desc
    if len(new_desc) + len(audit) < 2000:
        new_desc = new_desc + audit

    gl_ref_obj = stock or resolved['reagent']

    with db_transaction.atomic():
        line.amount = corrected_amount
        line.description = new_desc
        line.save(update_fields=['amount', 'description', 'modified'])

        from hospital.services.inventory_gl_service import (
            post_supplier_payable_amount_correction_gl,
        )

        gl = post_supplier_payable_amount_correction_gl(
            gl_ref_obj,
            old_amount,
            corrected_amount,
            user=user,
            category_key=category_key,
            description=(
                f'Supplier account correction ({line.reference or "no invoice"}): '
                f'{item_label} GHS {old_amount:.2f} → {corrected_amount:.2f} '
                f'(stock on hand not changed)'
            ),
        )

    return {
        'line': line,
        'old_amount': old_amount,
        'new_amount': corrected_amount,
        'old_qty': old_qty,
        'new_qty': new_qty,
        'stock_unchanged': True,
        'gl': gl,
    }


def _try_post_receipt_gl(*, category_key, amount, reference, description, user=None, entry_date=None):
    try:
        from hospital.services.inventory_gl_service import post_inventory_receipt_gl
        return post_inventory_receipt_gl(
            category_key=category_key,
            amount=amount,
            reference=reference,
            description=description,
            user=user,
            entry_date=entry_date,
        )
    except Exception:
        logger.exception('Inventory receipt GL failed for reference=%s', reference)
        return None


def post_lab_reagent_supplier_payable(*, reagent, supplier, user=None):
    """
    Create a stock_receipt line when a lab reagent is first received from procurement.
    Idempotent via OneToOne on lab_reagent.
    """
    if not supplier or not reagent:
        return None
    from decimal import Decimal as D

    qty = D(str(reagent.quantity_on_hand or 0))
    unit = D(str(reagent.unit_cost or 0))
    total = (qty * unit).quantize(D('0.01'))
    if total <= 0:
        return None
    if SupplierPayableLine.objects.filter(lab_reagent=reagent, is_deleted=False).exists():
        return SupplierPayableLine.objects.filter(lab_reagent=reagent, is_deleted=False).first()
    batch = (reagent.batch_number or '').strip()
    desc = f'Lab reagent: {reagent.name}'
    if batch:
        desc += f' batch {batch}'
    desc += f' qty {qty}'
    return SupplierPayableLine.objects.create(
        supplier=supplier,
        entry_type=SupplierPayableLine.ENTRY_STOCK_RECEIPT,
        amount=total,
        description=desc,
        lab_reagent=reagent,
        created_by=user,
    )


def post_lab_reagent_receipt_gl(reagent, user=None):
    """Post Dr 5120 Closing Inventory / Cr 2100 Trade Payables for lab reagent stock."""
    from decimal import Decimal as D
    from django.utils import timezone

    qty = D(str(reagent.quantity_on_hand or 0))
    unit = D(str(reagent.unit_cost or 0))
    total = (qty * unit).quantize(D('0.01'))
    if total <= 0:
        return None
    return _try_post_receipt_gl(
        category_key='lab',
        amount=total,
        reference=f'LAB-RCV-{reagent.pk}',
        description=f'Lab reagent receipt: {reagent.name} qty {qty}',
        user=user,
        entry_date=timezone.now().date(),
    )


def post_inventory_item_supplier_payable(*, inventory_item, quantity, unit_cost, supplier, user=None, entry_date=None):
    """
    Create a stock_receipt payable for a store InventoryItem (medical supplies / consumables).
    Idempotent via reference INV-ITEM-{inventory_item.pk}.
    """
    if not supplier or not inventory_item:
        return None
    from decimal import Decimal as D

    qty = D(str(quantity or 0))
    unit = D(str(unit_cost or 0))
    total = (qty * unit).quantize(D('0.01'))
    if total <= 0:
        return None
    reference = f'INV-ITEM-{inventory_item.pk}'
    existing = SupplierPayableLine.objects.filter(
        supplier=supplier,
        reference=reference,
        entry_type=SupplierPayableLine.ENTRY_STOCK_RECEIPT,
        is_deleted=False,
    ).first()
    if existing:
        return existing
    name = getattr(inventory_item, 'item_name', '') or 'Supply'
    return SupplierPayableLine.objects.create(
        supplier=supplier,
        entry_type=SupplierPayableLine.ENTRY_STOCK_RECEIPT,
        amount=total,
        description=f'Medical supplies/consumables: {name} qty {qty}',
        reference=reference,
        created_by=user,
    )


def post_inventory_item_receipt_accounting(*, inventory_item, quantity, unit_cost, supplier=None, user=None, reference=None, entry_date=None):
    """
    Post Dr 5120 (or 1400 for pharmacy-linked items) / Cr Trade Payables and supplier sub-ledger.
    """
    from decimal import Decimal as D
    from django.utils import timezone
    from hospital.services.inventory_account_mapping import resolve_inventory_category_from_item

    qty = D(str(quantity or 0))
    unit = D(str(unit_cost or 0))
    total = (qty * unit).quantize(D('0.01'))
    if total <= 0:
        return {'gl': None, 'payable': None}

    category_key = resolve_inventory_category_from_item(inventory_item)
    gl_ref = reference or f'STOCK-RCV-ITEMOPEN-{inventory_item.pk}'
    gl_result = _try_post_receipt_gl(
        category_key=category_key,
        amount=total,
        reference=gl_ref,
        description=f'Store inventory receipt: {getattr(inventory_item, "item_name", "")} qty {qty}',
        user=user,
        entry_date=entry_date or timezone.now().date(),
    )
    payable_line = None
    if supplier and not getattr(supplier, 'is_deleted', False):
        try:
            payable_line = post_inventory_item_supplier_payable(
                inventory_item=inventory_item,
                quantity=qty,
                unit_cost=unit,
                supplier=supplier,
                user=user,
                entry_date=entry_date,
            )
        except Exception:
            logger.exception(
                'Inventory item supplier payable failed for item pk=%s',
                getattr(inventory_item, 'pk', None),
            )
    return {'gl': gl_result, 'payable': payable_line}
