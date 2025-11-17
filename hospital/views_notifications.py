"""
Views for Multi-Channel Notification Management
Allows patients and staff to manage notification preferences
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import logging

from .models import Patient
from .models_notification import NotificationPreference, MultiChannelNotificationLog
from .services.multichannel_notification_service import multichannel_service

logger = logging.getLogger(__name__)


@login_required
def notification_preferences(request, patient_id):
    """
    View and update patient notification preferences
    """
    patient = get_object_or_404(Patient, id=patient_id, is_deleted=False)
    
    # Get or create notification preference
    preference, created = NotificationPreference.objects.get_or_create(
        patient=patient,
        defaults={
            'sms_enabled': True,
            'whatsapp_enabled': False,
            'email_enabled': False,
            'lab_results_notify': True,
            'appointment_notify': True,
            'payment_notify': True,
            'prescription_notify': True,
            'send_full_results': False
        }
    )
    
    if request.method == 'POST':
        # Update preferences from form
        try:
            # Channel preferences
            preference.sms_enabled = request.POST.get('sms_enabled') == 'on'
            preference.whatsapp_enabled = request.POST.get('whatsapp_enabled') == 'on'
            preference.email_enabled = request.POST.get('email_enabled') == 'on'
            
            # Contact overrides
            preference.sms_phone_number = request.POST.get('sms_phone_number', '').strip()
            preference.whatsapp_phone_number = request.POST.get('whatsapp_phone_number', '').strip()
            preference.email_address = request.POST.get('email_address', '').strip()
            
            # Notification types
            preference.lab_results_notify = request.POST.get('lab_results_notify') == 'on'
            preference.appointment_notify = request.POST.get('appointment_notify') == 'on'
            preference.payment_notify = request.POST.get('payment_notify') == 'on'
            preference.prescription_notify = request.POST.get('prescription_notify') == 'on'
            
            # Additional preferences
            preference.send_full_results = request.POST.get('send_full_results') == 'on'
            
            preference.save()
            
            messages.success(
                request,
                f'✅ Notification preferences updated successfully for {patient.full_name}'
            )
            
            return redirect('hospital:notification_preferences', patient_id=patient_id)
            
        except Exception as e:
            logger.error(f"Error updating notification preferences: {str(e)}", exc_info=True)
            messages.error(request, f'❌ Error updating preferences: {str(e)}')
    
    # Get notification history
    notification_logs = MultiChannelNotificationLog.objects.filter(
        patient=patient,
        is_deleted=False
    ).order_by('-created')[:20]
    
    context = {
        'title': f'Notification Preferences - {patient.full_name}',
        'patient': patient,
        'preference': preference,
        'notification_logs': notification_logs,
        'active_channels': preference.get_active_channels(),
    }
    
    return render(request, 'hospital/notification_preferences.html', context)


@login_required
def notification_history(request, patient_id):
    """
    View notification history for a patient
    """
    patient = get_object_or_404(Patient, id=patient_id, is_deleted=False)
    
    # Get all notification logs
    logs = MultiChannelNotificationLog.objects.filter(
        patient=patient,
        is_deleted=False
    ).order_by('-created')
    
    # Filter by notification type if specified
    notification_type = request.GET.get('type')
    if notification_type:
        logs = logs.filter(notification_type=notification_type)
    
    # Filter by status if specified
    status = request.GET.get('status')
    if status:
        logs = logs.filter(status=status)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(logs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': f'Notification History - {patient.full_name}',
        'patient': patient,
        'page_obj': page_obj,
        'notification_type': notification_type,
        'status': status,
    }
    
    return render(request, 'hospital/notification_history.html', context)


@login_required
@require_http_methods(["POST"])
def test_notification(request, patient_id):
    """
    Send a test notification to verify channels are working
    """
    patient = get_object_or_404(Patient, id=patient_id, is_deleted=False)
    
    try:
        # Get channels to test from request
        channels = request.POST.getlist('channels[]')
        if not channels:
            channels = None  # Will use patient preferences
        
        # Send test notification
        test_message = (
            f"Hello {patient.first_name}! This is a test notification from PrimeCare Hospital. "
            f"Your notification channels are working correctly. Thank you!"
        )
        
        notification_log = multichannel_service.send_notification(
            patient=patient,
            notification_type='general',
            subject='Test Notification',
            message=test_message,
            force_channels=channels
        )
        
        if notification_log:
            success_rate = notification_log.get_success_rate()
            
            if success_rate == 100:
                return JsonResponse({
                    'success': True,
                    'message': f'✅ Test notification sent successfully via all channels!',
                    'success_rate': success_rate,
                    'successful_channels': notification_log.channels_successful,
                    'failed_channels': notification_log.channels_failed
                })
            elif success_rate > 0:
                return JsonResponse({
                    'success': True,
                    'message': f'⚠️ Test notification partially sent. Success rate: {success_rate}%',
                    'success_rate': success_rate,
                    'successful_channels': notification_log.channels_successful,
                    'failed_channels': notification_log.channels_failed
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': f'❌ Test notification failed on all channels',
                    'success_rate': 0,
                    'successful_channels': [],
                    'failed_channels': notification_log.channels_failed
                })
        else:
            return JsonResponse({
                'success': False,
                'message': '❌ No notification channels enabled or available'
            })
    
    except Exception as e:
        logger.error(f"Error sending test notification: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'❌ Error: {str(e)}'
        })


@login_required
def notification_settings_bulk(request):
    """
    Bulk manage notification preferences for multiple patients
    """
    if request.method == 'POST':
        try:
            # Get patient IDs
            patient_ids = request.POST.getlist('patient_ids[]')
            
            # Get settings to apply
            settings = {
                'sms_enabled': request.POST.get('bulk_sms_enabled') == 'on',
                'whatsapp_enabled': request.POST.get('bulk_whatsapp_enabled') == 'on',
                'email_enabled': request.POST.get('bulk_email_enabled') == 'on',
                'lab_results_notify': request.POST.get('bulk_lab_results_notify') == 'on',
            }
            
            # Update all selected patients
            updated_count = 0
            for patient_id in patient_ids:
                try:
                    patient = Patient.objects.get(id=patient_id, is_deleted=False)
                    multichannel_service.update_patient_preferences(patient, **settings)
                    updated_count += 1
                except Patient.DoesNotExist:
                    continue
            
            messages.success(request, f'✅ Updated notification preferences for {updated_count} patients')
            return redirect('hospital:notification_settings_bulk')
        
        except Exception as e:
            logger.error(f"Error in bulk update: {str(e)}", exc_info=True)
            messages.error(request, f'❌ Error: {str(e)}')
    
    # Get all patients with their preferences
    patients = Patient.objects.filter(is_deleted=False).order_by('last_name', 'first_name')[:100]
    
    context = {
        'title': 'Bulk Notification Settings',
        'patients': patients,
    }
    
    return render(request, 'hospital/notification_settings_bulk.html', context)


















