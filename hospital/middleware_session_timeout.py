"""
Session Timeout Middleware
Automatically logs out users after 2 hours of inactivity
Throttles session writes to avoid saving on every request (reduces Redis/DB load under many users).
"""
from django.utils import timezone
from django.contrib.auth import logout
from django.contrib.sessions.models import Session
from django.shortcuts import redirect
from django.core.cache import cache
from datetime import timedelta, datetime
import logging

logger = logging.getLogger(__name__)

IDLE_TIMEOUT_MINUTES = 120  # 2 hours
# Only update session last_activity at most every 2 minutes (reduces session writes when many users active)
SESSION_ACTIVITY_UPDATE_INTERVAL_SECONDS = 120


class SessionTimeoutMiddleware:
    """
    Middleware to automatically log out users after 2 hours of inactivity.
    Tracks last activity time and logs out idle users.
    Throttles session writes so we don't save session on every request (better performance under load).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only check authenticated users
        if request.user.is_authenticated:
            last_activity_key = f'last_activity_{request.user.id}'
            last_activity = request.session.get(last_activity_key)

            if last_activity:
                # Check if idle timeout exceeded
                try:
                    if isinstance(last_activity, str):
                        last_activity_time = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
                        if timezone.is_naive(last_activity_time):
                            last_activity_time = timezone.make_aware(last_activity_time)
                    else:
                        last_activity_time = last_activity
                    idle_duration = timezone.now() - last_activity_time
                except (ValueError, AttributeError, TypeError) as e:
                    logger.warning(f"Error parsing last_activity: {e}, treating as new session")
                    last_activity_time = None
                    idle_duration = timedelta(0)

                if idle_duration > timedelta(minutes=IDLE_TIMEOUT_MINUTES):
                    # User has been idle for more than 2 hours, log them out
                    logger.info(
                        f"Auto-logging out user {request.user.username} due to "
                        f"{int(idle_duration.total_seconds() / 60)} minutes of inactivity"
                    )

                    try:
                        from .models import UserSession
                        user_sessions = UserSession.objects.filter(
                            user=request.user,
                            is_active=True,
                            logout_time__isnull=True
                        )
                        closed_count = 0
                        for us in user_sessions:
                            us.end()
                            closed_count += 1
                        if closed_count > 0:
                            logger.info(f"Closed {closed_count} active session(s) for user {request.user.username} due to timeout")
                    except Exception as e:
                        logger.error(f"Error ending UserSession: {e}")

                    try:
                        session = Session.objects.get(session_key=request.session.session_key)
                        session.delete()
                    except Session.DoesNotExist:
                        pass
                    except Exception as e:
                        logger.error(f"Error deleting session: {e}")

                    logout(request)

                    from django.contrib import messages
                    messages.warning(
                        request,
                        'You have been automatically logged out due to 2 hours of inactivity. '
                        'Please log in again to continue.'
                    )

                    return redirect('/hms/login/?timeout=1')
                else:
                    # Throttle session writes: only update last_activity in session every SESSION_ACTIVITY_UPDATE_INTERVAL_SECONDS
                    throttle_key = f'hms:session_activity_write_{request.user.id}'
                    last_write = cache.get(throttle_key)
                    now = timezone.now()
                    if last_write is None or (now - last_write).total_seconds() >= SESSION_ACTIVITY_UPDATE_INTERVAL_SECONDS:
                        request.session[last_activity_key] = now.isoformat()
                        request.session.modified = True
                        cache.set(throttle_key, now, SESSION_ACTIVITY_UPDATE_INTERVAL_SECONDS + 60)
            else:
                # First activity, set timestamp
                request.session[last_activity_key] = timezone.now().isoformat()
                request.session.modified = True

        response = self.get_response(request)
        return response

