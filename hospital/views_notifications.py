"""
Notification System Views
Manage and display notifications
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.utils import timezone
from .models import Notification


@login_required
def notifications_list(request):
    """List all notifications for the current user"""
    # Notification model uses recipient field (ForeignKey to User)
    notifications = Notification.objects.filter(
        recipient=request.user,
        is_deleted=False
    ).order_by('-created')
    
    unread_count = notifications.filter(is_read=False).count()
    
    context = {
        'title': 'Notifications',
        'notifications': notifications,
        'unread_count': unread_count,
    }
    
    return render(request, 'hospital/notifications/list.html', context)


@login_required
@require_http_methods(["POST"])
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user,
            is_deleted=False
        )
        notification.mark_as_read()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notification not found'}, status=404)


@login_required
@require_http_methods(["POST"])
def mark_all_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(
        recipient=request.user,
        is_read=False,
        is_deleted=False
    ).update(is_read=True, read_at=timezone.now())
    
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def clear_all_notifications(request):
    """Clear (soft-delete) all notifications for the current user."""
    updated = Notification.objects.filter(
        recipient=request.user,
        is_deleted=False
    ).update(is_deleted=True)
    
    return JsonResponse({'success': True, 'cleared': updated})


def _notification_links(n):
    """Build link URLs for notification: result (lab/imaging), encounter, patient, chat message."""
    from django.urls import reverse
    links = {}
    if n.notification_type == 'lab_result_ready' and n.related_object_id and n.related_object_type == 'LabResult':
        try:
            from .models import LabResult
            lab = LabResult.objects.filter(pk=n.related_object_id, is_deleted=False).select_related('order', 'order__encounter', 'order__encounter__patient').first()
            if lab and lab.order and lab.order.encounter:
                links['link'] = reverse('hospital:edit_lab_result', kwargs={'result_id': n.related_object_id})
                links['link_encounter'] = reverse('hospital:encounter_detail', kwargs={'pk': lab.order.encounter_id})
                if lab.order.encounter.patient_id:
                    links['link_patient'] = reverse('hospital:patient_detail', kwargs={'pk': lab.order.encounter.patient_id})
        except Exception:
            pass
    if n.notification_type == 'imaging_result_ready' and n.related_object_id:
        try:
            from .models_advanced import ImagingStudy
            study = ImagingStudy.objects.filter(pk=n.related_object_id, is_deleted=False).select_related('encounter', 'patient').first()
            if study:
                links['link'] = reverse('hospital:encounter_detail', kwargs={'pk': study.encounter_id}) if study.encounter_id else None
                if study.encounter_id:
                    links['link_encounter'] = reverse('hospital:encounter_detail', kwargs={'pk': study.encounter_id})
                if study.patient_id:
                    links['link_patient'] = reverse('hospital:patient_detail', kwargs={'pk': study.patient_id})
        except Exception:
            pass
    if n.related_object_type == 'chat_message' and n.related_object_id:
        try:
            from .models_chat import ChatMessage
            msg = ChatMessage.objects.filter(pk=n.related_object_id).select_related('sender', 'channel').first()
            if msg and msg.sender_id:
                # Link to chat dashboard and open conversation with the sender
                base = reverse('hospital:user_chat_dashboard')
                links['link'] = base + '?with=' + str(msg.sender_id)
        except Exception:
            pass
    if n.notification_type == 'activity' and n.related_object_id and n.related_object_type == 'HospitalActivity':
        try:
            links['link'] = reverse('hospital:activity_detail', kwargs={'pk': n.related_object_id})
        except Exception:
            pass
    return links


@login_required
def notifications_api(request):
    """API endpoint for getting notifications (for bell badge and popup)."""
    recent_notifications = Notification.objects.filter(
        recipient=request.user,
        is_deleted=False
    ).order_by('-created')[:10]
    
    unread_count = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
        is_deleted=False
    ).count()
    
    notifications_payload = []
    for n in recent_notifications:
        item = {
            'id': str(n.id),
            'title': n.title,
            'message': n.message,
            'type': n.notification_type,
            'is_read': n.is_read,
            'created': n.created.isoformat(),
        }
        extra = _notification_links(n)
        item.update(extra)
        notifications_payload.append(item)
    
    return JsonResponse({
        'unread_count': unread_count,
        'notifications': notifications_payload,
    })


@login_required
def notification_preferences(request, patient_id):
    """Notification preferences view (placeholder)"""
    from django.shortcuts import get_object_or_404
    from .models import Patient
    patient = get_object_or_404(Patient, id=patient_id, is_deleted=False)
    return JsonResponse({'message': 'Notification preferences view not yet implemented'})


@login_required
def notification_history(request, patient_id):
    """Notification history view (placeholder)"""
    from django.shortcuts import get_object_or_404
    from .models import Patient
    patient = get_object_or_404(Patient, id=patient_id, is_deleted=False)
    return JsonResponse({'message': 'Notification history view not yet implemented'})


@login_required
def test_notification(request, patient_id):
    """Test notification view (placeholder)"""
    from django.shortcuts import get_object_or_404
    from .models import Patient
    patient = get_object_or_404(Patient, id=patient_id, is_deleted=False)
    return JsonResponse({'message': 'Test notification view not yet implemented'})


@login_required
def notification_settings_bulk(request):
    """Bulk notification settings view (placeholder)"""
    return JsonResponse({'message': 'Bulk notification settings view not yet implemented'})
