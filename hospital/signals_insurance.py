"""
Signals for automatic insurance claim tracking
Automatically creates claim items when patients with insurance receive services
"""
from decimal import Decimal
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import IntegrityError
import logging

from .models import Invoice, InvoiceLine
from .models_insurance import InsuranceClaimItem

logger = logging.getLogger(__name__)


@receiver(post_save, sender=InvoiceLine)
def create_insurance_claim_item(sender, instance, created, **kwargs):
    """
    Automatically create insurance claim item when:
    1. An invoice line is created for a patient with insurance
    2. The invoice has a payer (insurance company)
    3. The payer is not 'cash' type

    Uses get_or_create to avoid IntegrityError on duplicate; never raises so
    the caller's transaction is not aborted (avoids "can't execute queries until
    the end of the atomic block" when this runs inside auto-billing).
    """
    if not created:
        return

    try:
        invoice = instance.invoice
        if not invoice:
            return

        if instance.is_insurance_excluded:
            return

        if not invoice.payer:
            return

        if invoice.payer.payer_type in ['cash', 'corporate']:
            return

        if invoice.payer.payer_type not in ['insurance', 'private', 'nhis']:
            return

        patient = invoice.patient
        if not patient:
            return

        insurance_id = patient.insurance_id or patient.insurance_member_id
        if not insurance_id:
            insurance_id = "NOT_PROVIDED"

        # get_or_create to avoid duplicate key / IntegrityError inside caller's atomic
        billed = instance.line_total if instance.line_total is not None else Decimal('0.00')
        if billed < Decimal('0.01'):
            billed = Decimal('0.01')
        service_desc = (instance.description or '')[:500] if instance.description else 'Service'
        _, _ = InsuranceClaimItem.objects.get_or_create(
            invoice_line=instance,
            defaults={
                'patient': patient,
                'payer': invoice.payer,
                'patient_insurance_id': insurance_id,
                'invoice': invoice,
                'encounter': invoice.encounter,
                'service_code': instance.service_code,
                'service_description': service_desc,
                'service_date': invoice.issued_at.date() if invoice.issued_at else timezone.now().date(),
                'billed_amount': billed,
                'claim_status': 'pending',
                'notes': f"Auto-generated from invoice line {instance.id}",
            },
        )
    except IntegrityError as e:
        logger.warning("Insurance claim item already exists for line %s: %s", instance.pk, e)
    except Exception as e:
        logger.warning("Could not create insurance claim item for invoice line %s: %s", instance.pk, e)


@receiver(post_save, sender=Invoice)
def update_insurance_claim_items_on_invoice_update(sender, instance, created, **kwargs):
    """
    Update claim items when invoice status changes or is updated
    """
    if created:
        return
    
    # If invoice is cancelled, mark all claim items as reversed
    if instance.status == 'cancelled':
        InsuranceClaimItem.objects.filter(invoice=instance).exclude(
            claim_status='reversed'
        ).update(
            claim_status='reversed',
            notes=f"Claim reversed due to invoice cancellation: {instance.invoice_number}"
        )

































