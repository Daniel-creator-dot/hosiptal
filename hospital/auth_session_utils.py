from django.utils import timezone
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.db import OperationalError, ProgrammingError, DatabaseError

from .models import UserSession


def _get_client_ip(request):
    """Best-effort extraction of client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def _safe_usersession_operation(operation):
    """
    Execute a UserSession DB operation, swallowing errors if the table
    does not yet exist (e.g., migrations pending in a fresh environment).
    """
    try:
        return operation()
    except (ProgrammingError, OperationalError, DatabaseError) as exc:
        if 'hospital_usersession' in str(exc):
            # Gracefully degrade when deployments haven't run the migration yet.
            return None
        raise


@receiver(user_logged_in)
def create_user_session(sender, request, user, **kwargs):
    """
    Create a UserSession record when a user logs in.
    """
    session_key = request.session.session_key or ''
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    ip_address = _get_client_ip(request)

    def close_previous_sessions():
        return UserSession.objects.filter(
            session_key=session_key,
            is_active=True
        ).update(is_active=False, logout_time=timezone.now())

    def create_session():
        return UserSession.objects.create(
            user=user,
            session_key=session_key,
            login_time=timezone.now(),
            user_agent=user_agent,
            ip_address=ip_address,
            is_active=True,
        )

    _safe_usersession_operation(close_previous_sessions)
    _safe_usersession_operation(create_session)


@receiver(user_logged_out)
def close_user_session(sender, request, user, **kwargs):
    """
    Mark the corresponding UserSession as ended when the user logs out.
    """
    if not request:
        return
    session_key = request.session.session_key or ''
    def close_sessions():
        qs = UserSession.objects.filter(
            user=user,
            session_key=session_key,
            is_active=True
        )
        for session in qs:
            session.end()

    _safe_usersession_operation(close_sessions)





