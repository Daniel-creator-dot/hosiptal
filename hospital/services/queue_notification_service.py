"""
Queue Notification Service
Sends SMS/WhatsApp/Email notifications for queue updates
"""
import logging
from django.utils import timezone
from django.conf import settings
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class QueueNotificationService:
    """
    Service for sending queue-related notifications
    Supports SMS, WhatsApp, and Email
    """
    
    # SMS Message Templates
    TEMPLATES = {
        'check_in': """🏥 {hospital_name}

Welcome! Your queue number is: {queue_number}

📍 Department: {department}
👥 Position: {position} in queue
⏱️ Estimated wait: {wait_time} minutes
📅 Date: {date}

Please wait in the Reception waiting area.
You'll receive updates via SMS.""",

        'progress_update': """🏥 Queue Update

Queue #{queue_number}
Current position: {position}
⏱️ Estimated wait: {wait_time} minutes

Thank you for your patience!""",

        'ready': """🏥 READY FOR CONSULTATION

Queue #{queue_number} - It's your turn!

📍 Please proceed to:
   {room_info}

⚠️ Please arrive within 5 minutes""",

        'no_show': """🏥 ATTENTION REQUIRED

Queue #{queue_number}
You were called but did not respond.

Please report to reception immediately
or you may lose your queue position.""",

        'completed': """🏥 Thank you for visiting!

Queue #{queue_number} - Consultation completed

💊 Next steps:
{next_steps}

📱 Questions? Call: {hospital_phone}
Visit us: {hospital_name}"""
    }
    
    def __init__(self):
        self.logger = logger
        self.hospital_name = getattr(settings, 'HOSPITAL_NAME', 'General Hospital')
        self.hospital_phone = getattr(settings, 'HOSPITAL_PHONE', '0123456789')
    
    def send_check_in_notification(self, queue_entry):
        """
        Send check-in confirmation SMS
        
        Args:
            queue_entry: QueueEntry object
        
        Returns:
            bool: Success status
        """
        try:
            # Check if department has notifications enabled (only if department exists)
            if queue_entry.department:
                from hospital.models_queue import QueueConfiguration
                
                try:
                    config = QueueConfiguration.objects.get(department=queue_entry.department)
                    if not config.send_check_in_sms:
                        self.logger.info(f"Check-in SMS disabled for {queue_entry.department.name}")
                        return False
                except QueueConfiguration.DoesNotExist:
                    # No config exists - enable by default
                    pass
            
            # Get patient phone number
            phone = self._get_patient_phone(queue_entry.patient)
            if not phone:
                self.logger.warning(
                    f"No phone number for patient {queue_entry.patient.mrn} "
                    f"({queue_entry.patient.full_name}). "
                    f"Patient phone_number field: '{queue_entry.patient.phone_number}'"
                )
                return False
            
            # Get queue position
            from .queue_service import queue_service
            position = queue_service.get_position_in_queue(queue_entry)
            
            # Format message
            department_name = queue_entry.department.name if queue_entry.department else 'General'
            message = self.TEMPLATES['check_in'].format(
                hospital_name=self.hospital_name,
                queue_number=queue_entry.queue_number,
                department=department_name,
                position=position,
                wait_time=queue_entry.estimated_wait_minutes or 0,
                date=queue_entry.queue_date.strftime('%b %d, %Y')
            )
            
            # Send SMS
            success = self._send_sms(
                phone, 
                message, 
                recipient_name=queue_entry.patient.full_name,
                message_type='queue_check_in',
                related_object_id=queue_entry.id,
                related_object_type='QueueEntry'
            )
            
            if success:
                # Log notification
                self._log_notification(
                    queue_entry,
                    'check_in',
                    'sms',
                    message
                )
                
                # Update queue entry
                queue_entry.sms_sent = True
                queue_entry.sms_sent_at = timezone.now()
                queue_entry.notification_count += 1
                queue_entry.last_notification_sent = timezone.now()
                queue_entry.save(update_fields=['sms_sent', 'sms_sent_at', 'notification_count', 'last_notification_sent', 'modified'])
                
                self.logger.info(f"✅ Check-in SMS sent to {queue_entry.patient.full_name} at {phone}")
            else:
                self.logger.warning(f"⚠️ SMS send returned False for {queue_entry.patient.full_name} at {phone}")
            
            return success
            
        except Exception as e:
            self.logger.error(
                f"❌ Error sending check-in notification for queue {queue_entry.queue_number}: {str(e)}", 
                exc_info=True
            )
            return False
    
    def send_progress_update(self, queue_entry):
        """
        Send queue progress update
        
        Args:
            queue_entry: QueueEntry object
        
        Returns:
            bool: Success status
        """
        try:
            # Check if progress updates are enabled
            from hospital.models_queue import QueueConfiguration
            
            try:
                config = QueueConfiguration.objects.get(department=queue_entry.department)
                if not config.send_progress_updates:
                    return False
            except QueueConfiguration.DoesNotExist:
                pass
            
            phone = self._get_patient_phone(queue_entry.patient)
            if not phone:
                return False
            
            # Get current position
            from .queue_service import queue_service
            position = queue_service.get_position_in_queue(queue_entry)
            
            # Calculate updated wait time
            estimated_wait = queue_service.calculate_estimated_wait(
                queue_entry.department,
                position
            )
            
            # Format message
            message = self.TEMPLATES['progress_update'].format(
                queue_number=queue_entry.queue_number,
                position=position,
                wait_time=estimated_wait
            )
            
            # Send SMS
            success = self._send_sms(
                phone, 
                message, 
                recipient_name=queue_entry.patient.full_name,
                message_type='queue_progress_update'
            )
            
            if success:
                self._log_notification(queue_entry, 'progress_update', 'sms', message)
                queue_entry.notification_count += 1
                queue_entry.last_notification_sent = timezone.now()
                queue_entry.save()
                
                self.logger.info(f"✅ Progress update sent to {queue_entry.patient.full_name}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending progress update: {str(e)}", exc_info=True)
            return False
    
    def send_ready_notification(self, queue_entry):
        """
        Send "your turn" notification
        
        Args:
            queue_entry: QueueEntry object
        
        Returns:
            bool: Success status
        """
        try:
            phone = self._get_patient_phone(queue_entry.patient)
            if not phone:
                return False
            
            # Format room info
            room_info = queue_entry.room_number or 'Main Consultation Area'
            if queue_entry.assigned_doctor:
                doctor_name = queue_entry.assigned_doctor.get_full_name()
                room_info = f"{room_info} - {doctor_name}"
            
            # Format message
            message = self.TEMPLATES['ready'].format(
                queue_number=queue_entry.queue_number,
                room_info=room_info
            )
            
            # Send SMS
            success = self._send_sms(
                phone, 
                message, 
                recipient_name=queue_entry.patient.full_name,
                message_type='queue_ready'
            )
            
            if success:
                self._log_notification(queue_entry, 'ready', 'sms', message)
                queue_entry.notification_count += 1
                queue_entry.last_notification_sent = timezone.now()
                queue_entry.save()
                
                self.logger.info(f"✅ Ready notification sent to {queue_entry.patient.full_name}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending ready notification: {str(e)}", exc_info=True)
            return False
    
    def send_no_show_warning(self, queue_entry):
        """
        Send no-show warning
        
        Args:
            queue_entry: QueueEntry object
        
        Returns:
            bool: Success status
        """
        try:
            phone = self._get_patient_phone(queue_entry.patient)
            if not phone:
                return False
            
            # Format message
            message = self.TEMPLATES['no_show'].format(
                queue_number=queue_entry.queue_number
            )
            
            # Send SMS
            success = self._send_sms(
                phone, 
                message, 
                recipient_name=queue_entry.patient.full_name,
                message_type='queue_no_show_warning'
            )
            
            if success:
                self._log_notification(queue_entry, 'no_show_warning', 'sms', message)
                queue_entry.notification_count += 1
                queue_entry.last_notification_sent = timezone.now()
                queue_entry.save()
                
                self.logger.info(f"⚠️ No-show warning sent to {queue_entry.patient.full_name}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending no-show warning: {str(e)}", exc_info=True)
            return False
    
    def send_completion_notification(self, queue_entry):
        """
        Send consultation completed notification
        
        Args:
            queue_entry: QueueEntry object
        
        Returns:
            bool: Success status
        """
        try:
            phone = self._get_patient_phone(queue_entry.patient)
            if not phone:
                return False
            
            # Format next steps
            next_steps = """- Pharmacy: If prescribed medication
- Lab: If tests ordered
- Cashier: For payment
- Reception: For follow-up appointment"""
            
            # Format message
            message = self.TEMPLATES['completed'].format(
                queue_number=queue_entry.queue_number,
                next_steps=next_steps,
                hospital_phone=self.hospital_phone,
                hospital_name=self.hospital_name
            )
            
            # Send SMS
            success = self._send_sms(
                phone, 
                message, 
                recipient_name=queue_entry.patient.full_name,
                message_type='queue_completed'
            )
            
            if success:
                self._log_notification(queue_entry, 'completed', 'sms', message)
                queue_entry.notification_count += 1
                queue_entry.last_notification_sent = timezone.now()
                queue_entry.save()
                
                self.logger.info(f"✅ Completion notification sent to {queue_entry.patient.full_name}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending completion notification: {str(e)}", exc_info=True)
            return False
    
    def check_and_send_progress_updates(self):
        """
        Check all waiting patients and send progress updates if needed
        Called periodically (e.g., every 5 minutes via cron/celery)
        
        Returns:
            int: Number of updates sent
        """
        from hospital.models_queue import QueueEntry, QueueConfiguration
        from .queue_service import queue_service
        
        try:
            today = timezone.now().date()
            updates_sent = 0
            
            # Get all waiting patients
            waiting_patients = QueueEntry.objects.filter(
                queue_date=today,
                status='checked_in',
                is_deleted=False
            ).select_related('patient', 'department')
            
            for queue_entry in waiting_patients:
                try:
                    # Get config
                    config = QueueConfiguration.objects.get(department=queue_entry.department)
                    if not config.send_progress_updates:
                        continue
                    
                    # Get current position
                    position = queue_service.get_position_in_queue(queue_entry)
                    
                    # Check if we should send update based on interval
                    interval = config.notification_interval_patients
                    
                    # Send update if position is a multiple of interval (e.g., 5, 10, 15)
                    if position > 0 and position % interval == 0:
                        # Check if we haven't sent recently (avoid spam)
                        if queue_entry.last_notification_sent:
                            minutes_since_last = (
                                timezone.now() - queue_entry.last_notification_sent
                            ).total_seconds() / 60
                            
                            if minutes_since_last < 10:  # Don't send more often than every 10 mins
                                continue
                        
                        # Send update
                        if self.send_progress_update(queue_entry):
                            updates_sent += 1
                
                except Exception as e:
                    self.logger.error(
                        f"Error checking queue entry {queue_entry.queue_number}: {str(e)}"
                    )
                    continue
            
            if updates_sent > 0:
                self.logger.info(f"📱 Sent {updates_sent} queue progress updates")
            
            return updates_sent
            
        except Exception as e:
            self.logger.error(f"Error in check_and_send_progress_updates: {str(e)}", exc_info=True)
            return 0
    
    def _get_patient_phone(self, patient):
        """Extract and format patient phone number"""
        # Get phone from patient model
        phone = getattr(patient, 'phone_number', None) or getattr(patient, 'phone', None)
        
        if not phone:
            self.logger.debug(f"No phone number found for patient {patient.mrn}")
            return None
        
        # Convert to string and clean
        phone = str(phone).strip()
        
        # Remove spaces, dashes, parentheses, dots
        phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
        
        # If empty after cleaning, return None
        if not phone:
            return None
        
        # Format for SMS service (it expects 233XXXXXXXXX format)
        # The SMS service will handle formatting, so just ensure we have a valid number
        # Remove + if present
        if phone.startswith('+'):
            phone = phone[1:]
        
        # Handle local numbers (starting with 0)
        if phone.startswith('0') and len(phone) == 10:
            phone = '233' + phone[1:]
        # Handle numbers without country code (9 digits)
        elif len(phone) == 9:
            phone = '233' + phone
        # Handle 00233 prefix
        elif phone.startswith('00233'):
            phone = phone[2:]
        
        # Validate format (should start with 233 and have 12 total digits)
        if phone.startswith('233') and len(phone) == 12 and phone[3:].isdigit():
            return phone
        elif phone.startswith('233'):
            # If it starts with 233 but wrong length, log warning but try anyway
            self.logger.warning(f"Phone number format unusual: {phone} (length: {len(phone)})")
            return phone
        
        # If doesn't start with 233, try to add it
        if not phone.startswith('233'):
            phone = '233' + phone.lstrip('0')
        
        return phone
    
    def _send_sms(self, phone, message, recipient_name='', message_type='queue_notification', 
                 related_object_id=None, related_object_type=''):
        """
        Send SMS via configured provider
        
        Args:
            phone: Phone number
            message: Message content
            recipient_name: Name of recipient (optional)
            message_type: Type of message (optional)
            related_object_id: Related object UUID (optional)
            related_object_type: Related object type (optional)
        
        Returns:
            bool: Success status
        """
        try:
            # Use the existing SMS service
            from .sms_service import sms_service
            
            self.logger.info(f"📱 Attempting to send SMS to {phone} for {recipient_name}")
            
            result = sms_service.send_sms(
                phone_number=phone,
                message=message,
                message_type=message_type,
                recipient_name=recipient_name,
                related_object_id=related_object_id,
                related_object_type=related_object_type
            )
            
            is_sent = result.status == 'sent'
            
            if is_sent:
                self.logger.info(f"✅ SMS sent successfully to {phone}")
            else:
                self.logger.warning(
                    f"⚠️ SMS send failed to {phone}. Status: {result.status}, "
                    f"Error: {getattr(result, 'error_message', 'No error message')}"
                )
            
            return is_sent
            
        except Exception as e:
            self.logger.error(f"❌ Exception sending SMS to {phone}: {str(e)}", exc_info=True)
            return False
    
    def _log_notification(self, queue_entry, notification_type, channel, message):
        """Log notification in database"""
        try:
            from hospital.models_queue import QueueNotification
            
            QueueNotification.objects.create(
                queue_entry=queue_entry,
                notification_type=notification_type,
                channel=channel,
                message_content=message,
                delivered=True
            )
            
        except Exception as e:
            self.logger.error(f"Error logging notification: {str(e)}", exc_info=True)


# Global instance
queue_notification_service = QueueNotificationService()



