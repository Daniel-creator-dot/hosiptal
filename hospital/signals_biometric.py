"""
Signals for Biometric System Integration
Connects biometric authentication with HR, Attendance, and Security
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models_biometric import (
    BiometricAuthenticationLog,
    BiometricSecurityAlert,
    StaffBiometric,
    BiometricSystemSettings,
)
from .models_advanced import Attendance
from .models_login_tracking import LoginHistory
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=BiometricAuthenticationLog)
def handle_biometric_authentication(sender, instance, created, **kwargs):
    """
    Handle post-authentication tasks
    - Create attendance records
    - Create login history
    - Check for security alerts
    """
    if not created:
        return
    
    try:
        settings = BiometricSystemSettings.get_settings()
        
        # Create attendance record on successful authentication
        if instance.status == 'success' and settings.auto_create_attendance:
            if not instance.created_attendance and instance.staff:
                today = timezone.now().date()
                
                # Check if attendance already exists for today
                attendance, created = Attendance.objects.get_or_create(
                    staff=instance.staff,
                    date=today,
                    defaults={
                        'check_in': timezone.now(),
                        'status': 'present',
                        'notes': f'Auto check-in via {instance.biometric_type.display_name} at {instance.location_name}'
                    }
                )
                
                if created:
                    instance.created_attendance = True
                    instance.attendance_record = attendance
                    instance.save(update_fields=['created_attendance', 'attendance_record'])
                    logger.info(f"Created attendance record for {instance.staff.user.username}")
        
        # Check for security issues
        check_security_alerts(instance)
        
    except Exception as e:
        logger.exception(f"Error in biometric authentication post-save: {e}")


def check_security_alerts(auth_log):
    """
    Check for security issues and create alerts
    """
    try:
        settings = BiometricSystemSettings.get_settings()
        
        if not settings.enable_security_alerts:
            return
        
        # Check for multiple failed attempts
        if auth_log.status != 'success' and settings.alert_on_multiple_failures:
            # Count recent failed attempts for this staff
            if auth_log.staff:
                recent_time = timezone.now() - timedelta(minutes=30)
                failed_count = BiometricAuthenticationLog.objects.filter(
                    staff=auth_log.staff,
                    status__startswith='failed',
                    timestamp__gte=recent_time
                ).count()
                
                if failed_count >= settings.alert_failure_threshold:
                    # Create security alert
                    BiometricSecurityAlert.objects.create(
                        alert_type='multiple_failures',
                        severity='medium' if failed_count < 10 else 'high',
                        staff=auth_log.staff,
                        device=auth_log.device if hasattr(auth_log, 'device') else None,
                        auth_log=auth_log,
                        title=f'Multiple Failed Authentication Attempts',
                        description=f'{auth_log.staff.user.get_full_name()} has {failed_count} failed authentication attempts in the last 30 minutes.',
                        metadata={
                            'failed_count': failed_count,
                            'time_window': '30 minutes',
                            'location': auth_log.location_name,
                        }
                    )
                    logger.warning(f"Security alert: Multiple failed attempts for {auth_log.staff.user.username}")
        
        # Check for spoofing detection
        if auth_log.spoofing_detected:
            BiometricSecurityAlert.objects.create(
                alert_type='spoofing_attempt',
                severity='critical',
                staff=auth_log.staff,
                device=auth_log.device if hasattr(auth_log, 'device') else None,
                auth_log=auth_log,
                title='Spoofing Attempt Detected',
                description=f'Potential spoofing attempt detected for {auth_log.staff.user.get_full_name() if auth_log.staff else "unknown staff"} at {auth_log.location_name}',
                metadata={
                    'location': auth_log.location_name,
                    'ip_address': str(auth_log.ip_address),
                }
            )
            logger.critical(f"Security alert: Spoofing attempt detected")
        
        # Check for suspicious activity (multiple faces, low quality, etc.)
        if auth_log.is_suspicious or auth_log.multiple_face_detected:
            BiometricSecurityAlert.objects.create(
                alert_type='suspicious_activity',
                severity='medium',
                staff=auth_log.staff,
                device=auth_log.device if hasattr(auth_log, 'device') else None,
                auth_log=auth_log,
                title='Suspicious Authentication Activity',
                description=f'Suspicious biometric authentication detected at {auth_log.location_name}',
                metadata={
                    'is_suspicious': auth_log.is_suspicious,
                    'multiple_faces': auth_log.multiple_face_detected,
                    'quality_score': str(auth_log.quality_score) if auth_log.quality_score else None,
                }
            )
    
    except Exception as e:
        logger.exception(f"Error checking security alerts: {e}")


@receiver(pre_save, sender=StaffBiometric)
def set_biometric_expiry(sender, instance, **kwargs):
    """
    Set expiry date for biometric template based on system settings
    """
    if not instance.expires_at:
        try:
            settings = BiometricSystemSettings.get_settings()
            if settings.template_expiry_days > 0:
                instance.expires_at = timezone.now() + timedelta(days=settings.template_expiry_days)
        except Exception as e:
            logger.exception(f"Error setting biometric expiry: {e}")


@receiver(post_save, sender=StaffBiometric)
def handle_biometric_enrollment(sender, instance, created, **kwargs):
    """
    Handle post-enrollment tasks
    """
    if created:
        logger.info(f"New biometric enrolled for {instance.staff.user.username}: {instance.biometric_type.display_name}")
        
        # Could send notification to staff/admin
        # Could create audit log
        pass


@receiver(post_save, sender=BiometricSecurityAlert)
def handle_security_alert(sender, instance, created, **kwargs):
    """
    Handle security alerts - send notifications
    """
    if created and not instance.notification_sent:
        try:
            # Get alert recipients
            settings = BiometricSystemSettings.get_settings()
            recipients = settings.alert_recipients_json
            
            # TODO: Send email/SMS notifications to security team
            # For now, just log
            logger.warning(f"Security Alert: {instance.title} - Severity: {instance.severity}")
            
            # Mark notification as sent
            instance.notification_sent = True
            instance.save(update_fields=['notification_sent'])
            
        except Exception as e:
            logger.exception(f"Error handling security alert: {e}")








