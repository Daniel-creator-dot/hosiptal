"""
Signals for automatic payer type synchronization during visits
Ensures payer type is properly set when encounters are created
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from hospital.models import Encounter
from hospital.services.visit_payer_sync_service import visit_payer_sync_service


@receiver(post_save, sender=Encounter)
def sync_encounter_payer_type(sender, instance, created, **kwargs):
    """
    Automatically sync payer type when encounter is created
    Ensures patient, encounter, and invoice all have correct payer
    """
    if not created:
        # Only sync on creation, not updates
        return
    
    try:
        # Sync payer type
        sync_result = visit_payer_sync_service.verify_and_set_payer_type(
            encounter=instance,
            payer_type=None  # Auto-detect from patient
        )
        
        if sync_result['success']:
            # Log success (but don't spam logs)
            if sync_result['payer_type'] != 'cash':
                visit_payer_sync_service.logger.info(
                    f"Auto-synced payer type for encounter {instance.id}: "
                    f"{sync_result['payer_type']} ({sync_result['payer'].name})"
                )
        else:
            visit_payer_sync_service.logger.warning(
                f"Failed to sync payer type for encounter {instance.id}: "
                f"{sync_result['message']}"
            )
            
    except Exception as e:
        # Don't fail encounter creation if sync fails
        visit_payer_sync_service.logger.error(
            f"Error syncing payer type for encounter {instance.id}: {str(e)}",
            exc_info=True
        )
