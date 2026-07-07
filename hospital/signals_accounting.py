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


def _find_insurance_receivable_entry_for_payment(invoice, payer):
    """
    Match a payment to the correct InsuranceReceivableEntry: invoice FK first,
    then notes containing invoice number, then oldest open line for payer (FIFO).
    """
    if not invoice or not payer:
        return None
    base = InsuranceReceivableEntry.objects.filter(
        payer=payer,
        is_deleted=False,
        outstanding_amount__gt=0,
    )
    receivable_entry = base.filter(invoice=invoice).order_by('-entry_date', '-created').first()
    if receivable_entry:
        return receivable_entry
    receivable_entry = base.filter(
        notes__icontains=invoice.invoice_number
    ).order_by('-entry_date', '-created').first()
    if receivable_entry:
        if receivable_entry.invoice_id is None:
            receivable_entry.invoice = invoice
            receivable_entry.save(update_fields=['invoice'])
        return receivable_entry
    receivable_entry = base.order_by('entry_date', 'created').first()
    if receivable_entry:
        logger.warning(
            '[AUTO-SYNC] InsuranceReceivableEntry matched by FIFO fallback for payer %s invoice %s — '
            'consider linking IRE.invoice',
            getattr(payer, 'name', str(payer)),
            getattr(invoice, 'invoice_number', invoice),
        )
    return receivable_entry


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
        if payer_type in ['private', 'nhis', 'corporate', 'insurance']:
            # Prefer invoice FK, then notes containing invoice number
            existing_entry = InsuranceReceivableEntry.objects.filter(
                invoice=instance,
                is_deleted=False,
            ).order_by('-created').first()
            if not existing_entry:
                existing_entry = InsuranceReceivableEntry.objects.filter(
                    payer=payer,
                    notes__icontains=instance.invoice_number,
                    is_deleted=False,
                ).order_by('-created').first()

            # Update existing entry if invoice amount changed (e.g., on discharge)
            if existing_entry and existing_entry.total_amount != instance.total_amount:
                old_amount = existing_entry.total_amount
                from hospital.services.credit_revenue_service import build_ire_revenue_breakdown

                breakdown = build_ire_revenue_breakdown(instance)
                existing_entry.total_amount = instance.total_amount
                existing_entry.outstanding_amount = (
                    instance.balance if getattr(instance, 'balance', None) is not None else instance.total_amount
                )
                existing_entry.consultation_amount = breakdown['consultation_amount']
                existing_entry.registration_amount = breakdown['registration_amount']
                existing_entry.laboratory_amount = breakdown['laboratory_amount']
                existing_entry.pharmacy_amount = breakdown['pharmacy_amount']
                existing_entry.surgeries_amount = breakdown['surgeries_amount']
                existing_entry.admissions_amount = breakdown['admissions_amount']
                existing_entry.radiology_amount = breakdown['radiology_amount']
                existing_entry.dental_amount = breakdown['dental_amount']
                existing_entry.physiotherapy_amount = breakdown['physiotherapy_amount']
                existing_entry.invoice = instance
                existing_entry.notes = f"Auto-updated from invoice {instance.invoice_number} for patient {instance.patient.full_name if instance.patient else 'N/A'}"
                existing_entry.save()
                
                logger.info(
                    f"[AUTO-SYNC] Updated InsuranceReceivableEntry {existing_entry.entry_number} for {payer_type} payer {payer.name} - "
                    f"Invoice {instance.invoice_number}: GHS {old_amount} → GHS {instance.total_amount}"
                )
            elif existing_entry:
                # Totals unchanged: still sync invoice link and outstanding from invoice balance
                update_fields = []
                if existing_entry.invoice_id != instance.id:
                    existing_entry.invoice = instance
                    update_fields.append('invoice')
                new_out = (
                    instance.balance
                    if getattr(instance, 'balance', None) is not None
                    else existing_entry.outstanding_amount
                )
                if existing_entry.outstanding_amount != new_out:
                    existing_entry.outstanding_amount = new_out
                    update_fields.append('outstanding_amount')
                if update_fields:
                    existing_entry.save(update_fields=update_fields)
            elif not existing_entry:
                from hospital.services.credit_revenue_service import build_ire_revenue_breakdown

                breakdown = build_ire_revenue_breakdown(instance)
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
                            invoice=instance,
                            entry_date=instance.issued_at.date() if instance.issued_at else timezone.now().date(),
                            total_amount=instance.total_amount,
                            outstanding_amount=(
                                instance.balance
                                if getattr(instance, 'balance', None) is not None
                                else instance.total_amount
                            ),
                            consultation_amount=breakdown['consultation_amount'],
                            registration_amount=breakdown['registration_amount'],
                            laboratory_amount=breakdown['laboratory_amount'],
                            pharmacy_amount=breakdown['pharmacy_amount'],
                            surgeries_amount=breakdown['surgeries_amount'],
                            admissions_amount=breakdown['admissions_amount'],
                            radiology_amount=breakdown['radiology_amount'],
                            dental_amount=breakdown['dental_amount'],
                            physiotherapy_amount=breakdown['physiotherapy_amount'],
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
    
    txn_id = instance.pk

    def _post_after_commit():
        try:
            from hospital.models_accounting import Transaction as TxnModel
            txn = TxnModel.objects.get(pk=txn_id)
            from hospital.services.payment_revenue_gl_service import post_payment_revenue_gl
            post_payment_revenue_gl(txn)

            if txn.invoice and txn.invoice.payer:
                payer = txn.invoice.payer
                payer_type = payer.payer_type if hasattr(payer, 'payer_type') else None

                if payer_type in ['private', 'nhis', 'corporate', 'insurance']:
                    try:
                        receivable_entry = _find_insurance_receivable_entry_for_payment(
                            txn.invoice, payer
                        )
                        if receivable_entry:
                            receivable_entry.amount_received += txn.amount
                            receivable_entry.outstanding_amount = (
                                receivable_entry.total_amount
                                - receivable_entry.amount_received
                                - receivable_entry.amount_rejected
                                - receivable_entry.withholding_tax
                            )
                            if receivable_entry.outstanding_amount <= 0:
                                receivable_entry.status = 'paid'
                            elif receivable_entry.amount_received > 0:
                                receivable_entry.status = 'partially_paid'
                            receivable_entry.save()
                            logger.info(
                                '[AUTO-SYNC] Updated InsuranceReceivableEntry %s',
                                receivable_entry.entry_number,
                            )
                    except Exception as e:
                        logger.warning(
                            '[AUTO-SYNC] Could not update InsuranceReceivableEntry: %s', e
                        )
                else:
                    try:
                        ar = AdvancedAccountsReceivable.objects.get(invoice=txn.invoice)
                        ar.amount_paid += txn.amount
                        ar.balance_due = ar.invoice_amount - ar.amount_paid
                        ar.save()
                    except AdvancedAccountsReceivable.DoesNotExist:
                        pass

            logger.info('[AUTO-SYNC] Payment GHS %s revenue GL posted [OK]', txn.amount)
        except Exception as e:
            logger.error('[AUTO-SYNC ERROR] Payment sync failed: %s', e, exc_info=True)

    db_transaction.on_commit(_post_after_commit)
