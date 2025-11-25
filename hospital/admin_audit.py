"""
Admin configuration for Audit Logging
"""
from django.contrib import admin
from .models_audit import AuditLog, ActivityLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin interface for audit logs"""
    list_display = ['created', 'user', 'action_type', 'model_name', 'object_repr', 'severity', 'success', 'ip_address']
    list_filter = ['action_type', 'severity', 'success', 'created', 'model_name']
    search_fields = ['user__username', 'description', 'object_repr', 'model_name', 'ip_address']
    readonly_fields = ['id', 'created', 'modified', 'user', 'action_type', 'severity', 'model_name', 
                      'object_id', 'object_repr', 'description', 'changes', 'metadata', 'ip_address',
                      'user_agent', 'request_path', 'request_method', 'success', 'error_message']
    date_hierarchy = 'created'
    ordering = ['-created']
    
    def has_add_permission(self, request):
        return False  # Audit logs are created automatically
    
    def has_change_permission(self, request, obj=None):
        return False  # Audit logs should not be modified
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superusers can delete audit logs


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """Admin interface for activity logs"""
    list_display = ['created', 'user', 'activity_type', 'description', 'ip_address']
    list_filter = ['activity_type', 'created']
    search_fields = ['user__username', 'description', 'activity_type', 'ip_address']
    readonly_fields = ['id', 'created', 'modified', 'user', 'activity_type', 'description', 
                      'ip_address', 'user_agent', 'session_key', 'metadata']
    date_hierarchy = 'created'
    ordering = ['-created']
    
    def has_add_permission(self, request):
        return False  # Activity logs are created automatically
    
    def has_change_permission(self, request, obj=None):
        return False  # Activity logs should not be modified
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superusers can delete activity logs






