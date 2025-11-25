"""
Login Tracking Signals
Automatically track all login attempts
"""
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.contrib.sessions.models import Session
import logging

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def track_successful_login(sender, request, user, **kwargs):
    """
    Track successful login with location and device info
    """
    try:
        from .services.login_location_service import login_location_service
        
        # Record login with full details
        login_record = login_location_service.record_login(
            user=user,
            request=request,
            success=True
        )
        
        # Store login record ID in session for logout tracking
        request.session['login_record_id'] = str(login_record.pk)
        
        logger.info(f"Successful login tracked for {user.username} from {login_record.ip_address}")
        
    except Exception as e:
        logger.error(f"Error tracking login for {user.username}: {str(e)}")


@receiver(user_login_failed)
def track_failed_login(sender, credentials, request, **kwargs):
    """
    Track failed login attempts
    """
    try:
        from django.contrib.auth.models import User
        from .services.login_location_service import login_location_service
        
        # Try to find user
        username = credentials.get('username', '')
        user = None
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                # Create a dummy user for tracking purposes
                pass
        
        if user:
            login_location_service.record_login(
                user=user,
                request=request,
                success=False,
                failure_reason='Invalid credentials'
            )
            
            logger.warning(f"Failed login attempt for {username}")
    
    except Exception as e:
        logger.error(f"Error tracking failed login: {str(e)}")


@receiver(user_logged_out)
def track_logout(sender, request, user, **kwargs):
    """
    Track logout and update session duration
    """
    try:
        from .services.login_location_service import login_location_service
        
        session_key = request.session.session_key
        if session_key and user:
            login_location_service.record_logout(user, session_key)
            logger.info(f"Logout tracked for {user.username}")
    
    except Exception as e:
        logger.error(f"Error tracking logout: {str(e)}")





















