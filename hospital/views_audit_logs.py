"""
Audit Log Views
View and search audit logs
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .models_audit import AuditLog, ActivityLog


def is_admin(user):
    """Check if user is admin or superuser"""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


@login_required
@user_passes_test(is_admin)
def audit_logs_view(request):
    """
    View audit logs with filtering and search
    """
    # Get filter parameters
    action_type = request.GET.get('action_type', '')
    severity = request.GET.get('severity', '')
    model_name = request.GET.get('model_name', '')
    user_id = request.GET.get('user', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search = request.GET.get('q', '')
    page_number = request.GET.get('page', 1)
    
    # Build query
    logs = AuditLog.objects.all()
    
    if action_type:
        logs = logs.filter(action_type=action_type)
    if severity:
        logs = logs.filter(severity=severity)
    if model_name:
        logs = logs.filter(model_name=model_name)
    if user_id:
        logs = logs.filter(user_id=user_id)
    if date_from:
        try:
            date_from_obj = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
            logs = logs.filter(created__date__gte=date_from_obj)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_obj = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
            logs = logs.filter(created__date__lte=date_to_obj)
        except ValueError:
            pass
    if search:
        logs = logs.filter(
            Q(description__icontains=search) |
            Q(object_repr__icontains=search) |
            Q(user__username__icontains=search) |
            Q(ip_address__icontains=search)
        )
    
    # Paginate
    paginator = Paginator(logs.order_by('-created'), 50)
    page_obj = paginator.get_page(page_number)
    
    # Get unique values for filters
    try:
        action_types = AuditLog.objects.values_list('action_type', flat=True).distinct().order_by('action_type')
        severities = AuditLog.objects.values_list('severity', flat=True).distinct().order_by('severity')
        model_names = AuditLog.objects.exclude(model_name='').values_list('model_name', flat=True).distinct().order_by('model_name')
    except Exception as e:
        # If table doesn't exist yet, use empty lists
        action_types = []
        severities = []
        model_names = []
    
    context = {
        'title': 'Audit Logs',
        'page_obj': page_obj,
        'logs': page_obj.object_list,
        'action_types': action_types,
        'severities': severities,
        'model_names': model_names,
        'filters': {
            'action_type': action_type,
            'severity': severity,
            'model_name': model_name,
            'user_id': user_id,
            'date_from': date_from,
            'date_to': date_to,
            'search': search,
        },
    }
    
    return render(request, 'hospital/admin/audit_logs.html', context)


@login_required
@user_passes_test(is_admin)
def activity_logs_view(request):
    """
    View activity logs with filtering
    """
    activity_type = request.GET.get('activity_type', '')
    user_id = request.GET.get('user', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search = request.GET.get('q', '')
    page_number = request.GET.get('page', 1)
    
    logs = ActivityLog.objects.all()
    
    if activity_type:
        logs = logs.filter(activity_type=activity_type)
    if user_id:
        logs = logs.filter(user_id=user_id)
    if date_from:
        try:
            date_from_obj = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
            logs = logs.filter(created__date__gte=date_from_obj)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_obj = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
            logs = logs.filter(created__date__lte=date_to_obj)
        except ValueError:
            pass
    if search:
        logs = logs.filter(
            Q(description__icontains=search) |
            Q(user__username__icontains=search) |
            Q(ip_address__icontains=search)
        )
    
    paginator = Paginator(logs.order_by('-created'), 50)
    page_obj = paginator.get_page(page_number)
    
    try:
        activity_types = ActivityLog.objects.values_list('activity_type', flat=True).distinct().order_by('activity_type')
    except Exception as e:
        activity_types = []
    
    context = {
        'title': 'Activity Logs',
        'page_obj': page_obj,
        'logs': page_obj.object_list,
        'activity_types': activity_types,
        'filters': {
            'activity_type': activity_type,
            'user_id': user_id,
            'date_from': date_from,
            'date_to': date_to,
            'search': search,
        },
    }
    
    return render(request, 'hospital/admin/activity_logs.html', context)

