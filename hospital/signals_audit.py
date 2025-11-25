"""
Audit Signals
Automatically log model changes for compliance and tracking
"""
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)


def get_user_from_request():
    """Try to get current user from thread-local storage"""
    try:
        from .middleware_thread_local import get_current_user
        user = get_current_user()
        if user and user.is_authenticated:
            return user
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Could not get user from request: {e}")
    return None


# Models that should be audited (critical business data)
# Using lowercase model names for matching
AUDITED_MODELS = [
    # Accounting & Finance
    'account', 'accountingentry', 'journalentry', 'transaction',
    'invoice', 'payment', 'claim', 'insuranceclaim', 'accountcategory',
    'accountingauditlog', 'revenue', 'expense',
    
    # HR & Staff
    'staff', 'leaverequest', 'payroll', 'attendance', 'dutyroster',
    'performance', 'training', 'contract', 'staffattendance',
    'attendancerecord', 'leaverecord',
    
    # Insurance
    'insurancecompany', 'insuranceplan', 'patientinsurance',
    'insurancepreauthorization', 'claimsbatch', 'chargecapture',
    
    # Procurement
    'procurementrequest', 'procurementapproval', 'storetransfer',
    'consumablesinventory', 'medicalequipment', 'maintenancelog',
    
    # Clinical
    'patient', 'encounter', 'order', 'prescription', 'labresult',
    'vitalsign', 'admission', 'appointment', 'medicalrecord',
    'imagingstudy', 'labtest',
]

@receiver(post_save)
def log_model_save(sender, instance, created, **kwargs):
    """
    Log model saves for audit purposes
    Only logs critical models from the hospital app
    """
    # Only log hospital app models
    if not sender._meta.app_label == 'hospital':
        return
    
    # Skip logging for audit models themselves (avoid recursion)
    model_name = sender._meta.model_name.lower()
    if model_name in ['auditlog', 'activitylog', 'usersession', 'loginattempt']:
        return
    
    # Only log critical models (to avoid performance issues)
    # Match exact model name (case-insensitive) or partial match
    model_name_lower = model_name
    should_audit = False
    
    # Check for exact match or substring match
    for audited in AUDITED_MODELS:
        if audited.lower() == model_name_lower or audited.lower() in model_name_lower or model_name_lower in audited.lower():
            should_audit = True
            break
    
    if not should_audit:
        return
    
    try:
        from .models_audit import AuditLog
        from django.contrib.auth.models import User
        
        # Try to get user from request (thread-local)
        user = get_user_from_request()
        
        # Fallback: Try to get from instance if it has a user field
        if not user or not user.is_authenticated:
            if hasattr(instance, 'user') and isinstance(instance.user, User):
                user = instance.user
            elif hasattr(instance, 'created_by') and isinstance(instance.created_by, User):
                user = instance.created_by
            elif hasattr(instance, 'modified_by') and isinstance(instance.modified_by, User):
                user = instance.modified_by
            elif hasattr(instance, 'requested_by'):
                if hasattr(instance.requested_by, 'user') and isinstance(instance.requested_by.user, User):
                    user = instance.requested_by.user
                elif isinstance(instance.requested_by, User):
                    user = instance.requested_by
        
        # If still no user, try to get from the model's related user
        if not user or not isinstance(user, User):
            # Check if model has a ForeignKey to Staff or User
            for field in sender._meta.get_fields():
                if field.name in ['user', 'created_by', 'modified_by', 'staff', 'provider', 'requested_by']:
                    try:
                        related_obj = getattr(instance, field.name, None)
                        if related_obj:
                            if isinstance(related_obj, User):
                                user = related_obj
                                break
                            elif hasattr(related_obj, 'user') and isinstance(related_obj.user, User):
                                user = related_obj.user
                                break
                    except:
                        pass
        
        # Skip if no user found (system operations)
        if not user or not isinstance(user, User):
            return
        
        action_type = 'create' if created else 'update'
        model_name = sender._meta.model_name
        object_id = str(instance.pk)
        object_repr = str(instance)[:255]
        
        # Get changes for updates (simplified - Django doesn't track old values by default)
        changes = {}
        if not created:
            # For updates, we'll log that an update occurred
            # To track actual field changes, you'd need to use django-model-utils or similar
            # For now, we'll just note that an update happened
            changes['_update_note'] = 'Model updated (field-level changes not tracked)'
        
        description = f"{action_type.capitalize()}d {model_name}: {object_repr}"
        
        # Log the action
        AuditLog.log_action(
            user=user,
            action_type=action_type,
            model_name=model_name,
            object_id=object_id,
            object_repr=object_repr,
            description=description,
            changes=changes,
            severity='info',
            success=True,
        )
    except Exception as e:
        # Don't break the save operation if logging fails
        logger.warning(f"Failed to log model save: {e}")


@receiver(post_delete)
def log_model_delete(sender, instance, **kwargs):
    """
    Log model deletes for audit purposes
    Only logs critical models from the hospital app
    """
    # Only log hospital app models
    if not sender._meta.app_label == 'hospital':
        return
    
    # Skip logging for audit models themselves
    model_name = sender._meta.model_name.lower()
    if model_name in ['auditlog', 'activitylog', 'usersession', 'loginattempt']:
        return
    
    # Only log critical models (to avoid performance issues)
    # Match exact model name (case-insensitive) or partial match
    model_name_lower = model_name
    should_audit = False
    
    # Check for exact match or substring match
    for audited in AUDITED_MODELS:
        if audited.lower() == model_name_lower or audited.lower() in model_name_lower or model_name_lower in audited.lower():
            should_audit = True
            break
    
    if not should_audit:
        return
    
    try:
        from .models_audit import AuditLog
        
        # Try to get user from request (thread-local)
        user = get_user_from_request()
        
        # Fallback: Try to get from instance
        if not user or not isinstance(user, User):
            if hasattr(instance, 'user') and isinstance(instance.user, User):
                user = instance.user
            elif hasattr(instance, 'created_by') and isinstance(instance.created_by, User):
                user = instance.created_by
            elif hasattr(instance, 'modified_by') and isinstance(instance.modified_by, User):
                user = instance.modified_by
        
        # Skip if no user found
        if not user or not isinstance(user, User):
            return
        
        model_name = sender._meta.model_name
        object_id = str(instance.pk)
        object_repr = str(instance)[:255]
        
        description = f"Deleted {model_name}: {object_repr}"
        
        # Log the action
        AuditLog.log_action(
            user=user,
            action_type='delete',
            model_name=model_name,
            object_id=object_id,
            object_repr=object_repr,
            description=description,
            changes={},
            severity='warning',
            success=True,
        )
    except Exception as e:
        # Don't break the delete operation if logging fails
        logger.warning(f"Failed to log model delete: {e}")

