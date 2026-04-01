"""
SMS Sending Views
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from .models import Patient, LabResult, Invoice, Appointment
from .models_reminders import SMSNotification
from .models_advanced import SMSLog
from .services.sms_service import sms_service

# Users allowed to access bulk SMS (in addition to staff with is_staff=True)
BULK_SMS_ALLOWED_USERS = [
    'min',  # Front desk user
    # Add more usernames here as needed
]

def can_access_bulk_sms(user):
    """Check if user can access bulk SMS features"""
    if not user or not user.is_authenticated:
        return False
    # Allow staff users
    if user.is_staff:
        return True
    # Allow specific usernames
    if user.username.lower() in [u.lower() for u in BULK_SMS_ALLOWED_USERS]:
        return True
    # Allow superusers
    if user.is_superuser:
        return True
    return False


@login_required
def send_sms(request):
    """SMS sending interface"""
    # CRITICAL: Reject auto-save requests to prevent duplicate SMS
    if request.method == 'POST':
        is_auto_save = request.POST.get('auto_save') == 'true' or \
                      request.META.get('HTTP_X_AUTO_SAVE') == 'true'
        if is_auto_save:
            return JsonResponse({'status': 'ignored', 'message': 'SMS sending cannot be auto-saved'})
    
    recipient_type = request.GET.get('type', 'patient')  # patient, staff, custom
    recipient_id = request.GET.get('id')
    message_type = request.GET.get('message_type', 'custom')
    
    recipient = None
    phone_number = ''
    recipient_name = ''
    
    if recipient_type == 'patient' and recipient_id:
        recipient = get_object_or_404(Patient, pk=recipient_id, is_deleted=False)
        phone_number = recipient.phone_number
        recipient_name = recipient.full_name
    elif recipient_type == 'lab_result' and recipient_id:
        lab_result = get_object_or_404(LabResult, pk=recipient_id, is_deleted=False)
        recipient = lab_result.order.encounter.patient
        phone_number = recipient.phone_number
        recipient_name = recipient.full_name
        message_type = 'lab_result'
    elif recipient_type == 'invoice' and recipient_id:
        invoice = get_object_or_404(Invoice, pk=recipient_id, is_deleted=False)
        recipient = invoice.patient
        phone_number = recipient.phone_number
        recipient_name = recipient.full_name
        message_type = 'payment_reminder'
    elif recipient_type == 'appointment' and recipient_id:
        appointment = get_object_or_404(Appointment, pk=recipient_id, is_deleted=False)
        recipient = appointment.patient
        phone_number = recipient.phone_number
        recipient_name = recipient.full_name
        message_type = 'appointment_reminder'
    
    if request.method == 'POST':
        # Log SMS creation attempt
        is_auto_save = request.POST.get('auto_save') == 'true' or \
                      request.META.get('HTTP_X_AUTO_SAVE') == 'true'
        import logging
        logger = logging.getLogger('hospital.bulk_creation_monitor')
        logger.info(
            f"SMS creation attempt - "
            f"User: {request.user.username}, "
            f"Recipient: {recipient_name or 'Custom'}, "
            f"Auto-save: {is_auto_save}, "
            f"IP: {request.META.get('REMOTE_ADDR', 'Unknown')}, "
            f"Timestamp: {timezone.now()}"
        )
        
        phone = request.POST.get('phone_number', '').strip()
        message_text = request.POST.get('message', '').strip()
        msg_type = request.POST.get('message_type', 'custom')
        
        if not phone or not message_text:
            messages.error(request, 'Phone number and message are required.')
            return redirect('hospital:send_sms')
        
        # Send SMS
        try:
            # Determine related object ID and type
            related_object_id = None
            related_object_type = ''
            if recipient_type == 'patient' and recipient:
                related_object_id = recipient.id
                related_object_type = 'Patient'
            elif recipient_type == 'lab_result' and recipient_id:
                related_object_id = recipient_id
                related_object_type = 'LabResult'
            elif recipient_type == 'invoice' and recipient_id:
                related_object_id = recipient_id
                related_object_type = 'Invoice'
            elif recipient_type == 'appointment' and recipient_id:
                related_object_id = recipient_id
                related_object_type = 'Appointment'
            
            sms_log = sms_service.send_sms(
                phone_number=phone,
                message=message_text,
                message_type=msg_type,
                recipient_name=recipient_name or request.POST.get('recipient_name', ''),
                related_object_id=related_object_id,
                related_object_type=related_object_type,
            )
            
            if sms_log.status == 'sent':
                messages.success(request, f'SMS sent successfully to {phone}')
                # Create SMS notification record
                try:
                    SMSNotification.objects.create(
                        notification_type=msg_type,
                        recipient_number=phone,
                        recipient_name=recipient_name or request.POST.get('recipient_name', ''),
                        message=message_text,
                        status='sent',
                        sent_at=sms_log.sent_at,
                        patient=recipient if recipient_type == 'patient' else None,
                    )
                except Exception as notify_error:
                    # Log but don't fail if notification record creation fails
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to create SMSNotification record: {notify_error}")
            else:
                error_msg = sms_log.error_message or 'Unknown error'
                messages.error(request, f'Failed to send SMS: {error_msg}')
                # Log the error for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"SMS send failed to {phone}: {error_msg}")
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Exception sending SMS to {phone}: {str(e)}", exc_info=True)
            messages.error(request, f'Error sending SMS: {str(e)}')
        
        return redirect('hospital:sms_notifications')
    
    # Pre-fill message based on type
    default_message = ''
    if message_type == 'lab_result' and recipient:
        default_message = (
            f"Dear {recipient.first_name},\n\n"
            f"Your lab test results are ready.\n"
            f"Please visit the hospital or check your patient portal.\n\n"
            f"Thank you.\n"
            f"PrimeCare Hospital"
        )
    elif message_type == 'payment_reminder' and recipient:
        invoice = Invoice.objects.filter(patient=recipient, is_deleted=False).order_by('-issued_at').first()
        if invoice:
            default_message = (
                f"Dear {recipient.first_name},\n\n"
                f"You have an outstanding balance on invoice {invoice.invoice_number}.\n"
                f"Please go to the Cashier to settle your bill — the correct amount is available there.\n\n"
                f"Thank you.\n"
                f"PrimeCare Hospital"
            )
    elif message_type == 'appointment_reminder' and recipient:
        appointment = Appointment.objects.filter(patient=recipient, is_deleted=False).order_by('-appointment_date').first()
        if appointment:
            date_str = appointment.appointment_date.strftime('%d/%m/%Y at %I:%M %p')
            default_message = (
                f"Dear {recipient.first_name},\n\n"
                f"Your appointment with Dr. {appointment.provider.user.get_full_name()}\n"
                f"is scheduled for {date_str}.\n\n"
                f"Please arrive 15 minutes early.\n\n"
                f"Reply STOP to opt out.\n"
                f"PrimeCare Hospital"
            )
    
    context = {
        'recipient_type': recipient_type,
        'recipient': recipient,
        'phone_number': phone_number,
        'recipient_name': recipient_name,
        'message_type': message_type,
        'default_message': default_message,
    }
    return render(request, 'hospital/send_sms.html', context)


@login_required
@login_required
def send_lab_result_sms(request, lab_result_id):
    """Send lab result via SMS"""
    # CRITICAL: Reject auto-save requests to prevent duplicate SMS
    if request.method == 'POST':
        is_auto_save = request.POST.get('auto_save') == 'true' or \
                      request.META.get('HTTP_X_AUTO_SAVE') == 'true'
        if is_auto_save:
            return JsonResponse({'status': 'ignored', 'message': 'Lab result SMS cannot be auto-saved'})
    """Send lab result notification via SMS"""
    from django.http import JsonResponse
    
    lab_result = get_object_or_404(LabResult, pk=lab_result_id, is_deleted=False)
    
    try:
        patient = lab_result.order.encounter.patient
    except AttributeError:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.method == 'GET':
            return JsonResponse({'success': False, 'error': 'Lab result does not have associated patient information'})
        messages.error(request, 'Lab result does not have associated patient information')
        return redirect('admin:hospital_labresult_changelist')
    
    # Check if patient has phone number
    if not patient.phone_number or not patient.phone_number.strip():
        error_msg = f'Patient {patient.full_name} does not have a phone number'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_msg})
        messages.error(request, error_msg)
        return redirect('admin:hospital_labresult_change', lab_result.pk)
    
    # Send SMS
    try:
        sms_log = sms_service.send_lab_result_ready(lab_result)
        
        if sms_log.status == 'sent':
            success_msg = f'Lab result SMS sent successfully to {patient.full_name} ({patient.phone_number})'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': success_msg,
                    'sms_log_id': str(sms_log.pk)
                })
            messages.success(request, success_msg)
        else:
            error_msg = f'Failed to send SMS: {sms_log.error_message or "Unknown error"}'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg})
            messages.error(request, error_msg)
    except Exception as e:
        error_msg = f'Error sending SMS: {str(e)}'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_msg})
        messages.error(request, error_msg)
    
    # Redirect based on where request came from
    referer = request.META.get('HTTP_REFERER', '')
    if 'admin' in referer:
        return redirect('admin:hospital_labresult_change', lab_result.pk)
    return redirect('hospital:sms_notifications')


@login_required
def bulk_sms_dashboard(request):
    """Bulk SMS dashboard - select recipients from database"""
    # Check if user has access to bulk SMS
    if not can_access_bulk_sms(request.user):
        messages.error(request, 'You do not have permission to access bulk SMS. Please contact an administrator.')
        return redirect('hospital:index')
    
    from .models import Staff
    
    # Filters
    search = request.GET.get('search', '').strip()
    recipient_type = request.GET.get('type', 'all')  # 'all', 'staff', 'patient'
    has_phone = request.GET.get('has_phone', '0')  # '1' = only with phone, '0' = all (default to show all)
    
    # Initialize default values
    staff_page_obj = None
    patient_page_obj = None
    total_staff = 0
    total_patients = 0
    
    # Get staff
    from django.db.models import OuterRef, Subquery
    
    staff_query = Staff.objects.none()
    if recipient_type in ['all', 'staff']:
        # Get the most recent staff record ID for each user to avoid duplicates
        from django.db.models import OuterRef, Subquery
        latest_staff = Staff.objects.filter(
            is_deleted=False,
            is_active=True,
            user=OuterRef('user')
        ).order_by('-created')[:1]
        latest_staff_ids = Staff.objects.filter(
            is_deleted=False,
            is_active=True
        ).annotate(
            latest_id=Subquery(latest_staff.values('id'))
        ).values_list('latest_id', flat=True).distinct()
        
        staff_query = Staff.objects.filter(
            id__in=latest_staff_ids,
            is_deleted=False,
            is_active=True
        ).select_related('user', 'department')
        
        if has_phone == '1':
            staff_query = staff_query.exclude(
                Q(phone_number__isnull=True) | Q(phone_number='')
            )
        
        if search:
            staff_query = staff_query.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__username__icontains=search) |
                Q(employee_id__icontains=search) |
                Q(phone_number__icontains=search) |
                Q(department__name__icontains=search)
            )
        
        staff_query = staff_query.order_by('user__first_name', 'user__last_name', 'user__username')
        total_staff = staff_query.count()
        
        # Always create paginator even if empty
        staff_paginator = Paginator(staff_query, 50)
        staff_page = request.GET.get('staff_page', 1)
        try:
            staff_page = int(staff_page)
        except:
            staff_page = 1
        staff_page_obj = staff_paginator.get_page(staff_page)
    
    # Get patients
    patient_query = Patient.objects.none()
    if recipient_type in ['all', 'patient']:
        patient_query = Patient.objects.filter(is_deleted=False)
        
        if has_phone == '1':
            patient_query = patient_query.exclude(
                Q(phone_number__isnull=True) | Q(phone_number='')
            )
        
        if search:
            patient_query = patient_query.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(mrn__icontains=search) |
                Q(phone_number__icontains=search)
            )
        
        patient_query = patient_query.order_by('first_name', 'last_name')
        total_patients = patient_query.count()
        
        # Always create paginator even if empty
        patient_paginator = Paginator(patient_query, 50)
        patient_page = request.GET.get('patient_page', 1)
        try:
            patient_page = int(patient_page)
        except:
            patient_page = 1
        patient_page_obj = patient_paginator.get_page(patient_page)
    
    context = {
        'staff_page_obj': staff_page_obj,
        'patient_page_obj': patient_page_obj,
        'search': search,
        'recipient_type': recipient_type,
        'has_phone': has_phone,
        'total_staff': total_staff,
        'total_patients': total_patients,
    }
    return render(request, 'hospital/bulk_sms_dashboard.html', context)


@login_required
@login_required
def send_bulk_sms(request):
    """Send bulk SMS to multiple recipients"""
    # CRITICAL: Reject auto-save requests to prevent duplicate bulk SMS
    if request.method == 'POST':
        is_auto_save = request.POST.get('auto_save') == 'true' or \
                      request.META.get('HTTP_X_AUTO_SAVE') == 'true'
        if is_auto_save:
            return JsonResponse({'status': 'ignored', 'message': 'Bulk SMS sending cannot be auto-saved'})
    """Send SMS to multiple recipients including custom phone numbers"""
    # Check if user has access to bulk SMS
    if not can_access_bulk_sms(request.user):
        messages.error(request, 'You do not have permission to send bulk SMS. Please contact an administrator.')
        return redirect('hospital:index')
    
    if request.method == 'POST':
        recipient_ids = request.POST.getlist('recipients')
        recipient_types = request.POST.getlist('recipient_types')  # 'staff' or 'patient'
        custom_phones = request.POST.getlist('custom_phones')  # Custom phone numbers
        custom_names = request.POST.getlist('custom_names')  # Custom names
        message_text = request.POST.get('message', '').strip()
        msg_type = request.POST.get('message_type', 'custom')
        
        # Check if we have any recipients (database or custom)
        if not recipient_ids and not custom_phones:
            messages.error(request, 'Please select recipients or add custom phone numbers and enter a message.')
            return redirect('hospital:bulk_sms_dashboard')
        
        if not message_text:
            messages.error(request, 'Please enter a message.')
            return redirect('hospital:bulk_sms_dashboard')
        
        from .models import Staff
        
        success_count = 0
        fail_count = 0
        failed_recipients = []
        
        # Process database recipients
        for idx, recipient_id in enumerate(recipient_ids):
            recipient_type = recipient_types[idx] if idx < len(recipient_types) else 'patient'
            
            try:
                if recipient_type == 'staff':
                    recipient = Staff.objects.get(pk=recipient_id, is_deleted=False)
                    phone = recipient.phone_number
                    name = recipient.user.get_full_name() or recipient.user.username
                else:
                    recipient = Patient.objects.get(pk=recipient_id, is_deleted=False)
                    phone = recipient.phone_number
                    name = recipient.full_name
                
                if not phone:
                    fail_count += 1
                    failed_recipients.append(name)
                    continue
                
                # Personalize message
                personalized_msg = message_text.replace('{name}', name)
                if '{first_name}' in personalized_msg:
                    first_name = name.split()[0] if name else 'Valued'
                    personalized_msg = personalized_msg.replace('{first_name}', first_name)
                
                # Determine related object ID and type
                related_object_id = recipient.id if recipient else None
                related_object_type = recipient_type.title()  # 'staff' -> 'Staff', 'patient' -> 'Patient'
                
                sms_log = sms_service.send_sms(
                    phone_number=phone,
                    message=personalized_msg,
                    message_type=msg_type,
                    recipient_name=name,
                    related_object_id=related_object_id,
                    related_object_type=related_object_type,
                )
                
                if sms_log.status == 'sent':
                    # Create notification record
                    SMSNotification.objects.create(
                        notification_type=msg_type,
                        recipient_number=phone,
                        recipient_name=name,
                        message=personalized_msg,
                        status='sent',
                        sent_at=sms_log.sent_at,
                        staff=recipient if recipient_type == 'staff' else None,
                        patient=recipient if recipient_type == 'patient' else None,
                    )
                    success_count += 1
                else:
                    fail_count += 1
                    error_reason = sms_log.error_message or 'Unknown error'
                    failed_recipients.append(f"{name} ({error_reason[:30]})")
            except Exception as e:
                fail_count += 1
                error_msg = str(e)[:50] if str(e) else 'Unknown error'
                failed_recipients.append(f"{name if 'name' in locals() else 'ID: ' + str(recipient_id)} ({error_msg})")
        
        # Process custom phone numbers
        for idx, phone in enumerate(custom_phones):
            name = custom_names[idx] if idx < len(custom_names) else 'Custom Contact'
            
            try:
                # Personalize message for custom contacts
                personalized_msg = message_text.replace('{name}', name)
                if '{first_name}' in personalized_msg:
                    first_name = name.split()[0] if name else 'Valued'
                    personalized_msg = personalized_msg.replace('{first_name}', first_name)
                
                # Send SMS to custom number
                sms_log = sms_service.send_sms(
                    phone_number=phone,
                    message=personalized_msg,
                    message_type=msg_type,
                    recipient_name=name,
                    related_object_id=None,
                    related_object_type='Custom',
                )
                
                if sms_log.status == 'sent':
                    # Create notification record for custom contact
                    SMSNotification.objects.create(
                        notification_type=msg_type,
                        recipient_number=phone,
                        recipient_name=name,
                        message=personalized_msg,
                        status='sent',
                        sent_at=sms_log.sent_at,
                        staff=None,
                        patient=None,
                    )
                    success_count += 1
                else:
                    fail_count += 1
                    error_reason = sms_log.error_message or 'Unknown error'
                    failed_recipients.append(f"{name} ({error_reason[:30]})")
            except Exception as e:
                fail_count += 1
                error_msg = str(e)[:50] if str(e) else 'Unknown error'
                failed_recipients.append(f"{name} ({error_msg})")
        
        if success_count > 0:
            messages.success(request, f'Bulk SMS completed: {success_count} sent successfully{fail_count > 0 and f", {fail_count} failed" or ""}')
        else:
            messages.error(request, f'Bulk SMS failed: All {fail_count} messages failed to send.')
        
        if failed_recipients:
            # Get error details for better messaging
            error_details = []
            for name_with_error in failed_recipients[:5]:
                error_details.append(name_with_error)
            
            error_msg = f'Failed recipients: {", ".join(error_details)}{"..." if len(failed_recipients) > 5 else ""}'
            
            # Check for API key errors in recent failures
            try:
                # Extract names from error messages (format: "Name (error)")
                recipient_names = []
                for name_with_error in failed_recipients[:5]:
                    if ' (' in name_with_error:
                        recipient_names.append(name_with_error.split(' (')[0])
                    else:
                        recipient_names.append(name_with_error)
                
                if recipient_names:
                    recent_failures = SMSLog.objects.filter(
                        recipient_name__in=recipient_names,
                        status='failed',
                        created__gte=timezone.now() - timedelta(minutes=5)
                    )
                    api_key_errors = recent_failures.filter(
                        Q(error_message__icontains='API key') | 
                        Q(error_message__icontains='1004') |
                        Q(error_message__icontains='INVALID API KEY')
                    )
                    if api_key_errors.exists():
                        error_msg += ' ⚠ Invalid API key! Run: python manage.py update_sms_api_key YOUR_KEY'
                        messages.error(request, 'SMS API Key is invalid! Update SMS_API_KEY to send messages.')
                    else:
                        messages.warning(request, error_msg)
                else:
                    messages.warning(request, error_msg)
            except Exception as e:
                # Don't fail if error checking fails
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error checking API key status: {str(e)}")
                messages.warning(request, error_msg)
        
        return redirect('hospital:bulk_sms_dashboard')
    
    return redirect('hospital:bulk_sms_dashboard')

