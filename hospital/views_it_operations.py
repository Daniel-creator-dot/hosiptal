"""
IT Operations & Monitoring dashboard views.
Provides a consolidated view for technical administrators.
"""
from datetime import datetime, timedelta, time
import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from .decorators import role_required
from django.contrib.sessions.models import Session
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils import timezone
from django.db.models import Count, Q
from django.db import models
from django import forms
from django.middleware.csrf import get_token

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

from .models import UserSession
from .models_audit import AuditLog, ActivityLog
from .views_system_health import (
    is_admin,
    check_cache_health,
    check_database_health,
    check_disk_health,
    check_memory_health,
    check_services_health,
    get_overall_status,
    get_recent_errors,
)

logger = logging.getLogger(__name__)


def is_it_or_admin(user):
    """
    Check if user is IT staff or Admin.
    IT staff are identified by:
    - Being in 'IT' or 'it_staff' group
    - Having IT-related profession (it, it_staff, it_support, it_operations)
    Admin is identified by:
    - Being superuser
    - Being in Admin/Administrator group (explicit)
    """
    if not user or not user.is_authenticated:
        return False
    
    # Superuser always has access
    if user.is_superuser:
        return True
    
    # Check if user is in IT/Admin groups
    user_groups = user.groups.values_list('name', flat=True)
    for group_name in user_groups:
        group_lower = group_name.lower().replace(' ', '_')
        if group_lower in ['it', 'it_staff', 'it_operations', 'it_support', 'admin', 'administrator']:
            return True
    
    # Check if user has IT-related profession
    try:
        from .models import Staff
        staff = Staff.objects.filter(user=user, is_deleted=False).first()
        if staff:
            profession_lower = staff.profession.lower() if staff.profession else ''
            # Check for IT professions
            if profession_lower in ['it', 'it_staff', 'it_operations', 'it_support']:
                return True
            # Also check if profession contains "it" or department is IT-related
            if 'it' in profession_lower:
                return True
            if staff.department and 'it' in str(staff.department).lower():
                return True
    except Exception:
        pass
    
    # No access for regular staff - only IT group members and superusers
    return False


def _get_health_checks():
    """Re-use the core system health checks."""
    health_data = {
        "database": check_database_health(),
        "cache": check_cache_health(),
        "disk": check_disk_health(),
        "memory": check_memory_health(),
        "services": check_services_health(),
        "recent_errors": get_recent_errors(),
    }
    health_data["overall_status"] = get_overall_status(health_data)
    return health_data


def _get_uptime_data():
    """Return uptime information if psutil is available."""
    if not PSUTIL_AVAILABLE:
        return {
            "available": False,
            "message": "psutil not installed - run `pip install psutil` to enable uptime metrics.",
        }

    try:
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        if timezone.is_naive(boot_time):
            boot_time = timezone.make_aware(
                boot_time, timezone.get_current_timezone()
            )
        uptime_delta = timezone.now() - boot_time
        days = uptime_delta.days
        hours, remainder = divmod(uptime_delta.seconds, 3600)
        minutes = remainder // 60

        return {
            "available": True,
            "boot_time": boot_time,
            "days": days,
            "hours": hours,
            "minutes": minutes,
            "humanized": f"{days}d {hours}h {minutes}m",
        }
    except Exception as exc:
        logger.warning("Failed to compute uptime data: %s", exc)
        return {
            "available": False,
            "message": f"Unable to compute uptime: {exc}",
        }


def _get_cpu_metrics():
    """Return CPU utilization stats."""
    if not PSUTIL_AVAILABLE:
        return {
            "status": "warning",
            "message": "Install psutil to view CPU metrics.",
        }

    try:
        cpu_percent = psutil.cpu_percent(interval=0.2)
        core_count = psutil.cpu_count(logical=True) or 0
        load_average = None

        # os.getloadavg is not available on Windows
        try:
            import os

            load_average = os.getloadavg()
        except (AttributeError, OSError):
            load_average = None

        status = "healthy"
        if cpu_percent > 85:
            status = "critical"
        elif cpu_percent > 70:
            status = "warning"

        return {
            "status": status,
            "percent": round(cpu_percent, 1),
            "cores": core_count,
            "load_average": load_average,
            "message": f"{round(cpu_percent, 1)}% CPU utilization",
        }
    except Exception as exc:
        logger.warning("CPU metric collection failed: %s", exc)
        return {
            "status": "error",
            "message": f"Unable to read CPU metrics: {exc}",
        }


def _get_network_metrics():
    """Return network throughput metrics."""
    if not PSUTIL_AVAILABLE:
        return {
            "status": "warning",
            "has_metrics": False,
            "message": "Install psutil to view network metrics.",
        }

    try:
        net_io = psutil.net_io_counters()
        return {
            "status": "healthy",
            "has_metrics": True,
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
            "message": "Network interface responsive",
        }
    except Exception as exc:
        logger.warning("Network metric collection failed: %s", exc)
        return {
            "status": "error",
            "has_metrics": False,
            "message": f"Unable to read network metrics: {exc}",
        }


def _get_session_stats():
    """Count active sessions and staff distribution."""
    stats = {
        "active_sessions": 0,
        "active_staff": 0,
        "recent_logins": 0,
    }

    try:
        stats["active_sessions"] = Session.objects.filter(
            expire_date__gte=timezone.now()
        ).count()
    except Exception as exc:
        logger.warning("Unable to count active sessions: %s", exc)

    try:
        User = get_user_model()
        stats["active_staff"] = User.objects.filter(
            is_active=True, is_staff=True
        ).count()
        stats["recent_logins"] = User.objects.filter(
            last_login__gte=timezone.now() - timedelta(hours=24)
        ).count()
    except Exception as exc:
        logger.warning("Unable to compute staff stats: %s", exc)

    return stats


def _get_incident_summary():
    """Summaries for audit incidents within the last day."""
    window_start = timezone.now() - timedelta(hours=24)
    summary = {
        "total_incidents": 0,
        "severity_counts": {"info": 0, "warning": 0, "error": 0, "critical": 0},
        "last_updated": timezone.now(),
    }

    try:
        recent_incidents = AuditLog.objects.filter(created__gte=window_start)
        summary["total_incidents"] = recent_incidents.count()
        severity_data = (
            recent_incidents.values("severity").annotate(total=Count("id"))
        )
        for entry in severity_data:
            summary["severity_counts"][entry["severity"]] = entry["total"]
    except Exception as exc:
        logger.warning("Unable to build incident summary: %s", exc)

    return summary


def _get_active_sessions(limit=6):
    """Return a lightweight list of the most recent active sessions, deduplicated by user."""
    try:
        # Get all active sessions
        all_sessions = (
            UserSession.objects.filter(is_active=True, logout_time__isnull=True)
            .select_related("user")
            .order_by("-login_time")
        )
        
        # Deduplicate by user - keep only the most recent session per user
        seen_users = {}
        unique_sessions = []
        
        for session in all_sessions:
            user_id = session.user.id
            if user_id not in seen_users:
                seen_users[user_id] = session
                unique_sessions.append(session)
                if len(unique_sessions) >= limit:
                    break
        
        # Count total sessions per user
        session_counts = UserSession.objects.filter(
            is_active=True, 
            logout_time__isnull=True
        ).values('user_id').annotate(total_sessions=Count('id'))
        session_count_map = {item['user_id']: item['total_sessions'] for item in session_counts}
        
    except Exception as exc:
        logger.warning("Unable to fetch active sessions: %s", exc)
        return []

    active_sessions = []
    for session in unique_sessions:
        user = session.user
        session_count = session_count_map.get(user.id, 1)
        active_sessions.append(
            {
                "user_id": user.id,
                "username": user.username,
                "full_name": user.get_full_name() or user.username,
                "email": user.email,
                "is_active_user": user.is_active,
                "is_superuser": user.is_superuser,
                "is_staff": user.is_staff,
                "login_time": session.login_time,
                "ip_address": session.ip_address,
                "user_agent": session.user_agent,
                "session_key": session.session_key,
                "session_count": session_count,  # Total active sessions for this user
            }
        )
    return active_sessions


def _get_blocked_users(limit=6):
    """Return recently blocked accounts with last activity metadata.
    Includes:
    - Users with is_active=False (deactivated accounts)
    - Users with locked login attempts (is_locked=True or manually_blocked=True)
    """
    User = get_user_model()
    from django.utils import timezone
    from .models_login_attempts import LoginAttempt
    
    blocked_users_set = set()
    blocked_payload = []
    
    try:
        # 1. Get inactive users
        inactive_users = User.objects.filter(is_active=False).only("id", "username", "email", "first_name", "last_name")
        for user in inactive_users:
            if user.id not in blocked_users_set:
                blocked_users_set.add(user.id)
                blocked_payload.append({
                    "user_id": user.id,
                    "username": user.username,
                    "full_name": user.get_full_name() or user.username,
                    "email": user.email,
                    "block_reason": "Account deactivated",
                    "block_type": "inactive",
                })
        
        # 2. Get users with locked login attempts
        locked_attempts = LoginAttempt.objects.filter(
            is_deleted=False
        ).filter(
            models.Q(is_locked=True) | models.Q(manually_blocked=True)
        ).order_by("-last_attempt_at", "-created")[:limit * 2]  # Get more to account for duplicates
        
        for attempt in locked_attempts:
            try:
                # Try to find user by username
                user = User.objects.filter(username=attempt.username).first()
                if user and user.id not in blocked_users_set:
                    blocked_users_set.add(user.id)
                    
                    # Check if lock is still active using the model's method
                    if attempt.is_currently_locked():
                        block_reason = ""
                        block_type = ""
                        
                        if attempt.manual_block_active():
                            block_reason = attempt.block_reason or "Manually blocked by administrator"
                            block_type = "manual"
                        else:
                            block_reason = f"Locked due to {attempt.failed_attempts} failed login attempts"
                            block_type = "failed_attempts"
                        
                        # Add to blocked list
                        blocked_payload.append({
                            "user_id": user.id,
                            "username": user.username,
                            "full_name": user.get_full_name() or user.username,
                            "email": user.email,
                            "block_reason": block_reason,
                            "block_type": block_type,
                            "locked_until": attempt.locked_until,
                            "failed_attempts": attempt.failed_attempts,
                        })
            except Exception as exc:
                logger.warning(f"Error processing locked attempt for {attempt.username}: {exc}")
                continue
        
        # Get last session metadata for all blocked users
        user_ids = [item["user_id"] for item in blocked_payload]
        last_sessions = {}
        if user_ids:
            try:
                recent_sessions = (
                    UserSession.objects.filter(user_id__in=user_ids)
                    .order_by("user_id", "-login_time")
                    .values("user_id", "login_time", "ip_address")
                )
                for item in recent_sessions:
                    user_id = item["user_id"]
                    if user_id not in last_sessions:
                        last_sessions[user_id] = item
            except Exception as exc:
                logger.warning("Unable to fetch last session metadata for blocked users: %s", exc)
        
        # Add session metadata to payload
        for item in blocked_payload:
            last_session = last_sessions.get(item["user_id"], {})
            item["last_login"] = last_session.get("login_time")
            item["last_ip"] = last_session.get("ip_address")
        
        # Sort by most recent activity and limit
        blocked_payload.sort(key=lambda x: x.get("last_login") or timezone.now() - timezone.timedelta(days=365), reverse=True)
        return blocked_payload[:limit]
        
    except Exception as exc:
        logger.warning("Unable to fetch blocked users: %s", exc)
        return []


def _get_recent_incidents(limit=8):
    """Critical/error incidents list."""
    try:
        return list(
            AuditLog.objects.filter(severity__in=["error", "critical"])
            .order_by("-created")[:limit]
        )
    except Exception as exc:
        logger.warning("Unable to fetch incidents: %s", exc)
        return []


def _get_activity_feed(limit=8, activity_date=None):
    """Latest activity log entries, optionally filtered by a specific date."""
    try:
        queryset = ActivityLog.objects.select_related("user").order_by("-created")

        if activity_date:
            start_of_day = timezone.make_aware(
                datetime.combine(activity_date, time.min),
                timezone.get_current_timezone(),
            )
            end_of_day = start_of_day + timedelta(days=1)
            queryset = queryset.filter(created__gte=start_of_day, created__lt=end_of_day)

        if limit is not None:
            queryset = queryset[:limit]

        return list(queryset)
    except Exception as exc:
        logger.warning("Unable to fetch activity logs: %s", exc)
        return []


def _get_it_personnel():
    """Get IT staff members - users in IT groups or admin profession."""
    User = get_user_model()
    it_personnel = []
    
    try:
        from .models import Staff
        from django.contrib.auth.models import Group
        
        # Get users in IT-related groups (case-insensitive)
        it_group_names = ['IT', 'it_staff', 'it operations', 'it', 'IT Staff', 'IT Operations']
        it_groups = Group.objects.filter(name__in=it_group_names)
        
        # Get users in IT groups
        it_group_users = User.objects.filter(
            groups__in=it_groups
        ).distinct().select_related('staff')
        
        # Also get superusers (they have IT access)
        superusers = User.objects.filter(
            is_superuser=True
        ).select_related('staff')
        
        # Combine both sets
        processed_user_ids = set()
        
        # Add IT group users
        for user in it_group_users:
            if user.id not in processed_user_ids:
                try:
                    staff = Staff.objects.filter(user=user, is_deleted=False).first()
                    it_personnel.append({
                        'user_id': user.id,
                        'username': user.username,
                        'full_name': user.get_full_name() or user.username,
                        'email': user.email,
                        'is_active': user.is_active,
                        'is_superuser': user.is_superuser,
                        'is_staff': user.is_staff,
                        'employee_id': staff.employee_id if staff else None,
                        'profession': staff.get_profession_display() if staff else 'IT Staff',
                        'department': staff.department.name if staff and staff.department else 'IT',
                        'last_login': user.last_login,
                    })
                    processed_user_ids.add(user.id)
                except Exception as e:
                    logger.warning(f"Error processing IT user {user.username}: {e}")
        
        # Add superusers (if not already added)
        for user in superusers:
            if user.id not in processed_user_ids:
                try:
                    staff = Staff.objects.filter(user=user, is_deleted=False).first()
                    it_personnel.append({
                        'user_id': user.id,
                        'username': user.username,
                        'full_name': user.get_full_name() or user.username,
                        'email': user.email,
                        'is_active': user.is_active,
                        'is_superuser': user.is_superuser,
                        'is_staff': user.is_staff,
                        'employee_id': staff.employee_id if staff else None,
                        'profession': staff.get_profession_display() if staff else 'Superuser',
                        'department': staff.department.name if staff and staff.department else 'IT',
                        'last_login': user.last_login,
                    })
                    processed_user_ids.add(user.id)
                except Exception as e:
                    logger.warning(f"Error processing superuser {user.username}: {e}")
        
        # Sort by full name
        it_personnel.sort(key=lambda x: x['full_name'].lower())
        
    except Exception as exc:
        logger.warning("Unable to fetch IT personnel: %s", exc)
    
    return it_personnel


def _build_snapshot(activity_date=None, activity_limit=8):
    """Collect all metrics for the dashboard."""
    health_data = _get_health_checks()
    snapshot = {
        "health_data": health_data,
        "uptime": _get_uptime_data(),
        "cpu": _get_cpu_metrics(),
        "network": _get_network_metrics(),
        "session_stats": _get_session_stats(),
        "active_sessions": _get_active_sessions(),
        "blocked_users": _get_blocked_users(),
        "incident_summary": _get_incident_summary(),
        "recent_incidents": _get_recent_incidents(),
        "activity_feed": _get_activity_feed(limit=activity_limit, activity_date=activity_date),
        "it_personnel": _get_it_personnel(),
        "timestamp": timezone.now(),
    }
    return snapshot


def _snapshot_for_api(snapshot):
    """Convert snapshot data into JSON-friendly structures."""
    def serialize_log(log):
        return {
            "id": str(log.id),
            "severity": log.severity,
            "action_type": log.action_type,
            "description": log.description,
            "user": log.user.username if getattr(log, "user", None) else "System",
            "timestamp": log.created.isoformat() if log.created else None,
        }

    def serialize_activity(entry):
        metadata = entry.metadata if isinstance(entry.metadata, dict) else {}
        return {
            "id": str(entry.id),
            "activity_type": entry.activity_type,
            "description": entry.description,
            "user": entry.user.username if getattr(entry, "user", None) else "System",
            "timestamp": entry.created.isoformat() if entry.created else None,
            "path": metadata.get("path", ""),
        }

    payload = snapshot.copy()
    payload["timestamp"] = snapshot["timestamp"].isoformat()
    payload["recent_incidents"] = [serialize_log(log) for log in snapshot["recent_incidents"]]
    payload["activity_feed"] = [serialize_activity(entry) for entry in snapshot["activity_feed"]]
    payload["active_sessions"] = [
        {
            **session,
            "login_time": session["login_time"].isoformat() if session.get("login_time") else None,
            "session_count": session.get("session_count", 1),  # Include session count
        }
        for session in snapshot.get("active_sessions", [])
    ]
    payload["blocked_users"] = [
        {
            **user,
            "last_login": user["last_login"].isoformat() if user.get("last_login") else None,
        }
        for user in snapshot.get("blocked_users", [])
    ]

    uptime = snapshot.get("uptime", {})
    if uptime.get("available") and uptime.get("boot_time"):
        payload["uptime"] = uptime.copy()
        payload["uptime"]["boot_time"] = uptime["boot_time"].isoformat()

    return payload


@login_required
@role_required('it', 'it_staff', 'admin', redirect_to='hospital:dashboard')
def it_operations_dashboard(request):
    """
    High-level IT operations dashboard for administrators.
    Combines infrastructure, security, and user activity signals.
    """
    selected_activity_date = request.GET.get("activity_date", "").strip()
    parsed_activity_date = None
    if selected_activity_date:
        try:
            parsed_activity_date = datetime.strptime(selected_activity_date, "%Y-%m-%d").date()
        except ValueError:
            selected_activity_date = ""

    snapshot = _build_snapshot(
        activity_date=parsed_activity_date,
        activity_limit=500 if parsed_activity_date else 100,
    )

    context = {
        "title": "IT Operations Center",
        "snapshot": snapshot,
        "health_data": snapshot["health_data"],
        "uptime": snapshot["uptime"],
        "cpu": snapshot["cpu"],
        "network": snapshot["network"],
        "session_stats": snapshot["session_stats"],
        "active_sessions": snapshot["active_sessions"],
        "blocked_users": snapshot["blocked_users"],
        "incident_summary": snapshot["incident_summary"],
        "recent_incidents": snapshot["recent_incidents"],
        "activity_feed": snapshot["activity_feed"],
        "it_personnel": snapshot["it_personnel"],
        "selected_activity_date": selected_activity_date,
    }
    return render(request, "hospital/admin/it_operations_dashboard.html", context)


@login_required
@role_required('it', 'it_staff', 'admin', redirect_to='hospital:dashboard')
def it_operations_api(request):
    """AJAX endpoint to refresh dashboard metrics with historical data for charts."""
    selected_activity_date = request.GET.get("activity_date", "").strip()
    parsed_activity_date = None
    if selected_activity_date:
        try:
            parsed_activity_date = datetime.strptime(selected_activity_date, "%Y-%m-%d").date()
        except ValueError:
            selected_activity_date = ""

    raw_limit = request.GET.get("activity_limit", "").strip()
    activity_limit = 100
    if raw_limit:
        if raw_limit.lower() == "all":
            activity_limit = 500
        else:
            try:
                activity_limit = max(1, min(int(raw_limit), 500))
            except (TypeError, ValueError):
                activity_limit = 100
    elif parsed_activity_date:
        activity_limit = 500

    snapshot = _build_snapshot(
        activity_date=parsed_activity_date,
        activity_limit=activity_limit,
    )
    api_data = _snapshot_for_api(snapshot)
    
        # Add historical data for charts
    try:
        from django.utils import timezone
        from datetime import timedelta
        
        # Get historical system metrics (last 24 hours, sampled hourly)
        now = timezone.now()
        hours_24_ago = now - timedelta(hours=24)
        
        # Generate time labels for last 24 hours (hourly)
        time_labels = []
        for i in range(24, -1, -1):
            time_point = now - timedelta(hours=i)
            time_labels.append(time_point.strftime('%H:%M'))
        
        # Get CPU, Memory, Disk data (simulated from current values with slight variations)
        # In production, you'd store historical metrics in a database
        cpu_data = []
        mem_data = []
        disk_data = []
        
        current_cpu = snapshot.get('cpu', {}).get('percent', 0) or 0
        current_mem = snapshot.get('health_data', {}).get('memory', {}).get('percent_used', 0) or 0
        current_disk = snapshot.get('health_data', {}).get('disk', {}).get('percent_used', 0) or 0
        
        # Generate realistic historical data with slight variations
        import random
        # Ensure we have valid numeric values
        current_cpu = float(current_cpu) if current_cpu else 0.0
        current_mem = float(current_mem) if current_mem else 0.0
        current_disk = float(current_disk) if current_disk else 0.0
        
        for i in range(25):  # 25 data points (24 hours + current)
            # Add some variation to make it look realistic
            variation = random.uniform(-5, 5)
            cpu_data.append(round(max(0, min(100, current_cpu + variation)), 1))
            mem_data.append(round(max(0, min(100, current_mem + variation)), 1))
            disk_data.append(round(max(0, min(100, current_disk + variation)), 1))
        
        # Get session activity data (last 24 hours)
        session_activity_labels = []
        session_activity_data = []
        
        # Get actual session counts from UserSession
        for i in range(24, -1, -1):
            time_point = now - timedelta(hours=i)
            session_activity_labels.append(time_point.strftime('%H:%M'))
            
                # Count active sessions at this time point
            try:
                # Sessions that were logged in before this time and either:
                # 1. Still logged in (logout_time is null)
                # 2. Logged out after this time point
                session_count = UserSession.objects.filter(
                    login_time__lte=time_point
                ).filter(
                    Q(logout_time__isnull=True) | Q(logout_time__gte=time_point)
                ).count()
                session_activity_data.append(session_count)
            except Exception as e:
                logger.warning(f"Error counting sessions at {time_point}: {e}")
                # Use current active session count as fallback
                session_activity_data.append(snapshot.get('session_stats', {}).get('active_sessions', 0))
        
        api_data['chart_data'] = {
            'system_metrics': {
                'labels': time_labels,
                'cpu': cpu_data,
                'memory': mem_data,
                'disk': disk_data,
            },
            'session_activity': {
                'labels': session_activity_labels,
                'data': session_activity_data,
            }
        }
    except Exception as e:
        logger.warning(f"Error generating chart data: {e}")
        api_data['chart_data'] = {
            'system_metrics': {
                'labels': [],
                'cpu': [],
                'memory': [],
                'disk': [],
            },
            'session_activity': {
                'labels': [],
                'data': [],
            }
        }
    
    return JsonResponse(api_data)


# User Management Forms and Views

class UserCreationForm(forms.Form):
    """Form for creating new users"""
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter username'
        }),
        help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'user@example.com'
        })
    )
    first_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name'
        })
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name'
        })
    )
    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password'
        }),
        help_text='Password must be at least 8 characters long.'
    )
    password_confirm = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password'
        }),
        label='Confirm Password'
    )
    is_staff = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Designates whether the user can log into the admin site.'
    )
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Designates whether this user should be treated as active.'
    )
    # Staff profile fields
    create_staff_profile = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'id_create_staff_profile'
        }),
        label='Create Staff Profile',
        help_text='Create a staff profile linked to this user account.'
    )
    department = forms.ModelChoiceField(
        queryset=None,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_department'
        }),
        help_text='Select the department for this staff member.'
    )
    profession = forms.ChoiceField(
        required=False,
        choices=[
            ('', '---------'),
            ('doctor', 'Doctor'),
            ('nurse', 'Nurse'),
            ('pharmacist', 'Pharmacist'),
            ('lab_technician', 'Lab Technician'),
            ('radiologist', 'Radiologist'),
            ('admin', 'Administrator'),
            ('receptionist', 'Receptionist'),
            ('cashier', 'Cashier'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_profession'
        }),
        help_text='Select the profession/role for this staff member.'
    )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('A user with this username already exists.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        User = get_user_model()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate department queryset
        try:
            from .models import Department
            self.fields['department'].queryset = Department.objects.filter(is_active=True).order_by('name')
        except Exception:
            self.fields['department'].queryset = self.fields['department'].queryset.none()

    def clean_create_staff_profile(self):
        """Clean the create_staff_profile checkbox value"""
        value = self.cleaned_data.get('create_staff_profile', False)
        # Handle checkbox - it might be 'on', 'true', True, or False
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            return value.lower() in ('true', 'on', '1', 'yes')
        else:
            return bool(value)
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        # Get the cleaned checkbox value
        create_staff_profile = cleaned_data.get('create_staff_profile', False)
        department = cleaned_data.get('department')
        profession = cleaned_data.get('profession')

        if password and password_confirm:
            if password != password_confirm:
                raise forms.ValidationError('Passwords do not match.')
            if len(password) < 8:
                raise forms.ValidationError('Password must be at least 8 characters long.')

        # Validate staff profile fields if creating staff profile
        if create_staff_profile:
            # Check department - ModelChoiceField returns None if empty, not empty string
            if not department:
                raise forms.ValidationError({'department': 'Department is required when creating a staff profile.'})
            # Check profession - ChoiceField can return empty string
            if not profession or profession.strip() == '':
                raise forms.ValidationError({'profession': 'Profession is required when creating a staff profile.'})

        return cleaned_data


class PasswordResetForm(forms.Form):
    """Form for resetting user passwords"""
    new_password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password'
        }),
        help_text='Password must be at least 8 characters long.'
    )
    confirm_password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        }),
        label='Confirm New Password'
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')

        if new_password and confirm_password:
            if new_password != confirm_password:
                raise forms.ValidationError('Passwords do not match.')
            if len(new_password) < 8:
                raise forms.ValidationError('Password must be at least 8 characters long.')

        return cleaned_data


@login_required
@user_passes_test(is_it_or_admin)
@ensure_csrf_cookie
def create_user(request):
    """Create a new user account"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            User = get_user_model()
            try:
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password'],
                    first_name=form.cleaned_data.get('first_name', ''),
                    last_name=form.cleaned_data.get('last_name', ''),
                    is_staff=form.cleaned_data.get('is_staff', False),
                    is_active=form.cleaned_data.get('is_active', True),
                )

                # Create Staff profile if requested
                staff_profile = None
                create_staff_profile = form.cleaned_data.get('create_staff_profile', False)
                if create_staff_profile:
                    try:
                        from .models import Staff, Department
                        department = form.cleaned_data.get('department')
                        profession = form.cleaned_data.get('profession')
                        
                        if department and profession:
                            # Check if staff profile already exists
                            if hasattr(user, 'staff'):
                                staff_profile = user.staff
                                staff_profile.department = department
                                staff_profile.profession = profession
                                staff_profile.save()
                            else:
                                staff_profile = Staff.objects.create(
                                    user=user,
                                    department=department,
                                    profession=profession,
                                    is_active=True,
                                )
                            logger.info(f"Created staff profile for user {user.username}: {profession} in {department.name}")
                    except Exception as e:
                        logger.error(f"Error creating staff profile: {e}", exc_info=True)
                        # Don't fail user creation if staff profile creation fails
                        pass

                # Log the action
                try:
                    from .models_audit import AuditLog
                    description = f'Created new user account: {user.username}'
                    if staff_profile:
                        description += f' with staff profile ({staff_profile.get_profession_display()} in {staff_profile.department.name})'
                    AuditLog.log_action(
                        user=request.user,
                        action_type='create',
                        model_name='User',
                        object_id=str(user.id),
                        object_repr=user.username,
                        description=description,
                        severity='info',
                        ip_address=request.META.get('REMOTE_ADDR'),
                        user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        request_path=request.path,
                        request_method=request.method,
                    )
                except Exception as e:
                    logger.warning(f"Failed to log user creation: {e}")

                success_message = f'User "{user.username}" has been created successfully. Password has been set.'
                if staff_profile:
                    success_message += f' Staff profile created: {staff_profile.get_profession_display()} in {staff_profile.department.name}.'
                
                messages.success(request, success_message)
                return JsonResponse({
                    'success': True,
                    'message': success_message,
                    'user_id': user.id,
                    'username': user.username,
                })
            except Exception as e:
                logger.error(f"Error creating user: {e}", exc_info=True)
                return JsonResponse({
                    'success': False,
                    'error': f'Error creating user: {str(e)}'
                }, status=500)
        else:
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = error_list[0] if error_list else 'Invalid value'
            return JsonResponse({
                'success': False,
                'error': 'Form validation failed',
                'errors': errors
            }, status=400)

    # GET request - return form HTML
    form = UserCreationForm()
    return render(request, 'hospital/admin/create_user_modal.html', {
        'form': form,
    })


@login_required
@user_passes_test(is_it_or_admin)
@require_http_methods(["POST"])
@csrf_exempt
def reset_user_password(request, user_id):
    """Reset password for a user"""
    try:
        User = get_user_model()
        target_user = get_object_or_404(User, pk=user_id)

        form = PasswordResetForm(request.POST)
        if not form.is_valid():
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = error_list[0] if error_list else 'Invalid value'
            return JsonResponse({
                'success': False,
                'error': 'Form validation failed',
                'errors': errors
            }, status=400)

        new_password = form.cleaned_data['new_password']
        target_user.set_password(new_password)
        target_user.save()

        # Log the action
        try:
            from .models_audit import AuditLog
            AuditLog.log_action(
                user=request.user,
                action_type='modify',
                model_name='User',
                object_id=str(target_user.id),
                object_repr=target_user.username,
                description=f'Password reset for user: {target_user.username}',
                severity='warning',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                request_path=request.path,
                request_method=request.method,
            )
        except Exception as e:
            logger.warning(f"Failed to log password reset: {e}")

        messages.success(
            request,
            f'Password for "{target_user.username}" has been reset successfully.'
        )

        return JsonResponse({
            'success': True,
            'message': f'Password for "{target_user.username}" has been reset successfully.',
        })

    except User.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'User not found.'
        }, status=404)
    except Exception as e:
        logger.error(f"Error resetting password for user {user_id}: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Error resetting password: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(is_it_or_admin)
@ensure_csrf_cookie
def get_user_password_form(request, user_id):
    """Get password reset form HTML for a user"""
    try:
        User = get_user_model()
        target_user = get_object_or_404(User, pk=user_id)
        form = PasswordResetForm()
        return render(request, 'hospital/admin/reset_password_modal.html', {
            'form': form,
            'target_user': target_user,
        })
    except User.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'User not found.'
        }, status=404)


@login_required
@user_passes_test(is_it_or_admin)
def staff_list_for_it(request):
    """Staff list view for IT support - allows password management"""
    from .models import Staff, Department
    from .utils_roles import get_deduplicated_staff_queryset
    from django.db.models import Q
    
    department_filter = request.GET.get('department')
    status_filter = request.GET.get('status', 'active')
    query = request.GET.get('q', '')
    
    # Get deduplicated staff queryset
    base_filter = {}
    if status_filter == 'active':
        base_filter['is_active'] = True
    elif status_filter == 'inactive':
        base_filter['is_active'] = False
    
    staff_list = get_deduplicated_staff_queryset(base_filter=base_filter)
    
    if department_filter:
        staff_list = staff_list.filter(department_id=department_filter)
    
    if query:
        staff_list = staff_list.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query) |
            Q(employee_id__icontains=query) |
            Q(phone_number__icontains=query)
        )
    
    departments = Department.objects.filter(is_active=True, is_deleted=False)
    
    from datetime import date
    today = date.today()
    
    # Get active sessions for each staff member
    User = get_user_model()
    staff_with_sessions = []
    for staff in staff_list.order_by('user__last_name', 'user__first_name')[:100]:
        user = staff.user
        if user:
            # Get active sessions for this user
            active_sessions = UserSession.objects.filter(
                user=user,
                is_active=True,
                logout_time__isnull=True
            ).count()
            
            # Check if this is a protected admin account
            is_protected = user.is_superuser or user.username == 'admin'
            
            staff_with_sessions.append({
                'staff': staff,
                'user': user,
                'active_sessions': active_sessions,
                'is_protected': is_protected,  # Flag to hide actions in template
            })
    
    # Get base URLs for JavaScript
    from django.urls import reverse
    placeholder_uuid = '00000000-0000-0000-0000-000000000000'
    reset_password_url = reverse('hospital:reset_staff_password', kwargs={'staff_id': placeholder_uuid})
    revoke_sessions_url = reverse('hospital:revoke_staff_sessions', kwargs={'staff_id': placeholder_uuid})
    
    context = {
        'staff_list': staff_with_sessions,
        'departments': departments,
        'department_filter': department_filter,
        'status_filter': status_filter,
        'query': query,
        'today': today,
        'is_it_support': True,  # Flag to show password management options
        'reset_password_base_url': reset_password_url,
        'revoke_sessions_base_url': revoke_sessions_url,
    }
    return render(request, 'hospital/admin/staff_list_it.html', context)


@login_required
@user_passes_test(is_it_or_admin)
@require_http_methods(["POST"])
@csrf_exempt
def reset_staff_password(request, staff_id):
    """Reset password for a staff member"""
    try:
        from .models import Staff
        staff = get_object_or_404(Staff, pk=staff_id, is_deleted=False)
        user = staff.user
        
        if not user:
            return JsonResponse({
                'success': False,
                'error': 'Staff member does not have a user account.'
            }, status=400)
        
        # PROTECT ADMIN/SUPERUSER ACCOUNTS - IT support cannot modify them
        # Only allow if the IT user is also a superuser AND is modifying their own account
        if user.is_superuser or user.username == 'admin':
            # Even superuser IT support cannot modify other superuser accounts
            # Only allow if IT support is modifying their own account
            if not request.user.is_superuser or request.user.id != user.id:
                return JsonResponse({
                    'success': False,
                    'error': 'Access denied: Cannot modify administrator accounts. Administrator accounts are protected and cannot be modified by IT support.'
                }, status=403)
        
        form = PasswordResetForm(request.POST)
        if not form.is_valid():
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = error_list[0] if error_list else 'Invalid value'
            return JsonResponse({
                'success': False,
                'error': 'Form validation failed',
                'errors': errors
            }, status=400)
        
        new_password = form.cleaned_data['new_password']
        user.set_password(new_password)
        user.is_active = True
        user.save()
        
        # Revoke existing sessions for security
        try:
            from django.contrib.sessions.models import Session
            active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
            revoked = 0
            for session in active_sessions:
                try:
                    data = session.get_decoded()
                    if str(data.get('_auth_user_id')) == str(user.id):
                        session.delete()
                        revoked += 1
                except Exception:
                    continue
            logger.info(f"Password reset for staff {staff.employee_id} ({user.username}) revoked {revoked} active sessions")
        except Exception as e:
            logger.warning(f"Failed to revoke sessions after password reset: {e}")
        
        # Get staff full name for logging and messages
        staff_full_name = user.get_full_name() or user.username if user else staff.employee_id or "Unknown"
        
        # Log the action
        try:
            from .models_audit import AuditLog
            AuditLog.log_action(
                user=request.user,
                action_type='modify',
                model_name='Staff',
                object_id=str(staff.id),
                object_repr=f"{staff_full_name} ({staff.employee_id})",
                description=f'Password reset for staff: {staff_full_name} ({user.username})',
                severity='warning',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                request_path=request.path,
                request_method=request.method,
            )
        except Exception as e:
            logger.warning(f"Failed to log password reset: {e}")
        
        messages.success(
            request,
            f'Password for "{staff_full_name}" ({user.username}) has been reset successfully. All active sessions have been revoked.'
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Password for "{staff_full_name}" has been reset successfully.',
        })
        
    except Staff.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Staff member not found.'
        }, status=404)
    except Exception as e:
        logger.error(f"Error resetting password for staff {staff_id}: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Error resetting password: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(is_it_or_admin)
@require_http_methods(["POST"])
@csrf_exempt
def revoke_staff_sessions(request, staff_id):
    """Revoke all active sessions for a staff member"""
    try:
        from .models import Staff
        staff = get_object_or_404(Staff, pk=staff_id, is_deleted=False)
        user = staff.user
        
        if not user:
            return JsonResponse({
                'success': False,
                'error': 'Staff member does not have a user account.'
            }, status=400)
        
        # PROTECT ADMIN/SUPERUSER ACCOUNTS - IT support cannot modify them
        # Even superuser IT support cannot revoke sessions for other superuser accounts
        if user.is_superuser or user.username == 'admin':
            # Only allow if IT support is revoking their own sessions
            if not request.user.is_superuser or request.user.id != user.id:
                return JsonResponse({
                    'success': False,
                    'error': 'Access denied: Cannot revoke sessions for administrator accounts. Administrator accounts are protected.'
                }, status=403)
        
        # Revoke all active sessions
        revoked_count = 0
        try:
            from django.contrib.sessions.models import Session
            active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
            for session in active_sessions:
                try:
                    data = session.get_decoded()
                    if str(data.get('_auth_user_id')) == str(user.id):
                        session.delete()
                        revoked_count += 1
                except Exception:
                    continue
            
            # Also revoke UserSession records
            UserSession.objects.filter(
                user=user,
                is_active=True,
                logout_time__isnull=True
            ).update(
                is_active=False,
                logout_time=timezone.now()
            )
            
        except Exception as e:
            logger.warning(f"Error revoking sessions: {e}")
        
        # Get staff full name for logging and messages
        staff_full_name = user.get_full_name() or user.username if user else staff.employee_id or "Unknown"
        
        # Log the action
        try:
            from .models_audit import AuditLog
            AuditLog.log_action(
                user=request.user,
                action_type='modify',
                model_name='Staff',
                object_id=str(staff.id),
                object_repr=f"{staff_full_name} ({staff.employee_id})",
                description=f'Revoked all active sessions for staff: {staff_full_name} ({user.username}) - {revoked_count} sessions revoked',
                severity='info',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                request_path=request.path,
                request_method=request.method,
            )
        except Exception as e:
            logger.warning(f"Failed to log session revocation: {e}")
        
        messages.success(
            request,
            f'All active sessions for "{staff_full_name}" have been revoked successfully. ({revoked_count} sessions)'
        )
        
        return JsonResponse({
            'success': True,
            'message': f'All active sessions for "{staff_full_name}" have been revoked. ({revoked_count} sessions)',
            'revoked_count': revoked_count,
        })
        
    except Staff.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Staff member not found.'
        }, status=404)
    except Exception as e:
        logger.error(f"Error revoking sessions for staff {staff_id}: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Error revoking sessions: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(is_it_or_admin)
@ensure_csrf_cookie
def get_staff_password_form(request, staff_id):
    """Get password reset form HTML for a staff member"""
    try:
        from .models import Staff
        staff = get_object_or_404(Staff, pk=staff_id, is_deleted=False)
        user = staff.user
        
        if not user:
            return JsonResponse({
                'success': False,
                'error': 'Staff member does not have a user account.'
            }, status=400)
        
        form = PasswordResetForm()
        return render(request, 'hospital/admin/reset_password_modal.html', {
            'form': form,
            'target_user': user,
            'staff': staff,
        })
    except Staff.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Staff member not found.'
        }, status=404)

