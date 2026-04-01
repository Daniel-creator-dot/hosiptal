"""
SMS Service Integration
Handles SMS sending via API providers (Hubtel, Twilio, etc.)
"""
import os
import requests
import json
import logging
import re
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from ..models_advanced import SMSLog

logger = logging.getLogger(__name__)

# Patient SMS: only official payment receipts should show money (paid amount). Everything else
# gets currency stripped so draft/pending totals never go out by SMS. Staff procurement alerts
# may legitimately include estimated totals — keep those exempt.
_MESSAGE_TYPES_ALLOW_GHS_IN_SMS = frozenset({
    'payment_receipt',
    'procurement_approval',
})


def _should_strip_payment_amounts_from_sms(message_type: str) -> bool:
    return (message_type or '') not in _MESSAGE_TYPES_ALLOW_GHS_IN_SMS


def _strip_payment_amounts_from_sms_text(text: str) -> str:
    """Remove GHS/cedi amount patterns so patients never get wrong figures via SMS."""
    if not text:
        return text
    out = text
    out = re.sub(r'\bGHS\s*[\d,]+(?:\.\d{1,4})?\b', '', out, flags=re.IGNORECASE)
    out = re.sub(r'\bGH[₵c]\s*[\d,]+(?:\.\d{1,4})?\b', '', out, flags=re.IGNORECASE)
    out = re.sub(r'(?<![\d-])₵\s*[\d,]+(?:\.\d{1,4})?\b', '', out)
    out = re.sub(r'(?i)\boutstanding\s+balance\s+of\s+', 'outstanding balance — ', out)
    out = re.sub(r'[ \t]{2,}', ' ', out)
    out = re.sub(r' *\n *', '\n', out)
    out = re.sub(r'\n{3,}', '\n\n', out)
    return out.strip()


class SMSService:
    """SMS sending service"""
    
    def __init__(self):
        # SMS Notify GH API configuration
        # IMPORTANT: Set SMS_API_KEY in environment or settings
        # Default key may be invalid - always use your own API key
        default_key = '84c879bb-f9f9-4666-84a8-9f70a9b238cc'
        self.api_key = getattr(settings, 'SMS_API_KEY', None) or os.environ.get('SMS_API_KEY', default_key)
        self.sender_id = getattr(settings, 'SMS_SENDER_ID', None) or os.environ.get('SMS_SENDER_ID', 'PrimeCare')
        self.base_url = getattr(settings, 'SMS_API_URL', None) or os.environ.get('SMS_API_URL', 'https://sms.smsnotifygh.com/smsapi')
        
        # Track if using default key (warn only when actually sending SMS)
        self._using_default_key = (self.api_key == default_key)
        self._default_key_warned = False
    
    def send_sms(self, phone_number, message, message_type='general', recipient_name='', 
                 related_object_id=None, related_object_type=''):
        """
        Send SMS message
        
        Args:
            phone_number: Recipient phone number (format: +233XXXXXXXXX)
            message: SMS message text
            message_type: Type of message (appointment_reminder, result_ready, etc.)
            recipient_name: Name of recipient
            related_object_id: Related object UUID
            related_object_type: Related object type
            
        Returns:
            SMSLog instance
        """
        # Warn if using default API key (only once per service instance)
        if self._using_default_key and not self._default_key_warned:
            logger.warning("Using default SMS API key. This may be invalid. Set SMS_API_KEY in settings or environment.")
            self._default_key_warned = True

        original_phone = (phone_number or '').strip()
        message_original = message or ''
        if _should_strip_payment_amounts_from_sms(message_type):
            message_original = _strip_payment_amounts_from_sms_text(message_original)
        normalized_phone = self._normalize_phone(original_phone)
        normalized_message = self._normalize_message(message_original)

        # Fail fast if phone is missing (still log once)
        if not original_phone:
            return SMSLog.objects.create(
                recipient_phone='',
                recipient_name=recipient_name,
                message=message_original,
                message_type=message_type,
                status='failed',
                error_message="Phone number is required",
                related_object_id=related_object_id,
                related_object_type=related_object_type
            )

        # Deduplicate by normalized phone + message_type + normalized message within a short window
        dedup_window = timezone.now() - timedelta(minutes=10)
        try:
            from django.db import transaction
            with transaction.atomic():
                duplicate = SMSLog.objects.select_for_update().filter(
                    recipient_phone__in=[normalized_phone, original_phone.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')],
                    message__iexact=normalized_message,
                    message_type=message_type,
                    created__gte=dedup_window
                ).exclude(status='failed').order_by('-created').first()

                if duplicate:
                    logger.info(f"Duplicate SMS suppressed for {normalized_phone} [{message_type}] within 10 minutes")
                    return duplicate

                # Create SMS log entry AFTER deduplication check
                sms_log = SMSLog.objects.create(
                    recipient_phone=normalized_phone,
                    recipient_name=recipient_name,
                    message=normalized_message,
                    message_type=message_type,
                    status='pending',
                    related_object_id=related_object_id,
                    related_object_type=related_object_type
                )
        except Exception as dedup_error:
            logger.warning(f"SMS deduplication check failed: {dedup_error}")
            # Fallback: create log without lock
            sms_log = SMSLog.objects.create(
                recipient_phone=normalized_phone,
                recipient_name=recipient_name,
                message=normalized_message,
                message_type=message_type,
                status='pending',
                related_object_id=related_object_id,
                related_object_type=related_object_type
            )

        try:
            # Validate final phone number format
            if not normalized_phone.startswith('233'):
                sms_log.status = 'failed'
                sms_log.error_message = f"Invalid phone number format: {original_phone} (formatted: {normalized_phone}). Must start with 233 for Ghana."
                sms_log.provider_response = {
                    'original_phone': original_phone,
                    'formatted_phone': normalized_phone,
                    'validation_error': 'Must start with 233'
                }
                sms_log.save()
                return sms_log
            
            if len(normalized_phone) != 12:
                sms_log.status = 'failed'
                sms_log.error_message = f"Invalid phone number length: {original_phone} (formatted: {normalized_phone}, length: {len(normalized_phone)}). Expected 12 digits (233XXXXXXXXX)."
                sms_log.provider_response = {
                    'original_phone': original_phone,
                    'formatted_phone': normalized_phone,
                    'length': len(normalized_phone),
                    'validation_error': f'Expected 12 digits, got {len(normalized_phone)}'
                }
                sms_log.save()
                return sms_log
            
            # Additional validation: check if all digits after 233 are numeric
            if not normalized_phone[3:].isdigit():
                sms_log.status = 'failed'
                sms_log.error_message = f"Invalid phone number: {original_phone} contains non-numeric characters after country code."
                sms_log.provider_response = {
                    'original_phone': original_phone,
                    'formatted_phone': normalized_phone,
                    'validation_error': 'Contains non-numeric characters'
                }
                sms_log.save()
                return sms_log
            
            # Prepare request payload for SMS Notify GH API
            payload = {
                'key': self.api_key,
                'to': normalized_phone,
                'msg': message_original,
                'sender_id': self.sender_id
            }
            
            # Send SMS via API (GET request for SMS Notify GH)
            response = requests.get(
                self.base_url,
                params=payload,
                timeout=30
            )
            
            # Handle response - SMS Notify GH returns JSON format:
            # {"success":true,"code":1000,"message":"message submitted successfully","data":{...}}
            # OR plain text status codes: "1701" = Success, "1702" = Invalid URL, etc.
            response_text = response.text.strip()
            response_lower = response_text.lower()
            
            # Check for success indicators
            if response.status_code == 200:
                # Try to parse as JSON first (new API format)
                try:
                    import json
                    response_json = json.loads(response_text)
                    
                    # Check for JSON success response
                    # API returns: {"success":true,"code":1000,"message":"message submitted successfully",...}
                    success_flag = response_json.get('success', False)
                    code_value = response_json.get('code', None)
                    
                    # Handle both boolean True and string "true", and both int 1000 and string "1000"
                    is_success = (
                        success_flag is True or 
                        (isinstance(success_flag, str) and success_flag.lower() == 'true') or
                        code_value == 1000 or
                        (isinstance(code_value, str) and code_value == '1000')
                    )
                    
                    # Log the parsed values for debugging
                    logger.debug(f"SMS API Response - success flag: {success_flag} (type: {type(success_flag)}), code: {code_value} (type: {type(code_value)}), is_success: {is_success}")
                    logger.debug(f"Full API response: {response_json}")
                    
                    if is_success:
                        sms_log.status = 'sent'
                        sms_log.sent_at = timezone.now()
                        sms_log.provider_response = {
                            'status': 'success',
                            'status_code': response.status_code,
                            'response': response_text,
                            'parsed_response': response_json,
                            'phone_sent_to': normalized_phone,
                            'api_success': success_flag,
                            'api_code': code_value
                        }
                        logger.info(f"✅ SMS marked as SENT for {normalized_phone}. API success={success_flag}, code={code_value}")
                    else:
                        # JSON response but not successful
                        error_code = response_json.get('code', 'unknown')
                        error_msg = response_json.get('message', response_text)
                        sms_log.status = 'failed'
                        
                        logger.warning(f"⚠️ SMS API returned failure for {normalized_phone}. Code: {error_code}, Message: {error_msg}")
                        
                        # Provide more helpful error messages
                        if error_code == 1004:
                            sms_log.error_message = f"INVALID API KEY (code {error_code}): {error_msg}. Please update SMS_API_KEY in settings or environment variables."
                        elif error_code == 1707:
                            sms_log.error_message = f"INSUFFICIENT BALANCE (code {error_code}): {error_msg}. Please top up your SMS account."
                        elif error_code == 1704:
                            sms_log.error_message = f"INVALID PHONE NUMBER (code {error_code}): {error_msg}. Phone: {normalized_phone}"
                        elif error_code == 1706:
                            sms_log.error_message = f"INVALID SENDER ID (code {error_code}): {error_msg}. Check SMS_SENDER_ID setting."
                        else:
                            sms_log.error_message = f"API Error (code {error_code}): {error_msg}"
                        
                        sms_log.provider_response = {
                            'status': 'failed',
                            'status_code': response.status_code,
                            'response': response_text,
                            'parsed_response': response_json,
                            'phone_attempted': normalized_phone,
                            'api_key_used': self.api_key[:10] + '...' if len(self.api_key) > 10 else self.api_key
                        }
                except (json.JSONDecodeError, ValueError) as parse_error:
                    # Not JSON - try old format (plain text status codes)
                    logger.warning(f"SMS API returned non-JSON response. Trying to parse as plain text. Error: {str(parse_error)}, Response: {response_text[:200]}")
                    
                    # Success codes: "1701" or contains "success"/"sent"
                    if response_text.startswith('1701') or 'success' in response_lower or 'sent' in response_lower or '1000' in response_text:
                        sms_log.status = 'sent'
                        sms_log.sent_at = timezone.now()
                        sms_log.provider_response = {
                            'status': 'success',
                            'status_code': response.status_code,
                            'response': response_text,
                            'phone_sent_to': normalized_phone,
                            'format': 'plain_text'
                        }
                        logger.info(f"✅ SMS marked as SENT (plain text format) for {normalized_phone}")
                    else:
                        # Error codes (old format)
                        sms_log.status = 'failed'
                        error_map = {
                            '1702': 'Invalid URL',
                            '1703': 'Invalid API key',
                            '1704': 'Invalid phone number',
                            '1705': 'Invalid message',
                            '1706': 'Invalid sender ID',
                            '1707': 'Insufficient balance',
                            '1708': 'Invalid credentials'
                        }
                        error_code = response_text[:4] if len(response_text) >= 4 else 'unknown'
                        error_msg = error_map.get(error_code, response_text[:200])
                        sms_log.error_message = f"API Error ({error_code}): {error_msg}. Raw response: {response_text[:200]}"
                        sms_log.provider_response = {
                            'status': 'failed',
                            'status_code': response.status_code,
                            'response': response_text,
                            'phone_attempted': normalized_phone,
                            'format': 'plain_text',
                            'parse_error': str(parse_error)
                        }
                        logger.error(f"❌ SMS failed (plain text format) for {normalized_phone}. Error code: {error_code}, Message: {error_msg}")
            else:
                sms_log.status = 'failed'
                sms_log.error_message = f"HTTP {response.status_code}: {response.text}"
                sms_log.provider_response = {
                    'status': 'failed',
                    'status_code': response.status_code,
                    'response': response.text,
                    'phone_attempted': normalized_phone
                }
            
        except requests.exceptions.Timeout:
            sms_log.status = 'failed'
            sms_log.error_message = "Request timeout - API did not respond within 30 seconds"
        except requests.exceptions.ConnectionError as e:
            sms_log.status = 'failed'
            sms_log.error_message = f"Connection error: Unable to reach SMS API server"
        except requests.exceptions.RequestException as e:
            sms_log.status = 'failed'
            sms_log.error_message = f"Request error: {str(e)}"
        except Exception as e:
            sms_log.status = 'failed'
            sms_log.error_message = f"Unexpected error: {str(e)}"
            import traceback
            sms_log.provider_response = {'error_traceback': traceback.format_exc()}
        
        sms_log.save()
        return sms_log

    @staticmethod
    def _normalize_phone(phone):
        """Normalize phone to 233XXXXXXXXX format as much as possible"""
        phone = phone.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '').strip()
        if phone.startswith('0'):
            phone = '233' + phone[1:]
        elif not phone.startswith('233'):
            if phone.startswith('00233'):
                phone = phone[2:]
            elif len(phone) == 9:
                phone = '233' + phone
            elif len(phone) == 10 and phone.startswith('0'):
                phone = '233' + phone[1:]
            elif not phone.startswith('233'):
                phone = '233' + phone
        return phone

    @staticmethod
    def _normalize_message(message):
        """Normalize message for deduplication without changing user-facing text meaningfully"""
        if not message:
            return ''
        # Collapse repeated whitespace but keep single spaces; strip ends
        return re.sub(r'\s+', ' ', message).strip()
    
    
    def send_appointment_reminder(self, appointment):
        """Send appointment reminder SMS"""
        patient = appointment.patient
        provider = appointment.provider
        date_str = appointment.appointment_date.strftime('%d/%m/%Y at %I:%M %p')
        
        message = (
            f"Dear {patient.first_name},\n\n"
            f"Your appointment with Dr. {provider.user.get_full_name()}\n"
            f"is scheduled for {date_str}.\n\n"
            f"Please arrive 15 minutes early.\n\n"
            f"Reply STOP to opt out."
        )
        
        return self.send_sms(
            phone_number=patient.phone_number,
            message=message,
            message_type='appointment_reminder',
            recipient_name=patient.full_name,
            related_object_id=appointment.id,
            related_object_type='Appointment'
        )
    
    def send_lab_result_ready(self, lab_result):
        """Send lab result ready notification"""
        try:
            patient = lab_result.order.encounter.patient

            # Check if patient has phone number
            if not patient.phone_number or not patient.phone_number.strip():
                # Create a failed log entry
                sms_log = SMSLog.objects.create(
                    recipient_phone='',
                    recipient_name=patient.full_name,
                    message='',
                    message_type='lab_result_ready',
                    status='failed',
                    error_message=f"Patient {patient.full_name} does not have a phone number",
                    related_object_id=lab_result.id,
                    related_object_type='LabResult'
                )
                return sms_log
            
            # Build message with result summary if available (no specific test name in SMS)
            message = f"Dear {patient.first_name},\n\n"
            message += "Your lab test results are ready.\n"
            
            # Add result summary if completed
            if lab_result.status == 'completed' and lab_result.value:
                result_text = f"Result: {lab_result.value}"
                if lab_result.units:
                    result_text += f" {lab_result.units}"
                if lab_result.range_low and lab_result.range_high:
                    result_text += f" (Normal range: {lab_result.range_low}-{lab_result.range_high})"
                if lab_result.is_abnormal:
                    result_text += " - ABNORMAL"
                message += f"{result_text}\n"
                
                # Add verification info if available
                if lab_result.verified_by:
                    message += f"Verified by: Dr. {lab_result.verified_by.user.get_full_name() or lab_result.verified_by.user.username}\n"
                if lab_result.verified_at:
                    message += f"Verified on: {lab_result.verified_at.strftime('%B %d, %Y at %I:%M %p')}\n"
            
            # Add reference number
            message += f"Reference: {lab_result.order.encounter.patient.mrn}\n"
            
            message += "\nPlease visit the hospital or check your patient portal for full details.\n\n"
            message += "Thank you,\nPrimeCare Hospital"
            
            return self.send_sms(
                phone_number=patient.phone_number,
                message=message,
                message_type='lab_result_ready',
                recipient_name=patient.full_name,
                related_object_id=lab_result.id,
                related_object_type='LabResult'
            )
        except AttributeError as e:
            # Handle missing relationships
            sms_log = SMSLog.objects.create(
                recipient_phone='',
                recipient_name='',
                message='',
                message_type='lab_result_ready',
                status='failed',
                error_message=f"Missing relationship: {str(e)}",
                related_object_id=lab_result.id if hasattr(lab_result, 'id') else None,
                related_object_type='LabResult'
            )
            return sms_log
    
    def send_payment_reminder(self, invoice):
        """Send payment reminder SMS (no amounts — patient confirms total at Cashier)."""
        patient = invoice.patient
        
        message = (
            f"Dear {patient.first_name},\n\n"
            f"You have an outstanding balance on invoice {invoice.invoice_number}.\n"
            f"Please go to the Cashier to settle your bill — the correct amount is available there.\n\n"
            f"Thank you."
        )
        
        return self.send_sms(
            phone_number=patient.phone_number,
            message=message,
            message_type='payment_reminder',
            recipient_name=patient.full_name,
            related_object_id=invoice.id,
            related_object_type='Invoice'
        )
    
    def send_leave_approved(self, leave_request):
        """Send leave approval notification SMS"""
        staff = leave_request.staff
        staff_name = staff.user.first_name or staff.user.get_full_name()
        
        # Get phone number from staff - check phone_number field first
        phone_number = getattr(staff, 'phone_number', None) or getattr(staff, 'phone', None)
        
        # Also try user's username as phone (some systems use phone as username)
        if not phone_number and staff.user.username and staff.user.username.replace('+', '').replace(' ', '').isdigit():
            phone_number = staff.user.username
        
        if not phone_number:
            # Create failed log
            sms_log = SMSLog.objects.create(
                recipient_phone='',
                recipient_name=staff.user.get_full_name(),
                message='',
                message_type='leave_approved',
                status='failed',
                error_message=f"Staff {staff.user.get_full_name()} does not have a phone number. Checked: phone_number={getattr(staff, 'phone_number', 'N/A')}, phone={getattr(staff, 'phone', 'N/A')}, username={staff.user.username}",
                related_object_id=leave_request.id,
                related_object_type='LeaveRequest'
            )
            return sms_log
        
        message = (
            f"Hello {staff_name},\n\n"
            f"Your leave request has been approved.\n\n"
            f"Type: {leave_request.get_leave_type_display()}\n"
            f"Dates: {leave_request.start_date.strftime('%d/%m/%Y')} to {leave_request.end_date.strftime('%d/%m/%Y')}\n"
            f"Days: {leave_request.days_requested} working day(s)\n\n"
            f"Kindly ensure all pending duties are properly handed over before your departure. "
            f"Wishing you a restful and refreshing break.\n\n"
            f"— PrimeCare Management"
        )
        
        return self.send_sms(
            phone_number=phone_number,
            message=message,
            message_type='leave_approved',
            recipient_name=staff.user.get_full_name(),
            related_object_id=leave_request.id,
            related_object_type='LeaveRequest'
        )
    
    def send_leave_rejected(self, leave_request):
        """Send leave rejection notification SMS"""
        staff = leave_request.staff
        staff_name = staff.user.first_name or staff.user.get_full_name()
        
        # Get phone number from staff - check phone_number field first
        phone_number = getattr(staff, 'phone_number', None) or getattr(staff, 'phone', None)
        
        # Also try user's username as phone
        if not phone_number and staff.user.username and staff.user.username.replace('+', '').replace(' ', '').isdigit():
            phone_number = staff.user.username
        
        if not phone_number:
            # Create failed log
            sms_log = SMSLog.objects.create(
                recipient_phone='',
                recipient_name=staff.user.get_full_name(),
                message='',
                message_type='leave_rejected',
                status='failed',
                error_message=f"Staff {staff.user.get_full_name()} does not have a phone number",
                related_object_id=leave_request.id,
                related_object_type='LeaveRequest'
            )
            return sms_log
        
        message = (
            f"Dear {staff_name},\n\n"
            f"Your leave request has been REJECTED.\n\n"
            f"Type: {leave_request.get_leave_type_display()}\n"
            f"Dates: {leave_request.start_date.strftime('%d/%m/%Y')} to {leave_request.end_date.strftime('%d/%m/%Y')}\n"
        )
        
        if leave_request.rejection_reason:
            message += f"\nReason: {leave_request.rejection_reason}\n"
        
        message += (
            f"\nPlease contact your supervisor for clarification.\n\n"
            f"PrimeCare Hospital"
        )
        
        return self.send_sms(
            phone_number=phone_number,
            message=message,
            message_type='leave_rejected',
            recipient_name=staff.user.get_full_name(),
            related_object_id=leave_request.id,
            related_object_type='LeaveRequest'
        )
    
    def send_leave_submitted(self, leave_request):
        """Send notification to manager when leave is submitted"""
        staff = leave_request.staff
        
        # Get manager/supervisor (could be department head or HR)
        manager_phone = None
        manager_name = "Manager"
        
        if staff.department and hasattr(staff.department, 'head') and staff.department.head:
            manager_staff = staff.department.head
            manager_phone = manager_staff.phone if hasattr(manager_staff, 'phone') else None
            manager_name = manager_staff.user.first_name or manager_staff.user.get_full_name()
        
        if not manager_phone:
            # No manager phone, skip notification
            return None
        
        message = (
            f"Dear {manager_name},\n\n"
            f"New leave request submitted by {staff.user.get_full_name()}:\n\n"
            f"Type: {leave_request.get_leave_type_display()}\n"
            f"Dates: {leave_request.start_date.strftime('%d/%m/%Y')} to {leave_request.end_date.strftime('%d/%m/%Y')}\n"
            f"Days: {leave_request.days_requested}\n\n"
            f"Please review and approve/reject.\n\n"
            f"PrimeCare Hospital"
        )
        
        return self.send_sms(
            phone_number=manager_phone,
            message=message,
            message_type='leave_submitted',
            recipient_name=manager_name,
            related_object_id=leave_request.id,
            related_object_type='LeaveRequest'
        )
    
    def send_birthday_wish(self, staff):
        """Send birthday wish SMS to staff"""
        staff_name = staff.user.first_name or staff.user.get_full_name()
        
        # Get phone number
        phone_number = staff.phone_number if staff.phone_number else None
        
        if not phone_number:
            # Create failed log
            sms_log = SMSLog.objects.create(
                recipient_phone='',
                recipient_name=staff.user.get_full_name(),
                message='',
                message_type='birthday_wish',
                status='failed',
                error_message=f"Staff {staff.user.get_full_name()} does not have a phone number",
                related_object_id=staff.id,
                related_object_type='Staff'
            )
            return sms_log
        
        # Calculate age
        age = staff.age if staff.age else ''
        age_text = f" (Age: {age})" if age else ''
        
        message = (
            f"🎉 Happy Birthday, {staff_name}!{age_text}\n\n"
            f"The entire PrimeCare Hospital family wishes you a wonderful day "
            f"filled with joy, happiness, and good health.\n\n"
            f"Thank you for your dedication and service!\n\n"
            f"Best wishes,\n"
            f"PrimeCare Hospital Management"
        )
        
        return self.send_sms(
            phone_number=phone_number,
            message=message,
            message_type='birthday_wish',
            recipient_name=staff.user.get_full_name(),
            related_object_id=staff.id,
            related_object_type='Staff'
        )
    
    def send_birthday_reminder_to_department(self, staff):
        """Send birthday reminder to department head/colleagues"""
        # Get department head or manager
        if not staff.department:
            return None
        
        department_head = staff.department.head if hasattr(staff.department, 'head') and staff.department.head else None
        
        if not department_head or not department_head.phone_number:
            return None
        
        message = (
            f"Birthday Reminder!\n\n"
            f"It's {staff.user.get_full_name()}'s birthday today!\n"
            f"Department: {staff.department.name}\n"
            f"Profession: {staff.get_profession_display()}\n\n"
            f"Consider celebrating with the team!\n\n"
            f"PrimeCare Hospital"
        )
        
        return self.send_sms(
            phone_number=department_head.phone_number,
            message=message,
            message_type='birthday_reminder',
            recipient_name=department_head.user.get_full_name(),
            related_object_id=staff.id,
            related_object_type='Staff'
        )


# Singleton instance
sms_service = SMSService()

