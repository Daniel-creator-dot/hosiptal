"""
Signals for automatic insurance claim tracking
Automatically creates claim items when patients with insurance receive services
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Invoice, InvoiceLine
from .models_insurance import InsuranceClaimItem


@receiver(post_save, sender=InvoiceLine)
def create_insurance_claim_item(sender, instance, created, **kwargs):
    """
    Automatically create insurance claim item when:
    1. An invoice line is created for a patient with insurance
    2. The invoice has a payer (insurance company)
    3. The payer is not 'cash' type
    """
    if not created:
        return
    
    invoice = instance.invoice
    if not invoice:
        return
    
    # Check if patient has insurance
    if not invoice.payer:
        return
    
    # Skip if payer is cash (no insurance)
    if invoice.payer.payer_type == 'cash':
        return
    
    # Check if patient has insurance ID
    patient = invoice.patient
    if not patient:
        return
    
    # Get insurance ID from patient
    insurance_id = patient.insurance_id or patient.insurance_member_id
    if not insurance_id:
        # If no insurance ID, we can still create the claim but log it
        insurance_id = "NOT_PROVIDED"
    
    # Check if claim item already exists for this invoice line
    if InsuranceClaimItem.objects.filter(invoice_line=instance).exists():
        return
    
    # Create insurance claim item
    claim_item = InsuranceClaimItem.objects.create(
        patient=patient,
        payer=invoice.payer,
        patient_insurance_id=insurance_id,
        invoice=invoice,
        invoice_line=instance,
        encounter=invoice.encounter,
        service_code=instance.service_code,
        service_description=instance.description,
        service_date=invoice.issued_at.date() if invoice.issued_at else timezone.now().date(),
        billed_amount=instance.line_total,
        claim_status='pending',
        notes=f"Auto-generated from invoice line {instance.id}"
    )
    
    return claim_item


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

























