"""
SMS Service Integration
Handles SMS sending via Intek SMS API (https://www.inteksms.top).
"""
import os
import requests
import json
import logging
import re
from urllib.parse import urlparse, urljoin
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from ..models_advanced import SMSLog

logger = logging.getLogger(__name__)

# Appended to automated / manual lab SMS so patients know how to follow up clinically.
LAB_SMS_NURSE_DOCTOR_LINE = "Please see a nurse to schedule you to see a doctor."

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
        # Intek SMS API — override via SMS_API_KEY / SMS_SENDER_ID / SMS_API_URL in env or settings
        default_key = 'INTEK_C29C88.0e7310c3b08164b4773cc74d81ab234b203b38a42800120f'
        self.api_key = getattr(settings, 'SMS_API_KEY', None) or os.environ.get('SMS_API_KEY', default_key)
        self.sender_id = getattr(settings, 'SMS_SENDER_ID', None) or os.environ.get('SMS_SENDER_ID', 'Primecare')
        self.base_url = getattr(settings, 'SMS_API_URL', None) or os.environ.get(
            'SMS_API_URL', 'https://www.inteksms.top/api/v1/messages/send'
        )
        self.wallet_url = getattr(settings, 'SMS_WALLET_URL', None) or os.environ.get(
            'SMS_WALLET_URL', 'https://www.inteksms.top/api/v1/balance'
        )

        self._using_default_key = (self.api_key == default_key)
        self._default_key_warned = False

    def _auth_headers(self, accept_json=True):
        headers = {'Authorization': f'Bearer {self.api_key}'}
        if accept_json:
            headers['Accept'] = 'application/json'
        return headers

    @staticmethod
    def _format_wallet_display(value):
        if value is None:
            return None
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, int):
            return f'{value:,}'
        if isinstance(value, float):
            if value == int(value):
                return f'{int(value):,}'
            return f'{value:,.2f}'.rstrip('0').rstrip('.')
        return str(value).strip()

    @classmethod
    def _parse_wallet_balance_payload(cls, data):
        """Extract balance value and display string from provider JSON `data` (shape varies)."""
        if data is None:
            return None, None
        if isinstance(data, (int, float)) and not isinstance(data, bool):
            return data, cls._format_wallet_display(data)
        if isinstance(data, str):
            s = data.strip()
            return (s, s) if s else (None, None)
        if isinstance(data, dict):
            for key in (
                'balance', 'sms_balance', 'credit', 'credits', 'wallet_balance',
                'amount', 'sms', 'units', 'remaining',
            ):
                if key not in data or data[key] in (None, ''):
                    continue
                val = data[key]
                if isinstance(val, dict):
                    nested_val, nested_disp = cls._parse_wallet_balance_payload(val)
                    if nested_disp:
                        return nested_val, nested_disp
                else:
                    return val, cls._format_wallet_display(val)
            if isinstance(data.get('wallet'), dict):
                return cls._parse_wallet_balance_payload(data['wallet'])
        return None, None

    def _wallet_url_candidates(self):
        """Ordered URLs to try for balance (SMS_WALLET_URL, then …/api/v1/balance on send host)."""
        seen = set()
        out = []
        for candidate in (self.wallet_url, getattr(settings, 'SMS_WALLET_URL', None), os.environ.get('SMS_WALLET_URL')):
            if candidate and str(candidate).strip():
                u = str(candidate).strip()
                if u not in seen:
                    seen.add(u)
                    out.append(u)
        parsed = urlparse(self.base_url)
        if parsed.scheme and parsed.netloc:
            origin = f'{parsed.scheme}://{parsed.netloc}'.rstrip('/')
            derived = urljoin(origin + '/', 'api/v1/balance')
            if derived not in seen:
                seen.add(derived)
                out.append(derived)
        return out

    def _interpret_intek_wallet_body(self, body, raw_text):
        """Map Intek SMS ``GET /api/v1/balance`` JSON to a wallet result dict."""
        if body.get('ok') is True:
            data = body.get('data') or {}
            units = data.get('balance_units')
            display = self._format_wallet_display(units) if units is not None else None
            if display:
                display = f'{display} units'
            return {
                'ok': True,
                'balance_display': display or '—',
                'message': (body.get('message') or '').strip(),
            }
        err = body.get('error') or body.get('message') or (raw_text or '')[:200]
        return {'ok': False, 'error': err, 'code': body.get('code')}

    def _request_wallet_get(self, url, timeout=15):
        """GET balance from Intek SMS (Bearer auth)."""
        try:
            response = requests.get(
                url,
                timeout=timeout,
                headers=self._auth_headers(),
            )
        except requests.exceptions.Timeout:
            return {'ok': False, 'error': 'SMS provider did not respond in time.'}
        except requests.exceptions.RequestException as exc:
            logger.warning('SMS wallet request failed (%s): %s', url, exc)
            return {'ok': False, 'error': f'Could not reach SMS provider: {exc}'}

        text = (response.text or '').strip()
        if not text or text.lstrip().startswith('<'):
            return None
        try:
            body = json.loads(text)
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning('SMS wallet: non-JSON from %s: %s', url, text[:300])
            return None
        if response.status_code == 401:
            return {'ok': False, 'error': body.get('error') or 'Invalid API key', 'code': 401}
        return self._interpret_intek_wallet_body(body, text)

    def fetch_wallet_balance(self, timeout=15):
        """Query SMS credit balance from Intek SMS ``GET /api/v1/balance``."""
        for wallet_link in self._wallet_url_candidates():
            result = self._request_wallet_get(wallet_link, timeout=timeout)
            if result is None:
                continue
            if result.get('ok'):
                return result
            if result.get('code') in (401, '401'):
                return result
        return {
            'ok': False,
            'error': 'Could not read SMS wallet balance from Intek SMS.',
        }
    
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
            
            # Intek SMS API: POST JSON with Bearer token
            payload = {
                'recipients': [normalized_phone],
                'message': message_original,
                'sender': self.sender_id,
            }
            headers = {**self._auth_headers(), 'Content-Type': 'application/json'}
            response = requests.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=30,
            )

            response_text = (response.text or '').strip()
            if response.status_code in (200, 201):
                try:
                    response_json = json.loads(response_text)
                except (json.JSONDecodeError, ValueError):
                    sms_log.status = 'failed'
                    sms_log.error_message = f'Invalid JSON from SMS provider: {response_text[:200]}'
                    sms_log.provider_response = {
                        'status': 'failed',
                        'status_code': response.status_code,
                        'response': response_text,
                        'phone_attempted': normalized_phone,
                    }
                else:
                    if response_json.get('ok') is True:
                        sms_log.status = 'sent'
                        sms_log.sent_at = timezone.now()
                        sms_log.provider_response = {
                            'status': 'success',
                            'status_code': response.status_code,
                            'response': response_text,
                            'parsed_response': response_json,
                            'phone_sent_to': normalized_phone,
                        }
                        logger.info('SMS sent via Intek for %s', normalized_phone)
                    else:
                        error_msg = response_json.get('error') or response_json.get('message') or response_text
                        hint = response_json.get('hint', '')
                        sms_log.status = 'failed'
                        if response.status_code == 401 or 'authorization' in str(error_msg).lower():
                            sms_log.error_message = (
                                f'Invalid API key: {error_msg}. Update SMS_API_KEY in settings or environment.'
                            )
                        elif 'sender' in str(error_msg).lower():
                            sms_log.error_message = (
                                f'Invalid sender ID ({self.sender_id}): {error_msg}. Check SMS_SENDER_ID.'
                            )
                        elif 'recipient' in str(error_msg).lower():
                            sms_log.error_message = f'Invalid phone number: {error_msg}. Phone: {normalized_phone}'
                        else:
                            sms_log.error_message = f'API error: {error_msg}'
                        if hint:
                            sms_log.error_message += f' ({hint})'
                        sms_log.provider_response = {
                            'status': 'failed',
                            'status_code': response.status_code,
                            'response': response_text,
                            'parsed_response': response_json,
                            'phone_attempted': normalized_phone,
                        }
                        logger.warning('Intek SMS failed for %s: %s', normalized_phone, error_msg)
            elif response.status_code == 401:
                sms_log.status = 'failed'
                try:
                    body = json.loads(response_text)
                    err = body.get('error', response_text)
                except (json.JSONDecodeError, ValueError):
                    err = response_text
                sms_log.error_message = f'Invalid API key: {err}. Update SMS_API_KEY in settings or environment.'
                sms_log.provider_response = {
                    'status': 'failed',
                    'status_code': response.status_code,
                    'response': response_text,
                    'phone_attempted': normalized_phone,
                }
            else:
                sms_log.status = 'failed'
                sms_log.error_message = f'HTTP {response.status_code}: {response_text[:300]}'
                sms_log.provider_response = {
                    'status': 'failed',
                    'status_code': response.status_code,
                    'response': response_text,
                    'phone_attempted': normalized_phone,
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

    @staticmethod
    def pending_labs_followup_wording(pending_qs, now=None):
        """
        One or two sentences for outstanding labs (partial-encounter SMS).
        Uses 'tomorrow' only when pending work clearly spills past today (TAT or expected date).
        """
        now = now or timezone.now()
        local_now = timezone.localtime(now)
        today = local_now.date()
        suggests_next_calendar_day = False
        for lr in pending_qs:
            exp = getattr(lr, 'expected_completion_datetime', None)
            if exp:
                if timezone.localtime(exp).date() > today:
                    suggests_next_calendar_day = True
                    break
                continue
            test = getattr(lr, 'test', None)
            tat = int(getattr(test, 'tat_minutes', 0) or 0)
            if tat >= 1440:
                suggests_next_calendar_day = True
                break
        if suggests_next_calendar_day:
            return (
                "Other tests are still running and may be ready tomorrow; "
                "we will send another message when all are ready."
            )
        return (
            "Other tests are still being processed; "
            "we will notify you when all are ready."
        )

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
            message += f"{LAB_SMS_NURSE_DOCTOR_LINE}\n\n"
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

    def send_encounter_lab_results_partial_ready(self, encounter):
        """Send once per encounter when some (not all) non-cancelled lab results are completed."""
        try:
            from ..models import LabResult

            patient = getattr(encounter, 'patient', None)
            if not patient:
                raise AttributeError("Encounter.patient missing")

            if not getattr(patient, 'phone_number', None) or not patient.phone_number.strip():
                sms_log = SMSLog.objects.create(
                    recipient_phone='',
                    recipient_name=getattr(patient, 'full_name', '') or '',
                    message='',
                    message_type='encounter_lab_results_partial',
                    status='failed',
                    error_message=f"Patient {getattr(patient, 'full_name', 'Unknown')} does not have a phone number",
                    related_object_id=getattr(encounter, 'id', None),
                    related_object_type='Encounter',
                )
                return sms_log

            pending = (
                LabResult.objects.filter(order__encounter=encounter, is_deleted=False)
                .exclude(status__in=('completed', 'cancelled'))
                .select_related('test')
            )
            if not pending.exists():
                sms_log = SMSLog.objects.create(
                    recipient_phone='',
                    recipient_name=getattr(patient, 'full_name', '') or '',
                    message='',
                    message_type='encounter_lab_results_partial',
                    status='failed',
                    error_message='No pending lab results for partial encounter SMS',
                    related_object_id=getattr(encounter, 'id', None),
                    related_object_type='Encounter',
                )
                return sms_log

            first_name = getattr(patient, 'first_name', None) or (
                getattr(patient, 'full_name', '').split(' ')[0] if getattr(patient, 'full_name', None) else 'Patient'
            )
            follow = self.pending_labs_followup_wording(pending, now=timezone.now())
            message = (
                f"Dear {first_name},\n\n"
                f"Some of your lab results for this visit are now ready.\n"
                f"{follow}\n"
                f"Reference: {getattr(patient, 'mrn', '') or ''}\n\n"
                f"Please visit the hospital or check your patient portal for details.\n\n"
                f"{LAB_SMS_NURSE_DOCTOR_LINE}\n\n"
                f"Thank you,\nPrimeCare Hospital"
            )

            return self.send_sms(
                phone_number=patient.phone_number,
                message=message,
                message_type='encounter_lab_results_partial',
                recipient_name=getattr(patient, 'full_name', '') or '',
                related_object_id=getattr(encounter, 'id', None),
                related_object_type='Encounter',
            )
        except Exception as e:
            sms_log = SMSLog.objects.create(
                recipient_phone='',
                recipient_name='',
                message='',
                message_type='encounter_lab_results_partial',
                status='failed',
                error_message=f"Failed to send partial encounter lab SMS: {str(e)}",
                related_object_id=getattr(encounter, 'id', None) if encounter else None,
                related_object_type='Encounter',
            )
            return sms_log

    def send_encounter_lab_results_ready(self, encounter):
        """Send one SMS when all labs for an encounter are completed/cancelled."""
        try:
            patient = getattr(encounter, 'patient', None)
            if not patient:
                raise AttributeError("Encounter.patient missing")

            if not getattr(patient, 'phone_number', None) or not patient.phone_number.strip():
                sms_log = SMSLog.objects.create(
                    recipient_phone='',
                    recipient_name=getattr(patient, 'full_name', '') or '',
                    message='',
                    message_type='encounter_lab_results_ready',
                    status='failed',
                    error_message=f"Patient {getattr(patient, 'full_name', 'Unknown')} does not have a phone number",
                    related_object_id=getattr(encounter, 'id', None),
                    related_object_type='Encounter',
                )
                return sms_log

            first_name = getattr(patient, 'first_name', None) or (getattr(patient, 'full_name', '').split(' ')[0] if getattr(patient, 'full_name', None) else 'Patient')
            message = (
                f"Dear {first_name},\n\n"
                f"All your lab results for this visit are now ready.\n"
                f"Reference: {getattr(patient, 'mrn', '') or ''}\n\n"
                f"Please visit the hospital or check your patient portal for full details.\n\n"
                f"{LAB_SMS_NURSE_DOCTOR_LINE}\n\n"
                f"Thank you,\nPrimeCare Hospital"
            )

            return self.send_sms(
                phone_number=patient.phone_number,
                message=message,
                message_type='encounter_lab_results_ready',
                recipient_name=getattr(patient, 'full_name', '') or '',
                related_object_id=getattr(encounter, 'id', None),
                related_object_type='Encounter',
            )
        except Exception as e:
            sms_log = SMSLog.objects.create(
                recipient_phone='',
                recipient_name='',
                message='',
                message_type='encounter_lab_results_ready',
                status='failed',
                error_message=f"Failed to send encounter lab SMS: {str(e)}",
                related_object_id=getattr(encounter, 'id', None) if encounter else None,
                related_object_type='Encounter',
            )
            return sms_log

    def send_payment_reminder(self, invoice):
        """Send payment reminder SMS (no amounts — patient confirms total at Cashier)."""
        from hospital.services.pending_payment_notification_service import (
            should_send_payment_notification_sms,
        )

        patient = invoice.patient
        if not should_send_payment_notification_sms(patient=patient, invoice=invoice):
            return None

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

