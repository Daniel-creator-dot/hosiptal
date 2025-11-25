"""
Session Timeout Middleware
Automatically logs out users after 2 hours of inactivity
"""
from django.utils import timezone
from django.contrib.auth import logout
from django.contrib.sessions.models import Session
from django.shortcuts import redirect
from datetime import timedelta, datetime
import logging

logger = logging.getLogger(__name__)

IDLE_TIMEOUT_MINUTES = 120  # 2 hours


class SessionTimeoutMiddleware:
    """
    Middleware to automatically log out users after 2 hours of inactivity
    Tracks last activity time and logs out idle users
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only check authenticated users
        if request.user.is_authenticated:
            # Get or create last activity timestamp
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
                    # If parsing fails, treat as new session
                    logger.warning(f"Error parsing last_activity: {e}, treating as new session")
                    last_activity_time = None
                    idle_duration = timedelta(0)
                
                if idle_duration > timedelta(minutes=IDLE_TIMEOUT_MINUTES):
                    # User has been idle for more than 2 hours, log them out
                    logger.info(
                        f"Auto-logging out user {request.user.username} due to "
                        f"{int(idle_duration.total_seconds() / 60)} minutes of inactivity"
                    )
                    
                    # End UserSession records
                    try:
                        from .models import UserSession
                        user_sessions = UserSession.objects.filter(
                            user=request.user,
                            is_active=True,
                            session_key=request.session.session_key
                        )
                        for us in user_sessions:
                            us.end()
                    except Exception as e:
                        logger.error(f"Error ending UserSession: {e}")
                    
                    # Delete Django session
                    try:
                        session = Session.objects.get(session_key=request.session.session_key)
                        session.delete()
                    except Session.DoesNotExist:
                        pass
                    except Exception as e:
                        logger.error(f"Error deleting session: {e}")
                    
                    # Logout user
                    logout(request)
                    
                    # Set message for next request
                    from django.contrib import messages
                    messages.warning(
                        request,
                        'You have been automatically logged out due to 2 hours of inactivity. '
                        'Please log in again to continue.'
                    )
                    
                    # Redirect to login page
                    return redirect('/hms/login/?timeout=1')
                else:
                    # User is still active, update last activity
                    request.session[last_activity_key] = timezone.now().isoformat()
            else:
                # First activity, set timestamp
                request.session[last_activity_key] = timezone.now().isoformat()
        
        response = self.get_response(request)
        return response

