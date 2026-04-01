"""
Comprehensive User Management Views for Admins
Allows admins to manage all users, end sessions, and unlock accounts
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.sessions.models import Session
from django.contrib.auth.models import User
from django.db.models import Q, Count
from django.core.paginator import Paginator
import logging

from .models import UserSession
from .models_login_attempts import LoginAttempt
from .utils_roles import get_user_role

logger = logging.getLogger(__name__)


def is_admin(user):
    """Strict admin/IT check (no is_staff fallback)."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return get_user_role(user) in {'admin', 'it'}


@login_required
@user_passes_test(is_admin)
def user_management_view(request):
    """
    Comprehensive user management page - shows ALL users
    Admin can end sessions and unlock accounts for any user
    """
    # Get all users
    users_queryset = User.objects.all().annotate(
        active_sessions_count=Count('sessions', filter=Q(sessions__is_active=True, sessions__logout_time__isnull=True))
    ).order_by('-date_joined')
    
    # Filter by search query
    search_query = request.GET.get('search', '')
    if search_query:
        users_queryset = users_queryset.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        users_queryset = users_queryset.filter(is_active=True)
    elif status_filter == 'blocked':
        users_queryset = users_queryset.filter(is_active=False)
    elif status_filter == 'has_sessions':
        users_queryset = users_queryset.filter(active_sessions_count__gt=0)
    
    # Pagination
    paginator = Paginator(users_queryset, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get additional info for each user
    users_list = []
    for user in page_obj:
        user_role = get_user_role(user) or 'User'
        # Get active sessions
        active_sessions = UserSession.objects.filter(
            user=user,
            is_active=True,
            logout_time__isnull=True
        ).order_by('-login_time')
        
        # Get Django sessions
        django_sessions = []
        for session in Session.objects.filter(expire_date__gte=timezone.now()):
            try:
                user_id = session.get_decoded().get('_auth_user_id')
                if user_id and str(user_id) == str(user.id):
                    django_sessions.append(session.session_key)
            except:
                continue
        
        # Get login attempt record (for lock status)
        login_attempt = LoginAttempt.objects.filter(
            username=user.username,
            is_deleted=False
        ).order_by('-last_attempt_at', '-created').first()
        
        is_locked = False
        lock_reason = ''
        if login_attempt:
            if login_attempt.manual_block_active():
                is_locked = True
                lock_reason = login_attempt.block_reason or 'Manually blocked by administrator'
            elif login_attempt.is_currently_locked():
                is_locked = True
                lock_reason = f'Locked due to {login_attempt.failed_attempts} failed login attempts'
        
        # Get last login
        last_session = UserSession.objects.filter(user=user).order_by('-login_time').first()
        last_login = last_session.login_time if last_session else None
        last_ip = last_session.ip_address if last_session else None
        
        users_list.append({
            'user': user,
            'active_sessions': active_sessions,
            'django_sessions': django_sessions,
            'total_sessions': len(active_sessions) + len(django_sessions),
            'is_locked': is_locked,
            'lock_reason': lock_reason,
            'login_attempt': login_attempt,
            'last_login': last_login,
            'last_ip': last_ip,
            'role': user_role,
        })
    
    # Statistics
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    blocked_users = User.objects.filter(is_active=False).count()
    users_with_sessions = User.objects.annotate(
        active_sessions_count=Count('sessions', filter=Q(sessions__is_active=True, sessions__logout_time__isnull=True))
    ).filter(active_sessions_count__gt=0).count()
    
    context = {
        'title': 'User Management',
        'users': users_list,
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'total_users': total_users,
        'active_users': active_users,
        'blocked_users': blocked_users,
        'users_with_sessions': users_with_sessions,
    }
    
    return render(request, 'hospital/admin/user_management.html', context)


@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
@csrf_exempt
def end_user_session(request, user_id):
    """
    End all sessions for a specific user
    Works even if user has no active sessions (cleans up any stale sessions)
    """
    try:
        target_user = get_object_or_404(User, pk=user_id)
        
        # Don't allow admins to logout themselves
        if target_user == request.user:
            return JsonResponse({
                'success': False,
                'error': 'You cannot logout yourself. Please use the logout button.'
            }, status=400)
        
        # Delete all Django sessions for this user
        deleted_count = 0
        sessions_to_delete = []
        for session in Session.objects.all():
            try:
                user_id_in_session = session.get_decoded().get('_auth_user_id')
                if user_id_in_session and str(user_id_in_session) == str(user_id):
                    sessions_to_delete.append(session.session_key)
                    session.delete()
                    deleted_count += 1
            except Exception:
                continue
        
        # Clear session cache if using cache-based sessions
        try:
            from django.core.cache import cache, caches
            from django.conf import settings
            from django.contrib.sessions.backends.cache import SessionStore
            
            session_cache_alias = getattr(settings, 'SESSION_CACHE_ALIAS', 'default')
            try:
                session_cache = caches[session_cache_alias] if session_cache_alias != 'default' else cache
            except:
                session_cache = cache
            
            if hasattr(settings, 'SESSION_ENGINE') and 'cache' in settings.SESSION_ENGINE:
                for session_key in sessions_to_delete:
                    cache_keys = [
                        f"session:{session_key}",
                        f"django.contrib.sessions.cache{session_key}",
                        f"django.contrib.sessions.cached_db{session_key}",
                        session_key,
                    ]
                    for cache_key in cache_keys:
                        try:
                            session_cache.delete(cache_key)
                        except:
                            pass
                    
                    try:
                        session_store = SessionStore(session_key=session_key)
                        session_store.delete()
                    except:
                        pass
        except Exception as e:
            logger.warning(f"Could not clear session cache: {e}")
        
        # End all UserSession records for this user
        user_sessions = UserSession.objects.filter(
            user=target_user,
            is_active=True
        )
        ended_count = user_sessions.count()
        for us in user_sessions:
            us.end()
        
        logger.info(
            f"Admin {request.user.username} ended all sessions for user {target_user.username}. "
            f"Deleted {deleted_count} Django sessions, ended {ended_count} UserSession records."
        )
        
        messages.success(
            request,
            f'All sessions for {target_user.username} have been ended. '
            f'Deleted {deleted_count} session(s).'
        )
        
        return JsonResponse({
            'success': True,
            'message': f'All sessions for {target_user.username} have been ended successfully.',
            'deleted_sessions': deleted_count,
            'ended_sessions': ended_count,
        })
        
    except User.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'User not found.'
        }, status=404)
    except Exception as e:
        logger.error(f"Error ending sessions for user {user_id}: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Error ending sessions: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
@csrf_exempt
def unlock_user_account(request, user_id):
    """
    Unlock a user account - handles both User.is_active and LoginAttempt locks
    """
    try:
        target_user = get_object_or_404(User, pk=user_id)
        
        # Unblock the user account
        was_blocked = not target_user.is_active
        target_user.is_active = True
        target_user.save()
        
        # Unblock LoginAttempt records
        login_attempts = LoginAttempt.objects.filter(
            username=target_user.username,
            is_deleted=False
        )
        
        unlocked_attempts = 0
        for attempt in login_attempts:
            if attempt.manual_block_active() or attempt.is_currently_locked():
                attempt.unblock(unblocked_by=request.user, note=f'Unlocked by admin {request.user.username}')
                unlocked_attempts += 1
        
        logger.info(
            f"Admin {request.user.username} unlocked user {target_user.username}. "
            f"Account was blocked: {was_blocked}, Unlocked {unlocked_attempts} login attempt(s)."
        )
        
        messages.success(
            request,
            f'✅ User {target_user.username} has been unlocked and can now login. '
            f'Unlocked {unlocked_attempts} login attempt record(s).'
        )
        
        return JsonResponse({
            'success': True,
            'message': f'✅ {target_user.username} has been unlocked successfully. They can now login immediately.',
            'is_blocked': False,
            'username': target_user.username,
            'unlocked_attempts': unlocked_attempts,
        })
        
    except User.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'User not found.'
        }, status=404)
    except Exception as e:
        logger.error(f"Error unlocking user {user_id}: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Error unlocking user: {str(e)}'
        }, status=500)


