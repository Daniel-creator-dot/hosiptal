"""
Session Management Views for Admins
Allows admins to view active sessions and force logout users
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
from django.db.models import Q
from datetime import timedelta
import logging

from .models import UserSession
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
def active_sessions_view(request):
    """
    View all active user sessions - Admin only
    Shows currently logged-in users with their session details
    Also shows blocked users for quick unblocking
    """
    # Get active UserSession records
    active_sessions = UserSession.objects.filter(
        is_active=True,
        logout_time__isnull=True
    ).select_related('user').order_by('-login_time')
    
    # Get active Django sessions
    active_django_sessions = []
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        try:
            user_id = session.get_decoded().get('_auth_user_id')
            if user_id:
                user = User.objects.get(pk=user_id)
                session_data = session.get_decoded()
                active_django_sessions.append({
                    'session_key': session.session_key,
                    'user': user,
                    'expire_date': session.expire_date,
                    'last_activity': session.expire_date - timedelta(seconds=1209600),  # Approximate (2 weeks default)
                })
        except (User.DoesNotExist, KeyError):
            continue
    
    # Combine and deduplicate
    all_active = {}
    for us in active_sessions:
        key = f"{us.user.id}_{us.session_key}"
        all_active[key] = {
            'user': us.user,
            'session_key': us.session_key,
            'login_time': us.login_time,
            'ip_address': us.ip_address,
            'user_agent': us.user_agent,
            'user_session_id': us.id,
            'source': 'UserSession',
        }
    
    for ds in active_django_sessions:
        key = f"{ds['user'].id}_{ds['session_key']}"
        if key not in all_active:
            all_active[key] = {
                'user': ds['user'],
                'session_key': ds['session_key'],
                'login_time': ds.get('last_activity', timezone.now()),
                'ip_address': None,
                'user_agent': None,
                'user_session_id': None,
                'expire_date': ds['expire_date'],
                'source': 'DjangoSession',
            }
    
    active_list = list(all_active.values())
    
    # Sort by login time
    active_list.sort(key=lambda x: x['login_time'], reverse=True)
    
    # Add user status (active/blocked) to each session
    for session in active_list:
        session['user_is_active'] = session['user'].is_active
    
    # Get all blocked users (for quick unblock access)
    blocked_users_queryset = User.objects.filter(
        is_active=False
    ).exclude(
        id=request.user.id  # Don't show current admin if they're blocked (shouldn't happen)
    ).order_by('-date_joined')[:50]  # Show most recently blocked first
    
    # Get last login info for blocked users
    blocked_users_list = []
    for user in blocked_users_queryset:
        last_session = UserSession.objects.filter(
            user=user
        ).order_by('-login_time').first()
        
        blocked_users_list.append({
            'user': user,
            'last_login': last_session.login_time if last_session else None,
            'last_ip': last_session.ip_address if last_session else None,
        })
    
    # Also check for locked login attempts (even if user is active)
    from .models_login_attempts import LoginAttempt
    locked_attempts_count = LoginAttempt.objects.filter(
        Q(is_locked=True) | 
        Q(manually_blocked=True) | 
        Q(locked_until__isnull=False)
    ).count()
    
    failed_attempts_count = LoginAttempt.objects.filter(failed_attempts__gt=0).count()
    
    context = {
        'title': 'Active Sessions & Blocked Users',
        'active_sessions': active_list,
        'total_active': len(active_list),
        'blocked_users': blocked_users_list,
        'total_blocked': len(blocked_users_list),
        'locked_attempts_count': locked_attempts_count,
        'failed_attempts_count': failed_attempts_count,
    }
    
    return render(request, 'hospital/admin/active_sessions.html', context)


@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
@csrf_exempt
def force_logout_user(request, user_id):
    """
    Force logout a specific user by deleting all their sessions
    Admin only
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
            from django.core.cache import cache
            from django.conf import settings
            from django.contrib.sessions.backends.cache import SessionStore
            
            # Get the cache alias for sessions
            session_cache_alias = getattr(settings, 'SESSION_CACHE_ALIAS', 'default')
            from django.core.cache import caches
            try:
                session_cache = caches[session_cache_alias] if session_cache_alias != 'default' else cache
            except:
                session_cache = cache
            
            if hasattr(settings, 'SESSION_ENGINE') and 'cache' in settings.SESSION_ENGINE:
                for session_key in sessions_to_delete:
                    # Try multiple cache key formats
                    cache_keys = [
                        f"session:{session_key}",
                        f"django.contrib.sessions.cache{session_key}",
                        f"django.contrib.sessions.cached_db{session_key}",
                        session_key,  # Sometimes the key is just the session_key
                    ]
                    for cache_key in cache_keys:
                        try:
                            session_cache.delete(cache_key)
                        except:
                            pass
                    
                    # Also try using SessionStore to delete
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
            f"Admin {request.user.username} force-logged-out user {target_user.username}. "
            f"Deleted {deleted_count} Django sessions, ended {ended_count} UserSession records."
        )
        
        messages.success(
            request,
            f'User {target_user.username} has been logged out. '
            f'Deleted {deleted_count} session(s).'
        )
        
        return JsonResponse({
            'success': True,
            'message': f'User {target_user.username} has been logged out successfully.',
            'deleted_sessions': deleted_count,
            'ended_sessions': ended_count,
        })
        
    except User.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'User not found.'
        }, status=404)
    except Exception as e:
        logger.error(f"Error force-logging-out user {user_id}: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Error logging out user: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
@csrf_exempt
def force_logout_session(request, session_key):
    """
    Force logout a specific session by session key
    Admin only
    """
    try:
        # Delete Django session
        session = Session.objects.filter(session_key=session_key).first()
        deleted_django = False
        if session:
            try:
                user_id = session.get_decoded().get('_auth_user_id')
                user = User.objects.get(pk=user_id) if user_id else None
            except:
                user = None
            session_key_to_delete = session.session_key
            session.delete()
            deleted_django = True
            
            # Clear session cache if using cache-based sessions
            try:
                from django.core.cache import cache, caches
                from django.conf import settings
                from django.contrib.sessions.backends.cache import SessionStore
                
                # Get the cache alias for sessions
                session_cache_alias = getattr(settings, 'SESSION_CACHE_ALIAS', 'default')
                try:
                    session_cache = caches[session_cache_alias] if session_cache_alias != 'default' else cache
                except:
                    session_cache = cache
                
                if hasattr(settings, 'SESSION_ENGINE') and 'cache' in settings.SESSION_ENGINE:
                    # Try multiple cache key formats
                    cache_keys = [
                        f"session:{session_key_to_delete}",
                        f"django.contrib.sessions.cache{session_key_to_delete}",
                        f"django.contrib.sessions.cached_db{session_key_to_delete}",
                        session_key_to_delete,
                    ]
                    for cache_key in cache_keys:
                        try:
                            session_cache.delete(cache_key)
                        except:
                            pass
                    
                    # Also try using SessionStore to delete (this handles cache clearing properly)
                    try:
                        session_store = SessionStore(session_key=session_key_to_delete)
                        session_store.delete()
                    except:
                        pass
            except Exception as e:
                logger.warning(f"Could not clear session cache: {e}")
        else:
            # Try to find user from UserSession
            user_session = UserSession.objects.filter(session_key=session_key).first()
            user = user_session.user if user_session else None
        
        # End UserSession record
        user_sessions = UserSession.objects.filter(session_key=session_key, is_active=True)
        ended_count = user_sessions.count()
        for us in user_sessions:
            us.end()
        
        username = user.username if user else 'Unknown'
        
        logger.info(
            f"Admin {request.user.username} force-logged-out session {session_key} "
            f"(user: {username}). Deleted Django session: {deleted_django}, ended {ended_count} UserSession records."
        )
        
        messages.success(
            request,
            f'Session {session_key[:8]}... has been terminated. '
            f'User: {username}'
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Session terminated successfully.',
            'username': username,
            'deleted_django_session': deleted_django,
            'ended_user_sessions': ended_count,
        })
        
    except Exception as e:
        logger.error(f"Error force-logging-out session {session_key}: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Error terminating session: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
@csrf_exempt
def block_user(request, user_id):
    """
    Block a user account - prevents login
    Admin only
    """
    try:
        target_user = get_object_or_404(User, pk=user_id)
        
        # Don't allow admins to block themselves
        if target_user == request.user:
            return JsonResponse({
                'success': False,
                'error': 'You cannot block yourself.'
            }, status=400)
        
        # Don't allow blocking superusers
        if target_user.is_superuser and not request.user.is_superuser:
            return JsonResponse({
                'success': False,
                'error': 'You cannot block a superuser account.'
            }, status=403)
        
        # Block the user
        target_user.is_active = False
        target_user.save()
        
        # Force logout all sessions for this user
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
        
        # End all UserSession records for this user
        user_sessions = UserSession.objects.filter(
            user=target_user,
            is_active=True
        )
        ended_count = user_sessions.count()
        for us in user_sessions:
            us.end()
        
        logger.warning(
            f"Admin {request.user.username} blocked user {target_user.username}. "
            f"Deleted {deleted_count} Django sessions, ended {ended_count} UserSession records."
        )
        
        messages.warning(
            request,
            f'User {target_user.username} has been blocked and all sessions terminated.'
        )
        
        return JsonResponse({
            'success': True,
            'message': f'User {target_user.username} has been blocked successfully.',
            'is_blocked': True,
            'deleted_sessions': deleted_count,
            'ended_sessions': ended_count,
        })
        
    except User.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'User not found.'
        }, status=404)
    except Exception as e:
        logger.error(f"Error blocking user {user_id}: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Error blocking user: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
@csrf_exempt
def unlock_all_accounts(request):
    """
    Unlock all locked/blocked accounts at once
    Admin only
    """
    try:
        from .models_login_attempts import LoginAttempt
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get counts before unlocking
        inactive_count = User.objects.filter(is_active=False).count()
        locked_attempts_count = LoginAttempt.objects.filter(
            Q(is_locked=True) | 
            Q(manually_blocked=True) | 
            Q(locked_until__isnull=False)
        ).count()
        failed_attempts_count = LoginAttempt.objects.filter(failed_attempts__gt=0).count()
        
        # Activate all inactive users
        inactive_users = User.objects.filter(is_active=False)
        activated_count = inactive_users.update(is_active=True)
        
        # Unlock all login attempts
        locked_attempts = LoginAttempt.objects.filter(
            Q(is_locked=True) | 
            Q(manually_blocked=True) | 
            Q(locked_until__isnull=False)
        )
        unlocked_count = 0
        for attempt in locked_attempts:
            attempt.unblock(unblocked_by=request.user, note='Bulk unlock from active sessions page')
            unlocked_count += 1
        
        # Reset failed attempts
        failed_attempts = LoginAttempt.objects.filter(failed_attempts__gt=0)
        reset_count = failed_attempts.update(failed_attempts=0)
        
        total_actions = activated_count + unlocked_count + reset_count
        
        logger.info(
            f"Admin {request.user.username} unlocked all accounts. "
            f"Activated {activated_count} users, unlocked {unlocked_count} login attempts, reset {reset_count} failed counters."
        )
        
        # Build detailed message
        message_parts = []
        if activated_count > 0:
            message_parts.append(f"activated {activated_count} user{'s' if activated_count != 1 else ''}")
        if unlocked_count > 0:
            message_parts.append(f"unlocked {unlocked_count} login attempt{'s' if unlocked_count != 1 else ''}")
        if reset_count > 0:
            message_parts.append(f"reset {reset_count} failed counter{'s' if reset_count != 1 else ''}")
        
        if message_parts:
            message = f"✅ All accounts unlocked! " + ", ".join(message_parts) + "."
        else:
            message = "✅ No locked accounts found. All accounts are already active!"
        
        return JsonResponse({
            'success': True,
            'message': message,
            'activated_users': activated_count,
            'unlocked_attempts': unlocked_count,
            'reset_counters': reset_count,
            'total_actions': total_actions,
        })
        
    except Exception as e:
        logger.error(f"Error unlocking all accounts: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Error unlocking all accounts: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
@csrf_exempt
def unblock_user(request, user_id):
    """
    Unblock a user account - allows login again
    Admin only
    """
    try:
        target_user = get_object_or_404(User, pk=user_id)
        
        # Unblock the user
        target_user.is_active = True
        target_user.save()
        
        logger.info(
            f"Admin {request.user.username} unblocked user {target_user.username}."
        )
        
        messages.success(
            request,
            f'✅ User {target_user.username} has been unblocked and can now login.'
        )
        
        return JsonResponse({
            'success': True,
            'message': f'✅ {target_user.username} has been unblocked successfully. They can now login immediately.',
            'is_blocked': False,
            'username': target_user.username,
        })
        
    except User.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'User not found.'
        }, status=404)
    except Exception as e:
        logger.error(f"Error unblocking user {user_id}: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Error unblocking user: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
@csrf_exempt
def force_logout_all(request):
    """
    Force logout all users except the current admin
    Admin only - Use with caution!
    """
    try:
        current_user_id = request.user.id
        
        # Delete all Django sessions except current admin's
        deleted_count = 0
        sessions_to_delete = []
        # More efficient: filter active sessions first
        all_sessions = Session.objects.filter(expire_date__gte=timezone.now())
        for session in all_sessions:
            try:
                user_id = session.get_decoded().get('_auth_user_id')
                if user_id and str(user_id) != str(current_user_id):
                    sessions_to_delete.append(session.session_key)
                    # Delete immediately
                    session.delete()
                    deleted_count += 1
            except Exception:
                continue
        
        # Clear session cache if using cache-based sessions
        try:
            from django.core.cache import cache
            from django.conf import settings
            from django.contrib.sessions.backends.cache import SessionStore
            
            # Get the cache alias for sessions
            session_cache_alias = getattr(settings, 'SESSION_CACHE_ALIAS', 'default')
            from django.core.cache import caches
            try:
                session_cache = caches[session_cache_alias] if session_cache_alias != 'default' else cache
            except:
                session_cache = cache
            
            if hasattr(settings, 'SESSION_ENGINE') and 'cache' in settings.SESSION_ENGINE:
                for session_key in sessions_to_delete:
                    # Try multiple cache key formats
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
                    
                    # Also try using SessionStore to delete
                    try:
                        session_store = SessionStore(session_key=session_key)
                        session_store.delete()
                    except:
                        pass
        except Exception as e:
            logger.warning(f"Could not clear session cache: {e}")
        
        # End all UserSession records except current admin's
        user_sessions = UserSession.objects.filter(
            is_active=True
        ).exclude(user=request.user)
        ended_count = user_sessions.count()
        for us in user_sessions:
            us.end()
        
        logger.warning(
            f"Admin {request.user.username} force-logged-out ALL users. "
            f"Deleted {deleted_count} Django sessions, ended {ended_count} UserSession records."
        )
        
        messages.warning(
            request,
            f'All users have been logged out (except you). '
            f'Deleted {deleted_count} session(s).'
        )
        
        return JsonResponse({
            'success': True,
            'message': f'All users logged out successfully (except current admin).',
            'deleted_sessions': deleted_count,
            'ended_sessions': ended_count,
        })
        
    except Exception as e:
        logger.error(f"Error force-logging-out all users: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Error logging out users: {str(e)}'
        }, status=500)

