"""
Deposit Payment Service
Applies patient deposit to invoices only when cashier runs Apply deposit / manual apply.
Unapplied deposit does not reduce displayed amount due (see patient_outstanding_service).
"""
from decimal import Decimal
from django.db import transaction
from django.db.models import F, Q, Sum
import logging

logger = logging.getLogger(__name__)


def _heal_deposit_available_balance(deposit):
    """
    Keep PatientDeposit.available_balance in sync with deposit_amount - used_amount.
    If available_balance was incorrectly zeroed while used_amount < deposit_amount, apply would
    skip the row (filter required available > 0) while the UI still showed remaining credit.
    """
    from ..models_patient_deposits import PatientDeposit

    if not deposit or not isinstance(deposit, PatientDeposit):
        return
    dep_amt = deposit.deposit_amount or Decimal('0.00')
    used = deposit.used_amount or Decimal('0.00')
    expected_avail = max(Decimal('0.00'), dep_amt - used)
    ab = deposit.available_balance or Decimal('0.00')
    if ab == expected_avail:
        return
    deposit.available_balance = expected_avail
    update_fields = ['available_balance', 'modified']
    if expected_avail <= Decimal('0.00') and used >= dep_amt and dep_amt > Decimal('0.00'):
        deposit.status = 'fully_used'
        update_fields.append('status')
    elif getattr(deposit, 'status', None) == 'fully_used' and expected_avail > Decimal('0.00'):
        deposit.status = 'active'
        update_fields.append('status')
    deposit.save(update_fields=update_fields)


def apply_deposit_to_invoice(invoice, applied_by=None, create_receipt=True):
    """
    Apply patient's deposit balance to an invoice. Reduces invoice.balance.
    Only called from explicit cashier actions (Apply deposit to bill / manual apply), not from payment views.
    
    Args:
        invoice: Invoice object (must have balance > 0, payer cash)
        applied_by: User applying (optional - uses deposit.received_by if None)
        create_receipt: If True, each deposit application creates a PaymentReceipt. Set False when
            the caller will create a single combined receipt (e.g. cashier "Apply deposit to bill").
    
    Returns:
        tuple: (amount_applied, remaining_balance)
    """
    from ..models_patient_deposits import PatientDeposit
    
    if not invoice:
        return (Decimal('0.00'), Decimal('0.00'))

    # Ensure invoice has correct balance (recalculate from lines and payments)
    try:
        invoice.update_totals()
    except Exception:
        invoice.refresh_from_db()

    if invoice.balance <= 0:
        return (Decimal('0.00'), invoice.balance)
    
    patient = invoice.patient
    payer_type = getattr(invoice.payer, 'payer_type', None) if invoice.payer else None
    # Apply deposits only to cash/self-pay invoices (not insurance/corporate)
    if payer_type not in ('cash', 'self_pay', None):
        return (Decimal('0.00'), invoice.balance)
    
    total_applied = Decimal('0.00')
    
    try:
        from .patient_outstanding_service import patient_billing_scope_ids

        scope_ids = patient_billing_scope_ids(patient)
        # Any row with remaining credit (deposit_amount > used); heal available_balance in-loop.
        deposits = PatientDeposit.objects.filter(
            patient_id__in=scope_ids,
            status='active',
            is_deleted=False,
        ).filter(Q(deposit_amount__gt=F('used_amount'))).order_by('deposit_date', 'deposit_number')

        for deposit in deposits:
            if invoice.balance <= 0:
                break
            deposit.refresh_from_db(fields=['deposit_amount', 'used_amount', 'available_balance', 'status'])
            _heal_deposit_available_balance(deposit)
            amount_to_apply = min(deposit.available_balance, invoice.balance)
            if amount_to_apply <= 0:
                continue
            try:
                deposit.apply_to_invoice(invoice, amount_to_apply, create_receipt=create_receipt)
                total_applied += amount_to_apply
                invoice.refresh_from_db()
                logger.info(
                    f"Applied deposit {deposit.deposit_number} GHS {amount_to_apply} "
                    f"to invoice {invoice.invoice_number}"
                )
            except Exception as e:
                logger.warning(f"Deposit apply failed: {e}")
    except Exception as e:
        logger.error(f"Error applying deposits: {e}", exc_info=True)
    
    return (total_applied, invoice.balance)


def apply_deposit_to_all_patient_invoices(patient, create_receipt=True, invoice_pks=None):
    """
    Apply patient's deposit balance to unpaid cash invoices.
    Called from cashier "Apply deposit to total bill" (explicit action only).

    Args:
        patient: Patient instance
        create_receipt: When True, each application posts a deposit PaymentReceipt (default).
        invoice_pks: Optional list of invoice UUIDs to restrict application (e.g. invoices
            currently on Total Bill). None = all unpaid cash invoices for this patient/MRN scope.
            An empty list applies nothing (returns 0).

    Returns total amount applied across processed invoices.
    """
    from ..models import Invoice
    from .patient_outstanding_service import patient_billing_scope_ids

    total_applied = Decimal('0.00')
    scope_ids = patient_billing_scope_ids(patient)
    if invoice_pks is not None and len(invoice_pks) == 0:
        return total_applied

    qs = (
        Invoice.all_objects.filter(patient_id__in=scope_ids, is_deleted=False)
        .exclude(status='paid')
        .select_related('payer')
    )
    if invoice_pks is not None:
        qs = qs.filter(pk__in=invoice_pks)
    invoices = qs.order_by('issued_at', 'pk')

    for inv in invoices:
        payer_type = getattr(inv.payer, 'payer_type', None) if inv.payer else None
        if payer_type not in ('cash', 'self_pay', None):
            continue
        applied, _ = apply_deposit_to_invoice(inv, None, create_receipt=create_receipt)
        total_applied += applied

    return total_applied


def get_patient_deposit_balance_display(patient):
    """
    Total deposit balance available for this patient (on account, not yet applied to invoices).
    Uses available_balance when set; for legacy records where available_balance=0 and
    used_amount=0, uses deposit_amount. This does not reduce invoice balances until Apply deposit runs.
    """
    from ..models_patient_deposits import PatientDeposit
    total = Decimal('0.00')
    deposits = PatientDeposit.objects.filter(
        patient=patient,
        status='active',
        is_deleted=False
    )
    for dep in deposits:
        if (dep.available_balance or Decimal('0')) > 0:
            total += dep.available_balance
        elif (dep.used_amount or Decimal('0')) == 0 and (dep.deposit_amount or Decimal('0')) > 0:
            total += dep.deposit_amount
        else:
            total += max(Decimal('0'), (dep.deposit_amount or Decimal('0')) - (dep.used_amount or Decimal('0')))
    return total


def get_patients_deposit_balance_display(patient_ids):
    """
    Sum on-account deposit balance across one or more patient rows (e.g. same MRN duplicates).
    Same rules as get_patient_deposit_balance_display per deposit row.
    """
    from ..models_patient_deposits import PatientDeposit

    if not patient_ids:
        return Decimal('0.00')
    total = Decimal('0.00')
    deposits = PatientDeposit.objects.filter(
        patient_id__in=list(patient_ids),
        status='active',
        is_deleted=False,
    )
    for dep in deposits:
        if (dep.available_balance or Decimal('0')) > 0:
            total += dep.available_balance
        elif (dep.used_amount or Decimal('0')) == 0 and (dep.deposit_amount or Decimal('0')) > 0:
            total += dep.deposit_amount
        else:
            total += max(Decimal('0'), (dep.deposit_amount or Decimal('0')) - (dep.used_amount or Decimal('0')))
    return total


def estimate_amount_after_deposit(invoice, full_amount):
    """
    Amount to collect for UI (read-only). Unapplied patient deposit does NOT reduce this;
    cashier applies deposit explicitly first; then invoice.balance reflects it.
    """
    fa = Decimal(str(full_amount))
    if not invoice:
        return max(Decimal('0.00'), fa)
    payer_type = getattr(invoice.payer, 'payer_type', None) if invoice.payer else None
    if payer_type not in ('cash', 'self_pay', None):
        return max(Decimal('0.00'), fa)
    balance = invoice.balance or Decimal('0.00')
    return max(Decimal('0.00'), min(fa, balance))


def refresh_combined_service_prices_after_deposit(services_list):
    """
    After deposits are applied to invoices, cap invoice / invoice_line row prices by
    remaining DB balances (so totals match post-deposit state). Rows the cashier
    zeroed (price 0) stay 0. Non-invoice rows (lab, imaging, walk-in, bed) unchanged.

    Returns total amount still due (sum of row prices).
    """
    from ..models import Invoice, InvoiceLine
    from ..utils_billing import consultation_line_display_amount

    inv_ids = set()
    for s in services_list:
        t = s.get('type')
        o = s.get('obj')
        if t in ('invoice', 'consumables') and o:
            inv_ids.add(o.id)
        elif t == 'invoice_line' and o:
            iid = getattr(o, 'invoice_id', None)
            if iid:
                inv_ids.add(iid)

    balance_map = {}
    for pk in inv_ids:
        inv = Invoice.all_objects.filter(pk=pk).first()
        if inv:
            inv.update_totals()
            balance_map[pk] = max(Decimal('0.00'), inv.balance or Decimal('0.00'))
        else:
            balance_map[pk] = Decimal('0.00')

    remaining = dict(balance_map)

    for s in services_list:
        t = s.get('type')
        o = s.get('obj')
        user_row = s.get('price')
        if user_row is None:
            user_row = Decimal('0.00')
        else:
            user_row = Decimal(str(user_row))

        if t in ('invoice', 'consumables') and o:
            pk = o.id
            if user_row <= 0:
                s['price'] = Decimal('0.00')
                s['unit_price'] = Decimal('0.00')
                continue
            bal = remaining.get(pk, Decimal('0.00'))
            new_price = min(user_row, bal)
            qty = s.get('quantity') or Decimal('1')
            if qty <= 0:
                qty = Decimal('1')
            s['price'] = new_price
            s['unit_price'] = new_price / qty
            remaining[pk] = bal - new_price
        elif t == 'invoice_line' and o:
            pk = getattr(o, 'invoice_id', None)
            if not pk:
                continue
            if user_row <= 0:
                s['price'] = Decimal('0.00')
                s['unit_price'] = Decimal('0.00')
                continue
            bal = remaining.get(pk, Decimal('0.00'))
            line_amt = Decimal('0.00')
            lid = s.get('id')
            if lid:
                line = InvoiceLine.objects.filter(pk=lid, is_deleted=False).first()
                if line:
                    la = consultation_line_display_amount(line)
                    if la is not None:
                        line_amt = la
            take = min(user_row, line_amt, bal)
            qty = s.get('quantity') or Decimal('1')
            if qty <= 0:
                qty = Decimal('1')
            s['price'] = take
            s['unit_price'] = take / qty
            remaining[pk] = bal - take

    return sum((s.get('price') or Decimal('0.00')) for s in services_list)


def deposit_amount_applied_to_invoice_for_display(invoice):
    """
    Deposit applied to one invoice for statements (matches Invoice.calculate_totals
    dedupe: max(DA, deposit-like receipts), not DA + receipts).
    """
    from django.db.models import Sum
    from ..models_accounting import PaymentReceipt
    from ..models_patient_deposits import DepositApplication

    if not invoice or not getattr(invoice, 'pk', None):
        return Decimal('0.00')

    da = (
        DepositApplication.objects.filter(invoice=invoice, is_deleted=False).aggregate(
            s=Sum('applied_amount')
        )['s']
        or Decimal('0.00')
    )
    receipts = PaymentReceipt.objects.filter(invoice=invoice, is_deleted=False).exclude(
        notes__icontains='Part of combined bill'
    ).exclude(notes__icontains='Combined payment (summary)')
    dr = sum(
        (
            r.amount_paid
            for r in receipts
            if r.payment_method == 'deposit'
            or (
                getattr(r, 'service_details', None)
                and isinstance(r.service_details, dict)
                and r.service_details.get('deposit_applied')
            )
        ),
        Decimal('0.00'),
    )
    return max(da, dr)


def deposit_amount_applied_to_invoices_for_display(invoices):
    """Sum deposit_amount_applied_to_invoice_for_display for a sequence of invoices."""
    total = Decimal('0.00')
    seen = set()
    for inv in invoices:
        if not inv or inv.pk in seen:
            continue
        seen.add(inv.pk)
        total += deposit_amount_applied_to_invoice_for_display(inv)
    return total


def deposit_amount_applied_for_pending_services_list(services_list):
    """
    Deposit applied only to invoices that appear as rows in a pending combined-bill
    services_list (output shape from _get_patient_pending_services_for_payment).

    Use this for Patient Bills and any view where row amounts are invoice balances, so
    totals are not inflated by deposit receipts on other invoices for the same patient.
    """
    if not services_list:
        return Decimal('0.00')
    from ..models import Invoice, InvoiceLine

    invoices = []
    seen = set()
    for s in services_list:
        if not isinstance(s, dict):
            continue
        stype = s.get('type')
        obj = s.get('obj')
        inv = None
        if stype == 'invoice' and obj is not None:
            inv = obj
        elif stype == 'invoice_line' and obj is not None:
            if isinstance(obj, InvoiceLine):
                inv = getattr(obj, 'invoice', None)
            elif getattr(obj, 'invoice_id', None):
                inv = Invoice.all_objects.filter(pk=obj.invoice_id).first()
        if inv is not None and getattr(inv, 'pk', None) and inv.pk not in seen:
            seen.add(inv.pk)
            invoices.append(inv)
    return deposit_amount_applied_to_invoices_for_display(invoices)


def reverse_deposit_payments_for_invoice(invoice):
    """
    Undo deposit applications and deposit receipts for this invoice so the patient’s
    deposit balance is restored and invoice totals no longer count that payment.

    Used when an accountant removes (cancels) an invoice from the bill so a duplicate
    or mistake does not leave deposit stuck on a removed invoice.

    Returns the total amount reversed (deposit currency).
    """
    from django.db.models import Q

    from ..models_accounting import PaymentReceipt, Transaction
    from ..models_patient_deposits import DepositApplication

    if not invoice or not getattr(invoice, 'pk', None):
        return Decimal('0.00')

    total_reversed = Decimal('0.00')

    with transaction.atomic():
        inv = (
            type(invoice).all_objects.select_for_update(of=('self',))
            .filter(pk=invoice.pk, is_deleted=False)
            .first()
        )
        if not inv:
            return Decimal('0.00')

        for app in (
            DepositApplication.objects.filter(invoice=inv, is_deleted=False)
            .select_for_update(of=('self',))
            .select_related('deposit')
        ):
            dep = app.deposit
            if dep and not getattr(dep, 'is_deleted', False):
                amount = app.applied_amount or Decimal('0.00')
                if amount > 0:
                    dep.used_amount = max(
                        Decimal('0.00'),
                        (dep.used_amount or Decimal('0.00')) - amount,
                    )
                    dep.available_balance = (dep.available_balance or Decimal('0.00')) + amount
                    if dep.status == 'fully_used' and dep.available_balance > Decimal('0.00'):
                        dep.status = 'active'
                    dep.save(
                        update_fields=['used_amount', 'available_balance', 'status', 'modified']
                    )
                    total_reversed += amount
            app.is_deleted = True
            app.save(update_fields=['is_deleted', 'modified'])

        receipt_qs = (
            PaymentReceipt.objects.filter(invoice=inv, is_deleted=False)
            .exclude(Q(notes__icontains='Part of combined bill'))
            .exclude(Q(notes__icontains='Combined payment (summary)'))
            .filter(
                Q(payment_method='deposit')
                | Q(service_details__deposit_applied=True)
                | Q(notes__icontains='Deposit applied to bill')
            )
        )
        for rec in receipt_qs.select_for_update(of=('self',)):
            tid = getattr(rec, 'transaction_id', None)
            rec.is_deleted = True
            rec.save(update_fields=['is_deleted', 'modified'])
            if tid:
                Transaction.objects.filter(pk=tid, is_deleted=False).update(is_deleted=True)

        inv.calculate_totals()
        inv.save(update_fields=['total_amount', 'balance', 'status', 'modified'])

    return total_reversed


def invoice_has_non_deposit_payment_recorded(invoice):
    """
    True if the invoice has any payment receipt that is not deposit-backed
    (cash, MoMo, card, etc.) or a non-deposit allocation.
    """
    from django.db.models import Q

    from ..models_accounting import PaymentAllocation, PaymentReceipt

    if not invoice or not getattr(invoice, 'pk', None):
        return False

    receipts = (
        PaymentReceipt.objects.filter(invoice=invoice, is_deleted=False)
        .exclude(Q(notes__icontains='Part of combined bill'))
        .exclude(Q(notes__icontains='Combined payment (summary)'))
    )
    for r in receipts:
        if r.payment_method == 'deposit':
            continue
        sd = getattr(r, 'service_details', None)
        if isinstance(sd, dict) and sd.get('deposit_applied'):
            continue
        return True

    alloc_qs = PaymentAllocation.objects.filter(
        invoice=invoice,
        is_deleted=False,
        payment_transaction__transaction_type='payment_received',
        payment_transaction__is_deleted=False,
    ).select_related('payment_transaction')
    for a in alloc_qs:
        txn = a.payment_transaction
        if not txn:
            continue
        pm = getattr(txn, 'payment_method', None) or ''
        if pm != 'deposit':
            return True

    return False


def get_invoice_for_lab(lab_result):
    """Get the invoice for a lab result (from auto-billing). Returns None if not found."""
    from hospital.models import InvoiceLine
    try:
        encounter = lab_result.order.encounter
        patient = encounter.patient
        test_code = getattr(lab_result.test, 'code', None) or str(lab_result.test.pk)
        svc_code = f"LAB-{test_code}"
        line = InvoiceLine.objects.filter(
            invoice__encounter=encounter,
            invoice__patient=patient,
            invoice__is_deleted=False,
            service_code__code=svc_code,
            is_deleted=False
        ).select_related('invoice').first()
        return line.invoice if line else None
    except Exception:
        return None


def get_invoice_for_prescription(prescription):
    """Get the invoice for a prescription (from auto-billing). Returns None if not found."""
    from hospital.models import InvoiceLine
    try:
        encounter = prescription.order.encounter
        patient = encounter.patient
        drug = prescription.drug
        code = getattr(drug, 'code', None) or str(drug.pk)
        svc_code = f"DRUG-{code}"
        line = InvoiceLine.objects.filter(
            invoice__encounter=encounter,
            invoice__patient=patient,
            invoice__is_deleted=False,
            prescription=prescription,
            is_deleted=False
        ).select_related('invoice').first()
        if line:
            return line.invoice
        # Fallback: same drug service code
        line = InvoiceLine.objects.filter(
            invoice__encounter=encounter,
            invoice__patient=patient,
            invoice__is_deleted=False,
            service_code__code=svc_code,
            is_deleted=False
        ).select_related('invoice').first()
        return line.invoice if line else None
    except Exception:
        return None


def get_invoice_for_imaging(imaging_study):
    """Get the invoice for an imaging study. Returns None if not found."""
    from hospital.models import InvoiceLine
    try:
        encounter = imaging_study.encounter
        patient = encounter.patient
        line = InvoiceLine.objects.filter(
            invoice__encounter=encounter,
            invoice__patient=patient,
            invoice__is_deleted=False,
            description__icontains=imaging_study.study_type or '',
            is_deleted=False
        ).select_related('invoice').first()
        return line.invoice if line else None
    except Exception:
        return None


def link_deposit_receipt_to_release(release_model, release_record, invoice, received_by_user):
    """
    When payment was fully covered by deposit, link the deposit receipt to the release record.
    Returns the receipt used for linking, or None.
    """
    from hospital.models_accounting import PaymentReceipt
    from django.utils import timezone
    from decimal import Decimal

    if not invoice or not release_record:
        return None

    # Only treat deposit as "payment verified" when the invoice is actually fully settled.
    # Otherwise a partial deposit would incorrectly mark services as paid/ready.
    try:
        invoice.update_totals()
    except Exception:
        try:
            invoice.refresh_from_db()
        except Exception:
            pass
    bal = getattr(invoice, 'balance', None)
    tot = getattr(invoice, 'total_amount', None)
    if (tot is None) or (Decimal(str(tot or 0)) <= 0):
        return None
    if bal is None or Decimal(str(bal or 0)) > 0:
        return None

    receipt = PaymentReceipt.objects.filter(
        invoice=invoice,
        payment_method='deposit',
        is_deleted=False
    ).order_by('-receipt_date').first()
    if receipt:
        release_record.payment_receipt = receipt
        release_record.payment_verified_at = timezone.now()
        release_record.payment_verified_by = received_by_user
        release_record.release_status = 'ready_for_release'
        release_record.save()
        return receipt
    return None
