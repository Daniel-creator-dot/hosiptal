"""
Patient Appointment Confirmation Views
Allow patients to confirm appointments via SMS link
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
import logging

from .models import Appointment
from .services.sms_service import sms_service

logger = logging.getLogger(__name__)


def appointment_confirmation_page(request, appointment_id, token):
    """
    Public page for patients to confirm their appointment
    No login required - accessed via SMS link
    """
    try:
        appointment = get_object_or_404(
            Appointment,
            pk=appointment_id,
            is_deleted=False,
            status__in=['scheduled', 'confirmed']
        )
        
        # Simple token validation (appointment ID + date hash)
        expected_token = generate_confirmation_token(appointment)
        
        if token != expected_token:
            return render(request, 'hospital/appointment_confirmation_error.html', {
                'error': 'Invalid confirmation link. Please contact the hospital.'
            })
        
        # Check if appointment is not in the past
        if appointment.appointment_date < timezone.now():
            return render(request, 'hospital/appointment_confirmation_error.html', {
                'error': 'This appointment has already passed.'
            })
        
        context = {
            'appointment': appointment,
            'token': token,
            'patient': appointment.patient,
            'provider': appointment.provider,
            'department': appointment.department,
        }
        
        return render(request, 'hospital/appointment_confirmation_public.html', context)
        
    except Exception as e:
        logger.error(f"Error loading confirmation page: {str(e)}")
        return render(request, 'hospital/appointment_confirmation_error.html', {
            'error': 'Unable to load appointment. Please contact the hospital.'
        })


@csrf_exempt
def confirm_appointment(request, appointment_id, token):
    """
    API endpoint to confirm appointment
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        appointment = get_object_or_404(
            Appointment,
            pk=appointment_id,
            is_deleted=False
        )
        
        # Validate token
        expected_token = generate_confirmation_token(appointment)
        if token != expected_token:
            return JsonResponse({'error': 'Invalid confirmation link'}, status=403)
        
        # Check if already confirmed
        if appointment.status == 'confirmed':
            return JsonResponse({
                'success': True,
                'message': 'Appointment already confirmed',
                'already_confirmed': True
            })
        
        # Confirm appointment
        appointment.status = 'confirmed'
        appointment.save()
        
        # Send detailed schedule SMS with preparation instructions
        try:
            send_appointment_schedule_sms(appointment)
        except Exception as e:
            logger.error(f"Error sending schedule SMS: {str(e)}")
        
        logger.info(f"Appointment {appointment.id} confirmed by patient via SMS link")
        
        return JsonResponse({
            'success': True,
            'message': 'Appointment confirmed successfully!'
        })
        
    except Exception as e:
        logger.error(f"Error confirming appointment: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def cancel_appointment_patient(request, appointment_id, token):
    """
    API endpoint for patient to cancel appointment
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        appointment = get_object_or_404(
            Appointment,
            pk=appointment_id,
            is_deleted=False
        )
        
        # Validate token
        expected_token = generate_confirmation_token(appointment)
        if token != expected_token:
            return JsonResponse({'error': 'Invalid link'}, status=403)
        
        # Check if already cancelled
        if appointment.status == 'cancelled':
            return JsonResponse({
                'success': True,
                'message': 'Appointment already cancelled',
                'already_cancelled': True
            })
        
        # Get cancellation reason
        reason = request.POST.get('reason', 'Cancelled by patient')
        
        # Cancel appointment
        appointment.status = 'cancelled'
        appointment.notes = f"{appointment.notes}\n\nCancelled by patient via SMS: {reason}".strip()
        appointment.save()
        
        # Send cancellation confirmation SMS
        try:
            patient = appointment.patient
            if patient.phone_number:
                message = (
                    f"Dear {patient.first_name}, "
                    f"Your appointment on {appointment.appointment_date.strftime('%d/%m/%Y at %I:%M %p')} "
                    f"has been cancelled. Please call us to reschedule. - PrimeCare Medical Center"
                )
                
                sms_service.send_sms(
                    phone_number=patient.phone_number,
                    message=message,
                    message_type='appointment_cancellation',
                    recipient_name=patient.full_name,
                    related_object_id=appointment.id,
                    related_object_type='Appointment'
                )
        except Exception as e:
            logger.error(f"Error sending cancellation SMS: {str(e)}")
        
        logger.info(f"Appointment {appointment.id} cancelled by patient via SMS link")
        
        return JsonResponse({
            'success': True,
            'message': 'Appointment cancelled successfully'
        })
        
    except Exception as e:
        logger.error(f"Error cancelling appointment: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


def generate_confirmation_token(appointment):
    """
    Generate a simple confirmation token for appointment
    Uses appointment ID + date + patient ID hash
    """
    import hashlib
    
    # Create a simple hash from appointment details
    data = f"{appointment.id}-{appointment.appointment_date.date()}-{appointment.patient.id}"
    token = hashlib.md5(data.encode()).hexdigest()[:16]
    
    return token


def get_confirmation_link(appointment, base_url=None):
    """
    Generate confirmation link for appointment
    """
    from django.conf import settings
    from django.contrib.sites.models import Site
    
    if base_url is None:
        # Try to get from settings first
        base_url = getattr(settings, 'SITE_URL', None)
        if base_url:
            # Remove trailing slash if present
            base_url = base_url.rstrip('/')
        
        # If not in settings, try to get from Site framework
        if not base_url:
            try:
                current_site = Site.objects.get_current()
                if current_site and current_site.domain and current_site.domain not in ['example.com', 'localhost', '127.0.0.1']:
                    protocol = 'https' if getattr(settings, 'USE_SSL', False) else 'http'
                    base_url = f"{protocol}://{current_site.domain}"
                    # Remove port if it's 8000 (default Django dev server)
                    if ':8000' in base_url and protocol == 'http':
                        base_url = base_url.replace(':8000', '')
            except Exception as e:
                logger.warning(f"Could not get site from Site framework: {e}")
                base_url = None
        
        # Fallback to ALLOWED_HOSTS
        if not base_url:
            allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])
            # Filter out localhost and 127.0.0.1 for production
            production_hosts = [h for h in allowed_hosts if h not in ['localhost', '127.0.0.1', '*']]
            if production_hosts:
                protocol = 'https' if getattr(settings, 'USE_SSL', False) else 'http'
                base_url = f"{protocol}://{production_hosts[0]}"
                # Remove port if it's 8000
                if ':8000' in base_url and protocol == 'http':
                    base_url = base_url.replace(':8000', '')
        
        # Last resort - use localhost (for development only)
        if not base_url:
            logger.warning("Using localhost for confirmation link - configure SITE_URL in settings for production")
            base_url = 'http://127.0.0.1:8000'
    
    token = generate_confirmation_token(appointment)
    return f"{base_url}/hms/appointments/confirm/{appointment.id}/{token}/"


def send_booking_confirmation_sms(appointment, request=None):
    """
    Send initial booking confirmation SMS (Step 1)
    Just confirms the booking was made, asks patient to confirm
    """
    try:
        logger.info(f"📱 Attempting to send booking confirmation SMS for appointment {appointment.id}")
        patient = appointment.patient
        
        if not patient:
            logger.error(f"❌ Cannot send SMS - appointment {appointment.id} has no patient assigned")
            return False
        
        if not patient.phone_number or not patient.phone_number.strip():
            logger.warning(
                f"⚠️ Cannot send SMS - Patient {patient.full_name} (MRN: {patient.mrn}) "
                f"has no valid phone number. Phone field value: '{getattr(patient, 'phone_number', 'None')}'"
            )
            return False
        
        phone = patient.phone_number.strip()
        logger.info(f"📱 Phone number found for {patient.full_name}: {phone}")
        
        # Get proper base URL for confirmation link
        base_url = None
        if request:
            base_url = request.build_absolute_uri('/')[:-1]  # Remove trailing slash
        
        # Generate confirmation link with proper URL
        confirmation_link = get_confirmation_link(appointment, base_url=base_url)
        
        # Shortened message for SMS (SMS has 160 char limit per segment)
        # Try to make it shorter and more actionable
        provider_name = appointment.provider.user.get_full_name() if appointment.provider and appointment.provider.user else "Doctor"
        dept_name = appointment.department.name if appointment.department else "General"
        
        # Format appointment date
        appointment_datetime = timezone.localtime(appointment.appointment_date)
        date_str = appointment_datetime.strftime('%d/%m/%Y')
        time_str = appointment_datetime.strftime('%I:%M %p')
        
        # Shorter message
        message = (
            f"Appointment Booking\n\n"
            f"Dear {patient.first_name},\n\n"
            f"Your appointment is scheduled:\n"
            f"Date: {date_str}\n"
            f"Time: {time_str}\n"
            f"Doctor: Dr. {provider_name}\n"
            f"Dept: {dept_name}\n\n"
            f"Confirm: {confirmation_link}\n\n"
            f"Please arrive 15 minutes early.\n"
            f"- PrimeCare Medical Center"
        )
        
        logger.info(f"📱 Sending booking confirmation SMS to {phone} for patient {patient.full_name} (Appointment: {appointment.id})")
        logger.debug(f"Message content (first 300 chars):\n{message[:300]}")
        logger.debug(f"Full message length: {len(message)} characters")
        
        # Send SMS
        related_id = str(appointment.id) if appointment.id else None
        logger.debug(f"SMS parameters: phone={phone}, recipient={patient.full_name}, type=appointment_booking_confirmation, related_id={related_id}")
        
        sms_log = sms_service.send_sms(
            phone_number=phone,
            message=message,
            message_type='appointment_booking_confirmation',
            recipient_name=patient.full_name,
            related_object_id=related_id,
            related_object_type='Appointment'
        )
        
        if not sms_log:
            logger.error(f"❌ SMS service returned None/empty result for {phone}")
            return False
        
        if sms_log.status == 'sent':
            logger.info(f"✅ Booking confirmation SMS sent successfully for appointment {appointment.id} to {patient.full_name} at {phone}")
            return True
        else:
            error_msg = sms_log.error_message or 'Unknown error'
            logger.error(
                f"❌ Failed to send booking SMS for appointment {appointment.id}. "
                f"Status: {sms_log.status}, Error: {error_msg}. "
                f"Phone: {phone}, Patient: {patient.full_name}"
            )
            if sms_log.provider_response:
                logger.debug(f"Provider response: {sms_log.provider_response}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Exception sending booking confirmation SMS: {str(e)}", exc_info=True)
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False


def send_appointment_notification_to_doctor(appointment):
    """
    Send SMS notification to doctor when appointment is created
    Includes date, time, and patient information
    """
    try:
        if not appointment.provider:
            logger.warning(f"Cannot send doctor SMS - no provider assigned for appointment {appointment.id}")
            return False
        
        doctor = appointment.provider
        doctor_user = doctor.user if doctor else None
        
        if not doctor_user:
            logger.warning(f"Cannot send doctor SMS - no user for provider {doctor.id}")
            return False
        
        # Get doctor's phone number from staff record
        doctor_phone = doctor.phone_number if hasattr(doctor, 'phone_number') and doctor.phone_number else None
        
        if not doctor_phone or not doctor_phone.strip():
            logger.warning(f"Cannot send doctor SMS - no phone number for doctor {doctor_user.get_full_name()}")
            return False
        
        # Get patient and appointment details
        patient = appointment.patient
        patient_name = patient.full_name if patient else "Patient"
        department_name = appointment.department.name if appointment.department else "General"
        
        # Format appointment date and time
        appointment_datetime = timezone.localtime(appointment.appointment_date)
        date_str = appointment_datetime.strftime('%A, %B %d, %Y')
        time_str = appointment_datetime.strftime('%I:%M %p')
        
        # Build SMS message for doctor
        message = (
            f"NEW APPOINTMENT\n\n"
            f"Dr. {doctor_user.get_full_name()},\n\n"
            f"You have a new appointment:\n\n"
            f"👤 PATIENT: {patient_name}\n"
            f"📅 DATE: {date_str}\n"
            f"🕐 TIME: {time_str}\n"
            f"🏥 DEPARTMENT: {department_name}\n"
        )
        
        # Add reason if available
        if appointment.reason:
            message += f"📝 REASON: {appointment.reason[:100]}\n"
        
        message += f"\n- PrimeCare Medical Center"
        
        # Send SMS to doctor
        sms_log = sms_service.send_sms(
            phone_number=doctor_phone,
            message=message,
            message_type='appointment_doctor_notification',
            recipient_name=doctor_user.get_full_name(),
            related_object_id=appointment.id,
            related_object_type='Appointment'
        )
        
        if sms_log.status == 'sent':
            logger.info(f"Doctor notification SMS sent for appointment {appointment.id} to {doctor_user.get_full_name()}")
            return True
        else:
            logger.error(f"Failed to send doctor SMS: {sms_log.error_message}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending doctor appointment notification: {str(e)}", exc_info=True)
        return False


def send_appointment_schedule_sms(appointment):
    """
    Send appointment schedule/reminder SMS (Step 2)
    Sent after patient confirms - includes date, time, and preparation
    """
    try:
        patient = appointment.patient
        
        if not patient.phone_number:
            logger.warning(f"Cannot send SMS - no phone number for patient {patient.id}")
            return False
        
        # Calculate days until appointment
        days_until = (appointment.appointment_date.date() - timezone.now().date()).days
        
        # Build preparation message
        preparation_msg = ""
        if days_until > 0:
            preparation_msg = f"\n\nPlease arrive 15 minutes early.\nBring your ID and insurance card if applicable."
        else:
            preparation_msg = f"\n\nYour appointment is TODAY! Please arrive 15 minutes early."
        
        # Detailed schedule message
        message = (
            f"APPOINTMENT CONFIRMED\n\n"
            f"Dear {patient.first_name},\n\n"
            f"Thank you for confirming!\n\n"
            f"📅 DATE: {appointment.appointment_date.strftime('%A, %B %d, %Y')}\n"
            f"🕐 TIME: {appointment.appointment_date.strftime('%I:%M %p')}\n"
            f"👨‍⚕️ DOCTOR: Dr. {appointment.provider.user.get_full_name()}\n"
            f"🏥 DEPARTMENT: {appointment.department.name}\n"
            f"📍 LOCATION: PrimeCare Medical Center"
            f"{preparation_msg}\n\n"
            f"Questions? Call us.\n"
            f"- PrimeCare"
        )
        
        # Send SMS
        sms_log = sms_service.send_sms(
            phone_number=patient.phone_number,
            message=message,
            message_type='appointment_schedule',
            recipient_name=patient.full_name,
            related_object_id=appointment.id,
            related_object_type='Appointment'
        )
        
        if sms_log.status == 'sent':
            logger.info(f"Schedule SMS sent for appointment {appointment.id}")
            # Mark reminder as sent
            appointment.reminder_sent = True
            appointment.save()
            return True
        else:
            logger.error(f"Failed to send schedule SMS: {sms_log.error_message}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending schedule SMS: {str(e)}")
        return False


# Alias for backwards compatibility
def send_appointment_notification_with_confirmation(appointment, request=None):
    """Alias for send_booking_confirmation_sms"""
    return send_booking_confirmation_sms(appointment, request=request)

