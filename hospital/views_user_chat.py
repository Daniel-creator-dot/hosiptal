"""
User-to-User Direct Chat System
WhatsApp-like private messaging with online status
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count, Max, Exists, OuterRef
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
import json

from .models_chat import ChatChannel, ChatMessage, ChatNotification
from .models import UserSession, Staff, Department

User = get_user_model()


def get_online_users():
    """Get list of currently online users (active sessions in last 30 minutes or active Django sessions)"""
    from django.contrib.sessions.models import Session
    from django.contrib.auth.models import AnonymousUser
    
    thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
    
    # Method 1: Get users with active UserSession records (recent logins)
    user_session_user_ids = UserSession.objects.filter(
        is_active=True,
        login_time__gte=thirty_minutes_ago,  # Extended to 30 minutes
        logout_time__isnull=True
    ).values_list('user_id', flat=True).distinct()
    
    # Method 2: Get users with active Django sessions (currently logged in)
    django_session_user_ids = set()
    try:
        # Get all active Django sessions
        active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
        
        for session in active_sessions:
            try:
                session_data = session.get_decoded()
                user_id = session_data.get('_auth_user_id')
                if user_id:
                    django_session_user_ids.add(int(user_id))
            except Exception:
                continue
    except Exception:
        pass
    
    # Combine both methods - user is online if they have either
    all_online_user_ids = set(user_session_user_ids) | django_session_user_ids
    
    # Get user objects with staff info
    online_users = User.objects.filter(
        id__in=all_online_user_ids,
        is_active=True
    ).select_related('staff').prefetch_related('staff__department')
    
    return online_users


@login_required
def user_chat_dashboard(request):
    """
    Main user chat dashboard - shows online users and conversations
    WhatsApp-like interface
    """
    current_user = request.user
    
    # Get online users (excluding current user)
    online_users = get_online_users().exclude(id=current_user.id)
    
    # Get all direct message channels for current user
    direct_channels = ChatChannel.objects.filter(
        channel_type='direct',
        is_deleted=False,
        members=current_user
    ).annotate(
        last_message_time=Max('messages__created')
    ).order_by('-last_message_time', '-created')
    
    # Get unread counts for each channel
    channels_with_unread = []
    for channel in direct_channels:
        unread_count = ChatMessage.objects.filter(
            channel=channel,
            is_deleted=False
        ).exclude(sender=current_user).exclude(read_by=current_user).count()
        
        # Get other participant
        other_participant = channel.get_other_participant(current_user)
        
        # Get last message
        last_message = channel.messages.filter(is_deleted=False).order_by('-created').first()
        
        channels_with_unread.append({
            'channel': channel,
            'other_participant': other_participant,
            'unread_count': unread_count,
            'last_message': last_message,
            'last_message_time': channel.last_message_time,
        })
    
    # Get online users with their staff info
    online_users_list = []
    for user in online_users:
        try:
            staff = user.staff
            display_name = user.get_full_name() or user.username
            department = staff.department.name if staff and staff.department else "Staff"
            profession = staff.get_profession_display() if staff else "User"
        except:
            display_name = user.get_full_name() or user.username
            department = "User"
            profession = "User"
        
        online_users_list.append({
            'user': user,
            'display_name': display_name,
            'department': department,
            'profession': profession,
        })
    
    # Get unread notifications count
    unread_notifications = ChatNotification.objects.filter(
        user=current_user,
        is_read=False
    ).count()
    
    # Get all departments with active staff
    departments = Department.objects.filter(
        is_active=True,
        is_deleted=False
    ).prefetch_related('staff__user').order_by('name')
    
    # Get all users with staff info (excluding current user)
    all_users_by_department = {}
    for dept in departments:
        staff_members = Staff.objects.filter(
            department=dept,
            is_active=True,
            is_deleted=False,
            user__is_active=True
        ).exclude(user=current_user).select_related('user')
        
        if staff_members.exists():
            dept_users = []
            for staff in staff_members:
                try:
                    user = staff.user
                    dept_users.append({
                        'id': user.id,
                        'username': user.username,
                        'full_name': user.get_full_name() or user.username,
                        'profession': staff.get_profession_display(),
                        'is_online': user.id in [u['user'].id for u in online_users_list],
                    })
                except:
                    continue
            if dept_users:
                all_users_by_department[dept.name] = dept_users
    
    # Also get users without departments
    users_without_dept = User.objects.filter(
        is_active=True
    ).exclude(id=current_user.id).exclude(
        id__in=Staff.objects.filter(is_active=True, is_deleted=False).values_list('user_id', flat=True)
    )
    
    if users_without_dept.exists():
        dept_users = []
        for user in users_without_dept:
            dept_users.append({
                'id': user.id,
                'username': user.username,
                'full_name': user.get_full_name() or user.username,
                'profession': 'User',
                'is_online': user.id in [u['user'].id for u in online_users_list],
            })
        if dept_users:
            all_users_by_department['Other Users'] = dept_users
    
    context = {
        'title': 'Chat',
        'online_users': online_users_list,
        'conversations': channels_with_unread,
        'unread_notifications': unread_notifications,
        'departments': departments,
        'users_by_department': all_users_by_department,
    }
    
    return render(request, 'hospital/user_chat/dashboard.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def direct_chat_api(request, user_id=None):
    """
    API for direct messaging
    GET: Get or create direct chat channel and retrieve messages
    POST: Send message in direct chat
    """
    current_user = request.user
    
    if request.method == 'POST':
        # Send message (supports JSON and multipart/form-data for file uploads)
        try:
            data = {}
            uploaded_file = None

            if request.content_type and 'multipart/form-data' in request.content_type:
                data = request.POST.dict()
                uploaded_file = request.FILES.get('attachment') or request.FILES.get('file')
            else:
                try:
                    if request.body:
                        data = json.loads(request.body)
                    else:
                        data = request.POST.dict()
                except json.JSONDecodeError:
                    data = request.POST.dict()

            recipient_id = data.get('recipient_id') or user_id
            content = (data.get('content') or '').strip()

            if not content and not uploaded_file:
                return JsonResponse({'error': 'Message content or a file attachment is required'}, status=400, content_type='application/json')

            if not recipient_id:
                return JsonResponse({'error': 'Recipient ID is required'}, status=400, content_type='application/json')

            # Validate file type if present (PDF and images only)
            ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tiff', 'tif'}
            if uploaded_file:
                ext = (uploaded_file.name or '').split('.')[-1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    return JsonResponse({
                        'error': 'Invalid file type. Allowed: PDF, JPEG, PNG, GIF, WEBP, BMP, TIFF'
                    }, status=400, content_type='application/json')
                if uploaded_file.size > 10 * 1024 * 1024:  # 10 MB
                    return JsonResponse({'error': 'File too large. Maximum size is 10 MB.'}, status=400, content_type='application/json')

            # Convert recipient_id to proper format (User model uses integer IDs, not UUIDs)
            try:
                recipient_id = int(recipient_id)
            except (ValueError, TypeError):
                try:
                    from uuid import UUID
                    recipient_id = str(UUID(str(recipient_id)))
                except (ValueError, TypeError):
                    return JsonResponse({'error': 'Invalid recipient ID format'}, status=400, content_type='application/json')

            try:
                recipient = User.objects.get(id=recipient_id, is_active=True)
            except User.DoesNotExist:
                return JsonResponse({'error': 'Recipient not found'}, status=404, content_type='application/json')

            channel, created = ChatChannel.get_or_create_direct_chat(current_user, recipient)
            if current_user not in channel.members.all():
                channel.members.add(current_user)
            if recipient not in channel.members.all():
                channel.members.add(recipient)

            message_type = 'file' if uploaded_file else data.get('message_type', 'text')
            if not content and uploaded_file:
                content = uploaded_file.name or 'Attachment'

            message = ChatMessage.objects.create(
                channel=channel,
                sender=current_user,
                content=content,
                message_type=message_type,
                attachment=uploaded_file or None
            )

            message.mark_as_read(current_user)
            ChatNotification.objects.get_or_create(
                user=recipient,
                message=message,
                defaults={'is_read': False}
            )

            from .models import Notification
            Notification.objects.create(
                recipient=recipient,
                notification_type='other',
                title=f'New message from {current_user.get_full_name() or current_user.username}',
                message=(content[:100] if content else f'Sent {uploaded_file.name}'),
                related_object_id=message.id,
                related_object_type='chat_message'
            )

            msg_payload = {
                'id': str(message.id),
                'content': message.content,
                'sender': {
                    'id': current_user.id,
                    'username': current_user.username,
                    'full_name': current_user.get_full_name() or current_user.username,
                },
                'created': message.created.isoformat(),
                'message_type': message.message_type,
            }
            if message.attachment:
                msg_payload['attachment_url'] = request.build_absolute_uri(message.attachment.url)
                msg_payload['attachment_name'] = message.attachment.name and message.attachment.name.split('/')[-1] or ''

            return JsonResponse({
                'success': True,
                'message': msg_payload,
                'channel_id': str(channel.id),
            }, content_type='application/json')
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error sending direct message: {e}', exc_info=True)
            return JsonResponse({'error': str(e)}, status=500, content_type='application/json')
    
    # GET: Get or create direct chat and retrieve messages
    try:
        if not user_id:
            return JsonResponse({'error': 'User ID is required'}, status=400, content_type='application/json')
        
        # Convert user_id to proper format (User model uses integer IDs, not UUIDs)
        try:
            # Try to convert to int first (Django User model uses integer IDs)
            user_id = int(user_id)
        except (ValueError, TypeError):
            # If not an integer, try UUID format (for custom user models)
            try:
                from uuid import UUID
                user_id = str(UUID(str(user_id)))
            except (ValueError, TypeError):
                return JsonResponse({'error': 'Invalid user ID format'}, status=400, content_type='application/json')
        
        # Get recipient user
        try:
            recipient = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404, content_type='application/json')
        
        # Get or create direct chat channel
        channel, created = ChatChannel.get_or_create_direct_chat(current_user, recipient)
        
        # Ensure both users are members (in case channel was created before members were added)
        if current_user not in channel.members.all():
            channel.members.add(current_user)
        if recipient not in channel.members.all():
            channel.members.add(recipient)
        
        # Check access (only participants can see)
        if current_user not in channel.members.all() and not current_user.is_superuser:
            return JsonResponse({'error': 'Access denied'}, status=403, content_type='application/json')
        
        # Get messages
        since = request.GET.get('since')
        limit = int(request.GET.get('limit', 50))
        
        messages_query = ChatMessage.objects.filter(
            channel=channel,
            is_deleted=False
        ).select_related('sender').prefetch_related('read_by').order_by('created')  # Order by created ascending for proper chronological order
        
        if since:
            try:
                # Parse the timestamp - handle both with and without timezone
                since_str = since.replace('Z', '+00:00') if 'Z' in since else since
                since_dt = timezone.datetime.fromisoformat(since_str)
                # Use gte (greater than or equal) to ensure we don't miss messages due to timing
                # Also subtract 1 second to account for any timing discrepancies
                since_dt = since_dt - timedelta(seconds=1)
                messages_query = messages_query.filter(created__gt=since_dt)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f'Error parsing since parameter: {e}, since={since}')
                # If parsing fails, just get all messages (fallback)
                pass
        
        messages = list(messages_query[:limit])
        
        # Mark messages as read
        for message in messages:
            message.mark_as_read(current_user)
            # Mark notification as read
            ChatNotification.objects.filter(
                user=current_user,
                message=message
            ).update(is_read=True, read_at=timezone.now())
        
        # Get recipient info
        try:
            recipient_staff = recipient.staff
            recipient_display = recipient.get_full_name() or recipient.username
            recipient_department = recipient_staff.department.name if recipient_staff and recipient_staff.department else "Staff"
        except:
            recipient_display = recipient.get_full_name() or recipient.username
            recipient_department = "User"
        
        messages_data = []
        # Messages are already in chronological order (created ascending)
        for msg in messages:
            item = {
                'id': str(msg.id),
                'content': msg.content,
                'sender': {
                    'id': msg.sender.id,
                    'username': msg.sender.username,
                    'full_name': msg.sender.get_full_name() or msg.sender.username,
                },
                'created': msg.created.isoformat(),
                'message_type': msg.message_type,
                'is_read': current_user in msg.read_by.all(),
            }
            if msg.attachment:
                item['attachment_url'] = request.build_absolute_uri(msg.attachment.url)
                item['attachment_name'] = msg.attachment.name and msg.attachment.name.split('/')[-1] or ''
            messages_data.append(item)
        
        return JsonResponse({
            'success': True,
            'channel': {
                'id': str(channel.id),
                'name': channel.name,
                'type': 'direct',
            },
            'recipient': {
                'id': recipient.id,
                'username': recipient.username,
                'full_name': recipient_display,
                'department': recipient_department,
            },
            'messages': messages_data,
            'unread_count': ChatNotification.objects.filter(
                user=current_user,
                is_read=False
            ).count(),
        }, content_type='application/json')
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error retrieving direct chat messages: {e}', exc_info=True)
        return JsonResponse({'error': str(e)}, status=500, content_type='application/json')


@login_required
def online_users_api(request):
    """API to get list of online users"""
    try:
        # Get all online users (excluding current user)
        online_users = get_online_users().exclude(id=request.user.id)
        
        users_data = []
        for user in online_users:
            try:
                # Try to get staff info
                try:
                    staff = user.staff
                    display_name = user.get_full_name() or user.username
                    department = staff.department.name if staff and staff.department else "Staff"
                    profession = staff.get_profession_display() if staff else "User"
                except Exception:
                    # User doesn't have staff profile - still include them
                    display_name = user.get_full_name() or user.username
                    department = "Staff"
                    profession = "User"
                
                users_data.append({
                    'id': user.id,
                    'username': user.username,
                    'full_name': display_name,
                    'department': department,
                    'profession': profession,
                })
            except Exception as e:
                # Even if there's an error getting user details, include basic info
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f'Error processing user {user.id} for online list: {e}')
                users_data.append({
                    'id': user.id,
                    'username': user.username,
                    'full_name': user.get_full_name() or user.username,
                    'department': 'Staff',
                    'profession': 'User',
                })
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f'Online users API: Found {len(users_data)} online users')
        
        return JsonResponse({
            'success': True,
            'online_users': users_data,
            'count': len(users_data),
        }, content_type='application/json')
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error getting online users: {e}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e),
            'online_users': [],
            'count': 0,
        }, content_type='application/json')


@login_required
def users_by_department_api(request):
    """API to get users grouped by department"""
    current_user = request.user
    department_id = request.GET.get('department_id')
    
    # Get all departments with active staff
    if department_id:
        departments = Department.objects.filter(
            id=department_id,
            is_active=True,
            is_deleted=False
        )
    else:
        departments = Department.objects.filter(
            is_active=True,
            is_deleted=False
        ).order_by('name')
    
    result = {}
    online_user_ids = set(get_online_users().values_list('id', flat=True))
    
    for dept in departments:
        staff_members = Staff.objects.filter(
            department=dept,
            is_active=True,
            is_deleted=False,
            user__is_active=True
        ).exclude(user=current_user).select_related('user')
        
        if staff_members.exists():
            dept_users = []
            for staff in staff_members:
                try:
                    user = staff.user
                    dept_users.append({
                        'id': user.id,
                        'username': user.username,
                        'full_name': user.get_full_name() or user.username,
                        'profession': staff.get_profession_display(),
                        'is_online': user.id in online_user_ids,
                    })
                except:
                    continue
            if dept_users:
                result[dept.name] = dept_users
    
    # Also get users without departments
    users_without_dept = User.objects.filter(
        is_active=True
    ).exclude(id=current_user.id).exclude(
        id__in=Staff.objects.filter(is_active=True, is_deleted=False).values_list('user_id', flat=True)
    )
    
    if users_without_dept.exists():
        dept_users = []
        for user in users_without_dept:
            dept_users.append({
                'id': user.id,
                'username': user.username,
                'full_name': user.get_full_name() or user.username,
                'profession': 'User',
                'is_online': user.id in online_user_ids,
            })
        if dept_users:
            result['Other Users'] = dept_users
    
    return JsonResponse({
        'success': True,
        'users_by_department': result,
    }, content_type='application/json')


@login_required
def chat_notifications_api(request):
    """
    API to get unread chat notifications and new messages
    Returns unread count and recent notifications
    """
    current_user = request.user
    
    # Get unread notifications count
    unread_count = ChatNotification.objects.filter(
        user=current_user,
        is_read=False
    ).count()
    
    # Get recent unread notifications
    recent_notifications = ChatNotification.objects.filter(
        user=current_user,
        is_read=False
    ).select_related('message__sender', 'message__channel').order_by('-created')[:10]
    
    notifications_data = []
    for notif in recent_notifications:
        if notif.message:
            notifications_data.append({
                'id': str(notif.id),
                'message_id': str(notif.message.id),
                'sender': {
                    'id': notif.message.sender.id,
                    'username': notif.message.sender.username,
                    'full_name': notif.message.sender.get_full_name() or notif.message.sender.username,
                },
                'content': notif.message.content[:100],
                'channel_id': str(notif.message.channel.id),
                'created': notif.message.created.isoformat(),
            })
    
    # Get all direct channels with unread messages
    direct_channels = ChatChannel.objects.filter(
        channel_type='direct',
        is_deleted=False,
        members=current_user
    )
    
    channels_with_unread = []
    for channel in direct_channels:
        unread_msgs = ChatMessage.objects.filter(
            channel=channel,
            is_deleted=False
        ).exclude(sender=current_user).exclude(read_by=current_user)
        
        unread_count_channel = unread_msgs.count()
        if unread_count_channel > 0:
            last_unread = unread_msgs.order_by('-created').first()
            other_participant = channel.get_other_participant(current_user)
            
            channels_with_unread.append({
                'channel_id': str(channel.id),
                'other_participant_id': other_participant.id if other_participant else None,
                'other_participant_name': other_participant.get_full_name() if other_participant else 'Unknown',
                'unread_count': unread_count_channel,
                'last_message': {
                    'content': last_unread.content[:100] if last_unread else '',
                    'created': last_unread.created.isoformat() if last_unread else None,
                },
            })
    
    return JsonResponse({
        'success': True,
        'unread_count': unread_count,
        'notifications': notifications_data,
        'channels_with_unread': channels_with_unread,
    }, content_type='application/json')


@login_required
def admin_all_conversations(request):
    """
    Admin view to see all conversations (for monitoring)
    Only accessible by admins
    """
    if not request.user.is_superuser and not (hasattr(request.user, 'staff') and 
                                               request.user.staff.profession == 'admin'):
        return JsonResponse({'error': 'Access denied. Admin only.'}, status=403)
    
    # Get all direct message channels
    direct_channels = ChatChannel.objects.filter(
        channel_type='direct',
        is_deleted=False
    ).annotate(
        last_message_time=Max('messages__created'),
        message_count=Count('messages', filter=Q(messages__is_deleted=False))
    ).order_by('-last_message_time')
    
    conversations_data = []
    for channel in direct_channels:
        participant1 = channel.participant1
        participant2 = channel.participant2
        
        last_message = channel.messages.filter(is_deleted=False).order_by('-created').first()
        
        conversations_data.append({
            'channel_id': str(channel.id),
            'participant1': {
                'id': participant1.id if participant1 else None,
                'username': participant1.username if participant1 else 'N/A',
                'full_name': participant1.get_full_name() if participant1 else 'N/A',
            },
            'participant2': {
                'id': participant2.id if participant2 else None,
                'username': participant2.username if participant2 else 'N/A',
                'full_name': participant2.get_full_name() if participant2 else 'N/A',
            },
            'last_message': {
                'content': last_message.content[:100] if last_message else None,
                'sender': last_message.sender.username if last_message else None,
                'created': last_message.created.isoformat() if last_message else None,
            },
            'message_count': channel.message_count,
            'created': channel.created.isoformat(),
        })
    
    return JsonResponse({
        'success': True,
        'conversations': conversations_data,
        'total': len(conversations_data),
    })

