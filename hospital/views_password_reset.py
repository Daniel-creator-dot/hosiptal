import json
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models_login_attempts import PasswordResetOTP
from .models import Staff
from .services.sms_service import SMSService

logger = logging.getLogger(__name__)

# Sensible, overrideable defaults
PASSWORD_RESET_REQUEST_LIMIT = getattr(settings, 'PASSWORD_RESET_REQUEST_LIMIT', 5)  # requests per window
PASSWORD_RESET_REQUEST_WINDOW_SECONDS = getattr(settings, 'PASSWORD_RESET_REQUEST_WINDOW_SECONDS', 15 * 60)
PASSWORD_RESET_CONFIRM_LIMIT = getattr(settings, 'PASSWORD_RESET_CONFIRM_LIMIT', 5)  # attempts per code
PASSWORD_RESET_CODE_EXPIRY_MINUTES = getattr(settings, 'PASSWORD_RESET_CODE_EXPIRY_MINUTES', 10)
PASSWORD_RESET_MIN_LENGTH = getattr(settings, 'PASSWORD_RESET_MIN_LENGTH', 10)


def _parse_body(request):
    if request.content_type == 'application/json':
        try:
            return json.loads(request.body.decode('utf-8'))
        except Exception:
            return {}
    return request.POST


def _mask_phone(phone):
    if not phone or len(phone) < 4:
        return phone or ''
    return f"{phone[:-4].ljust(len(phone)-4, '*')}{phone[-4:]}"


def _find_user(identifier):
    """
    Find a user by username, email, or staff phone.
    """
    User = get_user_model()
    try:
        return User.objects.get(username=identifier)
    except User.DoesNotExist:
        try:
            return User.objects.get(email__iexact=identifier)
        except User.DoesNotExist:
            staff = Staff.objects.filter(phone_number__icontains=identifier, is_deleted=False).select_related('user').first()
            return staff.user if staff else None


def _rate_limited(scope_key, limit, window_seconds):
    """
    Lightweight rate limiter backed by the configured cache.

    Returns (is_limited: bool, retry_after_seconds: int|None).
    """
    cache_key = f"pwdreset:{scope_key}"
    try:
        # First call sets the counter to 1 and returns not limited
        if cache.add(cache_key, 1, window_seconds):
            return False, None

        current = cache.incr(cache_key)
        if current > limit:
            retry_after = window_seconds
            ttl_fn = getattr(cache, 'ttl', None)
            if callable(ttl_fn):
                try:
                    ttl_val = ttl_fn(cache_key)
                    if isinstance(ttl_val, int) and ttl_val > 0:
                        retry_after = ttl_val
                except Exception:
                    # ttl not supported by backend; fall back to window
                    pass
            return True, retry_after
    except Exception as exc:
        # Fail open but log for visibility
        logger.warning("Password reset rate-limit check failed: %s", exc)
        return False, None

    return False, None


@csrf_exempt
@require_POST
def request_password_reset_sms(request):
    """
    Issue an SMS OTP for password reset.
    """
    data = _parse_body(request)
    identifier = data.get('username') or data.get('phone')
    if not identifier:
        return JsonResponse({'ok': False, 'error': 'username or phone is required'}, status=400)

    user = _find_user(identifier)
    if not user:
        return JsonResponse({'ok': False, 'error': 'User not found'}, status=404)

    # Enforce per-user and per-IP throttling to prevent abuse
    ip_address = request.META.get('REMOTE_ADDR', 'unknown')
    limited_user, retry_after_user = _rate_limited(
        scope_key=f"request:user:{user.id}",
        limit=PASSWORD_RESET_REQUEST_LIMIT,
        window_seconds=PASSWORD_RESET_REQUEST_WINDOW_SECONDS,
    )
    if limited_user:
        return JsonResponse({
            'ok': False,
            'error': 'Too many password reset requests. Please try again later.',
            'retry_after_seconds': retry_after_user,
        }, status=429)

    limited_ip, retry_after_ip = _rate_limited(
        scope_key=f"request:ip:{ip_address}",
        limit=PASSWORD_RESET_REQUEST_LIMIT * 2,  # allow more per shared IPs
        window_seconds=PASSWORD_RESET_REQUEST_WINDOW_SECONDS,
    )
    if limited_ip:
        return JsonResponse({
            'ok': False,
            'error': 'Too many password reset requests from this network. Please try again later.',
            'retry_after_seconds': retry_after_ip,
        }, status=429)

    staff = getattr(user, 'staff', None)
    phone = getattr(staff, 'phone_number', '') if staff else ''
    if not phone:
        return JsonResponse({'ok': False, 'error': 'No phone number on file for this user'}, status=400)

    # Invalidate any previous active codes to avoid parallel OTPs
    PasswordResetOTP.objects.filter(user=user, is_used=False, is_deleted=False).update(is_deleted=True)

    code = PasswordResetOTP.generate_code()
    expires_at = timezone.now() + timedelta(minutes=PASSWORD_RESET_CODE_EXPIRY_MINUTES)
    PasswordResetOTP.objects.create(
        user=user,
        code=PasswordResetOTP.hash_code(code),
        expires_at=expires_at,
        phone_snapshot=phone,
        sent_via='sms',
    )

    message = f"Your password reset code is {code}. It expires in {PASSWORD_RESET_CODE_EXPIRY_MINUTES} minutes."
    sms_service = SMSService()
    sms_service.send_sms(phone, message, message_type='password_reset', recipient_name=user.get_full_name() or user.username)

    return JsonResponse({'ok': True, 'message': 'OTP sent via SMS', 'phone_masked': _mask_phone(phone)})


@csrf_exempt
@require_POST
def confirm_password_reset_sms(request):
    """
    Verify SMS OTP and set a new password.
    """
    data = _parse_body(request)
    username = data.get('username')
    code = data.get('code')
    new_password = data.get('new_password')

    if not all([username, code, new_password]):
        return JsonResponse({'ok': False, 'error': 'username, code, and new_password are required'}, status=400)

    if len(new_password) < PASSWORD_RESET_MIN_LENGTH:
        return JsonResponse({'ok': False, 'error': f'Password must be at least {PASSWORD_RESET_MIN_LENGTH} characters long'}, status=400)

    user = _find_user(username)
    if not user:
        return JsonResponse({'ok': False, 'error': 'User not found'}, status=404)

    # Per-user rate limiting for confirmations to slow brute-force OTP guessing
    limited, retry_after = _rate_limited(
        scope_key=f"confirm:{user.id}",
        limit=PASSWORD_RESET_CONFIRM_LIMIT,
        window_seconds=PASSWORD_RESET_REQUEST_WINDOW_SECONDS,
    )
    if limited:
        return JsonResponse({
            'ok': False,
            'error': 'Too many verification attempts. Please try again later.',
            'retry_after_seconds': retry_after,
        }, status=429)

    otp = PasswordResetOTP.objects.filter(user=user, is_deleted=False, is_used=False).order_by('-created').first()
    if not otp:
        return JsonResponse({'ok': False, 'error': 'No active code. Please request a new one.'}, status=400)

    if timezone.now() > otp.expires_at:
        otp.is_deleted = True
        otp.save(update_fields=['is_deleted', 'modified'])
        return JsonResponse({'ok': False, 'error': 'Code expired. Please request a new one.'}, status=400)

    otp.attempts += 1
    otp.save(update_fields=['attempts', 'modified'])

    if otp.attempts > PASSWORD_RESET_CONFIRM_LIMIT:
        otp.is_deleted = True
        otp.save(update_fields=['is_deleted', 'modified'])
        return JsonResponse({'ok': False, 'error': 'Too many attempts. Please request a new code.'}, status=429)

    if not otp.is_valid(code):
        return JsonResponse({'ok': False, 'error': 'Invalid code'}, status=400)

    # Enforce password validators to meet enterprise baseline
    try:
        validate_password(new_password, user=user)
    except ValidationError as exc:
        return JsonResponse({'ok': False, 'error': ' '.join(exc.messages)}, status=400)

    if user.check_password(new_password):
        return JsonResponse({'ok': False, 'error': 'New password cannot match the previous password'}, status=400)

    user.set_password(new_password)
    user.is_active = True
    user.save()

    otp.mark_used()
    PasswordResetOTP.objects.filter(user=user, is_used=False, is_deleted=False).update(is_deleted=True)

    # Proactively revoke existing sessions for the user after password change
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
        logger.info("Password reset for user %s revoked %s active sessions", user.username, revoked)
    except Exception as exc:
        # Do not fail the reset on session cleanup errors
        logger.warning("Failed to revoke sessions after password reset for %s: %s", user.username, exc)

    return JsonResponse({'ok': True, 'message': 'Password updated successfully'})
















