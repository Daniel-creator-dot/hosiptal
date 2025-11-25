"""
IT Operations & Monitoring dashboard views.
Provides a consolidated view for technical administrators.
"""
from datetime import datetime, timedelta
import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.sessions.models import Session
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils import timezone
from django.db.models import Count
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
    """Return a lightweight list of the most recent active sessions."""
    try:
        sessions = (
            UserSession.objects.filter(is_active=True, logout_time__isnull=True)
            .select_related("user")
            .order_by("-login_time")[:limit]
        )
    except Exception as exc:
        logger.warning("Unable to fetch active sessions: %s", exc)
        return []

    active_sessions = []
    for session in sessions:
        user = session.user
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
            }
        )
    return active_sessions


def _get_blocked_users(limit=6):
    """Return recently blocked accounts with last activity metadata."""
    User = get_user_model()
    try:
        blocked_queryset = (
            User.objects.filter(is_active=False)
            .order_by("-date_joined")
            .only("id", "username", "email", "first_name", "last_name")[:limit]
        )
    except Exception as exc:
        logger.warning("Unable to fetch blocked users: %s", exc)
        return []

    blocked_users = list(blocked_queryset)
    if not blocked_users:
        return []

    user_ids = [user.id for user in blocked_users]
    last_sessions = {}
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

    blocked_payload = []
    for user in blocked_users:
        last_session = last_sessions.get(user.id, {})
        blocked_payload.append(
            {
                "user_id": user.id,
                "username": user.username,
                "full_name": user.get_full_name() or user.username,
                "email": user.email,
                "last_login": last_session.get("login_time"),
                "last_ip": last_session.get("ip_address"),
            }
        )

    return blocked_payload


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


def _get_activity_feed(limit=8):
    """Latest activity log entries."""
    try:
        return list(
            ActivityLog.objects.select_related("user")
            .order_by("-created")[:limit]
        )
    except Exception as exc:
        logger.warning("Unable to fetch activity logs: %s", exc)
        return []


def _build_snapshot():
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
        "activity_feed": _get_activity_feed(),
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
        return {
            "id": str(entry.id),
            "activity_type": entry.activity_type,
            "description": entry.description,
            "user": entry.user.username if getattr(entry, "user", None) else "System",
            "timestamp": entry.created.isoformat() if entry.created else None,
        }

    payload = snapshot.copy()
    payload["timestamp"] = snapshot["timestamp"].isoformat()
    payload["recent_incidents"] = [serialize_log(log) for log in snapshot["recent_incidents"]]
    payload["activity_feed"] = [serialize_activity(entry) for entry in snapshot["activity_feed"]]
    payload["active_sessions"] = [
        {
            **session,
            "login_time": session["login_time"].isoformat() if session.get("login_time") else None,
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
@user_passes_test(is_admin)
def it_operations_dashboard(request):
    """
    High-level IT operations dashboard for administrators.
    Combines infrastructure, security, and user activity signals.
    """
    snapshot = _build_snapshot()

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
    }
    return render(request, "hospital/admin/it_operations_dashboard.html", context)


@login_required
@user_passes_test(is_admin)
def it_operations_api(request):
    """AJAX endpoint to refresh dashboard metrics."""
    snapshot = _build_snapshot()
    return JsonResponse(_snapshot_for_api(snapshot))


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
@user_passes_test(is_admin)
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
@user_passes_test(is_admin)
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
@user_passes_test(is_admin)
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

