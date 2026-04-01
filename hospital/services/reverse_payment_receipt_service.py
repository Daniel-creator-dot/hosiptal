"""
Reverse a patient PaymentReceipt when no cash was actually taken (administrative reversal).

Soft-deletes the receipt and its Transaction, clears lab/pharmacy/imaging clearance links,
soft-deletes auto cashbook rows, and voids linked Revenue / ReceiptVoucher / journal entry
when they were created from the same payment transaction.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def reverse_payment_receipt_by_number(
    receipt_number: str,
    *,
    dry_run: bool = False,
    reason: str = '',
) -> dict:
    """
    Reverse one active PaymentReceipt by its public receipt_number (e.g. RCP...).

    Returns a dict with keys: ok, message, receipt_id, invoice_id, amount, dry_run, steps (list).
    Raises ValueError if receipt not found or already reversed.
    """
    from hospital.models_accounting import PaymentAllocation, PaymentReceipt, Transaction
    from hospital.models_accounting_advanced import (
        AdvancedJournalEntry,
        Cashbook,
        ReceiptVoucher,
        Revenue,
    )

    receipt_number = (receipt_number or '').strip()
    if not receipt_number:
        raise ValueError('receipt_number is required')

    rec = PaymentReceipt.objects.filter(
        receipt_number=receipt_number,
        is_deleted=False,
    ).select_related('invoice', 'patient', 'transaction').first()
    if not rec:
        raise ValueError(f'No active payment receipt with number {receipt_number!r}')

    steps: list[str] = []
    amount = rec.amount_paid
    inv = rec.invoice
    txn = rec.transaction

    if dry_run:
        return {
            'ok': True,
            'message': 'Dry run only; no changes made.',
            'receipt_id': str(rec.pk),
            'invoice_id': str(inv.pk) if inv else None,
            'patient_id': str(rec.patient_id) if rec.patient_id else None,
            'amount': str(amount),
            'transaction_number': txn.transaction_number if txn else None,
            'dry_run': True,
            'steps': ['Would soft-delete receipt, transaction, allocations, clearance links, cashbook, revenue/RV/JE when linked.'],
        }

    with db_transaction.atomic():
        rec_locked = (
            PaymentReceipt.objects.select_for_update(of=('self',))
            .filter(pk=rec.pk, is_deleted=False)
            .first()
        )
        if not rec_locked:
            raise ValueError(f'Receipt {receipt_number} was already reversed or deleted.')
        rec = rec_locked
        txn = rec.transaction

        # Payment allocations (combined payments)
        if txn:
            alloc_count = PaymentAllocation.objects.filter(
                payment_transaction=txn,
                is_deleted=False,
            ).update(is_deleted=True, modified=timezone.now())
            if alloc_count:
                steps.append(f'Soft-deleted {alloc_count} payment allocation(s).')

            txn_ref = txn.transaction_number
            txn_id = txn.pk

            # Auto-posted revenue / receipt voucher / JE (signals_accounting)
            revenues = list(
                Revenue.objects.filter(reference=txn_ref, is_deleted=False).select_for_update(of=('self',))
            )
            je_ids = set()
            for rev in revenues:
                if rev.journal_entry_id:
                    je_ids.add(rev.journal_entry_id)
            for rv in ReceiptVoucher.objects.filter(reference=txn_ref, is_deleted=False).select_for_update(
                of=('self',)
            ):
                if rv.journal_entry_id:
                    je_ids.add(rv.journal_entry_id)

            for je in AdvancedJournalEntry.objects.filter(pk__in=je_ids, is_deleted=False).select_for_update(
                of=('self',)
            ):
                if je.status == 'posted':
                    try:
                        je.void()
                        steps.append(f'Voided journal entry {je.entry_number}.')
                    except Exception as e:
                        logger.warning('Could not void journal %s: %s', je.entry_number, e)
                        steps.append(f'Journal {je.entry_number} not voided ({e}).')

            rv_count = ReceiptVoucher.objects.filter(reference=txn_ref, is_deleted=False).update(
                status='void', modified=timezone.now()
            )
            if rv_count:
                steps.append(f'Voided {rv_count} receipt voucher(s) for reference {txn_ref}.')

            rev_del = Revenue.objects.filter(reference=txn_ref, is_deleted=False).update(
                is_deleted=True, modified=timezone.now()
            )
            if rev_del:
                steps.append(f'Soft-deleted {rev_del} revenue row(s).')

            # Advanced AR (cash payer path in signal)
            if inv:
                try:
                    from hospital.models_accounting_advanced import AdvancedAccountsReceivable

                    ar = (
                        AdvancedAccountsReceivable.objects.filter(invoice=inv, is_deleted=False)
                        .select_for_update(of=('self',))
                        .first()
                    )
                    if ar and (ar.amount_paid or Decimal('0')) >= (txn.amount or Decimal('0')):
                        ar.amount_paid = max(
                            Decimal('0.00'),
                            (ar.amount_paid or Decimal('0')) - (txn.amount or Decimal('0')),
                        )
                        ar.balance_due = (ar.invoice_amount or Decimal('0')) - ar.amount_paid
                        ar.save(update_fields=['amount_paid', 'balance_due', 'modified'])
                        steps.append('Adjusted AdvancedAccountsReceivable for invoice.')
                except Exception as e:
                    logger.warning('AR adjustment skipped: %s', e)

            Transaction.objects.filter(pk=txn_id, is_deleted=False).update(
                is_deleted=True, modified=timezone.now()
            )
            steps.append(f'Soft-deleted transaction {txn_ref}.')

        # Lab / pharmacy / imaging release rows pointing at this receipt
        from hospital.models_payment_verification import (
            ImagingRelease,
            LabResultRelease,
            PaymentVerification,
            PharmacyDispensing,
            ReceiptQRCode,
        )

        n_lab = 0
        for lr in LabResultRelease.objects.filter(payment_receipt=rec, is_deleted=False):
            lr.payment_receipt = None
            lr.payment_verified_at = None
            lr.payment_verified_by = None
            if lr.release_status == 'ready_for_release':
                lr.release_status = 'pending_payment'
            lr.save(
                update_fields=[
                    'payment_receipt',
                    'payment_verified_at',
                    'payment_verified_by',
                    'release_status',
                    'modified',
                ]
            )
            n_lab += 1
        if n_lab:
            steps.append(f'Cleared lab release payment link(s): {n_lab}.')

        n_ph = 0
        for pd in PharmacyDispensing.objects.filter(payment_receipt=rec, is_deleted=False):
            pd.payment_receipt = None
            pd.payment_verified_at = None
            pd.payment_verified_by = None
            if pd.dispensing_status == 'ready_to_dispense':
                pd.dispensing_status = 'pending_payment'
            pd.save(
                update_fields=[
                    'payment_receipt',
                    'payment_verified_at',
                    'payment_verified_by',
                    'dispensing_status',
                    'modified',
                ]
            )
            n_ph += 1
        if n_ph:
            steps.append(f'Cleared pharmacy dispensing payment link(s): {n_ph}.')

        n_img = 0
        for ir in ImagingRelease.objects.filter(payment_receipt=rec, is_deleted=False):
            ir.payment_receipt = None
            ir.payment_verified_at = None
            ir.payment_verified_by = None
            if ir.release_status == 'ready_for_release':
                ir.release_status = 'pending_payment'
            ir.save(
                update_fields=[
                    'payment_receipt',
                    'payment_verified_at',
                    'payment_verified_by',
                    'release_status',
                    'modified',
                ]
            )
            n_img += 1
        if n_img:
            steps.append(f'Cleared imaging release payment link(s): {n_img}.')

        pv_count = PaymentVerification.objects.filter(receipt=rec, is_deleted=False).update(
            is_deleted=True, modified=timezone.now()
        )
        if pv_count:
            steps.append(f'Soft-deleted {pv_count} payment verification row(s).')

        try:
            from hospital.models_advanced import ImagingStudy

            ImagingStudy.objects.filter(payment_receipt_number=receipt_number, is_deleted=False).update(
                payment_receipt_number='',
                modified=timezone.now(),
            )
        except Exception:
            pass

        # Dispense history audit rows (keep row, clear receipt FK)
        try:
            from hospital.models_payment_verification import PharmacyDispenseHistory

            PharmacyDispenseHistory.objects.filter(payment_receipt=rec).update(
                payment_receipt=None, modified=timezone.now()
            )
        except Exception:
            pass

        ReceiptQRCode.objects.filter(receipt=rec, is_deleted=False).update(
            is_deleted=True, modified=timezone.now()
        )

        # Cashbook auto rows (reference = receipt number or transaction number)
        refs = [receipt_number]
        if txn:
            refs.append(txn.transaction_number)
        cb_q = Cashbook.objects.filter(is_deleted=False, reference__in=refs)
        cb_n = cb_q.update(is_deleted=True, modified=timezone.now())
        if cb_n:
            steps.append(f'Soft-deleted {cb_n} cashbook entr(y/ies).')

        rec.is_deleted = True
        rec.save(update_fields=['is_deleted', 'modified'])
        steps.append(f'Soft-deleted payment receipt {receipt_number}.')

        if inv:
            inv.calculate_totals()
            inv.save(update_fields=['total_amount', 'balance', 'status', 'modified'])
            steps.append(
                f'Recalculated invoice {inv.invoice_number}: balance GHS {inv.balance}, status {inv.status}.'
            )

    msg = '; '.join(steps)
    logger.info('Reversed payment receipt %s: %s', receipt_number, msg)
    return {
        'ok': True,
        'message': msg,
        'receipt_id': str(rec.pk),
        'invoice_id': str(inv.pk) if inv else None,
        'patient_id': str(rec.patient_id) if rec.patient_id else None,
        'amount': str(amount),
        'dry_run': False,
        'steps': steps,
    }
