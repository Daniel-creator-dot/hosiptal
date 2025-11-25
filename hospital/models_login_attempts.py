"""
Login Attempt Tracking Model
Tracks failed login attempts to prevent brute force attacks
"""
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from model_utils.models import TimeStampedModel
import uuid


class LoginAttempt(TimeStampedModel):
    """
    Tracks login attempts to prevent brute force attacks
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user_agent = models.CharField(max_length=500, blank=True)
    failed_attempts = models.PositiveIntegerField(default=0)
    is_locked = models.BooleanField(default=False)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    manually_blocked = models.BooleanField(default=False, help_text="Set when an administrator blocks this account manually")
    block_reason = models.CharField(max_length=255, blank=True)
    block_expires_at = models.DateTimeField(null=True, blank=True, help_text="Optional automatic unblock time for manual blocks")
    blocked_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='blocked_login_attempts')
    blocked_at = models.DateTimeField(null=True, blank=True)
    unblocked_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='unblocked_login_attempts')
    unblocked_at = models.DateTimeField(null=True, blank=True)
    unblock_note = models.CharField(max_length=255, blank=True)
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-last_attempt_at']
        indexes = [
            models.Index(fields=['username', 'is_locked']),
            models.Index(fields=['ip_address', 'is_locked']),
        ]
    
    def __str__(self):
        return f"{self.username} - {self.failed_attempts} attempts"
    
    def increment_failed_attempt(self, max_attempts=3, lockout_duration_minutes=15):
        """
        Increment failed attempt counter and lock if threshold reached
        Returns True if account should be locked
        """
        self.failed_attempts += 1
        self.last_attempt_at = timezone.now()
        
        if self.failed_attempts >= max_attempts:
            self.is_locked = True
            self.locked_until = timezone.now() + timezone.timedelta(minutes=lockout_duration_minutes)
            self.save(update_fields=['failed_attempts', 'is_locked', 'locked_until', 'last_attempt_at', 'modified'])
            return True
        
        self.save(update_fields=['failed_attempts', 'last_attempt_at', 'modified'])
        return False
    
    def reset_attempts(self):
        """Reset failed attempts on successful login"""
        self.failed_attempts = 0
        self.is_locked = False
        self.locked_until = None
        self.save(update_fields=['failed_attempts', 'is_locked', 'locked_until', 'modified'])
    
    def manual_block_active(self):
        """Check if a manual block is active and auto-unblock when expired."""
        if not self.manually_blocked:
            return False
        
        if self.block_expires_at and timezone.now() >= self.block_expires_at:
            self.unblock(note='Automatic unblock after expiry')
            return False
        
        return True
    
    def block(self, blocked_by=None, reason='', expires_at=None):
        """Manually block this account."""
        self.manually_blocked = True
        self.block_reason = reason or ''
        self.block_expires_at = expires_at
        self.blocked_by = blocked_by
        self.blocked_at = timezone.now()
        self.unblocked_by = None
        self.unblocked_at = None
        self.unblock_note = ''
        self.save(update_fields=[
            'manually_blocked', 'block_reason', 'block_expires_at',
            'blocked_by', 'blocked_at', 'unblocked_by', 'unblocked_at',
            'unblock_note', 'modified'
        ])
    
    def unblock(self, unblocked_by=None, note=''):
        """Remove manual block and reset lock state."""
        self.manually_blocked = False
        self.block_reason = ''
        self.block_expires_at = None
        self.unblocked_by = unblocked_by
        self.unblocked_at = timezone.now()
        self.unblock_note = note or ''
        self.is_locked = False
        self.locked_until = None
        self.failed_attempts = 0
        self.save(update_fields=[
            'manually_blocked', 'block_reason', 'block_expires_at',
            'unblocked_by', 'unblocked_at',
            'unblock_note', 'is_locked', 'locked_until', 'failed_attempts', 'modified'
        ])
    
    def manual_block_message(self):
        return self.block_reason or "Account blocked by an administrator. Please contact support."
    
    def is_currently_locked(self):
        """Check if account is currently locked"""
        if self.manual_block_active():
            return True
        
        if not self.is_locked:
            return False
        
        if self.locked_until and timezone.now() < self.locked_until:
            return True
        
        # Lockout period expired, unlock
        if self.locked_until and timezone.now() >= self.locked_until:
            self.is_locked = False
            self.locked_until = None
            self.failed_attempts = 0  # Reset attempts after lockout expires
            self.save(update_fields=['is_locked', 'locked_until', 'failed_attempts', 'modified'])
            return False
        
        return False
    
    @classmethod
    def get_or_create_attempt(cls, username, ip_address=None, user_agent=None):
        """Get or create login attempt record - tracks by username only"""
        # Get the most recent attempt for this username (regardless of IP)
        attempt = cls.objects.filter(
            username=username,
            is_deleted=False
        ).order_by('-last_attempt_at', '-created').first()
        
        if not attempt:
            # Create new attempt record
            attempt = cls.objects.create(
                username=username,
                ip_address=ip_address,
                user_agent=user_agent or '',
                failed_attempts=0,
            )
        else:
            # Update IP and user agent if changed
            update_fields = []
            if ip_address and attempt.ip_address != ip_address:
                attempt.ip_address = ip_address
                update_fields.append('ip_address')
            if user_agent and attempt.user_agent != user_agent:
                attempt.user_agent = user_agent
                update_fields.append('user_agent')
            if update_fields:
                attempt.save(update_fields=update_fields)
        
        return attempt
    
    @classmethod
    def get_remaining_attempts(cls, username, max_attempts=3):
        """Get remaining login attempts for a username"""
        try:
            # Get the most recent attempt for this username
            attempt = cls.objects.filter(
                username=username,
                is_deleted=False
            ).order_by('-last_attempt_at', '-created').first()
            
            if attempt:
                # Check if currently locked (this also auto-unlocks if expired)
                if attempt.manual_block_active():
                    return 0
                if attempt.is_currently_locked():
                    return 0
                # Return remaining attempts
                return max(0, max_attempts - attempt.failed_attempts)
            # No previous attempts, return max
            return max_attempts
        except Exception as e:
            # On any error, allow login attempts (fail open for security)
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting remaining attempts for {username}: {e}")
            return max_attempts

