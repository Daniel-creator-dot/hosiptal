from django.db.models.signals import post_save
from django.dispatch import receiver

from hospital.models_accounting import PaymentReceipt
from hospital.services.payment_clearance_service import PaymentClearanceService


@receiver(post_save, sender=PaymentReceipt)
def auto_link_receipt(sender, instance, created, **kwargs):
    """Attach receipt numbers to pending lab/pharmacy/imaging services."""
    if created:
        PaymentClearanceService.link_receipt_to_services(instance)












