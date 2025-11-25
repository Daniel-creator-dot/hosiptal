"""
Audit Logging Models
Tracks all critical operations for compliance and security
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from model_utils.models import TimeStampedModel
import uuid
import json


class AuditLog(TimeStampedModel):
    """
    Comprehensive audit log for all critical operations
    Tracks user actions, data changes, and system events
    """
    ACTION_TYPES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('view', 'View'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('print', 'Print'),
        ('access', 'Access'),
        ('modify', 'Modify'),
        ('system', 'System Event'),
    ]
    
    SEVERITY_LEVELS = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='info')
    
    # What was affected
    model_name = models.CharField(max_length=100, blank=True, help_text="Django model name (e.g., 'Patient', 'Encounter')")
    object_id = models.CharField(max_length=100, blank=True, help_text="ID of the affected object")
    object_repr = models.CharField(max_length=255, blank=True, help_text="String representation of the object")
    
    # Details
    description = models.TextField(help_text="Human-readable description of the action")
    changes = models.JSONField(default=dict, blank=True, help_text="JSON of what changed (field: {old: x, new: y})")
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional context (IP, user agent, etc.)")
    
    # Request context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    request_method = models.CharField(max_length=10, blank=True)
    
    # Status
    success = models.BooleanField(default=True, help_text="Whether the action succeeded")
    error_message = models.TextField(blank=True, help_text="Error message if action failed")
    
    class Meta:
        ordering = ['-created']
        indexes = [
            models.Index(fields=['-created']),
            models.Index(fields=['user', '-created']),
            models.Index(fields=['action_type', '-created']),
            models.Index(fields=['model_name', '-created']),
            models.Index(fields=['severity', '-created']),
        ]
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
    
    def __str__(self):
        return f"{self.action_type.upper()} - {self.model_name or 'System'} - {self.user.username if self.user else 'System'} - {self.created.strftime('%Y-%m-%d %H:%M')}"
    
    @classmethod
    def log_action(cls, user, action_type, model_name='', object_id='', object_repr='', 
                   description='', changes=None, metadata=None, severity='info', 
                   ip_address=None, user_agent=None, request_path='', request_method='',
                   success=True, error_message=''):
        """
        Convenience method to create an audit log entry
        """
        log_entry = cls.objects.create(
            user=user,
            action_type=action_type,
            severity=severity,
            model_name=model_name,
            object_id=str(object_id) if object_id else '',
            object_repr=object_repr[:255] if object_repr else '',
            description=description,
            changes=changes or {},
            metadata=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent or '',
            request_path=request_path[:500] if request_path else '',
            request_method=request_method,
            success=success,
            error_message=error_message[:1000] if error_message else '',
        )
        return log_entry


class ActivityLog(TimeStampedModel):
    """
    User activity log for tracking user behavior and system usage
    Lighter weight than AuditLog, for frequent actions
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='activity_logs')
    activity_type = models.CharField(max_length=50, db_index=True)
    description = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created']
        indexes = [
            models.Index(fields=['user', '-created']),
            models.Index(fields=['activity_type', '-created']),
            models.Index(fields=['-created']),
        ]
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'
    
    def __str__(self):
        return f"{self.user.username if self.user else 'Anonymous'} - {self.activity_type} - {self.created.strftime('%Y-%m-%d %H:%M')}"
    
    @classmethod
    def log_activity(cls, user, activity_type, description, ip_address=None, 
                    user_agent=None, session_key=None, metadata=None):
        """
        Convenience method to create an activity log entry
        """
        return cls.objects.create(
            user=user,
            activity_type=activity_type,
            description=description[:255],
            ip_address=ip_address,
            user_agent=user_agent or '',
            session_key=session_key or '',
            metadata=metadata or {},
        )






