"""
Admin Chat Channel Models
State-of-the-art chat system for IT/Admin team communication
"""
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.utils import timezone
from .models import BaseModel


class ChatChannel(BaseModel):
    """
    Chat channel for team communication
    """
    CHANNEL_TYPES = [
        ('admin', 'Admin Channel'),
        ('it', 'IT Operations'),
        ('general', 'General Discussion'),
        ('urgent', 'Urgent Alerts'),
        ('direct', 'Direct Message'),  # Private user-to-user chat
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    channel_type = models.CharField(max_length=20, choices=CHANNEL_TYPES, default='admin')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_channels')
    
    # Members who can access this channel
    members = models.ManyToManyField(User, related_name='chat_channels', blank=True)
    
    # For direct messages: store the two participants explicitly
    participant1 = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='direct_chats_as_participant1')
    participant2 = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='direct_chats_as_participant2')
    
    class Meta:
        ordering = ['-created']
        verbose_name = 'Chat Channel'
        verbose_name_plural = 'Chat Channels'
        # Ensure unique direct message channels between two users
        constraints = [
            models.UniqueConstraint(
                fields=['participant1', 'participant2'],
                condition=Q(channel_type='direct'),
                name='unique_direct_chat'
            )
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def member_count(self):
        return self.members.count()
    
    def get_unread_count(self, user):
        """Get unread message count for a user"""
        return ChatMessage.objects.filter(
            channel=self,
            is_deleted=False
        ).exclude(
            sender=user
        ).exclude(
            read_by=user
        ).count()
    
    def get_other_participant(self, user):
        """For direct messages, get the other participant"""
        if self.channel_type != 'direct':
            return None
        if self.participant1 == user:
            return self.participant2
        elif self.participant2 == user:
            return self.participant1
        return None
    
    @classmethod
    def get_or_create_direct_chat(cls, user1, user2):
        """Get or create a direct message channel between two users"""
        from django.db.models import Q
        # Try to find existing direct chat in both directions
        chat = cls.objects.filter(
            channel_type='direct',
            is_deleted=False
        ).filter(
            (Q(participant1=user1, participant2=user2) |
             Q(participant1=user2, participant2=user1))
        ).first()
        
        if chat:
            # Ensure both users are members
            if user1 not in chat.members.all():
                chat.members.add(user1)
            if user2 not in chat.members.all():
                chat.members.add(user2)
            return chat, False
        
        # Create new direct chat
        chat = cls.objects.create(
            channel_type='direct',
            name=f"Chat: {user1.get_full_name() or user1.username} & {user2.get_full_name() or user2.username}",
            description=f"Direct message between {user1.username} and {user2.username}",
            participant1=user1,
            participant2=user2,
            created_by=user1,
            is_active=True
        )
        chat.members.add(user1, user2)
        return chat, True


class ChatMessage(BaseModel):
    """
    Chat messages in channels
    """
    MESSAGE_TYPES = [
        ('text', 'Text Message'),
        ('system', 'System Message'),
        ('alert', 'Alert'),
        ('file', 'File Attachment'),
    ]
    
    channel = models.ForeignKey(ChatChannel, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_chat_messages')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField()
    attachment = models.FileField(upload_to='chat/attachments/', null=True, blank=True)
    
    # Read tracking
    read_by = models.ManyToManyField(User, related_name='read_messages', blank=True)
    
    # Reply/thread support
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    
    # Reactions (stored as JSON)
    reactions = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['created']
        indexes = [
            models.Index(fields=['channel', '-created']),
            models.Index(fields=['sender', '-created']),
        ]
    
    def __str__(self):
        return f"{self.sender.username}: {self.content[:50]}"
    
    def mark_as_read(self, user):
        """Mark message as read by user"""
        if user not in self.read_by.all():
            self.read_by.add(user)
    
    @property
    def is_read_by_all(self):
        """Check if message is read by all channel members"""
        channel_members = self.channel.members.all()
        if not channel_members.exists():
            return True
        return self.read_by.count() >= channel_members.count()
    
    @property
    def unread_count(self):
        """Get count of users who haven't read this message"""
        channel_members = self.channel.members.all()
        if not channel_members.exists():
            return 0
        return channel_members.count() - self.read_by.count()


class ChatNotification(BaseModel):
    """
    Notifications for new chat messages
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_notifications')
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='notifications')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created']
        unique_together = ['user', 'message']
    
    def __str__(self):
        return f"Chat notification for {self.user.username}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()











