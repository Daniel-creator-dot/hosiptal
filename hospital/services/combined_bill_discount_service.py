"""
Apply a cashier-level combined-bill discount by increasing InvoiceLine.discount_amount
so invoice balances drop before cash allocation (net cash = subtotal - discount).

When patient + user are supplied, a balanced journal is posted: Dr expense (5135),
Cr Accounts Receivable (1200) for the applied discount amount.
"""
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BillDiscountResult:
    """Outcome of distributing a combined-bill discount across invoices."""

    applied: Decimal
    gl_posted: bool = False
    gl_error: str = ''

    def __bool__(self):
        return self.applied > 0


def ensure_patient_bill_discount_chart_account():
    """Expense sub-account for patient bill discounts (under 5100 Operating Expenses when present)."""
    from hospital.models_accounting import Account

    parent = Account.objects.filter(account_code='5100', is_deleted=False).first()
    acct, _ = Account.objects.get_or_create(
        account_code='5135',
        defaults={
            'account_name': 'Patient Bill Discounts',
            'account_type': 'expense',
            'parent_account': parent,
            'description': 'Cashier combined-bill discounts (contra to billed charges).',
            'is_active': True,
        },
    )
    if parent and acct.parent_account_id != parent.pk:
        acct.parent_account = parent
        acct.save(update_fields=['parent_account'])
    return acct


def ensure_accounts_receivable_discount_offset_account():
    """Asset account used to credit (reduce) receivable when a bill discount is granted."""
    from hospital.models_accounting import Account

    acct, _ = Account.objects.get_or_create(
        account_code='1200',
        defaults={
            'account_name': 'Accounts Receivable',
            'account_type': 'asset',
            'description': 'Outstanding patient/insurer balances; credited when bill discounts reduce amounts due.',
            'is_active': True,
        },
    )
    return acct


def post_patient_bill_discount_to_general_ledger(applied_amount, patient, user):
    """
    Dr Patient Bill Discounts (expense) / Cr Accounts Receivable for the discount amount.
    Returns the posted JournalEntry, or None if nothing to post.
    """
    from hospital.models_accounting import JournalEntry, JournalEntryLine

    applied_amount = Decimal(str(applied_amount or 0))
    if applied_amount <= 0 or patient is None or user is None:
        return None

    disc_acct = ensure_patient_bill_discount_chart_account()
    ar_acct = ensure_accounts_receivable_discount_offset_account()
    ref = f"PBD-{patient.pk}-{uuid.uuid4().hex[:10].upper()}"
    pname = getattr(patient, 'full_name', None) or str(patient)
    mrn = getattr(patient, 'mrn', None) or ''
    desc = f'Patient bill discount GHS {applied_amount} — {pname} (MRN {mrn})'.strip()

    je = JournalEntry.objects.create(
        entry_date=timezone.now().date(),
        entry_type='adjustment',
        ref=ref,
        reference_number=ref,
        description=desc,
        entered_by=user,
        status='draft',
        is_posted=False,
    )
    JournalEntryLine.objects.create(
        journal_entry=je,
        account=disc_acct,
        debit_amount=applied_amount,
        credit_amount=Decimal('0.00'),
        description='Patient bill discount (expense)',
        ext_ref=str(patient.pk),
    )
    JournalEntryLine.objects.create(
        journal_entry=je,
        account=ar_acct,
        debit_amount=Decimal('0.00'),
        credit_amount=applied_amount,
        description='Reduce receivable — bill discount',
        ext_ref=str(patient.pk),
    )
    je.post(user=user)
    logger.info('Posted bill discount GL %s GHS %s patient=%s', ref, applied_amount, patient.pk)
    return je


def _line_discount_capacity(line):
    from hospital.models import InvoiceLine

    if not isinstance(line, InvoiceLine):
        return Decimal('0')
    if getattr(line, 'waived_at', None) or getattr(line, 'is_deleted', False):
        return Decimal('0')
    qty = Decimal(str(line.quantity or 0))
    unit = Decimal(str(line.unit_price or 0))
    tax = Decimal(str(line.tax_amount or 0))
    disc = Decimal(str(line.discount_amount or 0))
    subtotal = qty * unit
    cap = subtotal + tax - disc
    return max(Decimal('0'), cap)


def _apply_share_to_invoice_lines(invoice, share: Decimal) -> Decimal:
    """Increase discount_amount on invoice lines until `share` is distributed. Returns amount actually applied."""
    from hospital.models import InvoiceLine

    if share <= 0:
        return Decimal('0')
    lines = list(
        InvoiceLine.objects.filter(invoice=invoice, is_deleted=False, waived_at__isnull=True).order_by('created')
    )
    capacities = [(ln, _line_discount_capacity(ln)) for ln in lines]
    total_cap = sum(c for _, c in capacities)
    if total_cap <= 0:
        return Decimal('0')
    target = min(share, total_cap)
    remaining = target
    for idx, (line, cap) in enumerate(capacities):
        if remaining <= 0 or cap <= 0:
            continue
        if idx == len(capacities) - 1:
            portion = min(remaining, cap)
        else:
            portion = (target * (cap / total_cap)).quantize(Decimal('0.01'))
            portion = min(portion, cap, remaining)
        if portion <= 0:
            continue
        line.discount_amount = Decimal(str(line.discount_amount or 0)) + portion
        line.save()
        remaining -= portion
    if remaining > 0:
        for line, cap in capacities:
            if remaining <= 0:
                break
            extra = min(remaining, _line_discount_capacity(line))
            if extra <= 0:
                continue
            line.discount_amount = Decimal(str(line.discount_amount or 0)) + extra
            line.save()
            remaining -= extra
    return (target - remaining).quantize(Decimal('0.01'))


@transaction.atomic
def distribute_combined_bill_discount_across_invoices(
    invoices, discount_total, patient=None, user=None
):
    """
    invoices: iterable of Invoice (will be de-duplicated by pk).
    discount_total: positive Decimal; capped to sum of positive balances.
    patient, user: when both set, posts Dr 5135 Patient Bill Discounts / Cr 1200 A/R for the applied amount.

    Returns BillDiscountResult. Line discounts commit even if GL posting fails (savepoint rollback on GL only).
    """
    ensure_patient_bill_discount_chart_account()
    discount_total = Decimal(str(discount_total or 0))
    if discount_total <= 0:
        return BillDiscountResult(applied=Decimal('0'))

    seen = set()
    inv_list = []
    for inv in invoices:
        if inv is None or inv.pk in seen:
            continue
        seen.add(inv.pk)
        inv_list.append(inv)

    if not inv_list:
        return BillDiscountResult(applied=Decimal('0'))

    bal_by_inv = {}
    total_balance = Decimal('0')
    for inv in inv_list:
        inv.refresh_from_db()
        b = inv.balance or Decimal('0')
        if b > 0:
            bal_by_inv[inv] = b
            total_balance += b

    if total_balance <= 0:
        return BillDiscountResult(applied=Decimal('0'))

    applied = min(discount_total, total_balance)
    inv_items = list(bal_by_inv.items())
    allocated_sum = Decimal('0.00')
    actual_applied = Decimal('0.00')
    for idx, (inv, bal) in enumerate(inv_items):
        if idx == len(inv_items) - 1:
            share = (applied - allocated_sum).quantize(Decimal('0.01'))
        else:
            share = (applied * (bal / total_balance)).quantize(Decimal('0.01'))
            allocated_sum += share
        actual_applied += _apply_share_to_invoice_lines(inv, share)

    for inv in bal_by_inv:
        inv.update_totals()

    gl_posted = False
    gl_error = ''
    if actual_applied > 0 and patient is not None and user is not None:
        try:
            with transaction.atomic():
                post_patient_bill_discount_to_general_ledger(actual_applied, patient, user)
            gl_posted = True
        except Exception as exc:
            logger.exception(
                'Bill discount GL post failed patient=%s amount=%s',
                getattr(patient, 'pk', patient),
                actual_applied,
            )
            gl_error = str(exc)

    return BillDiscountResult(applied=actual_applied, gl_posted=gl_posted, gl_error=gl_error)
