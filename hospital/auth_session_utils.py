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
    Prevents duplicates by checking for existing active sessions with the same session_key.
    """
    session_key = request.session.session_key or ''
    if not session_key:
        # No session key yet, skip
        return
    
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    ip_address = _get_client_ip(request)

    def close_previous_sessions():
        """Close any existing sessions with the same session_key"""
        return UserSession.objects.filter(
            session_key=session_key,
            is_active=True
        ).update(is_active=False, logout_time=timezone.now())

    def create_session():
        """Create a new session, but check for duplicates first"""
        # Check if a session already exists for this session_key and user
        existing = UserSession.objects.filter(
            session_key=session_key,
            user=user,
            is_active=True,
            logout_time__isnull=True
        ).first()
        
        if existing:
            # Update existing session instead of creating duplicate
            existing.login_time = timezone.now()
            existing.user_agent = user_agent
            existing.ip_address = ip_address
            existing.is_active = True
            existing.save(update_fields=['login_time', 'user_agent', 'ip_address', 'is_active', 'modified'])
            return existing
        
        # Optional: Close other active sessions for this user (prevents multiple device logins showing as duplicates)
        # Uncomment the next 3 lines if you want to allow only one active session per user
        # UserSession.objects.filter(
        #     user=user, is_active=True, logout_time__isnull=True
        # ).exclude(session_key=session_key).update(is_active=False, logout_time=timezone.now())
        
        # Create new session
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
    Closes all active sessions for the user to ensure real-time updates.
    """
    if not user or not user.is_authenticated:
        return
    
    def close_sessions():
        # Close all active sessions for this user (not just matching session_key)
        # This ensures real-time updates when user logs out from any device
        active_sessions = UserSession.objects.filter(
            user=user,
            is_active=True,
            logout_time__isnull=True
        )
        
        closed_count = 0
        for session in active_sessions:
            session.end()
            closed_count += 1
        
        if closed_count > 0:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Closed {closed_count} active session(s) for user {user.username} on logout")
        
        return closed_count

    _safe_usersession_operation(close_sessions)





