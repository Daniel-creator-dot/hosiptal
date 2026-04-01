"""
Signals for Patient Deposit System
Accounting hooks for deposits and applications (auto-apply on invoice issue is disabled).
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


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
    Create accounting entries when a patient deposit is created
    Deposits are liabilities (money owed to patients) until applied to invoices
    """
    if not created:
        return
    
    try:
        from .models_accounting import Transaction
        from .models_accounting_advanced import (
            AdvancedJournalEntry, AdvancedJournalEntryLine, Journal, Account
        )
        
        # Get or create Patient Deposits liability account
        deposits_account, _ = Account.objects.get_or_create(
            account_code='2100',
            defaults={
                'account_name': 'Patient Deposits',
                'account_type': 'liability',
                'description': 'Money received from patients before treatment (liability until applied)'
            }
        )
        
        # Get or create Cash account
        cash_account, _ = Account.objects.get_or_create(
            account_code='1000',
            defaults={
                'account_name': 'Cash on Hand',
                'account_type': 'asset'
            }
        )
        
        # Check for duplicate transaction before creating
        existing_transaction = Transaction.objects.filter(
            transaction_type='deposit_received',
            reference_number=instance.deposit_number,
            is_deleted=False
        ).first()
        
        if existing_transaction:
            # Duplicate found - use existing transaction
            transaction = existing_transaction
        else:
            # Create transaction
            transaction = Transaction.objects.create(
                transaction_type='deposit_received',
                patient=instance.patient,
                amount=instance.deposit_amount,
                payment_method=instance.payment_method,
                reference_number=instance.deposit_number,
                processed_by=instance.received_by,
                transaction_date=instance.deposit_date,
                notes=f'Patient deposit {instance.deposit_number}'
            )
        
        instance.transaction = transaction
        instance.save(update_fields=['transaction'])
        
        # Create journal entry
        journal, _ = Journal.objects.get_or_create(
            code='CASH',
            defaults={'name': 'Cash Journal', 'journal_type': 'cash'}
        )
        
        amount = instance.deposit_amount
        je = AdvancedJournalEntry.objects.create(
            journal=journal,
            entry_date=instance.deposit_date.date() if hasattr(instance.deposit_date, 'date') else instance.deposit_date,
            description=f"Patient deposit received: {instance.patient.full_name} - {instance.deposit_number}",
            reference=instance.deposit_number,
            created_by=instance.created_by,
            status='draft',
            total_debit=amount,
            total_credit=amount,
        )
        
        # Debit: Cash (Asset increases)
        AdvancedJournalEntryLine.objects.create(
            journal_entry=je,
            line_number=1,
            account=cash_account,
            description=f"Cash received from {instance.patient.full_name}",
            debit_amount=amount,
            credit_amount=Decimal('0.00'),
            patient=instance.patient,
        )
        
        # Credit: Patient Deposits (Liability increases)
        AdvancedJournalEntryLine.objects.create(
            journal_entry=je,
            line_number=2,
            account=deposits_account,
            description=f"Deposit liability for {instance.patient.full_name}",
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
            f"Cash +GHS {instance.deposit_amount}, Deposits Liability +GHS {instance.deposit_amount}"
        )
    
    except Exception as e:
        logger.error(f"Error creating accounting entries for deposit {instance.deposit_number}: {e}", exc_info=True)


@receiver(post_save, sender='hospital.DepositApplication')
def create_accounting_entries_for_application(sender, instance, created, **kwargs):
    """
    Create accounting entries when a deposit is applied to an invoice
    Moves money from Patient Deposits (liability) to Revenue
    """
    if not created:
        return
    
    try:
        from .models_accounting_advanced import (
            AdvancedJournalEntry, AdvancedJournalEntryLine, Journal, Account, Revenue, RevenueCategory
        )
        
        # Get accounts
        deposits_account, _ = Account.objects.get_or_create(
            account_code='2100',
            defaults={
                'account_name': 'Patient Deposits',
                'account_type': 'liability'
            }
        )
        
        revenue_account, _ = Account.objects.get_or_create(
            account_code='4000',
            defaults={
                'account_name': 'Patient Services Revenue',
                'account_type': 'revenue'
            }
        )
        
        # Get or create revenue category
        revenue_category, _ = RevenueCategory.objects.get_or_create(
            code='REV-PATIENT',
            defaults={'name': 'Patient Services', 'account': revenue_account}
        )
        
        # Create revenue entry
        revenue = Revenue.objects.create(
            revenue_date=instance.applied_date.date() if hasattr(instance.applied_date, 'date') else instance.applied_date,
            category=revenue_category,
            description=f"Revenue from deposit application: Invoice {instance.invoice.invoice_number}",
            amount=instance.applied_amount,
            patient=instance.deposit.patient,
            invoice=instance.invoice,
            payment_method='deposit',
            reference=f"DEP-{instance.deposit.deposit_number}",
            recorded_by=instance.applied_by,
        )
        
        # Create journal entry
        journal, _ = Journal.objects.get_or_create(
            code='REV',
            defaults={'name': 'Revenue Journal', 'journal_type': 'revenue'}
        )
        
        amount = instance.applied_amount
        je = AdvancedJournalEntry.objects.create(
            journal=journal,
            entry_date=instance.applied_date.date() if hasattr(instance.applied_date, 'date') else instance.applied_date,
            description=f"Deposit applied to invoice: {instance.invoice.invoice_number}",
            reference=f"DEP-{instance.deposit.deposit_number}",
            created_by=instance.applied_by,
            status='draft',
            total_debit=amount,
            total_credit=amount,
        )
        
        # Debit: Patient Deposits (Liability decreases)
        AdvancedJournalEntryLine.objects.create(
            journal_entry=je,
            line_number=1,
            account=deposits_account,
            description=f"Deposit applied: {instance.deposit.deposit_number}",
            debit_amount=amount,
            credit_amount=Decimal('0.00'),
            patient=instance.deposit.patient,
        )
        
        # Credit: Revenue (Revenue increases)
        AdvancedJournalEntryLine.objects.create(
            journal_entry=je,
            line_number=2,
            account=revenue_account,
            description=f"Revenue from invoice {instance.invoice.invoice_number}",
            debit_amount=Decimal('0.00'),
            credit_amount=amount,
            patient=instance.deposit.patient,
        )
        
        je.post(instance.applied_by)
        
        logger.info(
            f"Created accounting entries for deposit application: "
            f"Deposits Liability -GHS {instance.applied_amount}, Revenue +GHS {instance.applied_amount}"
        )
    
    except Exception as e:
        logger.error(f"Error creating accounting entries for deposit application: {e}", exc_info=True)





