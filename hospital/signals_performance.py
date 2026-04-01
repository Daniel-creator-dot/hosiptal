"""
Performance Tracking Signals
Automatically updates staff performance snapshots when they perform work
"""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

try:
    from .models import Encounter, Prescription, LabResult, Order, VitalSign
    from .models_advanced import MedicationAdministrationRecord
    from .services.performance_analytics import performance_analytics_service
except ImportError:
    logger.warning("Performance analytics service not available")
    performance_analytics_service = None


def _schedule_staff_performance_snapshot(staff_id):
    """Run performance snapshot after commit; prefer Celery, fall back to sync."""
    if not staff_id or not performance_analytics_service:
        return

    def _run():
        try:
            from hms.tasks import refresh_staff_performance_snapshot

            refresh_staff_performance_snapshot.delay(staff_id)
        except Exception:
            try:
                from hospital.models import Staff

                staff = Staff.objects.filter(pk=staff_id, is_deleted=False).first()
                if staff:
                    performance_analytics_service.generate_snapshot(staff)
            except Exception as exc:
                logger.warning(
                    'Performance snapshot failed for staff %s: %s', staff_id, exc
                )

    transaction.on_commit(_run)


@receiver(post_save, sender=Encounter)
def update_doctor_performance_on_encounter(sender, instance, created, **kwargs):
    """Update doctor performance when encounter is created or completed"""
    if not performance_analytics_service:
        return
    
    try:
        # Only update if encounter is completed or created
        if created or instance.status == 'completed':
            if instance.provider and instance.provider.profession == 'doctor':
                # Update performance snapshot asynchronously
                try:
                    performance_analytics_service.generate_snapshot(instance.provider)
                    logger.debug(f"Updated performance for doctor: {instance.provider.user.get_full_name()}")
                except Exception as e:
                    logger.error(f"Error updating doctor performance: {e}")
    except Exception as e:
        logger.error(f"Error in encounter performance signal: {e}")


@receiver(post_save, sender=Prescription)
def update_doctor_performance_on_prescription(sender, instance, created, **kwargs):
    """Update doctor performance when prescription is written"""
    if not performance_analytics_service:
        return
    
    try:
        if created and instance.prescribed_by:
            if instance.prescribed_by.profession == 'doctor':
                _schedule_staff_performance_snapshot(instance.prescribed_by_id)
                try:
                    _dn = instance.prescribed_by.user.get_full_name()
                except Exception:
                    _dn = str(instance.prescribed_by_id)
                logger.debug(
                    'Scheduled performance snapshot for doctor (prescription): %s',
                    _dn,
                )

            # Also update pharmacist if dispensed
            if instance.status == 'dispensed' and instance.dispensed_by:
                if instance.dispensed_by.profession == 'pharmacist':
                    try:
                        performance_analytics_service.generate_snapshot(instance.dispensed_by)
                        logger.debug(f"Updated performance for pharmacist: {instance.dispensed_by.user.get_full_name()}")
                    except Exception as e:
                        logger.error(f"Error updating pharmacist performance: {e}")
    except Exception as e:
        logger.error(f"Error in prescription performance signal: {e}")


@receiver(post_save, sender=LabResult)
def update_lab_performance_on_result(sender, instance, created, **kwargs):
    """Update lab technician performance when lab result is completed"""
    if not performance_analytics_service:
        return
    
    try:
        # Update when result is verified/completed
        if instance.status == 'completed' and instance.verified_by:
            if instance.verified_by.profession == 'lab_technician':
                try:
                    performance_analytics_service.generate_snapshot(instance.verified_by)
                    logger.debug(f"Updated performance for lab technician: {instance.verified_by.user.get_full_name()}")
                except Exception as e:
                    logger.error(f"Error updating lab technician performance: {e}")
    except Exception as e:
        logger.error(f"Error in lab result performance signal: {e}")


@receiver(post_save, sender=VitalSign)
def update_nurse_performance_on_vitals(sender, instance, created, **kwargs):
    """Update nurse performance when vital signs are recorded"""
    if not performance_analytics_service:
        return
    
    try:
        if created and instance.recorded_by:
            if instance.recorded_by.profession == 'nurse':
                try:
                    performance_analytics_service.generate_snapshot(instance.recorded_by)
                    logger.debug(f"Updated performance for nurse (vitals): {instance.recorded_by.user.get_full_name()}")
                except Exception as e:
                    logger.error(f"Error updating nurse performance (vitals): {e}")
    except Exception as e:
        logger.error(f"Error in vital signs performance signal: {e}")


@receiver(post_save, sender=MedicationAdministrationRecord)
def update_nurse_performance_on_medication(sender, instance, created, **kwargs):
    """Update nurse performance when medication is administered"""
    if not performance_analytics_service:
        return
    
    try:
        if created and instance.administered_by:
            if instance.administered_by.profession == 'nurse':
                try:
                    performance_analytics_service.generate_snapshot(instance.administered_by)
                    logger.debug(f"Updated performance for nurse (medication): {instance.administered_by.user.get_full_name()}")
                except Exception as e:
                    logger.error(f"Error updating nurse performance (medication): {e}")
    except Exception as e:
        logger.error(f"Error in medication administration performance signal: {e}")


@receiver(post_save, sender=Order)
def update_staff_performance_on_order(sender, instance, created, **kwargs):
    """Update staff performance when orders are created"""
    if not performance_analytics_service:
        return
    
    try:
        if created and instance.requested_by:
            profession = instance.requested_by.profession
            
            # Update doctor performance for lab orders
            if instance.order_type == 'lab' and profession == 'doctor':
                _schedule_staff_performance_snapshot(instance.requested_by_id)
                try:
                    _rn = instance.requested_by.user.get_full_name()
                except Exception:
                    _rn = str(instance.requested_by_id)
                logger.debug(
                    'Scheduled performance snapshot for doctor (lab order): %s',
                    _rn,
                )
    except Exception as e:
        logger.error(f"Error in order performance signal: {e}")





