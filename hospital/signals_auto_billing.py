"""
🔔 AUTO-BILLING SIGNALS
Automatically create bills when services are ordered
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender='hospital.LabResult')
def auto_bill_lab_test(sender, instance, created, **kwargs):
    """
    Automatically create bill when lab test is ordered
    """
    if created:
        try:
            from hospital.services.auto_billing_service import AutoBillingService
            
            # Only create bill if test has a price
            if instance.test.price > 0:
                result = AutoBillingService.create_lab_bill(instance)
                
                if result['success']:
                    logger.info(
                        f"✅ Auto-bill created for lab test: {instance.test.name} "
                        f"- {instance.order.encounter.patient.full_name} - GHS {result['amount']}"
                    )
                else:
                    logger.error(f"❌ Auto-billing failed for lab test {instance.id}: {result.get('message')}")
        except Exception as e:
            logger.error(f"Error in auto_bill_lab_test signal: {str(e)}")


@receiver(post_save, sender='hospital.Prescription')
def auto_bill_prescription(sender, instance, created, **kwargs):
    """
    Automatically create bill when medication is prescribed
    """
    if created:
        try:
            from hospital.services.auto_billing_service import AutoBillingService
            
            # Only create bill if drug has a price
            drug_price = getattr(instance.drug, 'unit_price', 0)
            if drug_price > 0:
                result = AutoBillingService.create_pharmacy_bill(instance)
                
                if result['success']:
                    logger.info(
                        f"✅ Auto-bill created for prescription: {instance.drug.name} x{instance.quantity} "
                        f"- {instance.order.encounter.patient.full_name} - GHS {result['amount']}"
                    )
                else:
                    logger.error(f"❌ Auto-billing failed for prescription {instance.id}: {result.get('message')}")
        except Exception as e:
            logger.error(f"Error in auto_bill_prescription signal: {str(e)}")

























