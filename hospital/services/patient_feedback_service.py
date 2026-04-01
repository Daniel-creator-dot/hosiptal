"""
Send customer service review / feedback request via SMS to patients.
Used after appointments and after pharmacy dispensing.
"""
import logging
import uuid
from django.conf import settings

logger = logging.getLogger(__name__)


def _safe_related_object_id(value):
    """SMSLog.related_object_id is UUIDField – pass only UUID or None."""
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def send_customer_service_review_sms(patient, message_type='patient_feedback',
                                     related_object_id=None, related_object_type='PharmacyDispensing'):
    """
    Send SMS to patient with feedback form link (customer service review).
    Safe to call if patient has no phone; logs and returns False.

    Returns:
        bool: True if SMS was sent successfully, False otherwise.
    """
    if not patient:
        return False
    phone = getattr(patient, 'phone_number', None) or getattr(patient, 'phone', '')
    if not phone or not str(phone).strip():
        logger.debug("No phone for patient %s – skip feedback SMS", getattr(patient, 'id', ''))
        return False
    hospital_name = getattr(settings, 'HOSPITAL_NAME', 'PrimeCare')
    feedback_url = getattr(
        settings,
        'PATIENT_FEEDBACK_FORM_URL',
        'https://docs.google.com/forms/d/e/1FAIpQLSdtYFfaF1O3jnSzrRhbB0K3KB5MOxhaQZzQ2dDjXs9mR6jIvQ/viewform?usp=header',
    )
    friendly_name = getattr(patient, 'first_name', None) or getattr(patient, 'full_name', '') or ''
    message = (
        f"Hi {friendly_name or 'there'}, thanks for visiting {hospital_name}. "
        f"Please share quick feedback: {feedback_url}"
    )
    try:
        from hospital.services.sms_service import sms_service
        sms_log = sms_service.send_sms(
            phone_number=phone,
            message=message,
            message_type=message_type,
            recipient_name=getattr(patient, 'full_name', None) or '',
            related_object_id=_safe_related_object_id(related_object_id),
            related_object_type=related_object_type or '',
        )
        if getattr(sms_log, 'status', None) == 'sent':
            logger.info("Customer service review SMS sent to %s", phone)
            return True
        logger.warning("Feedback SMS not sent: %s", getattr(sms_log, 'error_message', 'Unknown'))
        return False
    except Exception as e:
        logger.warning("Failed to send customer service review SMS to patient %s: %s",
                       getattr(patient, 'id', ''), e)
        return False


def send_customer_service_review_sms_to_phone(phone, recipient_name='',
                                              message_type='patient_feedback',
                                              related_object_id=None, related_object_type='WalkInSale'):
    """
    Send customer service review SMS to a phone number (e.g. walk-in customer).
    Returns True if sent successfully, False otherwise.
    """
    if not phone or not str(phone).strip():
        return False
    hospital_name = getattr(settings, 'HOSPITAL_NAME', 'PrimeCare')
    feedback_url = getattr(
        settings,
        'PATIENT_FEEDBACK_FORM_URL',
        'https://docs.google.com/forms/d/e/1FAIpQLSdtYFfaF1O3jnSzrRhbB0K3KB5MOxhaQZzQ2dDjXs9mR6jIvQ/viewform?usp=header',
    )
    friendly = (recipient_name or '').strip() or 'there'
    message = (
        f"Hi {friendly}, thanks for visiting {hospital_name}. "
        f"Please share quick feedback: {feedback_url}"
    )
    try:
        from hospital.services.sms_service import sms_service
        sms_log = sms_service.send_sms(
            phone_number=phone,
            message=message,
            message_type=message_type,
            recipient_name=recipient_name or '',
            related_object_id=_safe_related_object_id(related_object_id),
            related_object_type=related_object_type or '',
        )
        return getattr(sms_log, 'status', None) == 'sent'
    except Exception as e:
        logger.warning("Failed to send customer service review SMS to %s: %s", phone, e)
        return False
