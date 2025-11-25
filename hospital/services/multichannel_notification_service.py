"""
Multi-Channel Notification Service
Unified service to send notifications via SMS, WhatsApp, and Email
Handles notification preferences and logs all attempts
"""
from django.utils import timezone
from django.db import transaction
import logging

from .sms_service import sms_service
from .whatsapp_service import whatsapp_service
from .email_service import email_service
from ..models_notification import NotificationPreference, MultiChannelNotificationLog

logger = logging.getLogger(__name__)


class MultiChannelNotificationService:
    """
    Unified service for sending notifications across multiple channels
    Respects patient preferences and logs all delivery attempts
    """
    
    def __init__(self):
        self.sms_service = sms_service
        self.whatsapp_service = whatsapp_service
        self.email_service = email_service
    
    def send_lab_result_notification(self, lab_result, force_channels=None, include_attachment=False, pdf_path=''):
        """
        Send lab result notification via patient's preferred channels
        
        Args:
            lab_result: LabResult instance
            force_channels: List of channels to force use (overrides preferences) e.g., ['sms', 'email']
            include_attachment: Whether to include PDF attachment (for email/whatsapp)
            pdf_path: Path to PDF file (if include_attachment=True)
            
        Returns:
            MultiChannelNotificationLog instance
        """
        try:
            patient = lab_result.order.encounter.patient
            test = lab_result.test
            
            # Get or create notification preference
            preference, created = NotificationPreference.objects.get_or_create(
                patient=patient,
                defaults={
                    'sms_enabled': True,  # Default to SMS
                    'whatsapp_enabled': False,
                    'email_enabled': False,
                    'lab_results_notify': True
                }
            )
            
            # Check if patient wants lab result notifications
            if not preference.lab_results_notify and not force_channels:
                logger.info(f"Patient {patient.full_name} has disabled lab result notifications")
                return None
            
            # Determine channels to use
            if force_channels:
                channels_to_use = force_channels
            else:
                channels_to_use = preference.get_active_channels()
            
            if not channels_to_use:
                logger.warning(f"No notification channels enabled for patient {patient.full_name}")
                return None
            
            # Create notification log
            notification_log = MultiChannelNotificationLog.objects.create(
                patient=patient,
                notification_type='lab_result',
                subject=f"Lab Result Ready: {test.name}",
                message_body=f"Lab result for {test.name} is ready for {patient.full_name}",
                channels_attempted=channels_to_use,
                related_object_id=str(lab_result.id),
                related_object_type='LabResult'
            )
            
            # Send via each channel
            channel_responses = {}
            successful_channels = []
            failed_channels = []
            
            for channel in channels_to_use:
                try:
                    if channel == 'sms':
                        result = self._send_lab_result_sms(lab_result, patient)
                        channel_responses['sms'] = result
                        if result and hasattr(result, 'status') and result.status == 'sent':
                            successful_channels.append('sms')
                        else:
                            failed_channels.append('sms')
                    
                    elif channel == 'whatsapp':
                        result = self.whatsapp_service.send_lab_result_whatsapp(
                            lab_result, 
                            patient, 
                            include_pdf=include_attachment, 
                            pdf_url=pdf_path
                        )
                        channel_responses['whatsapp'] = result
                        if result.get('success'):
                            successful_channels.append('whatsapp')
                        else:
                            failed_channels.append('whatsapp')
                    
                    elif channel == 'email':
                        result = self.email_service.send_lab_result_email(
                            lab_result, 
                            patient, 
                            include_pdf=include_attachment, 
                            pdf_path=pdf_path
                        )
                        channel_responses['email'] = result
                        if result.get('success'):
                            successful_channels.append('email')
                        else:
                            failed_channels.append('email')
                
                except Exception as e:
                    logger.error(f"Error sending {channel} notification: {str(e)}", exc_info=True)
                    channel_responses[channel] = {
                        'success': False,
                        'error': str(e)
                    }
                    failed_channels.append(channel)
            
            # Update notification log
            notification_log.channels_successful = successful_channels
            notification_log.channels_failed = failed_channels
            notification_log.channel_responses = channel_responses
            notification_log.mark_sent()
            
            logger.info(
                f"Lab result notification sent to {patient.full_name}. "
                f"Successful: {successful_channels}, Failed: {failed_channels}"
            )
            
            return notification_log
        
        except Exception as e:
            logger.error(f"Error in multi-channel lab result notification: {str(e)}", exc_info=True)
            return None
    
    def _send_lab_result_sms(self, lab_result, patient):
        """Send lab result via SMS (uses existing SMS service)"""
        try:
            return self.sms_service.send_lab_result_ready(lab_result)
        except Exception as e:
            logger.error(f"SMS send error: {str(e)}", exc_info=True)
            return None
    
    def send_notification(self, patient, notification_type, subject, message, 
                         force_channels=None, attachment_path=''):
        """
        Send generic notification via multiple channels
        
        Args:
            patient: Patient instance
            notification_type: Type of notification ('appointment_reminder', 'payment_reminder', etc.)
            subject: Notification subject/title
            message: Notification message body
            force_channels: List of channels to use (overrides preferences)
            attachment_path: Path to attachment file
            
        Returns:
            MultiChannelNotificationLog instance
        """
        try:
            # Get or create notification preference
            preference, created = NotificationPreference.objects.get_or_create(
                patient=patient,
                defaults={
                    'sms_enabled': True,
                    'whatsapp_enabled': False,
                    'email_enabled': False
                }
            )
            
            # Determine channels
            if force_channels:
                channels_to_use = force_channels
            else:
                channels_to_use = preference.get_active_channels()
            
            if not channels_to_use:
                return None
            
            # Create notification log
            notification_log = MultiChannelNotificationLog.objects.create(
                patient=patient,
                notification_type=notification_type,
                subject=subject,
                message_body=message,
                channels_attempted=channels_to_use
            )
            
            # Send via each channel
            channel_responses = {}
            successful_channels = []
            failed_channels = []
            
            for channel in channels_to_use:
                try:
                    if channel == 'sms':
                        phone = preference.get_sms_number()
                        if phone:
                            sms_log = self.sms_service.send_sms(
                                phone_number=phone,
                                message=message,
                                message_type=notification_type,
                                recipient_name=patient.full_name
                            )
                            channel_responses['sms'] = {'status': sms_log.status}
                            if sms_log.status == 'sent':
                                successful_channels.append('sms')
                            else:
                                failed_channels.append('sms')
                        else:
                            failed_channels.append('sms')
                    
                    elif channel == 'whatsapp':
                        whatsapp_num = preference.get_whatsapp_number()
                        if whatsapp_num:
                            result = self.whatsapp_service.send_whatsapp(
                                phone_number=whatsapp_num,
                                message=message,
                                message_type=notification_type,
                                recipient_name=patient.full_name
                            )
                            channel_responses['whatsapp'] = result
                            if result.get('success'):
                                successful_channels.append('whatsapp')
                            else:
                                failed_channels.append('whatsapp')
                        else:
                            failed_channels.append('whatsapp')
                    
                    elif channel == 'email':
                        email_addr = preference.get_email()
                        if email_addr:
                            # Create simple HTML message
                            html_message = f"""
                            <html>
                                <body style="font-family: Arial, sans-serif; padding: 20px;">
                                    <h2>{subject}</h2>
                                    <p>{message.replace(chr(10), '<br>')}</p>
                                    <p style="color: #666; font-size: 12px; margin-top: 30px;">
                                        This is an automated notification from PrimeCare Hospital.
                                    </p>
                                </body>
                            </html>
                            """
                            result = self.email_service.send_email(
                                recipient_email=email_addr,
                                subject=subject,
                                message_html=html_message,
                                message_text=message,
                                attachment_path=attachment_path if attachment_path else None,
                                recipient_name=patient.full_name
                            )
                            channel_responses['email'] = result
                            if result.get('success'):
                                successful_channels.append('email')
                            else:
                                failed_channels.append('email')
                        else:
                            failed_channels.append('email')
                
                except Exception as e:
                    logger.error(f"Error sending {channel}: {str(e)}", exc_info=True)
                    channel_responses[channel] = {'error': str(e)}
                    failed_channels.append(channel)
            
            # Update log
            notification_log.channels_successful = successful_channels
            notification_log.channels_failed = failed_channels
            notification_log.channel_responses = channel_responses
            notification_log.mark_sent()
            
            return notification_log
        
        except Exception as e:
            logger.error(f"Error in multi-channel notification: {str(e)}", exc_info=True)
            return None
    
    def update_patient_preferences(self, patient, **kwargs):
        """
        Update patient's notification preferences
        
        Args:
            patient: Patient instance
            **kwargs: Fields to update (sms_enabled, whatsapp_enabled, email_enabled, etc.)
            
        Returns:
            NotificationPreference instance
        """
        preference, created = NotificationPreference.objects.get_or_create(
            patient=patient,
            defaults={
                'sms_enabled': True,
                'whatsapp_enabled': False,
                'email_enabled': False
            }
        )
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(preference, key):
                setattr(preference, key, value)
        
        preference.save()
        return preference
    
    def get_patient_preferences(self, patient):
        """Get patient's notification preferences"""
        try:
            return patient.notification_preference
        except NotificationPreference.DoesNotExist:
            # Create default preferences
            return NotificationPreference.objects.create(
                patient=patient,
                sms_enabled=True,
                whatsapp_enabled=False,
                email_enabled=False
            )


# Singleton instance
multichannel_service = MultiChannelNotificationService()
























