"""
Patient Pending Payment Notification Service
Notifies patients about pending payments for lab, imaging, and prescription.
All payments must be made at Cashier (cash) before service is delivered.
"""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

SERVICE_TYPE_LAB = 'lab'
SERVICE_TYPE_IMAGING = 'imaging'
SERVICE_TYPE_PRESCRIPTION = 'prescription'

SERVICE_LABELS = {
    SERVICE_TYPE_LAB: 'Lab',
    SERVICE_TYPE_IMAGING: 'Imaging',
    SERVICE_TYPE_PRESCRIPTION: 'Prescription',
}


def notify_patient_pending_payment(patient, service_type, service_name, amount,
                                   message_type='pending_payment', send_email=True):
    """
    Send SMS (and optionally email) to patient about pending payment.
    Instructs patient to pay at Cashier before receiving the service.

    Args:
        patient: Patient model instance (must have phone_number, full_name, email optional)
        service_type: 'lab', 'imaging', or 'prescription'
        service_name: Human-readable service name (e.g. "FBC", "X-Ray Chest", "Paracetamol x2")
        amount: Decimal or number - kept for logging/server use; not included in SMS/email body
        message_type: SMS log message_type (default 'pending_payment')
        send_email: If True and patient has email, send email too (default True)

    Returns:
        dict with 'sms_sent', 'email_sent', 'errors'
    """
    result = {'sms_sent': False, 'email_sent': False, 'errors': []}

    if not patient:
        result['errors'].append('Patient is required')
        return result

    try:
        amount_val = Decimal(str(amount))
    except (TypeError, ValueError):
        amount_val = Decimal('0.00')

    # Normalize so we never miss lab/imaging due to casing or aliases (keeps SMS off specific test names).
    st_raw = str(service_type or '').strip()
    st = st_raw.lower()
    if st in ('laboratory', 'lab_test', 'lab_tests'):
        st = SERVICE_TYPE_LAB
    elif st in ('radiology', 'radiology_study', 'scan', 'scans'):
        st = SERVICE_TYPE_IMAGING

    label = SERVICE_LABELS.get(st, st_raw.title() if st_raw else 'Service')
    try:
        from django.conf import settings
        hospital_name = getattr(settings, 'HOSPITAL_NAME', 'PrimeCare')
    except Exception:
        hospital_name = 'PrimeCare'

    # SMS: no amounts (cashier has the correct bill). Prescription: no drug names.
    if st == SERVICE_TYPE_PRESCRIPTION:
        sms_msg = (
            f"{hospital_name}: You have a pending payment. "
            f"Please go to the Cashier to pay before collecting medication."
        )
    elif st == SERVICE_TYPE_LAB:
        sms_msg = (
            f"{hospital_name}: You have a pending lab payment. "
            f"Please go to the Cashier to pay — amounts are confirmed at the desk."
        )
    elif st == SERVICE_TYPE_IMAGING:
        sms_msg = (
            f"{hospital_name}: You have a pending imaging payment. "
            f"Please go to the Cashier to pay — amounts are confirmed at the desk."
        )
    else:
        sms_msg = (
            f"{hospital_name}: You have a pending payment. "
            f"Please go to the Cashier to pay before receiving the service."
        )

    phone = getattr(patient, 'phone_number', None) or getattr(patient, 'phone', '')
    name = getattr(patient, 'full_name', None) or (f"{getattr(patient, 'first_name', '')} {getattr(patient, 'last_name', '')}".strip()) or 'Patient'

    if phone and str(phone).strip():
        try:
            from hospital.services.sms_service import sms_service
            sms_service.send_sms(
                phone_number=phone,
                message=sms_msg,
                message_type=message_type,
                recipient_name=name,
                related_object_type=f'pending_payment_{st}',
            )
            result['sms_sent'] = True
            logger.info("Pending payment SMS sent to %s for %s - GHS %s", name, service_name, amount_val)
        except Exception as e:
            logger.warning("Failed to send pending payment SMS to patient %s: %s", getattr(patient, 'id', ''), e)
            result['errors'].append(f"SMS: {str(e)}")
    else:
        result['errors'].append('Patient has no phone number')

    # Email: optional, same message in body (no drug names for pharmacy)
    if send_email:
        email_addr = getattr(patient, 'email', None) or ''
        if email_addr and str(email_addr).strip() and '@' in str(email_addr):
            try:
                from hospital.services.email_service import EmailService
                email_svc = EmailService()
                subject = f"Pending payment: {label} - visit Cashier before service"
                if st == SERVICE_TYPE_PRESCRIPTION:
                    detail_line = "Pharmacy."
                elif st == SERVICE_TYPE_LAB:
                    detail_line = "Lab services."
                elif st == SERVICE_TYPE_IMAGING:
                    detail_line = "Imaging/scan services."
                else:
                    detail_line = f"<strong>{label}</strong>: <strong>{service_name}</strong>."
                body_html = (
                    f"<p>Dear {name},</p>"
                    f"<p>You have a pending payment for <strong>{detail_line}</strong></p>"
                    f"<p>Please go to the <strong>Cashier</strong> to pay. Your correct balance is available at the desk.</p>"
                    f"<p>Thank you,<br>{hospital_name}</p>"
                )
                body_text = sms_msg
                email_svc.send_email(
                    recipient_email=email_addr,
                    subject=subject,
                    message_html=body_html,
                    message_text=body_text,
                    recipient_name=name,
                )
                result['email_sent'] = True
                logger.info("Pending payment email sent to %s for %s", email_addr, service_name)
            except Exception as e:
                logger.warning("Failed to send pending payment email to patient %s: %s", getattr(patient, 'id', ''), e)
                result['errors'].append(f"Email: {str(e)}")

    return result
