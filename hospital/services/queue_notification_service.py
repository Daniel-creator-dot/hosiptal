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

Your visit ticket: {queue_number}
(Use this code on the queue screen and when called.)

📍 {department}
👥 You are #{position} in line
⏱️ Est. wait: ~{wait_time} min
📅 {date}

Please wait in the reception area — you will receive SMS when it is your turn.""",

        'progress_update': """🏥 Queue update

Ticket {queue_number}
You're now #{position} in line
⏱️ Est. wait: ~{wait_time} min

Thanks for waiting — we're moving as fast as we can.""",

        'ready': """🏥 It's your turn — {queue_number}

📍 Please go to:
   {room_info}

Please arrive within 5 minutes. Show this ticket if asked.""",

        'no_show': """🏥 Please come to the desk

Ticket {queue_number} — we called you but there was no response.

Please see reception right away so you don't lose your place.""",

        'completed': """🏥 Thank you for visiting!

Ticket {queue_number} — visit completed

💊 Next steps:
{next_steps}

📱 Questions? Call: {hospital_phone}
Visit us: {hospital_name}"""
    }
    
    def __init__(self):
        self.logger = logger
        self.hospital_name = getattr(settings, 'HOSPITAL_NAME', 'General Hospital')
        self.hospital_phone = getattr(settings, 'HOSPITAL_PHONE', '0123456789')

    def _ticket_label(self, queue_entry):
        """Patient-facing ticket number without internal prefix."""
        try:
            ticket = getattr(queue_entry, 'display_ticket_number', None)
            if ticket is not None:
                s = str(ticket).strip()
                if s and s != '---':
                    return s
        except Exception:
            pass
        return str(getattr(queue_entry, 'queue_number', '') or '')
    
    def send_check_in_notification(self, queue_entry, consultation_amount=None):
        """
        Send check-in confirmation SMS. If consultation_amount is set, reminds patient
        to pay at Cashier (no amounts in SMS).

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
            
            # Check for pending bills if consultation_amount not provided
            if consultation_amount is None and queue_entry.encounter:
                try:
                    from hospital.models import Invoice, InvoiceLine
                    from decimal import Decimal
                    invoice = Invoice.objects.filter(
                        encounter=queue_entry.encounter,
                        is_deleted=False,
                        status__in=['draft', 'pending', 'unpaid']
                    ).first()
                    
                    if invoice:
                        # Get consultation charge amount
                        consultation_line = invoice.invoice_lines.filter(
                            service_code__code__in=['CON001', 'CON002'],
                            is_deleted=False
                        ).first()
                        
                        if consultation_line:
                            consultation_amount = consultation_line.unit_price
                except Exception as e:
                    self.logger.warning(f"Error checking for consultation amount: {e}")
            
            # Format base message
            department_name = queue_entry.department.name if queue_entry.department else 'General'
            ticket = self._ticket_label(queue_entry)
            base_message = self.TEMPLATES['check_in'].format(
                hospital_name=self.hospital_name,
                queue_number=ticket,
                department=department_name,
                position=position,
                wait_time=queue_entry.estimated_wait_minutes or 0,
                date=queue_entry.queue_date.strftime('%b %d, %Y')
            )
            
            # Remind to pay at Cashier (no amounts in SMS — total is confirmed at desk)
            payment_info = ""
            if consultation_amount:
                payment_info = (
                    "\n\nPlease proceed to the Cashier to make payment before consultation.\n"
                    "Your correct bill is available at the desk."
                )
            
            message = base_message + payment_info
            
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
            ticket = self._ticket_label(queue_entry)
            message = self.TEMPLATES['progress_update'].format(
                queue_number=ticket,
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
        Send "your turn" notification with room and doctor information
        
        Args:
            queue_entry: QueueEntry object
        
        Returns:
            bool: Success status
        """
        try:
            # Log attempt
            self.logger.info(f"📱 Attempting to send ready notification for queue {queue_entry.queue_number}")
            
            # Check if patient exists
            if not queue_entry.patient:
                self.logger.error(f"QueueEntry {queue_entry.queue_number} has no patient assigned")
                return False
            
            # Get patient phone number
            phone = self._get_patient_phone(queue_entry.patient)
            if not phone:
                self.logger.warning(
                    f"⚠️ Cannot send SMS: Patient {queue_entry.patient.full_name} (MRN: {queue_entry.patient.mrn}) "
                    f"has no valid phone number. Phone field value: '{getattr(queue_entry.patient, 'phone_number', 'None')}'"
                )
                return False
            
            self.logger.info(f"📱 Phone number found for {queue_entry.patient.full_name}: {phone}")
            
            # Format room info with doctor name
            room_info = queue_entry.room_number or 'Main Consultation Area'
            doctor_name = ''
            if queue_entry.assigned_doctor:
                doctor_name = queue_entry.assigned_doctor.get_full_name() or queue_entry.assigned_doctor.username
                # Format: "Room 5 - Dr. John Doe" or "Dr. John Doe - Room 5"
                if room_info and room_info != 'Main Consultation Area':
                    room_info = f"{room_info} - Dr. {doctor_name}"
                elif doctor_name:
                    room_info = f"Dr. {doctor_name} - Main Consultation Area"
            
            # Enhanced message with more details
            ticket = self._ticket_label(queue_entry)
            if doctor_name and room_info and room_info != 'Main Consultation Area':
                message = (
                    f"🏥 It's your turn\n\n"
                    f"Ticket {ticket}\n\n"
                    f"👨‍⚕️ Dr. {doctor_name}\n"
                    f"🚪 Room {queue_entry.room_number}\n\n"
                    f"Please go to that room now.\n\n"
                    f"⚠️ Please arrive within 5 minutes.\n\n"
                    f"— {self.hospital_name}"
                )
            elif doctor_name:
                message = (
                    f"🏥 It's your turn\n\n"
                    f"Ticket {ticket}\n\n"
                    f"👨‍⚕️ Dr. {doctor_name}\n\n"
                    f"Please go to the consultation area now.\n\n"
                    f"⚠️ Within 5 minutes please.\n\n"
                    f"— {self.hospital_name}"
                )
            else:
                # Fallback to template format
                message = self.TEMPLATES['ready'].format(
                    queue_number=ticket,
                    room_info=room_info
                )
            
            # Send SMS
            self.logger.info(f"📱 Sending SMS to {phone} for patient {queue_entry.patient.full_name} (Queue: {queue_entry.queue_number})")
            self.logger.debug(f"Message content (first 300 chars):\n{message[:300]}")
            self.logger.debug(f"Full message length: {len(message)} characters")
            
            # Convert UUID to string for related_object_id
            related_id = str(queue_entry.id) if queue_entry.id else None
            
            self.logger.debug(f"SMS parameters: phone={phone}, recipient={queue_entry.patient.full_name}, type=queue_ready, related_id={related_id}")
            
            success = self._send_sms(
                phone, 
                message, 
                recipient_name=queue_entry.patient.full_name,
                message_type='queue_ready',
                related_object_id=related_id,
                related_object_type='QueueEntry'
            )
            
            if success:
                try:
                    self._log_notification(queue_entry, 'ready', 'sms', message)
                    queue_entry.notification_count += 1
                    queue_entry.last_notification_sent = timezone.now()
                    queue_entry.save(update_fields=['notification_count', 'last_notification_sent', 'modified'])
                    
                    self.logger.info(f"✅ Ready notification sent successfully to {queue_entry.patient.full_name} at {phone}")
                except Exception as save_error:
                    self.logger.error(f"Error updating queue entry after SMS send: {str(save_error)}")
            else:
                self.logger.warning(
                    f"⚠️ SMS send failed for {queue_entry.patient.full_name} at {phone}. "
                    f"Queue: {queue_entry.queue_number}"
                )
            
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
            ticket = self._ticket_label(queue_entry)
            message = self.TEMPLATES['no_show'].format(
                queue_number=ticket
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
            ticket = self._ticket_label(queue_entry)
            message = self.TEMPLATES['completed'].format(
                queue_number=ticket,
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
            related_object_id: Related object UUID (optional) - will be converted to string
            related_object_type: Related object type (optional)
        
        Returns:
            bool: Success status
        """
        try:
            # Use the existing SMS service
            from .sms_service import sms_service
            
            self.logger.info(f"📱 Attempting to send SMS to {phone} for {recipient_name}")
            self.logger.debug(f"SMS Details: type={message_type}, related_id={related_object_id}, related_type={related_object_type}")
            
            # Convert UUID to string if needed
            if related_object_id and not isinstance(related_object_id, str):
                related_object_id = str(related_object_id)
            
            result = sms_service.send_sms(
                phone_number=phone,
                message=message,
                message_type=message_type,
                recipient_name=recipient_name,
                related_object_id=related_object_id,
                related_object_type=related_object_type
            )
            
            # Check if result is valid
            if not result:
                self.logger.error(f"❌ SMS service returned None/empty result for {phone}")
                return False
            
            is_sent = getattr(result, 'status', None) == 'sent'
            
            if is_sent:
                self.logger.info(f"✅ SMS sent successfully to {phone} for {recipient_name}")
            else:
                status = getattr(result, 'status', 'unknown')
                error_msg = getattr(result, 'error_message', getattr(result, 'message', 'No error message'))
                self.logger.warning(
                    f"⚠️ SMS send failed to {phone}. Status: {status}, "
                    f"Error: {error_msg}. "
                    f"Result object: {result}"
                )
            
            return is_sent
            
        except Exception as e:
            self.logger.error(f"❌ Exception sending SMS to {phone} for {recipient_name}: {str(e)}", exc_info=True)
            import traceback
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
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



