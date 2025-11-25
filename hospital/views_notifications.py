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
def notifications_api(request):
    """API endpoint for getting notifications"""
    recent_notifications = Notification.objects.filter(
        recipient=request.user,
        is_deleted=False
    ).order_by('-created')[:10]
    
    unread_count = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
        is_deleted=False
    ).count()
    
    return JsonResponse({
        'unread_count': unread_count,
        'notifications': [
            {
                'id': str(n.id),
                'title': n.title,
                'message': n.message,
                'type': n.notification_type,
                'is_read': n.is_read,
                'created': n.created.isoformat(),
            }
            for n in recent_notifications
        ]
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
