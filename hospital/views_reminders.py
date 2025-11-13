"""
Views for Birthday Reminders and SMS Notifications
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import date, timedelta
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Staff, Patient
from .models_reminders import BirthdayReminder, SMSNotification
from .services.sms_service import sms_service
from django.core.paginator import Paginator


@login_required
def birthday_reminders(request):
    """View upcoming birthday reminders"""
    days_ahead = int(request.GET.get('days', 30))
    reminder_type = request.GET.get('type', 'all')  # 'staff', 'patient', 'all'
    
    today = date.today()
    
    # Get today's birthdays
    today_staff_birthdays = Staff.objects.filter(
        date_of_birth__month=today.month,
        date_of_birth__day=today.day,
        is_active=True,
        is_deleted=False
    ).select_related('user', 'department') if reminder_type in ['all', 'staff'] else []
    
    today_patient_birthdays = Patient.objects.filter(
        date_of_birth__month=today.month,
        date_of_birth__day=today.day,
        is_deleted=False
    ) if reminder_type in ['all', 'patient'] else []
    
    # Get upcoming birthdays (excluding today)
    upcoming_staff_birthdays = []
    upcoming_patient_birthdays = []
    
    if reminder_type in ['all', 'staff']:
        for i in range(1, days_ahead + 1):
            check_date = today + timedelta(days=i)
            staff_birthdays = Staff.objects.filter(
                date_of_birth__month=check_date.month,
                date_of_birth__day=check_date.day,
                is_active=True,
                is_deleted=False
            ).select_related('user', 'department')
            for staff in staff_birthdays:
                # Calculate days until birthday
                this_year_bday = date(today.year, staff.date_of_birth.month, staff.date_of_birth.day)
                if this_year_bday < today:
                    this_year_bday = date(today.year + 1, staff.date_of_birth.month, staff.date_of_birth.day)
                days_until = (this_year_bday - today).days
                staff.days_until_birthday = days_until
                upcoming_staff_birthdays.append(staff)
    
    if reminder_type in ['all', 'patient']:
        for i in range(1, days_ahead + 1):
            check_date = today + timedelta(days=i)
            patient_birthdays = Patient.objects.filter(
                date_of_birth__month=check_date.month,
                date_of_birth__day=check_date.day,
                is_deleted=False
            )
            for patient in patient_birthdays:
                # Calculate days until birthday
                this_year_bday = date(today.year, patient.date_of_birth.month, patient.date_of_birth.day)
                if this_year_bday < today:
                    this_year_bday = date(today.year + 1, patient.date_of_birth.month, patient.date_of_birth.day)
                days_until = (this_year_bday - today).days
                patient.days_until_birthday = days_until
                upcoming_patient_birthdays.append(patient)
    
    # Get recent SMS notifications for birthdays
    recent_sms = SMSNotification.objects.filter(
        notification_type='birthday',
        is_deleted=False
    ).select_related('staff', 'patient').order_by('-created')[:10]
    
    # Sort by days until birthday
    upcoming_staff_birthdays.sort(key=lambda x: getattr(x, 'days_until_birthday', 999))
    upcoming_patient_birthdays.sort(key=lambda x: getattr(x, 'days_until_birthday', 999))
    
    context = {
        'today_staff_birthdays': today_staff_birthdays,
        'today_patient_birthdays': today_patient_birthdays,
        'upcoming_staff_birthdays': upcoming_staff_birthdays,
        'upcoming_patient_birthdays': upcoming_patient_birthdays,
        'recent_sms': recent_sms,
        'days_ahead': days_ahead,
        'reminder_type': reminder_type,
        'today': today,
    }
    return render(request, 'hospital/birthday_reminders.html', context)


@login_required
def sms_notifications(request):
    """View SMS notification history"""
    notification_type = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    notifications = SMSNotification.objects.filter(is_deleted=False)
    
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)
    if status_filter:
        notifications = notifications.filter(status=status_filter)
    if search:
        notifications = notifications.filter(
            Q(recipient_name__icontains=search) |
            Q(recipient_number__icontains=search) |
            Q(message__icontains=search)
        )
    
    paginator = Paginator(notifications.order_by('-created'), 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'notification_type': notification_type,
        'status_filter': status_filter,
        'search': search,
    }
    return render(request, 'hospital/sms_notifications.html', context)


@login_required
@require_http_methods(["POST"])
def send_birthday_sms_api(request):
    """API endpoint to send birthday SMS"""
    try:
        recipient_type = request.POST.get('recipient_type')
        recipient_id = request.POST.get('recipient_id')
        phone_number = request.POST.get('phone_number', '').strip()
        message_text = request.POST.get('message', '').strip()
        recipient_name = request.POST.get('recipient_name', '')
        
        if not phone_number or not message_text:
            return JsonResponse({
                'success': False,
                'message': 'Phone number and message are required'
            })
        
        # Send SMS
        sms_log = sms_service.send_sms(
            phone_number=phone_number,
            message=message_text,
            message_type='birthday',
            recipient_name=recipient_name,
        )
        
        if sms_log.status == 'sent':
            # Get recipient object for SMSNotification
            staff = None
            patient = None
            
            if recipient_type == 'staff' and recipient_id:
                try:
                    staff = Staff.objects.get(pk=recipient_id, is_deleted=False)
                except Staff.DoesNotExist:
                    pass
            elif recipient_type == 'patient' and recipient_id:
                try:
                    patient = Patient.objects.get(pk=recipient_id, is_deleted=False)
                except Patient.DoesNotExist:
                    pass
            
            # Create SMS notification record
            SMSNotification.objects.create(
                notification_type='birthday',
                recipient_number=phone_number,
                recipient_name=recipient_name,
                message=message_text,
                status='sent',
                sent_at=sms_log.sent_at,
                staff=staff,
                patient=patient,
            )
            
            return JsonResponse({
                'success': True,
                'message': 'SMS sent successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': f'Failed to send SMS: {sms_log.error_message or "Unknown error"}'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })

