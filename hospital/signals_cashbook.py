"""
Cashbook Auto-Recording Signals
Automatically creates cashbook entries when payments are received
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

from .models_accounting import Transaction, PaymentReceipt
from .models_accounting_advanced import Cashbook, Account

AUTO_CASHBOOK_ENABLED = True


@receiver(post_save, sender=Transaction)
def auto_create_cashbook_entry_on_payment(sender, instance, created, **kwargs):
    """
    Automatically create cashbook entry when payment is received
    """
    if not AUTO_CASHBOOK_ENABLED or not created:
        return
    
    if instance.transaction_type != 'payment_received':
        return
    
    try:
        with transaction.atomic():
            # Get or create cash account
            cash_account, _ = Account.objects.get_or_create(
                account_code='1000',
                defaults={
                    'account_name': 'Cash on Hand',
                    'account_type': 'asset',
                    'is_active': True,
                }
            )
            
            # Check if cashbook entry already exists for this transaction
            existing = Cashbook.objects.filter(
                reference=instance.transaction_number,
                is_deleted=False
            ).first()
            
            if existing:
                logger.info(f"Cashbook entry already exists for transaction {instance.transaction_number}")
                return
            
            # Determine payment method for cashbook
            payment_method = instance.payment_method or 'cash'
            
            # Create cashbook entry
            cashbook_entry = Cashbook.objects.create(
                entry_type='receipt',
                entry_date=instance.transaction_date.date() if hasattr(instance.transaction_date, 'date') else instance.transaction_date,
                amount=instance.amount,
                payee_or_payer=instance.patient.full_name if instance.patient else 'Unknown',
                description=f"Payment received: {instance.transaction_number}",
                reference=instance.transaction_number,
                payment_method=payment_method,
                patient=instance.patient,
                invoice=instance.invoice,
                cash_account=cash_account,
                status='pending',
                created_by=instance.processed_by,
            )
            
            logger.info(
                f"✅ Auto-created cashbook entry {cashbook_entry.entry_number} "
                f"for payment {instance.transaction_number} - GHS {instance.amount}"
            )
            
    except Exception as e:
        logger.error(f"❌ Error creating cashbook entry for transaction {instance.id}: {e}", exc_info=True)


@receiver(post_save, sender=PaymentReceipt)
def auto_create_cashbook_entry_on_receipt(sender, instance, created, **kwargs):
    """
    Automatically create cashbook entry when payment receipt is created
    (Backup signal in case Transaction signal doesn't fire)
    """
    if not AUTO_CASHBOOK_ENABLED or not created:
        return
    
    try:
        with transaction.atomic():
            # Get or create cash account
            cash_account, _ = Account.objects.get_or_create(
                account_code='1000',
                defaults={
                    'account_name': 'Cash on Hand',
                    'account_type': 'asset',
                    'is_active': True,
                }
            )
            
            # Check if cashbook entry already exists
            existing = Cashbook.objects.filter(
                reference=instance.receipt_number if hasattr(instance, 'receipt_number') else str(instance.id),
                is_deleted=False
            ).first()
            
            if existing:
                return
            
            # Get transaction if linked
            trans = getattr(instance, 'transaction', None)
            if not trans:
                return
            
            # Create cashbook entry
            cashbook_entry = Cashbook.objects.create(
                entry_type='receipt',
                entry_date=instance.received_at.date() if hasattr(instance.received_at, 'date') else timezone.now().date(),
                amount=instance.amount_paid,
                payee_or_payer=instance.patient.full_name if instance.patient else 'Unknown',
                description=f"Payment receipt: {instance.id}",
                reference=getattr(instance, 'receipt_number', str(instance.id)),
                payment_method=instance.payment_method or 'cash',
                patient=instance.patient,
                invoice=getattr(instance, 'invoice', None),
                cash_account=cash_account,
                status='pending',
                created_by=instance.received_by,
            )
            
            logger.info(
                f"✅ Auto-created cashbook entry {cashbook_entry.entry_number} "
                f"for receipt {instance.id} - GHS {instance.amount_paid}"
            )
            
    except Exception as e:
        logger.error(f"❌ Error creating cashbook entry for receipt {instance.id}: {e}", exc_info=True)








