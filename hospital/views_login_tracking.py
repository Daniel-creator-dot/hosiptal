"""
Login Location Tracking Views
View login history, security alerts, and trusted locations
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta
import logging

from .models_login_tracking import LoginHistory, SecurityAlert, TrustedLocation, TrustedDevice

logger = logging.getLogger(__name__)


@login_required
def my_login_history(request):
    """
    Show current user's login history
    """
    # Get user's login history
    login_history = LoginHistory.objects.filter(
        user=request.user,
        is_deleted=False
    ).order_by('-login_time')[:50]
    
    # Statistics
    total_logins = LoginHistory.objects.filter(
        user=request.user,
        status='success',
        is_deleted=False
    ).count()
    
    failed_attempts = LoginHistory.objects.filter(
        user=request.user,
        status='failed',
        is_deleted=False
    ).count()
    
    unique_locations = LoginHistory.objects.filter(
        user=request.user,
        is_deleted=False
    ).values('city', 'country').distinct().count()
    
    # Recent security alerts
    security_alerts = SecurityAlert.objects.filter(
        user=request.user,
        is_resolved=False,
        is_deleted=False
    ).order_by('-alert_time')[:10]
    
    # Current session
    current_session = LoginHistory.objects.filter(
        user=request.user,
        session_key=request.session.session_key,
        is_deleted=False
    ).first()
    
    context = {
        'title': 'My Login History',
        'login_history': login_history,
        'total_logins': total_logins,
        'failed_attempts': failed_attempts,
        'unique_locations': unique_locations,
        'security_alerts': security_alerts,
        'current_session': current_session,
    }
    return render(request, 'hospital/my_login_history.html', context)


@login_required
def all_login_activity(request):
    """
    Admin view: All users' login activity
    Requires admin/superuser permissions
    """
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to view this page.')
        return redirect('hospital:dashboard')
    
    # Filters
    user_filter = request.GET.get('user', '')
    status_filter = request.GET.get('status', '')
    date_filter = request.GET.get('date', 'today')
    suspicious_only = request.GET.get('suspicious', '') == 'yes'
    
    # Base queryset
    login_history = LoginHistory.objects.filter(is_deleted=False).select_related('user', 'staff')
    
    # Apply filters
    if user_filter:
        login_history = login_history.filter(
            Q(user__username__icontains=user_filter) |
            Q(user__first_name__icontains=user_filter) |
            Q(user__last_name__icontains=user_filter)
        )
    
    if status_filter:
        login_history = login_history.filter(status=status_filter)
    
    if date_filter == 'today':
        today = timezone.now().date()
        login_history = login_history.filter(login_time__date=today)
    elif date_filter == 'week':
        week_ago = timezone.now() - timedelta(days=7)
        login_history = login_history.filter(login_time__gte=week_ago)
    elif date_filter == 'month':
        month_ago = timezone.now() - timedelta(days=30)
        login_history = login_history.filter(login_time__gte=month_ago)
    
    if suspicious_only:
        login_history = login_history.filter(is_suspicious=True)
    
    login_history = login_history.order_by('-login_time')[:100]
    
    # Statistics
    today = timezone.now().date()
    stats = {
        'total_today': LoginHistory.objects.filter(login_time__date=today, status='success', is_deleted=False).count(),
        'failed_today': LoginHistory.objects.filter(login_time__date=today, status='failed', is_deleted=False).count(),
        'suspicious_today': LoginHistory.objects.filter(login_time__date=today, is_suspicious=True, is_deleted=False).count(),
        'unique_users_today': LoginHistory.objects.filter(login_time__date=today, is_deleted=False).values('user').distinct().count(),
    }
    
    context = {
        'title': 'All Login Activity',
        'login_history': login_history,
        'stats': stats,
        'user_filter': user_filter,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'suspicious_only': suspicious_only,
    }
    return render(request, 'hospital/all_login_activity.html', context)


@login_required
def security_alerts_dashboard(request):
    """
    View all security alerts
    Requires admin or IT permissions
    """
    # Check if user is admin, superuser, or IT staff
    is_authorized = False
    if request.user.is_superuser or request.user.is_staff:
        is_authorized = True
    else:
        # Check if user is in IT group
        user_groups = request.user.groups.values_list('name', flat=True)
        for group_name in user_groups:
            group_lower = group_name.lower().replace(' ', '_')
            if group_lower in ['it', 'it_staff', 'it_operations', 'it_support']:
                is_authorized = True
                break
        # Check if user has IT-related profession
        if not is_authorized:
            try:
                from .models import Staff
                staff = Staff.objects.filter(user=request.user, is_deleted=False).first()
                if staff and staff.profession:
                    profession_lower = staff.profession.lower()
                    if profession_lower in ['it', 'it_staff', 'it_operations', 'it_support'] or 'it' in profession_lower:
                        is_authorized = True
            except Exception:
                pass
    
    if not is_authorized:
        messages.error(request, 'You do not have permission to view this page.')
        return redirect('hospital:dashboard')
    
    # Base queryset for unresolved alerts (don't slice yet - need it for stats)
    unresolved_alerts_base = SecurityAlert.objects.filter(
        is_resolved=False,
        is_deleted=False
    ).select_related('user', 'login_history')
    
    # Statistics (calculate before slicing)
    stats = {
        'total_unresolved': unresolved_alerts_base.count(),
        'critical': unresolved_alerts_base.filter(severity='critical').count(),
        'high': unresolved_alerts_base.filter(severity='high').count(),
        'medium': unresolved_alerts_base.filter(severity='medium').count(),
    }
    
    # Now slice for display (limit to 50 most recent)
    unresolved_alerts = unresolved_alerts_base.order_by('-alert_time')[:50]
    
    context = {
        'title': 'Security Alerts',
        'alerts': unresolved_alerts,
        'stats': stats,
    }
    return render(request, 'hospital/security_alerts_dashboard.html', context)


@login_required
def login_map_view(request):
    """
    Geographic map view of login locations
    """
    # Get recent logins with coordinates
    recent_logins = LoginHistory.objects.filter(
        status='success',
        latitude__isnull=False,
        longitude__isnull=False,
        is_deleted=False
    ).select_related('user').order_by('-login_time')[:100]
    
    # Prepare data for map
    login_points = []
    for login in recent_logins:
        login_points.append({
            'username': login.user.username,
            'location': login.location_display,
            'lat': float(login.latitude),
            'lng': float(login.longitude),
            'time': login.login_time.strftime('%Y-%m-%d %H:%M'),
            'suspicious': login.is_suspicious,
        })
    
    context = {
        'title': 'Login Map',
        'login_points': login_points,
    }
    return render(request, 'hospital/login_map_view.html', context)

