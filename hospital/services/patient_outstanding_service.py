"""
Single source of truth for patient outstanding balance across the entire app.
Use get_patient_outstanding(patient) everywhere; one URL serves the same data for frontends.
Formula: total_outstanding = max(0, total_billed - total_paid)
         amount_due_after_deposit = max(0, total_outstanding - deposit_balance)
"""
from datetime import datetime, time
from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone


def get_patient_outstanding(patient, include_deposit_breakdown=False):
    """
    Canonical patient outstanding and amount due. Use this everywhere in the app.

    Args:
        patient: Patient instance (or patient_id for bulk).
        include_deposit_breakdown: If True, also return total_deposited, deposit_used (for patient detail).

    Returns:
        dict with:
            total_billed: Sum of all non-cancelled invoice total_amount.
            total_paid: Sum of all PaymentReceipt.amount_paid for patient (with legacy fallback).
            deposit_balance: Available deposit (uses get_patient_deposit_balance_display when available).
            total_outstanding: max(0, total_billed - total_paid).
            amount_due_after_deposit: max(0, total_outstanding - deposit_balance).
            Optionally: total_deposited, deposit_used (when include_deposit_breakdown=True).
    """
    from ..models import Invoice
    from ..models_accounting import PaymentReceipt

    total_billed = (
        Invoice.objects.filter(patient=patient, is_deleted=False)
        .exclude(status='cancelled')
        .aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
    )

    total_paid = (
        PaymentReceipt.objects.filter(patient=patient, is_deleted=False)
        .aggregate(s=Sum('amount_paid'))['s'] or Decimal('0.00')
    )
    if total_paid == 0:
        inv_total = (
            Invoice.objects.filter(patient=patient, is_deleted=False)
            .exclude(status='cancelled')
            .aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
        )
        inv_balance = (
            Invoice.objects.filter(patient=patient, is_deleted=False)
            .exclude(status='cancelled')
            .aggregate(s=Sum('balance'))['s'] or Decimal('0.00')
        )
        if (inv_total - inv_balance) > 0:
            total_paid = inv_total - inv_balance

    # Can be negative when total_paid > total_billed (patient has credit)
    total_outstanding = (total_billed or Decimal('0.00')) - (total_paid or Decimal('0.00'))
    credit_balance = max(Decimal('0.00'), (total_paid or Decimal('0.00')) - (total_billed or Decimal('0.00')))

    try:
        from .deposit_payment_service import get_patient_deposit_balance_display
        deposit_balance = get_patient_deposit_balance_display(patient)
    except Exception:
        deposit_balance = Decimal('0.00')
    if not isinstance(deposit_balance, Decimal):
        deposit_balance = Decimal(str(deposit_balance))

    amount_due_after_deposit = max(Decimal('0.00'), total_outstanding - deposit_balance)

    result = {
        'total_billed': total_billed,
        'total_paid': total_paid,
        'deposit_balance': deposit_balance,
        'total_outstanding': total_outstanding,
        'credit_balance': credit_balance,
        'amount_due_after_deposit': amount_due_after_deposit,
    }

    if include_deposit_breakdown:
        try:
            from ..models_patient_deposits import PatientDeposit
            total_deposited = (
                PatientDeposit.objects.filter(patient=patient, is_deleted=False)
                .exclude(status__in=['cancelled', 'refunded'])
                .aggregate(s=Sum('deposit_amount'))['s'] or Decimal('0.00')
            )
            if total_deposited == 0:
                receipt_deposit = (
                    PaymentReceipt.objects.filter(
                        patient=patient, is_deleted=False, payment_method='deposit'
                    ).aggregate(s=Sum('amount_paid'))['s'] or Decimal('0.00')
                )
                if receipt_deposit > 0:
                    total_deposited = receipt_deposit
            if total_deposited == 0:
                from ..models_patient_deposits import DepositApplication
                inv_ids = list(Invoice.objects.filter(patient=patient, is_deleted=False).values_list('id', flat=True))
                if inv_ids:
                    applied = DepositApplication.objects.filter(
                        invoice_id__in=inv_ids, is_deleted=False
                    ).aggregate(s=Sum('applied_amount'))['s'] or Decimal('0.00')
                    if applied and applied > 0:
                        total_deposited = applied
            deposit_used = total_deposited - deposit_balance
            if total_deposited > 0 and deposit_used < 0:
                deposit_used = Decimal('0.00')
        except Exception:
            total_deposited = Decimal('0.00')
            deposit_used = Decimal('0.00')
        result['total_deposited'] = total_deposited
        result['deposit_used'] = deposit_used

    return result


def sum_payment_receipts_for_patient_in_date_range(patient, date_from, date_to):
    """
    Sum PaymentReceipt.amount_paid for patient where receipt_date falls within
    local start/end of day bounds (inclusive). Used for cashier Total Bill payment-date filter.
    """
    from ..models_accounting import PaymentReceipt

    if not date_from or not date_to:
        return Decimal('0.00')
    if date_to < date_from:
        date_from, date_to = date_to, date_from
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(date_from, time.min), tz)
    end = timezone.make_aware(datetime.combine(date_to, time.max), tz)
    return (
        PaymentReceipt.objects.filter(
            patient=patient,
            is_deleted=False,
            receipt_date__gte=start,
            receipt_date__lte=end,
        ).aggregate(s=Sum('amount_paid'))['s']
        or Decimal('0.00')
    )


def get_patient_outstanding_bulk(patient_ids):
    """
    Return outstanding for many patients in one go (for lists). Keys are patient_id (UUID).
    """
    from ..models import Invoice
    from ..models_accounting import PaymentReceipt
    from ..models_patient_deposits import PatientDeposit
    from .deposit_payment_service import get_patient_deposit_balance_display

    if not patient_ids:
        return {}

    # total_billed per patient
    billed = (
        Invoice.objects.filter(patient_id__in=patient_ids, is_deleted=False)
        .exclude(status='cancelled')
        .values('patient_id')
        .annotate(total_billed=Sum('total_amount'))
    )
    by_patient = {r['patient_id']: {'total_billed': r['total_billed'] or Decimal('0.00')} for r in billed}

    # total_paid per patient
    paid = (
        PaymentReceipt.objects.filter(patient_id__in=patient_ids, is_deleted=False)
        .values('patient_id')
        .annotate(total_paid=Sum('amount_paid'))
    )
    for r in paid:
        pid = r['patient_id']
        if pid not in by_patient:
            by_patient[pid] = {'total_billed': Decimal('0.00')}
        by_patient[pid]['total_paid'] = r['total_paid'] or Decimal('0.00')
    for pid in patient_ids:
        if pid not in by_patient:
            by_patient[pid] = {'total_billed': Decimal('0.00'), 'total_paid': Decimal('0.00')}
        elif 'total_paid' not in by_patient[pid]:
            by_patient[pid]['total_paid'] = Decimal('0.00')
    # Legacy fallback: when total_paid is 0, use invoice total - balance
    for pid in patient_ids:
        if by_patient[pid]['total_paid'] == 0:
            inv_total = (
                Invoice.objects.filter(patient_id=pid, is_deleted=False)
                .exclude(status='cancelled')
                .aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
            )
            inv_balance = (
                Invoice.objects.filter(patient_id=pid, is_deleted=False)
                .exclude(status='cancelled')
                .aggregate(s=Sum('balance'))['s'] or Decimal('0.00')
            )
            if (inv_total - inv_balance) > 0:
                by_patient[pid]['total_paid'] = inv_total - inv_balance

    # deposit_balance per patient (need to call existing helper per patient or aggregate)
    from ..models import Patient
    for pid in patient_ids:
        try:
            p = Patient.objects.get(pk=pid)
            deposit_balance = get_patient_deposit_balance_display(p)
        except Exception:
            deposit_balance = Decimal('0.00')
        if not isinstance(deposit_balance, Decimal):
            deposit_balance = Decimal(str(deposit_balance))
        by_patient[pid]['deposit_balance'] = deposit_balance
        tb = by_patient[pid]['total_billed']
        tp = by_patient[pid]['total_paid']
        to = tb - tp  # can be negative (credit)
        by_patient[pid]['total_outstanding'] = to
        by_patient[pid]['credit_balance'] = max(Decimal('0.00'), tp - tb)
        by_patient[pid]['amount_due_after_deposit'] = max(Decimal('0.00'), to - deposit_balance)

    return by_patient
