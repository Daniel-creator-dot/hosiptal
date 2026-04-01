"""
Link PharmacyDispensing when an encounter invoice is fully settled (cashier, deposit,
allocations, combined payment). Receipt FK is optional — deposit-only and summary flows
often leave no receipt on the invoice, but the queue must still move to Ready to Dispense.

Also sync WalkInPharmacySale when prescribe (walk-in) invoice lines are fully settled.
"""
import logging
import re
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)

# Matches e.g. "... (Sale PS202603221818070009)" from ensure_sale_invoice line descriptions
WALKIN_SALE_REF_RE = re.compile(r"\(Sale\s+(PS\d+)\)", re.IGNORECASE)


def resolve_receipt_for_invoice_payment(invoice, explicit_receipt=None):
    """
    Find a PaymentReceipt to attach to dispensing for this invoice.
    Prefer explicit receipt; then receipt on invoice; then receipt from PaymentAllocation.
    """
    from ..models_accounting import PaymentAllocation, PaymentReceipt

    if explicit_receipt is not None:
        return explicit_receipt

    r = (
        PaymentReceipt.objects.filter(invoice=invoice, is_deleted=False)
        .exclude(notes__icontains='Part of combined bill')
        .exclude(notes__icontains='Combined payment (summary)')
        .order_by('-receipt_date')
        .first()
    )
    if r:
        return r

    alloc = (
        PaymentAllocation.objects.filter(
            invoice=invoice,
            is_deleted=False,
            payment_transaction__transaction_type='payment_received',
            payment_transaction__is_deleted=False,
        )
        .select_related('payment_transaction')
        .order_by('-created')
        .first()
    )
    if not alloc or not alloc.payment_transaction_id:
        return None
    try:
        return alloc.payment_transaction.receipt
    except Exception:
        return (
            PaymentReceipt.objects.filter(
                transaction=alloc.payment_transaction,
                is_deleted=False,
            )
            .first()
        )


def get_prescription_ids_on_settled_pharmacy_invoices():
    """
    Prescriptions with a non-waived line on an invoice that is financially settled.
    Uses Invoice.all_objects so visibility rules do not hide paid invoices.
    """
    from ..models import Invoice, InvoiceLine

    settled_invoice_ids = Invoice.all_objects.filter(
        is_deleted=False,
    ).filter(
        Q(status='paid')
        | Q(
            balance__lte=Decimal('0'),
            total_amount__gt=Decimal('0'),
        )
    ).exclude(status__in=['cancelled', 'draft']).values_list('id', flat=True)

    return set(
        InvoiceLine.objects.filter(
            prescription_id__isnull=False,
            is_deleted=False,
            waived_at__isnull=True,
            invoice_id__in=settled_invoice_ids,
        ).values_list('prescription_id', flat=True).distinct()
    )


def reconcile_pending_pharmacy_dispensing_with_invoices():
    """
    Safety net (e.g. legacy data or missed hooks): pending_payment → ready_to_dispense
    when the prescription's invoice is already settled. Returns rows updated.
    """
    from ..models_payment_verification import PharmacyDispensing

    rx_ids = get_prescription_ids_on_settled_pharmacy_invoices()
    if not rx_ids:
        return 0
    now = timezone.now()
    return PharmacyDispensing.objects.filter(
        prescription_id__in=rx_ids,
        dispensing_status='pending_payment',
    ).update(
        dispensing_status='ready_to_dispense',
        payment_verified_at=now,
    )


def link_pharmacy_dispensing_when_invoice_paid(
    invoice,
    receipt=None,
    verified_by_user=None,
    *,
    refresh_invoice=True,
):
    """
    When invoice balance is fully settled, move matching PharmacyDispensing rows to
    ready_to_dispense. Attaches receipt when one exists; settlement still applies without it.

    If refresh_invoice=True, reloads from DB and recalculates totals (does not call
    update_totals(), to avoid re-entrancy with Invoice.update_totals).

    Returns number of dispensing records updated.
    """
    from ..models import InvoiceLine
    from ..models_payment_verification import PharmacyDispensing

    if not invoice or not getattr(invoice, 'pk', None):
        return 0

    if refresh_invoice:
        invoice.refresh_from_db()
        invoice.calculate_totals()
        invoice.save(update_fields=['total_amount', 'balance', 'status'])

    bal = invoice.balance or Decimal('0')
    tot = invoice.total_amount or Decimal('0')
    if bal > Decimal('0') or tot <= Decimal('0'):
        return 0
    if getattr(invoice, 'status', None) == 'cancelled':
        return 0
    if getattr(invoice, 'is_deleted', False):
        return 0

    resolved_receipt = resolve_receipt_for_invoice_payment(invoice, receipt)

    updated = 0
    lines = InvoiceLine.objects.filter(
        invoice=invoice,
        is_deleted=False,
        waived_at__isnull=True,
        prescription_id__isnull=False,
    ).select_related('prescription')

    for line in lines:
        rx = line.prescription
        if not rx:
            continue
        try:
            disp = rx.dispensing_record
        except PharmacyDispensing.DoesNotExist:
            continue
        if not disp or getattr(disp, 'is_deleted', False):
            continue
        if disp.dispensing_status == 'cancelled':
            continue

        # Already cleared by Invoice.update_totals() but receipt FK missing (deposit / combined pay)
        if disp.dispensing_status == 'ready_to_dispense':
            if resolved_receipt is not None and not disp.payment_receipt_id:
                disp.payment_receipt = resolved_receipt
                save_fields = ['payment_receipt', 'modified']
                if verified_by_user is not None:
                    disp.payment_verified_by = verified_by_user
                    save_fields.append('payment_verified_by')
                disp.save(update_fields=save_fields)
                updated += 1
            continue

        if disp.dispensing_status != 'pending_payment':
            continue

        disp.dispensing_status = 'ready_to_dispense'
        disp.payment_verified_at = timezone.now()
        save_fields = ['dispensing_status', 'payment_verified_at', 'modified']
        if resolved_receipt is not None:
            disp.payment_receipt = resolved_receipt
            save_fields.append('payment_receipt')
        if verified_by_user is not None:
            disp.payment_verified_by = verified_by_user
            save_fields.append('payment_verified_by')
        disp.save(update_fields=save_fields)
        updated += 1

    return updated


def link_pharmacy_dispensing_for_paid_invoices(invoices, receipt=None, verified_by_user=None):
    """Run link_pharmacy_dispensing_when_invoice_paid for each invoice (e.g. after combined payment)."""
    total = 0
    seen = set()
    for inv in invoices:
        if not inv or inv.pk in seen:
            continue
        seen.add(inv.pk)
        total += link_pharmacy_dispensing_when_invoice_paid(
            inv, receipt=receipt, verified_by_user=verified_by_user, refresh_invoice=True
        )
    return total


def link_walkin_sales_when_invoice_paid(invoice, receipt=None, *, refresh_invoice=True):
    """
    When an invoice is fully settled (balance <= 0), mark any WalkInPharmacySale
    referenced in line descriptions as paid so cashier lists drop them.
    """
    from ..models import InvoiceLine
    from ..models_pharmacy_walkin import WalkInPharmacySale

    if not invoice or not getattr(invoice, 'pk', None):
        return 0

    if refresh_invoice:
        invoice.refresh_from_db()
        invoice.calculate_totals()
        invoice.save(update_fields=['total_amount', 'balance', 'status'])

    if (invoice.balance or Decimal('0')) > Decimal('0'):
        return 0

    patient_id = getattr(invoice, 'patient_id', None)
    lines = InvoiceLine.objects.filter(
        invoice=invoice,
        is_deleted=False,
        waived_at__isnull=True,
    ).values_list('description', flat=True)

    sale_numbers = set()
    for desc in lines:
        if not desc:
            continue
        for m in WALKIN_SALE_REF_RE.finditer(str(desc)):
            sale_numbers.add(m.group(1).upper())

    if not sale_numbers:
        return 0

    updated = 0
    for sn in sale_numbers:
        qs = WalkInPharmacySale.objects.filter(
            sale_number__iexact=sn,
            is_deleted=False,
        )
        if patient_id:
            sale = qs.filter(patient_id=patient_id).first() or qs.first()
        else:
            sale = qs.first()
        if not sale or getattr(sale, 'waived_at', None):
            continue
        if sale.payment_status == 'paid' and (sale.amount_paid or Decimal('0')) >= (
            sale.total_amount or Decimal('0')
        ):
            continue
        sale.amount_paid = sale.total_amount or Decimal('0.00')
        sale.save()
        updated += 1

    return updated


def sync_walkin_sale_payment_from_invoices(sale):
    """
    Re-run invoice totals and walk-in sale linking for any invoice that references this
    prescribe sale. Use when cash was collected on the invoice but the sale row still
    shows pending (missed hook or legacy data).

    Returns True if the sale is now payable/dispensable (paid, or billed to company).
    """
    from ..models import Invoice, InvoiceLine

    if not sale or not getattr(sale, 'sale_number', None):
        return False
    sn = str(sale.sale_number).strip()
    if not sn:
        return False

    lines = InvoiceLine.objects.filter(
        description__icontains=sn,
        is_deleted=False,
        waived_at__isnull=True,
    )
    if getattr(sale, 'patient_id', None):
        lines = lines.filter(invoice__patient_id=sale.patient_id)

    invoice_ids = set()
    for line in lines:
        desc = line.description or ''
        desc_l = desc.lower()
        if f'(sale {sn.lower()})' not in desc_l and not WALKIN_SALE_REF_RE.search(desc):
            continue
        invoice_ids.add(line.invoice_id)

    for iid in invoice_ids:
        inv = Invoice.all_objects.filter(pk=iid, is_deleted=False).first()
        if not inv:
            continue
        try:
            inv.update_totals()
        except Exception:
            logger.exception(
                'sync_walkin_sale_payment_from_invoices: update_totals failed for invoice %s',
                iid,
            )

    try:
        sale.refresh_from_db()
    except Exception:
        return False
    paid_ok = sale.payment_status == 'paid' and (sale.amount_paid or Decimal('0')) >= (
        sale.total_amount or Decimal('0')
    )
    return bool(paid_ok or getattr(sale, 'is_billed_to_company', False))


def link_walkin_sales_for_paid_invoices(invoices, receipt=None):
    """Run link_walkin_sales_when_invoice_paid for each distinct invoice."""
    total = 0
    seen = set()
    for inv in invoices:
        if not inv or inv.pk in seen:
            continue
        seen.add(inv.pk)
        total += link_walkin_sales_when_invoice_paid(inv, receipt=receipt, refresh_invoice=True)
    return total


def waive_invoice_lines_for_prescribe_sale(sale, waived_by_user=None, reason='Prescribe sale waived'):
    """
    When pharmacy/cashier waives a prescribe sale, waive matching invoice lines
    (description contains ``(Sale <sale_number>)``) so the invoice total drops.
    """
    from ..models import Invoice, InvoiceLine

    if not sale or not getattr(sale, 'sale_number', None):
        return 0
    sn = str(sale.sale_number).strip()
    if not sn:
        return 0
    needle_lower = f'(sale {sn.lower()})'
    qs = InvoiceLine.objects.filter(
        description__icontains=sn,
        is_deleted=False,
        waived_at__isnull=True,
    ).select_related('invoice')
    if getattr(sale, 'patient_id', None):
        qs = qs.filter(invoice__patient_id=sale.patient_id)

    invoice_ids = set()
    updated = 0
    now = timezone.now()
    reason_text = (reason or '')[:255]
    for line in qs:
        desc = (line.description or '')
        desc_l = desc.lower()
        if needle_lower not in desc_l:
            continue
        line.waived_at = now
        line.waived_by = waived_by_user
        line.waiver_reason = reason_text
        line.save()
        invoice_ids.add(line.invoice_id)
        updated += 1

    for iid in invoice_ids:
        inv = Invoice.all_objects.filter(pk=iid).first()
        if inv:
            inv.update_totals()
    return updated
