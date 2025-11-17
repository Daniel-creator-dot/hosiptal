from django.utils import timezone
from django.contrib.sessions.models import Session
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .models import UserSession


def _get_client_ip(request):
    """Best-effort extraction of client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@receiver(user_logged_in)
def create_user_session(sender, request, user, **kwargs):
    """
    Create a UserSession record when a user logs in.
    """
    session_key = request.session.session_key or ''
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    ip_address = _get_client_ip(request)

    # Close any previous active sessions with same session key
    UserSession.objects.filter(
        session_key=session_key,
        is_active=True
    ).update(is_active=False, logout_time=timezone.now())

    UserSession.objects.create(
        user=user,
        session_key=session_key,
        login_time=timezone.now(),
        user_agent=user_agent,
        ip_address=ip_address,
        is_active=True,
    )


@receiver(user_logged_out)
def close_user_session(sender, request, user, **kwargs):
    """
    Mark the corresponding UserSession as ended when the user logs out.
    """
    if not request:
        return
    session_key = request.session.session_key or ''
    qs = UserSession.objects.filter(
        user=user,
        session_key=session_key,
        is_active=True
    )
    for session in qs:
        session.end()




