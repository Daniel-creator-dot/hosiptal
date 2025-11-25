"""
Audit Utility Functions
Helper functions for creating audit logs
"""
from django.contrib.auth.models import User
from django.db import models
import logging

logger = logging.getLogger(__name__)


def log_audit_action(user, action_type, model_instance=None, description='', 
                    changes=None, metadata=None, severity='info', request=None,
                    success=True, error_message=''):
    """
    Create an audit log entry for a user action
    
    Args:
        user: User performing the action
        action_type: Type of action (create, update, delete, etc.)
        model_instance: Django model instance that was affected
        description: Human-readable description
        changes: Dict of field changes {field: {'old': x, 'new': y}}
        metadata: Additional context
        severity: info, warning, error, critical
        request: Django request object (for IP, user agent, etc.)
        success: Whether action succeeded
        error_message: Error message if failed
    """
    try:
        from .models_audit import AuditLog
        
        model_name = ''
        object_id = ''
        object_repr = ''
        
        if model_instance:
            model_name = model_instance.__class__.__name__
            object_id = str(model_instance.pk)
            object_repr = str(model_instance)[:255]
        
        ip_address = None
        user_agent = ''
        request_path = ''
        request_method = ''
        
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            request_path = request.path
            request_method = request.method
        
        AuditLog.log_action(
            user=user,
            action_type=action_type,
            model_name=model_name,
            object_id=object_id,
            object_repr=object_repr,
            description=description,
            changes=changes or {},
            metadata=metadata or {},
            severity=severity,
            ip_address=ip_address,
            user_agent=user_agent,
            request_path=request_path,
            request_method=request_method,
            success=success,
            error_message=error_message,
        )
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")


def track_model_changes(instance, action_type, user, request=None):
    """
    Track changes to a model instance
    
    Args:
        instance: Django model instance
        action_type: create, update, or delete
        user: User making the change
        request: Django request object
    """
    try:
        from .models_audit import AuditLog
        
        model_name = instance.__class__.__name__
        object_id = str(instance.pk)
        object_repr = str(instance)[:255]
        
        # Get changes if this is an update
        changes = {}
        if action_type == 'update' and hasattr(instance, '_state'):
            # Try to get changed fields
            if hasattr(instance, '_changed_fields'):
                for field in instance._changed_fields:
                    if hasattr(instance, field):
                        # This is simplified - in production, track old values
                        changes[field] = {'new': str(getattr(instance, field, ''))}
        
        description = f"{action_type.capitalize()}d {model_name}: {object_repr}"
        
        ip_address = None
        user_agent = ''
        request_path = ''
        request_method = ''
        
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            request_path = request.path
            request_method = request.method
        
        AuditLog.log_action(
            user=user,
            action_type=action_type,
            model_name=model_name,
            object_id=object_id,
            object_repr=object_repr,
            description=description,
            changes=changes,
            metadata={},
            severity='info',
            ip_address=ip_address,
            user_agent=user_agent,
            request_path=request_path,
            request_method=request_method,
            success=True,
        )
    except Exception as e:
        logger.error(f"Failed to track model changes: {e}")






