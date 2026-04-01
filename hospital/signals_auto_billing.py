"""
🔔 AUTO-BILLING SIGNALS
Automatically create bills when services are ordered
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

INSURANCE_CORPORATE_PAYER_TYPES = ('insurance', 'private', 'nhis', 'corporate')


def _patient_has_insurance_or_corporate(patient):
    """True if patient has a corporate or insurance payer (primary_insurance or encounter invoice)."""
    if not patient:
        return False
    payer = getattr(patient, 'primary_insurance', None)
    if payer and getattr(payer, 'payer_type', None) in INSURANCE_CORPORATE_PAYER_TYPES:
        return True
    try:
        from hospital.models import Encounter
        enc = Encounter.objects.filter(patient=patient, is_deleted=False).order_by('-created').first()
        if enc and getattr(enc, 'current_invoice', None):
            inv = enc.current_invoice
            if inv and inv.payer_id and getattr(inv.payer, 'payer_type', None) in INSURANCE_CORPORATE_PAYER_TYPES:
                return True
    except Exception:
        pass
    return False


@receiver(post_save, sender='hospital.LabResult')
def auto_bill_lab_test(sender, instance, created, **kwargs):
    """
    Automatically create bill as soon as lab test is ordered so it goes straight to cashier.
    Always create bill (price can be 0; pricing engine resolves amount).
    """
    if created:
        try:
            if not instance.order or not instance.order.encounter or not instance.test:
                return
            from hospital.services.auto_billing_service import AutoBillingService
            result = AutoBillingService.create_lab_bill(instance)
            if result.get('success'):
                logger.info(
                    "✅ Lab bill created for %s - %s - GHS %s",
                    instance.test.name,
                    instance.order.encounter.patient.full_name,
                    result.get('amount', 0),
                )
            else:
                logger.warning("Lab auto-bill failed for %s: %s", instance.id, result.get('message'))
        except Exception as e:
            logger.error("Error in auto_bill_lab_test signal: %s", e, exc_info=True)


@receiver(post_save, sender='hospital.ImagingStudy')
def auto_bill_imaging_study(sender, instance, created, **kwargs):
    """
    Automatically create bill as soon as scan/imaging is ordered so it goes straight to cashier.
    """
    if created:
        try:
            # Need order or at least patient for billing
            if not getattr(instance, 'order', None) and not getattr(instance, 'patient', None):
                return
            from hospital.services.auto_billing_service import AutoBillingService
            result = AutoBillingService.create_imaging_bill(instance)
            if result.get('success'):
                patient = None
                if getattr(instance, 'order', None) and getattr(instance.order, 'encounter', None):
                    patient = getattr(instance.order.encounter, 'patient', None)
                if not patient:
                    patient = getattr(instance, 'patient', None)
                logger.info(
                    "✅ Imaging bill created for %s - %s - GHS %s",
                    getattr(instance, 'study_type', None) or 'imaging',
                    getattr(patient, 'full_name', '') if patient else '',
                    result.get('amount', 0),
                )
            else:
                logger.warning("Imaging auto-bill failed for %s: %s", instance.id, result.get('message'))
        except Exception as e:
            logger.error("Error in auto_bill_imaging_study signal: %s", e, exc_info=True)


@receiver(post_save, sender='hospital.Prescription')
def auto_bill_prescription(sender, instance, created, **kwargs):
    """
    Queue prescription for pharmacy only. Do NOT create InvoiceLine or send to cashier here.

    Flow: doctor → PharmacyDispensing (this signal) → pharmacy verifies → Send to Cashier/Insurance
    → AutoBillingService.create_pharmacy_bill (InvoiceLine). create_pharmacy_bill refuses to run
    until a PharmacyDispensing row exists so nothing reaches the payer before pharmacy.
    """
    if created:
        try:
            if not instance.order or not instance.order.encounter or not instance.drug:
                logger.warning(f"⚠️ Pharmacy queue skipped: Prescription {instance.id} missing relationships")
                return
            from hospital.services.auto_billing_service import AutoBillingService
            result = AutoBillingService.create_pharmacy_dispensing_record_only(instance)
            if result.get('success'):
                logger.info(
                    f"✅ Prescription queued for pharmacy (not sent to cashier): {instance.drug.name} x{instance.quantity} "
                    f"- {instance.order.encounter.patient.full_name}"
                )
        except Exception as e:
            import traceback
            logger.error(
                f"❌ Error queueing prescription {instance.id}: {str(e)}\n{traceback.format_exc()}"
            )

























