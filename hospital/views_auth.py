from django.contrib.auth.views import LoginView, PasswordChangeView
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.urls import reverse, reverse_lazy
from django.shortcuts import redirect, render
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse
from django.db import transaction
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.middleware.csrf import get_token
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@login_required
def change_password(request):
    """Change password view for authenticated users"""
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            # Update the session to prevent logout after password change
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, form.user)
            messages.success(request, 'Your password has been changed successfully.')
            return redirect('hospital:dashboard')
    else:
        form = PasswordChangeForm(user=request.user)
    
    return render(request, 'hospital/account/change_password.html', {
        'form': form,
    })


@method_decorator(ensure_csrf_cookie, name='dispatch')
class HMSLoginView(LoginView):
    """
    HMS login view that redirects users to their role-specific dashboard after login.
    Uses Django's built-in authentication with CSRF protection.
    Handles 'next' parameter for redirecting to originally requested page.
    Implements 5-attempt login limit to prevent brute force attacks.
    """
    template_name = "hospital/login.html"
    redirect_authenticated_user = True
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15
    
    def get_client_ip(self):
        """Get client IP address"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip
    
    def get_user_agent(self):
        """Get user agent string"""
        return self.request.META.get('HTTP_USER_AGENT', '')[:500]  # Limit to 500 chars
    
    def get(self, request, *args, **kwargs):
        """Ensure CSRF cookie is set on GET requests"""
        # Ensure session exists (required for CSRF token generation)
        if not request.session.session_key:
            request.session.create()
        
        # Force CSRF token generation to ensure cookie is set
        # The @ensure_csrf_cookie decorator handles setting the cookie in the response
        get_token(request)
        
        return super().get(request, *args, **kwargs)
    
    def dispatch(self, request, *args, **kwargs):
        """Check for locked accounts and existing sessions before processing login"""
        if request.method == 'POST':
            # Support both username and email authentication
            username_or_email = request.POST.get('username', '').strip()
            if username_or_email:
                # Try to find user by email if it looks like an email
                username = username_or_email
                if '@' in username_or_email:
                    try:
                        from django.contrib.auth import get_user_model
                        User = get_user_model()
                        user = User.objects.filter(email=username_or_email).first()
                        if user:
                            username = user.username
                    except Exception:
                        pass  # Fall back to using as username
                try:
                    from .models_login_attempts import LoginAttempt
                    
                    # Get the most recent attempt for this username
                    attempt = LoginAttempt.objects.filter(
                        username=username,
                        is_deleted=False
                    ).order_by('-last_attempt_at', '-created').first()
                    
                    if attempt:
                        if attempt.manual_block_active():
                            messages.error(
                                request,
                                f"{attempt.manual_block_message()} Please contact an administrator to reactivate your access."
                            )
                            return self.render_to_response(self.get_context_data())
                        # Check if account is currently locked (this auto-unlocks if expired)
                        if attempt.is_currently_locked():
                            remaining_time = attempt.locked_until - timezone.now()
                            minutes = max(1, int(remaining_time.total_seconds() / 60))
                            messages.error(
                                request,
                                f"Account locked due to too many failed login attempts. "
                                f"Please try again in {minutes} minute(s)."
                            )
                            return self.render_to_response(self.get_context_data())
                    
                    # Check remaining attempts (this will return max if no attempt exists)
                    remaining = LoginAttempt.get_remaining_attempts(username, self.MAX_LOGIN_ATTEMPTS)
                    if remaining <= 0:
                        messages.error(
                            request,
                            f"Maximum login attempts ({self.MAX_LOGIN_ATTEMPTS}) exceeded. "
                            f"Account has been locked for {self.LOCKOUT_DURATION_MINUTES} minutes."
                        )
                        return self.render_to_response(self.get_context_data())
                    
                    # Check for existing active sessions for this user
                    try:
                        from django.contrib.auth.models import User
                        from django.contrib.sessions.models import Session
                        from .models import UserSession
                        
                        user = User.objects.filter(username=username).first()
                        if user:
                            # Check for active UserSession records
                            active_user_sessions = UserSession.objects.filter(
                                user=user,
                                is_active=True,
                                logout_time__isnull=True
                            ).exclude(session_key=request.session.session_key if request.session.session_key else '')
                            
                            # Check for active Django sessions - OPTIMIZED: Limit query and decode efficiently
                            active_django_sessions = []
                            # Only check sessions that might belong to this user (optimize by limiting)
                            potential_sessions = Session.objects.filter(expire_date__gte=timezone.now())[:1000]  # Limit to prevent full table scan
                            for session in potential_sessions:
                                try:
                                    user_id = session.get_decoded().get('_auth_user_id')
                                    if user_id and str(user_id) == str(user.id):
                                        if session.session_key != request.session.session_key:
                                            active_django_sessions.append(session)
                                except (KeyError, ValueError):
                                    continue
                            
                            if active_user_sessions.exists() or active_django_sessions:
                                # User has active sessions - show warning but allow login
                                session_count = active_user_sessions.count() + len(active_django_sessions)
                                messages.warning(
                                    request,
                                    f"⚠️ Warning: This account is already logged in from {session_count} other location(s). "
                                    f"Logging in here will not automatically logout those sessions. "
                                    f"Please ensure you're authorized to access this account."
                                )
                    except Exception as e:
                        logger.warning(f"Error checking existing sessions: {e}")
                
                except Exception as e:
                    logger.error(f"Error checking login attempts: {e}")
                    # Don't block login on error - fail open
        
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Handle successful login - reset failed attempts and set last activity"""
        # Call parent first to ensure authentication succeeds
        response = super().form_valid(form)
        
        # Now handle post-login operations in a separate transaction-safe block
        try:
            from .models_login_attempts import LoginAttempt
            from django.contrib.auth.models import User
            from django.contrib.sessions.models import Session
            from .models import UserSession
            
            username = form.cleaned_data.get('username')
            if username:
                # Use a savepoint to handle any errors gracefully
                try:
                    with transaction.atomic():
                        # Find all attempts for this username and reset them
                        attempts = LoginAttempt.objects.filter(
                            username=username,
                            is_deleted=False
                        )
                        for attempt in attempts:
                            attempt.reset_attempts()
                except Exception as e:
                    logger.error(f"Error resetting login attempts: {e}")
                    # Don't fail the login if this fails
                
                # Set last activity timestamp for session timeout tracking
                if self.request.user.is_authenticated:
                    try:
                        last_activity_key = f'last_activity_{self.request.user.id}'
                        self.request.session[last_activity_key] = timezone.now().isoformat()
                        
                        # Check for other active sessions after successful login
                        user = self.request.user
                        active_user_sessions = UserSession.objects.filter(
                            user=user,
                            is_active=True,
                            logout_time__isnull=True
                        ).exclude(session_key=self.request.session.session_key)
                        
                        active_django_sessions = []
                        # OPTIMIZED: Limit query to prevent full table scan
                        potential_sessions = Session.objects.filter(expire_date__gte=timezone.now())[:1000]
                        for session in potential_sessions:
                            try:
                                user_id = session.get_decoded().get('_auth_user_id')
                                if user_id and str(user_id) == str(user.id):
                                    if session.session_key != self.request.session.session_key:
                                        active_django_sessions.append(session)
                            except (KeyError, ValueError):
                                continue
                        
                        if active_user_sessions.exists() or active_django_sessions:
                            session_count = active_user_sessions.count() + len(active_django_sessions)
                            messages.warning(
                                self.request,
                                f'⚠️ Your account is currently logged in from {session_count} other location(s). '
                                f'If this is not you, please change your password immediately or contact an administrator.'
                            )
                    except Exception as e:
                        logger.error(f"Error checking active sessions: {e}")
                        # Don't fail the login if this fails
        except Exception as e:
            logger.error(f"Error in post-login operations: {e}")
            # Don't fail the login if post-login operations fail
        
        return response
    
    def form_invalid(self, form):
        """Handle invalid login attempts - increment counter"""
        username = form.data.get('username', '').strip()
        
        if username:
            try:
                from .models_login_attempts import LoginAttempt
                # Wrap in atomic transaction to prevent transaction errors
                try:
                    with transaction.atomic():
                        attempt = LoginAttempt.get_or_create_attempt(
                            username=username,
                            ip_address=self.get_client_ip(),
                            user_agent=self.get_user_agent()
                        )
                        
                        # Increment failed attempt
                        is_locked = attempt.increment_failed_attempt(
                            max_attempts=self.MAX_LOGIN_ATTEMPTS,
                            lockout_duration_minutes=self.LOCKOUT_DURATION_MINUTES
                        )
                        
                        remaining = self.MAX_LOGIN_ATTEMPTS - attempt.failed_attempts
                        
                        # Store values for use after transaction
                        is_locked_value = is_locked
                        remaining_value = remaining
                        failed_attempts = attempt.failed_attempts
                except Exception as e:
                    logger.error(f"Error tracking login attempt in transaction: {e}")
                    is_locked_value = False
                    remaining_value = self.MAX_LOGIN_ATTEMPTS
                    failed_attempts = 0
                
                # Check if this is Dr. Kwadwo Ayisi's account and send SMS after 2 failed attempts
                try:
                    self._check_and_notify_dr_kwadwo(username, failed_attempts)
                except Exception as e:
                    logger.error(f"Error sending SMS notification to Dr. Kwadwo Ayisi: {e}")
                    # Don't fail login if SMS fails
                
                # Show messages after transaction completes
                try:
                    if is_locked_value:
                        messages.error(
                            self.request,
                            f"Maximum login attempts ({self.MAX_LOGIN_ATTEMPTS}) exceeded. "
                            f"Account has been locked for {self.LOCKOUT_DURATION_MINUTES} minutes. "
                            f"Please try again later."
                        )
                    elif remaining_value > 0:
                        messages.error(
                            self.request,
                            f"Invalid username or password. {remaining_value} attempt(s) remaining."
                        )
                    else:
                        messages.error(
                            self.request,
                            "Invalid username or password. Please try again."
                        )
                except NameError:
                    messages.error(
                        self.request,
                        "Invalid username or password. Please try again."
                    )
            except Exception as e:
                logger.error(f"Error tracking login attempt: {e}")
                messages.error(
                    self.request,
                    "Invalid username or password. Please try again."
                )
        else:
            messages.error(
                self.request,
                "Invalid username or password. Please try again."
            )
        
        return super().form_invalid(form)
    
    def _check_and_notify_dr_kwadwo(self, username, failed_attempts):
        """
        Check if login attempt is for Dr. Kwadwo Ayisi and send SMS notification
        after exactly 2 failed attempts (only once)
        """
        # Only send SMS when exactly 2 failed attempts (not on 3rd, 4th, etc.)
        if failed_attempts != 2:
            return
        
        # Dr. Kwadwo Ayisi's known usernames and employee ID
        DR_KWADWO_USERNAMES = ['drayisi', 'kwadwo.ayisi', 'kwadwoayisi', 'dr.kwadwo', 'drkwadwo']
        DR_KWADWO_EMPLOYEE_ID = 'SPE-DOC-0001'
        
        # Check if username matches Dr. Kwadwo Ayisi
        is_dr_kwadwo = False
        user = None
        staff = None
        
        try:
            from django.contrib.auth.models import User
            from .models import Staff
            
            # Try to find user by username
            try:
                user = User.objects.get(username__iexact=username)
                # Check if user has staff record with employee ID SPE-DOC-0001
                try:
                    staff = Staff.objects.get(user=user, employee_id=DR_KWADWO_EMPLOYEE_ID, is_deleted=False)
                    is_dr_kwadwo = True
                except Staff.DoesNotExist:
                    # Check by username match
                    if username.lower() in [u.lower() for u in DR_KWADWO_USERNAMES]:
                        is_dr_kwadwo = True
                        # Try to get staff by employee ID
                        try:
                            staff = Staff.objects.get(employee_id=DR_KWADWO_EMPLOYEE_ID, is_deleted=False)
                            user = staff.user
                        except Staff.DoesNotExist:
                            pass
            except User.DoesNotExist:
                # Check if username matches known usernames
                if username.lower() in [u.lower() for u in DR_KWADWO_USERNAMES]:
                    is_dr_kwadwo = True
                    # Try to get staff by employee ID
                    try:
                        staff = Staff.objects.get(employee_id=DR_KWADWO_EMPLOYEE_ID, is_deleted=False)
                        user = staff.user
                    except Staff.DoesNotExist:
                        pass
            
            # If we found Dr. Kwadwo Ayisi, send SMS notification
            if is_dr_kwadwo:
                # Get staff record to get phone number
                try:
                    if not staff:
                        if user:
                            staff = Staff.objects.get(user=user, is_deleted=False)
                        else:
                            staff = Staff.objects.get(employee_id=DR_KWADWO_EMPLOYEE_ID, is_deleted=False)
                    
                    phone_number = staff.phone_number
                    if phone_number and phone_number.strip():
                        # Send SMS notification
                        self._send_security_alert_sms(phone_number, username, failed_attempts, staff)
                    else:
                        logger.warning(f"Dr. Kwadwo Ayisi's phone number not found. Cannot send security alert.")
                except Staff.DoesNotExist:
                    logger.warning(f"Dr. Kwadwo Ayisi's staff record not found. Cannot send security alert.")
        except Exception as e:
            logger.error(f"Error checking Dr. Kwadwo Ayisi account: {e}")
    
    def _send_security_alert_sms(self, phone_number, username, failed_attempts, staff):
        """
        Send SMS security alert to Dr. Kwadwo Ayisi
        """
        try:
            from .services.sms_service import sms_service
            
            # Get IP address and user agent for context
            ip_address = self.get_client_ip()
            user_agent = self.get_user_agent()[:100]  # Limit length
            
            # Create message
            message = (
                f"SECURITY ALERT: Someone attempted to access your HMS account ({username}) "
                f"with incorrect password {failed_attempts} time(s). "
                f"IP: {ip_address}. "
                f"If this was not you, please change your password immediately or contact IT support."
            )
            
            # Send SMS
            sms_log = sms_service.send_sms(
                phone_number=phone_number,
                message=message,
                message_type='security_alert',
                recipient_name=f"Dr. {staff.user.get_full_name()}" if staff.user else "Dr. Kwadwo Ayisi",
                related_object_id=str(staff.user.id) if staff.user else None,
                related_object_type='User'
            )
            
            if sms_log.status == 'sent':
                logger.info(f"Security alert SMS sent to Dr. Kwadwo Ayisi at {phone_number}")
            else:
                logger.warning(f"Failed to send security alert SMS to Dr. Kwadwo Ayisi. Status: {sms_log.status}, Error: {getattr(sms_log, 'error_message', 'Unknown error')}")
        except Exception as e:
            logger.error(f"Error sending security alert SMS to Dr. Kwadwo Ayisi: {e}", exc_info=True)
    
    def get_success_url(self):
        """
        Redirect to role-specific dashboard after successful login.
        Respects 'next' parameter if present, otherwise uses role-based routing.
        Falls back to main dashboard if role detection fails.
        """
        # Check for 'next' parameter (e.g., from @login_required redirect)
        next_url = self.request.GET.get('next') or self.request.POST.get('next')
        if next_url:
            return next_url
        
        user = self.request.user
        if not user.is_authenticated:
            return reverse('hospital:login')
        
        # Try to get role-specific dashboard
        try:
            from .utils_roles import get_user_role, get_user_dashboard_url
            role = get_user_role(user)
            dashboard_url = get_user_dashboard_url(user, role)
            if dashboard_url:
                # Try to reverse the URL to ensure it exists
                try:
                    # If it's already a full URL path, use it directly
                    if dashboard_url.startswith('/'):
                        return dashboard_url
                    # Otherwise try to reverse it
                    return reverse(dashboard_url)
                except Exception as reverse_error:
                    logger.warning(f"Failed to reverse dashboard URL {dashboard_url} for user {user.username}: {reverse_error}")
                    # Fall through to default dashboard
        except Exception as e:
            # If role detection fails, fall back to main dashboard
            # Log error but don't break login flow
            logger.warning(f"Role detection failed for user {user.username}: {e}")
        
        # Default redirect to main dashboard (with error handling)
        try:
            return reverse('hospital:dashboard')
        except Exception as e:
            logger.error(f"Failed to reverse 'hospital:dashboard' URL: {e}")
            # Ultimate fallback - use direct path
            return '/hms/'
    
    def get_context_data(self, **kwargs):
        """Add remaining attempts info to context"""
        context = super().get_context_data(**kwargs)
        username = self.request.POST.get('username', '').strip() or self.request.GET.get('username', '').strip()
        
        # Add authentication method to context for template
        context['ACCOUNT_AUTHENTICATION_METHOD'] = getattr(settings, 'ACCOUNT_AUTHENTICATION_METHOD', 'username')
        
        # Always set max_attempts
        context['max_attempts'] = self.MAX_LOGIN_ATTEMPTS
        
        if username:
            try:
                from .models_login_attempts import LoginAttempt
                remaining = LoginAttempt.get_remaining_attempts(username, self.MAX_LOGIN_ATTEMPTS)
                context['remaining_attempts'] = remaining
                
                # Check if locked
                attempt = LoginAttempt.objects.filter(
                    username=username,
                    is_deleted=False
                ).order_by('-last_attempt_at', '-created').first()
                
                if attempt:
                    if attempt.is_currently_locked():
                        context['is_locked'] = True
                        context['locked_until'] = attempt.locked_until
                    else:
                        context['is_locked'] = False
                else:
                    context['is_locked'] = False
                    context['remaining_attempts'] = self.MAX_LOGIN_ATTEMPTS
            except Exception as e:
                logger.warning(f"Error getting login attempt context: {e}")
                context['remaining_attempts'] = self.MAX_LOGIN_ATTEMPTS
                context['is_locked'] = False
        else:
            context['remaining_attempts'] = self.MAX_LOGIN_ATTEMPTS
            context['is_locked'] = False
        
        return context




