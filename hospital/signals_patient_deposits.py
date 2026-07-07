"""
Signals for Patient Deposit System
Accounting hooks for deposits and applications (auto-apply on invoice issue is disabled).
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
import logging

from hospital.services.receipt_revenue_allocation import allocate_payment_to_revenue_accounts
from hospital.services.service_account_mapping import (
    CUSTOMER_DEPOSITS_CODE,
    CUSTOMER_DEPOSITS_NAME,
    resolve_payment_account_meta,
    resolve_revenue_account_meta,
)

logger = logging.getLogger(__name__)


def _ensure_account(code, name, account_type):
    from hospital.models_accounting import Account

    account, _ = Account.objects.get_or_create(
        account_code=code,
        defaults={'account_name': name, 'account_type': account_type, 'is_active': True},
    )
    return account


@receiver(post_save, sender='hospital.Invoice')
def auto_apply_deposits_to_invoice(sender, instance, created, **kwargs):
    """
    Deposit application to issued invoices is cashier-driven (Apply deposit to bill / manual apply).
    Auto-apply on issue is disabled so balances stay full until the cashier applies deposit.
    """
    return


@receiver(post_save, sender='hospital.PatientDeposit')
def create_accounting_entries_for_deposit(sender, instance, created, **kwargs):
    """
    Create accounting entries when a patient deposit is created.
    Dr Cash and Cash Equivalents / Cr Customer Deposits liability.
    """
    if not created:
        return

    try:
        from .models_accounting import Transaction
        from .models_accounting_advanced import (
            AdvancedJournalEntry,
            AdvancedJournalEntryLine,
            Journal,
        )

        deposits_account = _ensure_account(
            CUSTOMER_DEPOSITS_CODE, CUSTOMER_DEPOSITS_NAME, 'liability'
        )
        pay_code, pay_name = resolve_payment_account_meta(instance.payment_method)
        cash_account = _ensure_account(pay_code, pay_name, 'asset')

        existing_transaction = Transaction.objects.filter(
            transaction_type='deposit_received',
            reference_number=instance.deposit_number,
            is_deleted=False,
        ).first()

        if existing_transaction:
            transaction = existing_transaction
        else:
            transaction = Transaction.objects.create(
                transaction_type='deposit_received',
                patient=instance.patient,
                amount=instance.deposit_amount,
                payment_method=instance.payment_method,
                reference_number=instance.deposit_number,
                processed_by=instance.received_by,
                transaction_date=instance.deposit_date,
                notes=f'Patient deposit {instance.deposit_number}',
            )

        instance.transaction = transaction
        instance.save(update_fields=['transaction'])

        journal, _ = Journal.objects.get_or_create(
            code='CASH',
            defaults={'name': 'Cash Journal', 'journal_type': 'cash'},
        )

        amount = instance.deposit_amount
        je = AdvancedJournalEntry.objects.create(
            journal=journal,
            entry_date=(
                instance.deposit_date.date()
                if hasattr(instance.deposit_date, 'date')
                else instance.deposit_date
            ),
            description=(
                f"Patient deposit received: {instance.patient.full_name} - "
                f"{instance.deposit_number}"
            ),
            reference=instance.deposit_number,
            created_by=instance.created_by,
            status='draft',
            total_debit=amount,
            total_credit=amount,
        )

        AdvancedJournalEntryLine.objects.create(
            journal_entry=je,
            line_number=1,
            account=cash_account,
            description=f"Cash received from {instance.patient.full_name}",
            debit_amount=amount,
            credit_amount=Decimal('0.00'),
            patient=instance.patient,
        )

        AdvancedJournalEntryLine.objects.create(
            journal_entry=je,
            line_number=2,
            account=deposits_account,
            description=f"Customer deposit liability for {instance.patient.full_name}",
            debit_amount=Decimal('0.00'),
            credit_amount=amount,
            patient=instance.patient,
        )

        post_user = getattr(instance, 'received_by', None) or instance.created_by
        je.post(post_user)

        instance.journal_entry = je
        instance.save(update_fields=['journal_entry'])

        logger.info(
            f"Created accounting entries for deposit {instance.deposit_number}: "
            f"Cash +GHS {instance.deposit_amount}, Customer Deposits +GHS {instance.deposit_amount}"
        )

    except Exception as e:
        logger.error(
            f"Error creating accounting entries for deposit {instance.deposit_number}: {e}",
            exc_info=True,
        )


@receiver(post_save, sender='hospital.DepositApplication')
def create_accounting_entries_for_application(sender, instance, created, **kwargs):
    """
    Create accounting entries when a deposit is applied to an invoice.
    Dr Customer Deposits / Cr stream-specific revenue accounts.
    """
    if not created:
        return

    try:
        from .models_accounting_advanced import (
            AdvancedJournalEntry,
            AdvancedJournalEntryLine,
            Journal,
            Revenue,
            RevenueCategory,
        )

        deposits_account = _ensure_account(
            CUSTOMER_DEPOSITS_CODE, CUSTOMER_DEPOSITS_NAME, 'liability'
        )

        amount = instance.applied_amount
        splits = allocate_payment_to_revenue_accounts(instance.invoice, amount)
        primary_service_type = splits[0][0] if splits else 'other'
        primary_rev_code, primary_rev_name = resolve_revenue_account_meta(primary_service_type)
        primary_revenue_account = _ensure_account(primary_rev_code, primary_rev_name, 'revenue')

        revenue_category, _ = RevenueCategory.objects.get_or_create(
            code=f'REV-{primary_rev_code}',
            defaults={'name': primary_rev_name, 'account': primary_revenue_account},
        )

        split_desc = ', '.join(f'{st} GHS {amt}' for st, amt in splits)
        revenue = Revenue.objects.create(
            revenue_date=(
                instance.applied_date.date()
                if hasattr(instance.applied_date, 'date')
                else instance.applied_date
            ),
            category=revenue_category,
            description=(
                f"Revenue from deposit application: Invoice {instance.invoice.invoice_number} "
                f"({split_desc})"
            ),
            amount=amount,
            patient=instance.deposit.patient,
            invoice=instance.invoice,
            payment_method='deposit',
            reference=f"DEP-{instance.deposit.deposit_number}",
            recorded_by=instance.applied_by,
        )

        journal, _ = Journal.objects.get_or_create(
            code='REV',
            defaults={'name': 'Revenue Journal', 'journal_type': 'revenue'},
        )

        je = AdvancedJournalEntry.objects.create(
            journal=journal,
            entry_date=(
                instance.applied_date.date()
                if hasattr(instance.applied_date, 'date')
                else instance.applied_date
            ),
            description=f"Deposit applied to invoice: {instance.invoice.invoice_number}",
            reference=f"DEP-{instance.deposit.deposit_number}",
            created_by=instance.applied_by,
            status='draft',
            total_debit=amount,
            total_credit=amount,
            invoice=instance.invoice,
        )

        line_number = 1
        AdvancedJournalEntryLine.objects.create(
            journal_entry=je,
            line_number=line_number,
            account=deposits_account,
            description=f"Deposit applied: {instance.deposit.deposit_number}",
            debit_amount=amount,
            credit_amount=Decimal('0.00'),
            patient=instance.deposit.patient,
        )
        line_number += 1

        for svc_type, share in splits:
            rev_code, rev_name = resolve_revenue_account_meta(svc_type)
            revenue_account = _ensure_account(rev_code, rev_name, 'revenue')
            AdvancedJournalEntryLine.objects.create(
                journal_entry=je,
                line_number=line_number,
                account=revenue_account,
                description=f'{rev_name} from deposit apply ({svc_type})',
                debit_amount=Decimal('0.00'),
                credit_amount=share,
                patient=instance.deposit.patient,
            )
            line_number += 1

        je.post(instance.applied_by)
        revenue.journal_entry = je
        revenue.save(update_fields=['journal_entry'])

        logger.info(
            f"Created accounting entries for deposit application: "
            f"Customer Deposits -GHS {instance.applied_amount}, Revenue +GHS {instance.applied_amount}"
        )

    except Exception as e:
        logger.error(
            f"Error creating accounting entries for deposit application: {e}",
            exc_info=True,
        )


@receiver(post_save, sender='hospital.Transaction')
def create_accounting_entries_for_deposit_refund(sender, instance, created, **kwargs):
    """Post Dr Customer Deposits / Cr Cash when a patient deposit refund is recorded."""
    if not created:
        return
    if instance.transaction_type != 'refund':
        return
    ref = (instance.reference_number or '')
    if not ref.startswith('REFUND-'):
        return

    try:
        from .models_accounting_advanced import (
            AdvancedJournalEntry,
            AdvancedJournalEntryLine,
            Journal,
        )

        if AdvancedJournalEntry.objects.filter(
            reference=ref, status='posted', is_deleted=False
        ).exists():
            return

        deposits_account = _ensure_account(
            CUSTOMER_DEPOSITS_CODE, CUSTOMER_DEPOSITS_NAME, 'liability'
        )
        pay_code, pay_name = resolve_payment_account_meta(instance.payment_method)
        cash_account = _ensure_account(pay_code, pay_name, 'asset')

        journal, _ = Journal.objects.get_or_create(
            code='CASH',
            defaults={'name': 'Cash Journal', 'journal_type': 'cash'},
        )

        amount = instance.amount
        je = AdvancedJournalEntry.objects.create(
            journal=journal,
            entry_date=(
                instance.transaction_date.date()
                if hasattr(instance.transaction_date, 'date')
                else instance.transaction_date
            ),
            description=f"Patient deposit refund: {ref}",
            reference=ref,
            created_by=instance.processed_by,
            status='draft',
            total_debit=amount,
            total_credit=amount,
        )

        AdvancedJournalEntryLine.objects.create(
            journal_entry=je,
            line_number=1,
            account=deposits_account,
            description=f"Customer deposit refunded: {ref}",
            debit_amount=amount,
            credit_amount=Decimal('0.00'),
            patient=instance.patient,
        )

        AdvancedJournalEntryLine.objects.create(
            journal_entry=je,
            line_number=2,
            account=cash_account,
            description=f"Cash refunded: {ref}",
            debit_amount=Decimal('0.00'),
            credit_amount=amount,
            patient=instance.patient,
        )

        je.post(instance.processed_by)

        logger.info(
            f"Created accounting entries for deposit refund {ref}: "
            f"Customer Deposits -GHS {amount}, Cash -GHS {amount}"
        )

    except Exception as e:
        logger.error(
            f"Error creating accounting entries for deposit refund {ref}: {e}",
            exc_info=True,
        )
