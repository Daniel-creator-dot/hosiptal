"""
Accounting Signals - Auto-sync Everything
Automatic journal entry creation for all financial transactions
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction as db_transaction
from decimal import Decimal
from django.utils import timezone

# Import all models
from .models import Invoice
from .models_accounting import Transaction, Account
from .models_accounting_advanced import (
    Revenue, RevenueCategory, AdvancedAccountsReceivable,
    AdvancedJournalEntry, AdvancedJournalEntryLine, Journal,
    ReceiptVoucher
)


# Enable/disable auto-sync (can be toggled)
AUTO_SYNC_ENABLED = True


@receiver(post_save, sender=Invoice)
def auto_create_ar_on_invoice(sender, instance, created, **kwargs):
    """Auto-create AR when invoice is created"""
    if not AUTO_SYNC_ENABLED or not created:
        return
    
    if instance.status not in ['issued', 'partially_paid', 'overdue']:
        return
    
    try:
        ar, ar_created = AdvancedAccountsReceivable.objects.get_or_create(
            invoice=instance,
            defaults={
                'patient': instance.patient,
                'invoice_amount': instance.total_amount,
                'amount_paid': Decimal('0.00'),
                'balance_due': instance.total_amount,
                'due_date': instance.due_date or (timezone.now().date() + timezone.timedelta(days=30)),
            }
        )
        
        if ar_created:
            print(f"[AUTO-SYNC] Invoice {instance.invoice_number} to AR GHS {instance.total_amount}")
    
    except Exception as e:
        print(f"[AUTO-SYNC ERROR] AR creation failed: {e}")


@receiver(post_save, sender=Transaction)
def auto_create_revenue_on_payment(sender, instance, created, **kwargs):
    """
    Auto-create revenue, receipt voucher, and journal entry when payment received
    """
    if not AUTO_SYNC_ENABLED or not created:
        return
    
    if instance.transaction_type != 'payment_received':
        return
    
    try:
        with db_transaction.atomic():
            # Get default accounts
            cash_account, _ = Account.objects.get_or_create(
                account_code='1000',
                defaults={'account_name': 'Cash on Hand', 'account_type': 'asset'}
            )
            
            revenue_account, _ = Account.objects.get_or_create(
                account_code='4000',
                defaults={'account_name': 'Patient Services Revenue', 'account_type': 'revenue'}
            )
            
            # Get revenue category
            revenue_category, _ = RevenueCategory.objects.get_or_create(
                code='REV-PATIENT',
                defaults={'name': 'Patient Services', 'account': revenue_account}
            )
            
            # Create revenue entry
            revenue = Revenue.objects.create(
                revenue_date=instance.transaction_date.date() if hasattr(instance.transaction_date, 'date') else instance.transaction_date,
                category=revenue_category,
                description=f"Payment: {instance.patient.full_name if instance.patient else 'Patient'} - {instance.transaction_number}",
                amount=instance.amount,
                patient=instance.patient,
                invoice=instance.invoice,
                payment_method=instance.payment_method,
                reference=instance.transaction_number,
                recorded_by=instance.processed_by,
            )
            
            # Create receipt voucher
            receipt = ReceiptVoucher.objects.create(
                receipt_date=revenue.revenue_date,
                received_from=instance.patient.full_name if instance.patient else 'Patient',
                patient=instance.patient,
                amount=instance.amount,
                payment_method=instance.payment_method,
                description=revenue.description,
                reference=instance.transaction_number,
                status='issued',
                revenue_account=revenue_account,
                cash_account=cash_account,
                invoice=instance.invoice,
                received_by=instance.processed_by,
            )
            
            # Create journal entry
            journal = Journal.objects.filter(journal_type='receipt').first()
            if journal:
                je = AdvancedJournalEntry.objects.create(
                    journal=journal,
                    entry_date=revenue.revenue_date,
                    description=revenue.description,
                    reference=instance.transaction_number,
                    status='draft',  # Will be posted below
                    total_debit=instance.amount,
                    total_credit=instance.amount,
                    created_by=instance.processed_by,
                    invoice=instance.invoice,
                )
                
                # Dr: Cash
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=1,
                    account=cash_account,
                    description="Cash received",
                    debit_amount=instance.amount,
                    credit_amount=Decimal('0.00'),
                    patient=instance.patient,
                )
                
                # Cr: Revenue
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=2,
                    account=revenue_account,
                    description="Patient services revenue",
                    debit_amount=Decimal('0.00'),
                    credit_amount=instance.amount,
                    patient=instance.patient,
                )
                
                # Post to GL
                je.post(instance.processed_by)
                
                # Link to revenue
                revenue.journal_entry = je
                revenue.save()
                
                receipt.journal_entry = je
                receipt.save()
            
            # Update AR
            if instance.invoice:
                try:
                    ar = AdvancedAccountsReceivable.objects.get(invoice=instance.invoice)
                    ar.amount_paid += instance.amount
                    ar.save()
                except AdvancedAccountsReceivable.DoesNotExist:
                    pass
            
            print(f"[AUTO-SYNC] Payment GHS {instance.amount} to Revenue to JE to GL [OK]")
    
    except Exception as e:
        print(f"[AUTO-SYNC ERROR] Payment sync failed: {e}")
        import traceback
        traceback.print_exc()
