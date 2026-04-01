"""
Accounting Signals - Auto-sync Everything
Automatic journal entry creation for all financial transactions
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction as db_transaction, IntegrityError
from decimal import Decimal
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

# Import all models
from .models import Invoice
from .models_accounting import Transaction, Account
from .models_accounting_advanced import (
    Revenue, RevenueCategory, AdvancedAccountsReceivable,
    AdvancedJournalEntry, AdvancedJournalEntryLine, Journal,
    ReceiptVoucher
)
from .models_primecare_accounting import InsuranceReceivableEntry


# Enable/disable auto-sync (can be toggled)
AUTO_SYNC_ENABLED = True


@receiver(post_save, sender=Invoice)
def auto_create_ar_on_invoice(sender, instance, created, **kwargs):
    """
    Auto-create AR when invoice is created/issued
    Also ensures invoice is properly linked to company account
    - For insurance/corporate: Creates InsuranceReceivableEntry
    - For cash: Creates AdvancedAccountsReceivable
    
    This ensures that when a patient visits with insurance/corporate selected,
    the receivable entry is automatically created for easy claims processing.
    """
    if not AUTO_SYNC_ENABLED:
        return
    
    # Only process when invoice is issued (not draft)
    if instance.status not in ['issued', 'partially_paid', 'overdue']:
        return
    
    # Skip if invoice has no payer or zero amount
    if not instance.payer or not instance.total_amount or instance.total_amount <= 0:
        return
    
    try:
        payer = instance.payer
        payer_type = payer.payer_type if hasattr(payer, 'payer_type') else None
        
        # For insurance or corporate payers, create InsuranceReceivableEntry
        if payer_type in ['private', 'nhis', 'corporate']:
            # Check if entry already exists for this invoice (prevent duplicates)
            # Use a more specific check to avoid duplicates - check by invoice number in notes
            existing_entry = InsuranceReceivableEntry.objects.filter(
                payer=payer,
                notes__icontains=instance.invoice_number,  # Check if notes mention this invoice
                is_deleted=False
            ).order_by('-created').first()  # Get most recent entry for this invoice
            
            # Update existing entry if invoice amount changed (e.g., on discharge)
            if existing_entry and existing_entry.total_amount != instance.total_amount:
                old_amount = existing_entry.total_amount
                # Recalculate revenue breakdown from invoice lines
                consultation_amount = Decimal('0.00')
                registration_amount = Decimal('0.00')
                laboratory_amount = Decimal('0.00')
                pharmacy_amount = Decimal('0.00')
                surgeries_amount = Decimal('0.00')
                admissions_amount = Decimal('0.00')
                radiology_amount = Decimal('0.00')
                dental_amount = Decimal('0.00')
                physiotherapy_amount = Decimal('0.00')
                
                # Try to break down by service type from invoice lines
                if hasattr(instance, 'lines'):
                    for line in instance.lines.all():
                        if hasattr(line, 'service_code') and line.service_code:
                            service_desc = line.service_code.description.lower() if line.service_code.description else ''
                            amount = line.line_total or Decimal('0.00')
                            
                            if 'consultation' in service_desc or 'consult' in service_desc:
                                consultation_amount += amount
                            elif 'registration' in service_desc or 'reg' in service_desc:
                                registration_amount += amount
                            elif 'lab' in service_desc or 'laboratory' in service_desc:
                                laboratory_amount += amount
                            elif 'pharmacy' in service_desc or 'drug' in service_desc or 'medication' in service_desc:
                                pharmacy_amount += amount
                            elif 'surgery' in service_desc or 'surgical' in service_desc:
                                surgeries_amount += amount
                            elif 'admission' in service_desc or 'ward' in service_desc or 'bed' in service_desc:
                                admissions_amount += amount
                            elif 'radiology' in service_desc or 'x-ray' in service_desc or 'imaging' in service_desc:
                                radiology_amount += amount
                            elif 'dental' in service_desc:
                                dental_amount += amount
                            elif 'physiotherapy' in service_desc or 'physio' in service_desc:
                                physiotherapy_amount += amount
                            else:
                                # Default to consultation if unclear
                                consultation_amount += amount
                
                # If no breakdown found, allocate all to consultation
                if consultation_amount == 0 and registration_amount == 0:
                    consultation_amount = instance.total_amount
                
                # Update existing entry
                existing_entry.total_amount = instance.total_amount
                existing_entry.outstanding_amount = instance.balance or instance.total_amount
                existing_entry.consultation_amount = consultation_amount
                existing_entry.registration_amount = registration_amount
                existing_entry.laboratory_amount = laboratory_amount
                existing_entry.pharmacy_amount = pharmacy_amount
                existing_entry.surgeries_amount = surgeries_amount
                existing_entry.admissions_amount = admissions_amount
                existing_entry.radiology_amount = radiology_amount
                existing_entry.dental_amount = dental_amount
                existing_entry.physiotherapy_amount = physiotherapy_amount
                existing_entry.notes = f"Auto-updated from invoice {instance.invoice_number} for patient {instance.patient.full_name if instance.patient else 'N/A'}"
                existing_entry.save()
                
                logger.info(
                    f"[AUTO-SYNC] Updated InsuranceReceivableEntry {existing_entry.entry_number} for {payer_type} payer {payer.name} - "
                    f"Invoice {instance.invoice_number}: GHS {old_amount} → GHS {instance.total_amount}"
                )
            elif not existing_entry:
                # Calculate revenue breakdown from invoice lines
                consultation_amount = Decimal('0.00')
                registration_amount = Decimal('0.00')
                laboratory_amount = Decimal('0.00')
                pharmacy_amount = Decimal('0.00')
                surgeries_amount = Decimal('0.00')
                admissions_amount = Decimal('0.00')
                radiology_amount = Decimal('0.00')
                dental_amount = Decimal('0.00')
                physiotherapy_amount = Decimal('0.00')
                
                # Try to break down by service type from invoice lines
                if hasattr(instance, 'lines'):
                    for line in instance.lines.all():
                        if hasattr(line, 'service_code') and line.service_code:
                            service_desc = line.service_code.description.lower() if line.service_code.description else ''
                            amount = line.line_total or Decimal('0.00')
                            
                            if 'consultation' in service_desc or 'consult' in service_desc:
                                consultation_amount += amount
                            elif 'registration' in service_desc or 'reg' in service_desc:
                                registration_amount += amount
                            elif 'lab' in service_desc or 'laboratory' in service_desc:
                                laboratory_amount += amount
                            elif 'pharmacy' in service_desc or 'drug' in service_desc or 'medication' in service_desc:
                                pharmacy_amount += amount
                            elif 'surgery' in service_desc or 'surgical' in service_desc:
                                surgeries_amount += amount
                            elif 'admission' in service_desc or 'ward' in service_desc or 'bed' in service_desc:
                                admissions_amount += amount
                            elif 'radiology' in service_desc or 'x-ray' in service_desc or 'imaging' in service_desc:
                                radiology_amount += amount
                            elif 'dental' in service_desc:
                                dental_amount += amount
                            elif 'physiotherapy' in service_desc or 'physio' in service_desc:
                                physiotherapy_amount += amount
                            else:
                                # Default to consultation if unclear
                                consultation_amount += amount
                
                # If no breakdown found, allocate all to consultation
                if consultation_amount == 0 and registration_amount == 0:
                    consultation_amount = instance.total_amount
                
                # Generate non-empty unique entry_number (includes uuid suffix to avoid duplicates).
                # Catch IntegrityError and do not re-raise so the outer transaction is not broken
                # (avoids TransactionManagementError for audit log and cashier flow).
                entry_number = InsuranceReceivableEntry.generate_entry_number()
                if not (entry_number and str(entry_number).strip()):
                    entry_number = InsuranceReceivableEntry.generate_entry_number()
                try:
                    with db_transaction.atomic():
                        receivable_entry = InsuranceReceivableEntry.objects.create(
                            entry_number=entry_number,
                            payer=payer,
                            entry_date=instance.issued_at.date() if instance.issued_at else timezone.now().date(),
                            total_amount=instance.total_amount,
                            outstanding_amount=instance.balance or instance.total_amount,
                            consultation_amount=consultation_amount,
                            registration_amount=registration_amount,
                            laboratory_amount=laboratory_amount,
                            pharmacy_amount=pharmacy_amount,
                            surgeries_amount=surgeries_amount,
                            admissions_amount=admissions_amount,
                            radiology_amount=radiology_amount,
                            dental_amount=dental_amount,
                            physiotherapy_amount=physiotherapy_amount,
                            status='pending',
                            notes=f"Auto-created from invoice {instance.invoice_number} for patient {instance.patient.full_name if instance.patient else 'N/A'}"
                        )
                        logger.info(f"[AUTO-SYNC] Created InsuranceReceivableEntry {receivable_entry.entry_number} for {payer_type} payer {payer.name} - Invoice {instance.invoice_number} - GHS {instance.total_amount}")
                except IntegrityError as e:
                    logger.warning(
                        f"[AUTO-SYNC] Could not create InsuranceReceivableEntry for invoice {instance.invoice_number} (duplicate or constraint): {e}. "
                        "Invoice save will still succeed."
                    )
                except Exception as e:
                    logger.warning(
                        f"[AUTO-SYNC] Could not create InsuranceReceivableEntry for invoice {instance.invoice_number}: {e}. Invoice save will still succeed.",
                        exc_info=True,
                    )
        
        # For cash payers, create AdvancedAccountsReceivable (existing logic)
        elif payer_type == 'cash' or not payer_type:
            ar, ar_created = AdvancedAccountsReceivable.objects.get_or_create(
                invoice=instance,
                defaults={
                    'patient': instance.patient,
                    'invoice_amount': instance.total_amount,
                    'amount_paid': Decimal('0.00'),
                    'balance_due': instance.total_amount,
                    'due_date': instance.due_at.date() if instance.due_at else (timezone.now().date() + timezone.timedelta(days=30)),
                }
            )
            
            # Update existing AR entry if invoice amount changed (e.g., on discharge)
            if not ar_created and ar.invoice_amount != instance.total_amount:
                old_amount = ar.invoice_amount
                ar.invoice_amount = instance.total_amount
                # Recalculate balance_due: new invoice amount minus what's already paid
                ar.balance_due = instance.total_amount - ar.amount_paid
                ar.save()
                logger.info(
                    f"[AUTO-SYNC] Updated AdvancedAccountsReceivable for invoice {instance.invoice_number}: "
                    f"GHS {old_amount} → GHS {instance.total_amount} (balance: GHS {ar.balance_due})"
                )
            elif ar_created:
                logger.info(f"[AUTO-SYNC] Created AdvancedAccountsReceivable for cash invoice {instance.invoice_number}: GHS {instance.total_amount}")
    
    except Exception as e:
        logger.error(f"[AUTO-SYNC ERROR] AR/Receivable creation failed for invoice {instance.invoice_number}: {e}", exc_info=True)
    
    # Ensure invoice is properly linked to company account
    try:
        from hospital.services.billing_account_link_service import BillingAccountLinkService
        link_result = BillingAccountLinkService.ensure_invoice_linked_to_account(instance)
        if link_result['success']:
            logger.info(
                f"[AUTO-LINK] Invoice {instance.invoice_number} linked to {link_result.get('account_type', 'unknown')} account: {link_result.get('message', '')}"
            )
        else:
            logger.warning(
                f"[AUTO-LINK] Failed to link invoice {instance.invoice_number}: {link_result.get('message', 'Unknown error')}"
            )
    except ImportError:
        # Service not available
        pass
    except Exception as e:
        logger.error(f"[AUTO-LINK ERROR] Failed to link invoice {instance.invoice_number}: {e}", exc_info=True)


@receiver(post_save, sender=Transaction)
def auto_create_revenue_on_payment(sender, instance, created, **kwargs):
    """
    Auto-create revenue, receipt voucher, and journal entry when payment received.
    Single source for payment_received posting. Skip deposit applications (handled
    by signals_patient_deposits with Dr Patient Deposits / Cr Revenue).
    """
    if not AUTO_SYNC_ENABLED or not created:
        return
    
    if instance.transaction_type != 'payment_received':
        return

    # Do not post as cash: deposit applications are already posted by DepositApplication signal
    if getattr(instance, 'payment_method', None) == 'deposit':
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
            
            # Update AR or InsuranceReceivableEntry based on payer type
            if instance.invoice and instance.invoice.payer:
                payer = instance.invoice.payer
                payer_type = payer.payer_type if hasattr(payer, 'payer_type') else None
                
                # For insurance/corporate: Update InsuranceReceivableEntry
                if payer_type in ['private', 'nhis', 'corporate']:
                    try:
                        # Find the most recent receivable entry for this payer and invoice date
                        receivable_entry = InsuranceReceivableEntry.objects.filter(
                            payer=payer,
                            is_deleted=False,
                            outstanding_amount__gt=0
                        ).order_by('-entry_date', '-created').first()
                        
                        if receivable_entry:
                            receivable_entry.amount_received += instance.amount
                            receivable_entry.outstanding_amount = (
                                receivable_entry.total_amount - 
                                receivable_entry.amount_received - 
                                receivable_entry.amount_rejected - 
                                receivable_entry.withholding_tax
                            )
                            
                            # Update status
                            if receivable_entry.outstanding_amount <= 0:
                                receivable_entry.status = 'paid'
                            elif receivable_entry.amount_received > 0:
                                receivable_entry.status = 'partially_paid'
                            
                            receivable_entry.save()
                            logger.info(f"[AUTO-SYNC] Updated InsuranceReceivableEntry {receivable_entry.entry_number} - Payment: GHS {instance.amount}, Outstanding: GHS {receivable_entry.outstanding_amount}")
                    except Exception as e:
                        logger.warning(f"[AUTO-SYNC] Could not update InsuranceReceivableEntry for payment: {e}")
                
                # For cash: Update AdvancedAccountsReceivable
                else:
                    try:
                        ar = AdvancedAccountsReceivable.objects.get(invoice=instance.invoice)
                        ar.amount_paid += instance.amount
                        ar.balance_due = ar.invoice_amount - ar.amount_paid
                        ar.save()
                        logger.info(f"[AUTO-SYNC] Updated AdvancedAccountsReceivable for invoice {instance.invoice.invoice_number} - Payment: GHS {instance.amount}")
                    except AdvancedAccountsReceivable.DoesNotExist:
                        pass
            
            logger.info(f"[AUTO-SYNC] Payment GHS {instance.amount} to Revenue to JE to GL [OK]")
    
    except Exception as e:
        print(f"[AUTO-SYNC ERROR] Payment sync failed: {e}")
        import traceback
        traceback.print_exc()
