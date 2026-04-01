"""
Admin Chat Channel Views
State-of-the-art chat system for IT/Admin team communication
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count, Max
from django.utils import timezone
from django.contrib.auth import get_user_model
import json

from .models_chat import ChatChannel, ChatMessage, ChatNotification
from .decorators import role_required

User = get_user_model()


@login_required
@role_required('admin', 'it', 'it_staff', redirect_to='hospital:dashboard')
def chat_dashboard(request):
    """
    Main chat dashboard for admins
    """
    # Get or create default admin channel
    default_channel, created = ChatChannel.objects.get_or_create(
        channel_type='admin',
        name='Admin Channel',
        defaults={
            'description': 'Main communication channel for administrators',
            'created_by': request.user,
            'is_active': True
        }
    )
    
    # Add current user to channel if not already a member
    if request.user not in default_channel.members.all():
        default_channel.members.add(request.user)
    
    # Get all channels user is a member of (exclude direct messages - they have their own view)
    user_channels = ChatChannel.objects.filter(
        Q(members=request.user) | Q(channel_type='admin')
    ).exclude(channel_type='direct').distinct().order_by('-created')
    
    # Calculate unread count for each channel and add as attribute
    channels_with_unread = []
    for channel in user_channels:
        unread_messages = ChatMessage.objects.filter(
            channel=channel,
            is_deleted=False
        ).exclude(sender=request.user).exclude(read_by=request.user)
        # Add unread_count as a regular attribute (not property, no underscore)
        channel.unread_count_value = unread_messages.count()
        channels_with_unread.append(channel)
    
    # Get recent messages for default channel
    recent_messages = ChatMessage.objects.filter(
        channel=default_channel,
        is_deleted=False
    ).select_related('sender').prefetch_related('read_by').order_by('-created')[:50]
    
    # Get unread notifications count
    unread_notifications = ChatNotification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    context = {
        'title': 'Admin Chat Channel',
        'channels': user_channels,
        'default_channel': default_channel,
        'recent_messages': reversed(recent_messages),
        'unread_notifications': unread_notifications,
    }
    
    return render(request, 'hospital/admin/chat_dashboard.html', context)


@login_required
@role_required('admin', 'it', 'it_staff', redirect_to='hospital:dashboard')
@require_http_methods(["GET", "POST"])
def chat_api(request, channel_id=None):
    """
    API endpoint for chat operations
    Supports both with and without channel_id in URL
    """
    """
    API endpoint for chat operations
    GET: Retrieve messages
    POST: Send new message
    """
    if request.method == 'POST':
        # Send message
        try:
            data = json.loads(request.body) if request.body else request.POST
            channel_id = data.get('channel_id') or channel_id
            content = data.get('content', '').strip()
            
            if not content:
                return JsonResponse({'error': 'Message content is required'}, status=400)
            
            if channel_id:
                try:
                    from uuid import UUID
                    channel = get_object_or_404(ChatChannel, id=UUID(str(channel_id)), is_deleted=False)
                except (ValueError, TypeError):
                    channel = get_object_or_404(ChatChannel, id=channel_id, is_deleted=False)
            else:
                # Get or create default channel
                channel, _ = ChatChannel.objects.get_or_create(
                    channel_type='admin',
                    name='Admin Channel',
                    defaults={
                        'description': 'Main communication channel for administrators',
                        'created_by': request.user,
                        'is_active': True
                    }
                )
                if request.user not in channel.members.all():
                    channel.members.add(request.user)
            
            # Check if user has access to channel
            # For direct messages, only participants can access
            if channel.channel_type == 'direct':
                if request.user not in [channel.participant1, channel.participant2] and not request.user.is_superuser:
                    return JsonResponse({'error': 'Access denied'}, status=403)
            else:
                # For other channels, check membership
                if request.user not in channel.members.all() and not request.user.is_superuser:
                    return JsonResponse({'error': 'Access denied'}, status=403)
            
            # Create message
            message = ChatMessage.objects.create(
                channel=channel,
                sender=request.user,
                content=content,
                message_type=data.get('message_type', 'text')
            )
            
            # Mark as read by sender
            message.mark_as_read(request.user)
            
            # Create notifications for all channel members except sender
            channel_members = channel.members.exclude(id=request.user.id)
            for member in channel_members:
                ChatNotification.objects.get_or_create(
                    user=member,
                    message=message,
                    defaults={'is_read': False}
                )
            
            # Also create notification in main Notification system
            from .models import Notification
            for member in channel_members:
                Notification.objects.create(
                    recipient=member,
                    notification_type='other',
                    title=f'New message in {channel.name}',
                    message=f'{request.user.get_full_name() or request.user.username}: {content[:100]}',
                    related_object_id=message.id,
                    related_object_type='chat_message'
                )
            
            return JsonResponse({
                'success': True,
                'message': {
                    'id': str(message.id),
                    'content': message.content,
                    'sender': {
                        'id': request.user.id,
                        'username': request.user.username,
                        'full_name': request.user.get_full_name() or request.user.username,
                        'email': getattr(request.user, 'email', ''),
                    },
                    'created': message.created.isoformat(),
                    'message_type': message.message_type,
                    'is_read': True,
                }
            })
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error sending chat message: {e}', exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)
    
    # GET: Retrieve messages
    try:
        if channel_id:
            try:
                from uuid import UUID
                channel = get_object_or_404(ChatChannel, id=UUID(str(channel_id)), is_deleted=False)
            except (ValueError, TypeError):
                channel = get_object_or_404(ChatChannel, id=channel_id, is_deleted=False)
        else:
            # Get default channel
            channel, _ = ChatChannel.objects.get_or_create(
                channel_type='admin',
                name='Admin Channel',
                defaults={
                    'description': 'Main communication channel for administrators',
                    'created_by': request.user,
                    'is_active': True
                }
            )
            if request.user not in channel.members.all():
                channel.members.add(request.user)
        
        # Check access
        # For direct messages, only participants can access
        if channel.channel_type == 'direct':
            if request.user not in [channel.participant1, channel.participant2] and not request.user.is_superuser:
                return JsonResponse({'error': 'Access denied'}, status=403)
        else:
            # For other channels, check membership
            if request.user not in channel.members.all() and not request.user.is_superuser:
                return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get messages
        since = request.GET.get('since')
        limit = int(request.GET.get('limit', 50))
        
        messages_query = ChatMessage.objects.filter(
            channel=channel,
            is_deleted=False
        ).select_related('sender').prefetch_related('read_by').order_by('-created')
        
        if since:
            try:
                since_dt = timezone.datetime.fromisoformat(since.replace('Z', '+00:00'))
                messages_query = messages_query.filter(created__gt=since_dt)
            except:
                pass
        
        messages = messages_query[:limit]
        
        # Mark messages as read
        for message in messages:
            message.mark_as_read(request.user)
            # Mark notification as read
            ChatNotification.objects.filter(
                user=request.user,
                message=message
            ).update(is_read=True, read_at=timezone.now())
        
        messages_data = []
        for msg in reversed(messages):
            messages_data.append({
                'id': str(msg.id),
                'content': msg.content,
                'sender': {
                    'id': msg.sender.id,
                    'username': msg.sender.username,
                    'full_name': msg.sender.get_full_name() or msg.sender.username,
                    'email': getattr(msg.sender, 'email', ''),
                },
                'created': msg.created.isoformat(),
                'message_type': msg.message_type,
                'is_read': request.user in msg.read_by.all(),
                'reactions': msg.reactions or {},
            })
        
        return JsonResponse({
            'success': True,
            'channel': {
                'id': str(channel.id),
                'name': channel.name,
                'description': channel.description,
            },
            'messages': messages_data,
            'unread_count': ChatNotification.objects.filter(
                user=request.user,
                is_read=False
            ).count(),
        })
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error retrieving chat messages: {e}', exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def chat_notifications_api(request):
    """
    Get unread chat notifications count
    Returns JSON even if user doesn't have admin access (returns empty data)
    This prevents HTML redirect errors when non-admin users access the page
    """
    # Check if user has access to chat (admin/it staff)
    # If not, return empty data instead of redirecting (which would return HTML)
    has_chat_access = (
        request.user.is_superuser or 
        request.user.is_staff or
        (hasattr(request.user, 'staff_profile') and 
         request.user.staff_profile.profession in ['admin', 'it', 'it_staff'])
    )
    
    if not has_chat_access:
        # Return empty JSON response instead of redirecting
        return JsonResponse({
            'unread_count': 0,
            'notifications': [],
        })
    
    # User has access, get notifications
    try:
        unread_count = ChatNotification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        
        # Also get recent notifications
        recent_notifications = ChatNotification.objects.filter(
            user=request.user,
            is_read=False
        ).select_related('message', 'message__sender', 'message__channel').order_by('-created')[:10]
        
        notifications_data = []
        for notif in recent_notifications:
            notifications_data.append({
                'id': str(notif.id),
                'message_id': str(notif.message.id),
                'channel_name': notif.message.channel.name,
                'sender': notif.message.sender.get_full_name() or notif.message.sender.username,
                'content': notif.message.content[:100],
                'created': notif.created.isoformat(),
            })
        
        return JsonResponse({
            'unread_count': unread_count,
            'notifications': notifications_data,
        })
    except Exception as e:
        # If ChatNotification model doesn't exist or any error, return empty data
        return JsonResponse({
            'unread_count': 0,
            'notifications': [],
        })











