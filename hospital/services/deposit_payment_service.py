"""
Deposit Payment Service
Applies patient deposit balance when processing payments - deducts from amount due
Ensures deposit is applied to invoice BEFORE collecting remaining amount
"""
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
import logging

logger = logging.getLogger(__name__)


def apply_deposit_to_invoice(invoice, applied_by=None, create_receipt=True):
    """
    Apply patient's deposit balance to an invoice. Reduces invoice.balance.
    Call BEFORE processing cash/momo payment - then only collect invoice.balance.
    
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
        from django.db.models import Q
        # Include deposits with available_balance > 0, or legacy records (available=0, used=0, amount>0)
        deposits = PatientDeposit.objects.filter(
            patient=patient,
            status='active',
            is_deleted=False
        ).filter(
            Q(available_balance__gt=0) |
            (Q(available_balance=0) & Q(used_amount=0) & Q(deposit_amount__gt=0))
        ).order_by('deposit_date')
        
        for deposit in deposits:
            if invoice.balance <= 0:
                break
            # Fix legacy: available_balance=0 but used_amount=0 and deposit_amount>0
            if (deposit.available_balance or Decimal('0')) <= 0 and (deposit.used_amount or Decimal('0')) == 0 and (deposit.deposit_amount or Decimal('0')) > 0:
                deposit.available_balance = deposit.deposit_amount
                deposit.save(update_fields=['available_balance'])
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


def apply_deposit_to_all_patient_invoices(patient, create_receipt=True):
    """
    Apply patient's deposit balance to ALL unpaid cash invoices.
    Call when viewing patient bill so deposit is applied before showing amounts.
    When create_receipt=False (e.g. from cashier "Apply deposit to bill" one-click), no
    per-application receipts are created; the caller must create one combined receipt to
    avoid double-counting in "Amount Paid". Default True preserves existing behavior.
    Returns total amount applied across all invoices.
    """
    from ..models import Invoice

    total_applied = Decimal('0.00')
    invoices = Invoice.objects.filter(
        patient=patient,
        is_deleted=False
    ).exclude(status='paid').select_related('payer')

    for inv in invoices:
        payer_type = getattr(inv.payer, 'payer_type', None) if inv.payer else None
        if payer_type not in ('cash', 'self_pay', None):
            continue
        applied, _ = apply_deposit_to_invoice(inv, None, create_receipt=create_receipt)
        total_applied += applied

    return total_applied


def get_patient_deposit_balance_display(patient):
    """
    Total deposit balance available for this patient (for display / temporary deduction).
    Uses available_balance when set; for legacy records where available_balance=0 and
    used_amount=0, uses deposit_amount so the bill shows the correct "amount after deposit".
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


def estimate_amount_after_deposit(invoice, full_amount):
    """
    Estimate amount due after applying deposit (read-only, does not persist).
    Use for displaying default 'amount to collect' on payment form.
    """
    if not invoice:
        return full_amount
    patient = invoice.patient
    payer_type = getattr(invoice.payer, 'payer_type', None) if invoice.payer else None
    if payer_type not in ('cash', 'self_pay', None):
        return full_amount
    balance = invoice.balance
    # Same effective pool as apply_deposit_to_invoice (includes legacy 0/0 deposits)
    deposit_avail = get_patient_deposit_balance_display(patient)
    return max(Decimal('0.00'), balance - deposit_avail)


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
        if t == 'invoice' and o:
            inv_ids.add(o.id)
        elif t == 'invoice_line' and o:
            inv_ids.add(o.id)

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

        if t == 'invoice' and o:
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
            pk = o.id
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
    receipt = PaymentReceipt.objects.filter(
        invoice=invoice,
        payment_method='deposit',
        is_deleted=False
    ).order_by('-receipt_date').first()
    if receipt and release_record:
        release_record.payment_receipt = receipt
        release_record.payment_verified_at = timezone.now()
        release_record.payment_verified_by = received_by_user
        release_record.release_status = 'ready_for_release'
        release_record.save()
        return receipt
    return None
