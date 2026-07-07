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


def post_pharmacy_stock_supplier_payable(*, stock, quantity_added, unit_cost, supplier, user):
    """
    Create a stock_receipt line for a new pharmacy batch. Caller must be inside transaction.atomic().
    Idempotent: skips if a line already exists for this stock.
    """
    if not supplier or quantity_added is None:
        return None
    from decimal import Decimal as D

    unit = D(str(unit_cost or 0))
    qty = int(quantity_added or 0)
    total = (D(qty) * unit).quantize(D('0.01'))
    if total <= 0:
        return None
    if SupplierPayableLine.objects.filter(pharmacy_stock=stock, is_deleted=False).exists():
        return SupplierPayableLine.objects.filter(pharmacy_stock=stock, is_deleted=False).first()
    drug_name = getattr(getattr(stock, 'drug', None), 'name', '') or 'Drug'
    batch = getattr(stock, 'batch_number', '') or ''
    return SupplierPayableLine.objects.create(
        supplier=supplier,
        entry_type=SupplierPayableLine.ENTRY_STOCK_RECEIPT,
        amount=total,
        description=f'Pharmacy stock: {drug_name} batch {batch} qty {qty}',
        pharmacy_stock=stock,
        created_by=user,
    )


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
    """Post Dr 1400 / Cr AP for lab reagent stock on hand."""
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
