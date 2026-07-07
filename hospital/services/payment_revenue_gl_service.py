"""
Post cash payment revenue to Advanced GL using Primecare account codes.
Idempotent per Transaction reference.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from hospital.models_accounting import Account, PaymentReceipt, Transaction
from hospital.models_accounting_advanced import (
    AdvancedJournalEntry,
    AdvancedJournalEntryLine,
    Journal,
    ReceiptVoucher,
    Revenue,
    RevenueCategory,
)
from hospital.services.receipt_revenue_allocation import revenue_splits_for_transaction
from hospital.services.service_account_mapping import (
    resolve_payment_account_meta,
    resolve_revenue_account_meta,
)

logger = logging.getLogger(__name__)

D0 = Decimal('0.00')


def _ensure_account(code, name, account_type):
    account, _ = Account.objects.get_or_create(
        account_code=code,
        defaults={'account_name': name, 'account_type': account_type, 'is_active': True},
    )
    return account


def post_payment_revenue_gl(payment_transaction):
    """
    Dr Cash (1010 etc.) / Cr Revenue (4120/4130/4190 etc.) for a payment_received Transaction.
    Mixed invoices get multiple credit lines by line stream allocation.
    Returns dict with success flag; skips deposits and duplicate postings.
    """
    if not payment_transaction or payment_transaction.transaction_type != 'payment_received':
        return {'success': False, 'posted': False, 'message': 'Not a payment receipt transaction'}

    if getattr(payment_transaction, 'payment_method', None) == 'deposit':
        return {'success': True, 'posted': False, 'message': 'Deposit application — skipped'}

    ref = payment_transaction.transaction_number

    with transaction.atomic():
        txn = Transaction.objects.select_for_update().get(pk=payment_transaction.pk)
        if AdvancedJournalEntry.objects.filter(
            reference=ref, status='posted', is_deleted=False
        ).exists():
            return {'success': True, 'posted': False, 'already_posted': True, 'message': 'Already posted'}

        receipt = PaymentReceipt.objects.filter(
            transaction=txn, is_deleted=False
        ).first()
        splits = revenue_splits_for_transaction(txn, receipt)
        primary_service_type = splits[0][0] if splits else 'other'

        pay_code, pay_name = resolve_payment_account_meta(txn.payment_method)
        cash_account = _ensure_account(pay_code, pay_name, 'asset')

        amount = txn.amount
        entry_date = txn.transaction_date.date() if hasattr(
            txn.transaction_date, 'date'
        ) else txn.transaction_date

        primary_rev_code, primary_rev_name = resolve_revenue_account_meta(primary_service_type)
        primary_revenue_account = _ensure_account(primary_rev_code, primary_rev_name, 'revenue')

        revenue_category, _ = RevenueCategory.objects.get_or_create(
            code=f'REV-{primary_rev_code}',
            defaults={'name': primary_rev_name, 'account': primary_revenue_account},
        )

        split_desc = ', '.join(f'{st} GHS {amt}' for st, amt in splits)
        revenue = Revenue.objects.create(
            revenue_date=entry_date,
            category=revenue_category,
            description=(
                f"Payment: {txn.patient.full_name if txn.patient else 'Patient'} "
                f"- {ref} ({split_desc})"
            ),
            amount=amount,
            patient=txn.patient,
            invoice=txn.invoice,
            payment_method=txn.payment_method,
            reference=ref,
            recorded_by=txn.processed_by,
        )

        receipt_voucher = ReceiptVoucher.objects.create(
            receipt_date=entry_date,
            received_from=(
                txn.patient.full_name if txn.patient else 'Patient'
            ),
            patient=txn.patient,
            amount=amount,
            payment_method=txn.payment_method,
            description=revenue.description,
            reference=ref,
            status='issued',
            revenue_account=primary_revenue_account,
            cash_account=cash_account,
            invoice=txn.invoice,
            received_by=txn.processed_by,
        )

        journal = Journal.objects.filter(journal_type='receipt').first()
        if not journal:
            journal, _ = Journal.objects.get_or_create(
                code='RCPT',
                defaults={'name': 'Receipt Journal', 'journal_type': 'receipt'},
            )

        je = AdvancedJournalEntry.objects.create(
            journal=journal,
            entry_date=entry_date,
            description=revenue.description,
            reference=ref,
            status='draft',
            total_debit=amount,
            total_credit=amount,
            created_by=txn.processed_by,
            invoice=txn.invoice,
        )

        line_number = 1
        AdvancedJournalEntryLine.objects.create(
            journal_entry=je,
            line_number=line_number,
            account=cash_account,
            description=f'Cash received ({pay_code})',
            debit_amount=amount,
            credit_amount=D0,
            patient=txn.patient,
        )
        line_number += 1
        for svc_type, share in splits:
            rev_code, rev_name = resolve_revenue_account_meta(svc_type)
            revenue_account = _ensure_account(rev_code, rev_name, 'revenue')
            AdvancedJournalEntryLine.objects.create(
                journal_entry=je,
                line_number=line_number,
                account=revenue_account,
                description=f'{rev_name} ({svc_type})',
                debit_amount=D0,
                credit_amount=share,
                patient=txn.patient,
            )
            line_number += 1

        je.post(txn.processed_by)
        revenue.journal_entry = je
        revenue.save(update_fields=['journal_entry'])
        receipt_voucher.journal_entry = je
        receipt_voucher.save(update_fields=['journal_entry'])

    credit_codes = [
        resolve_revenue_account_meta(st)[0] for st, _ in splits
    ]
    logger.info(
        '[AUTO-SYNC] Posted payment revenue Dr %s / Cr %s GHS %s ref %s',
        pay_code, '+'.join(credit_codes), amount, ref,
    )
    return {
        'success': True,
        'posted': True,
        'debit_account': pay_code,
        'credit_account': credit_codes[0] if len(credit_codes) == 1 else credit_codes,
        'service_type': primary_service_type,
        'journal_entry': je,
    }
