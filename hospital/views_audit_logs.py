"""
Audit Log Views
View and search audit logs
"""
import json
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.db.models.functions import Extract, TruncDate
from django.utils import timezone

from .models_audit import AuditLog, ActivityLog
from .utils_roles import get_user_role


def is_admin(user):
    """Check if user is admin, superuser, or IT staff"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return get_user_role(user) in {'admin', 'it'}


def _build_activity_log_analytics(queryset):
    """
    Aggregations for charts (same filters as the table, full filtered set — not just current page).
    """
    total = queryset.count()
    unique_users = (
        queryset.exclude(user__isnull=True).values("user_id").distinct().count()
    )
    distinct_types = (
        queryset.values("activity_type").distinct().count()
    )

    by_type_rows = list(
        queryset.values("activity_type")
        .annotate(c=Count("id"))
        .order_by("-c")[:20]
    )
    by_type_labels = [r["activity_type"] or "—" for r in by_type_rows]
    by_type_data = [r["c"] for r in by_type_rows]

    by_user_rows = list(
        queryset.exclude(user__isnull=True)
        .values("user__username")
        .annotate(c=Count("id"))
        .order_by("-c")[:15]
    )
    by_user_labels = [r["user__username"] or "—" for r in by_user_rows]
    by_user_data = [r["c"] for r in by_user_rows]

    hour_rows = list(
        queryset.annotate(h=Extract("created", "hour"))
        .values("h")
        .annotate(c=Count("id"))
        .order_by("h")
    )
    hour_map = {int(r["h"]): r["c"] for r in hour_rows if r["h"] is not None}
    by_hour_labels = [f"{h:02d}:00" for h in range(24)]
    by_hour_data = [hour_map.get(h, 0) for h in range(24)]

    day_rows = list(
        queryset.annotate(d=TruncDate("created"))
        .values("d")
        .annotate(c=Count("id"))
        .order_by("d")[:90]
    )
    by_day_labels = []
    by_day_data = []
    for r in day_rows:
        d = r["d"]
        if d:
            by_day_labels.append(d.isoformat() if hasattr(d, "isoformat") else str(d))
            by_day_data.append(r["c"])

    return {
        "total": total,
        "unique_users": unique_users,
        "distinct_types": distinct_types,
        "by_type": {"labels": by_type_labels, "data": by_type_data},
        "by_user": {"labels": by_user_labels, "data": by_user_data},
        "by_hour": {"labels": by_hour_labels, "data": by_hour_data},
        "by_day": {"labels": by_day_labels, "data": by_day_data},
    }


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
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            logs = logs.filter(created__date__gte=date_from_obj)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            logs = logs.filter(created__date__lte=date_to_obj)
        except ValueError:
            pass

    if search:
        logs = logs.filter(
            Q(description__icontains=search) |
            Q(user__username__icontains=search) |
            Q(ip_address__icontains=search)
        )

    analytics = _build_activity_log_analytics(logs)

    paginator = Paginator(logs.order_by('-created'), 50)
    page_obj = paginator.get_page(page_number)

    try:
        activity_types = ActivityLog.objects.values_list('activity_type', flat=True).distinct().order_by('activity_type')
    except Exception:
        activity_types = []

    filter_params = {}
    if activity_type:
        filter_params['activity_type'] = activity_type
    if user_id:
        filter_params['user'] = user_id
    if date_from:
        filter_params['date_from'] = date_from
    if date_to:
        filter_params['date_to'] = date_to
    if search:
        filter_params['q'] = search
    filter_query = urlencode(filter_params)

    # Quick presets (optional links in template)
    today = timezone.now().date()
    preset_7d = urlencode({
        'date_from': (today - timedelta(days=7)).isoformat(),
        'date_to': today.isoformat(),
    })
    preset_30d = urlencode({
        'date_from': (today - timedelta(days=30)).isoformat(),
        'date_to': today.isoformat(),
    })

    context = {
        'title': 'Activity Logs',
        'page_obj': page_obj,
        'logs': page_obj.object_list,
        'activity_types': activity_types,
        'analytics': analytics,
        'filter_query': filter_query,
        'preset_7d': preset_7d,
        'preset_30d': preset_30d,
        'filters': {
            'activity_type': activity_type,
            'user_id': user_id,
            'date_from': date_from,
            'date_to': date_to,
            'search': search,
        },
    }
    
    return render(request, 'hospital/admin/activity_logs.html', context)


@login_required
@user_passes_test(is_admin)
def activity_log_detail_view(request, pk):
    """
    Detailed view of a single activity log entry.
    """
    log = get_object_or_404(ActivityLog.objects.select_related('user'), pk=pk)
    activity_meta = log.metadata if isinstance(log.metadata, dict) else {}
    metadata_pretty = ""
    if activity_meta:
        try:
            metadata_pretty = json.dumps(activity_meta, indent=2, default=str)
        except (TypeError, ValueError):
            metadata_pretty = str(activity_meta)
    context = {
        'title': 'Activity Log Detail',
        'log': log,
        'activity_meta': activity_meta,
        'metadata_pretty': metadata_pretty,
    }
    return render(request, 'hospital/admin/activity_log_detail.html', context)

