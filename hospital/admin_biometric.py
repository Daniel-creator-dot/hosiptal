"""
Admin Interface for Biometric Authentication System
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from .models_biometric import (
    BiometricType,
    StaffBiometric,
    BiometricAuthenticationLog,
    BiometricDevice,
    BiometricEnrollmentSession,
    BiometricSecurityAlert,
    BiometricSystemSettings,
)


@admin.register(BiometricType)
class BiometricTypeAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'display_name',
        'is_active',
        'requires_liveness_check',
        'min_confidence_score',
        'max_failed_attempts',
        'enrolled_staff_count'
    ]
    list_filter = ['is_active', 'requires_liveness_check', 'name']
    search_fields = ['name', 'display_name', 'description']
    readonly_fields = ['created', 'modified']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'description', 'is_active')
        }),
        ('Security Settings', {
            'fields': (
                'requires_liveness_check',
                'min_confidence_score',
                'max_failed_attempts',
                'lockout_duration_minutes'
            )
        }),
        ('Configuration', {
            'fields': ('config_json',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    
    def enrolled_staff_count(self, obj):
        count = obj.staff_biometrics.filter(is_active=True, is_deleted=False).count()
        return format_html(
            '<span style="font-weight: bold; color: #28a745;">{}</span> staff',
            count
        )
    enrolled_staff_count.short_description = 'Enrolled Staff'


@admin.register(StaffBiometric)
class StaffBiometricAdmin(admin.ModelAdmin):
    list_display = [
        'staff_name',
        'biometric_type_display',
        'status_badge',
        'quality_score',
        'enrolled_at',
        'last_verified',
        'verification_count',
        'failed_attempts',
    ]
    list_filter = [
        'biometric_type',
        'is_active',
        'is_primary',
        'enrolled_at',
        'last_verified'
    ]
    search_fields = [
        'staff__user__username',
        'staff__user__first_name',
        'staff__user__last_name',
        'staff__employee_id',
        'template_hash'
    ]
    readonly_fields = [
        'template_hash',
        'enrolled_at',
        'enrolled_by',
        'last_verified',
        'verification_count',
        'failed_attempts',
        'locked_until',
        'created',
        'modified',
        'template_metadata_display'
    ]
    date_hierarchy = 'enrolled_at'
    
    fieldsets = (
        ('Staff Information', {
            'fields': ('staff', 'biometric_type')
        }),
        ('Enrollment Details', {
            'fields': (
                'enrolled_at',
                'enrolled_by',
                'enrollment_device',
                'enrollment_location',
                'quality_score',
                'sample_count'
            )
        }),
        ('Template Data', {
            'fields': ('template_hash', 'template_metadata_display'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': (
                'is_active',
                'is_primary',
                'expires_at',
                'last_verified',
                'verification_count'
            )
        }),
        ('Security', {
            'fields': (
                'failed_attempts',
                'locked_until',
                'backup_method'
            )
        }),
        ('Metadata', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    
    def staff_name(self, obj):
        return obj.staff.user.get_full_name()
    staff_name.short_description = 'Staff'
    staff_name.admin_order_field = 'staff__user__last_name'
    
    def biometric_type_display(self, obj):
        return obj.biometric_type.display_name
    biometric_type_display.short_description = 'Biometric Type'
    biometric_type_display.admin_order_field = 'biometric_type__name'
    
    def status_badge(self, obj):
        if not obj.is_active:
            return format_html(
                '<span style="background-color: #6c757d; color: white; padding: 3px 8px; border-radius: 3px;">Inactive</span>'
            )
        elif obj.is_locked:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 8px; border-radius: 3px;">🔒 Locked</span>'
            )
        elif obj.is_expired:
            return format_html(
                '<span style="background-color: #ffc107; color: black; padding: 3px 8px; border-radius: 3px;">⚠️ Expired</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 8px; border-radius: 3px;">✓ Active</span>'
            )
    status_badge.short_description = 'Status'
    
    def template_metadata_display(self, obj):
        import json
        metadata_json = json.dumps(obj.template_metadata, indent=2)
        return format_html('<pre>{}</pre>', metadata_json)
    template_metadata_display.short_description = 'Template Metadata'
    
    actions = ['activate_biometrics', 'deactivate_biometrics', 'unlock_biometrics']
    
    def activate_biometrics(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} biometric(s) activated.')
    activate_biometrics.short_description = 'Activate selected biometrics'
    
    def deactivate_biometrics(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} biometric(s) deactivated.')
    deactivate_biometrics.short_description = 'Deactivate selected biometrics'
    
    def unlock_biometrics(self, request, queryset):
        updated = queryset.update(locked_until=None, failed_attempts=0)
        self.message_user(request, f'{updated} biometric(s) unlocked.')
    unlock_biometrics.short_description = 'Unlock selected biometrics'


@admin.register(BiometricAuthenticationLog)
class BiometricAuthenticationLogAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp',
        'staff_name',
        'biometric_type_display',
        'status_badge',
        'confidence_score',
        'quality_score',
        'location_name',
        'device_name',
        'security_flags'
    ]
    list_filter = [
        'status',
        'biometric_type',
        'timestamp',
        'is_suspicious',
        'spoofing_detected',
        'created_attendance',
        'created_login_record'
    ]
    search_fields = [
        'staff__user__username',
        'staff__user__first_name',
        'staff__user__last_name',
        'location_name',
        'device_name',
        'ip_address'
    ]
    readonly_fields = [
        'timestamp',
        'staff',
        'biometric',
        'biometric_type',
        'status',
        'confidence_score',
        'quality_score',
        'liveness_score',
        'device_info_display',
        'created_attendance',
        'attendance_record',
        'created_login_record',
        'login_record',
        'processing_time_ms',
        'created',
        'modified'
    ]
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Authentication Details', {
            'fields': (
                'timestamp',
                'staff',
                'biometric',
                'biometric_type',
                'status'
            )
        }),
        ('Metrics', {
            'fields': (
                'confidence_score',
                'quality_score',
                'liveness_score',
                'processing_time_ms'
            )
        }),
        ('Device & Location', {
            'fields': (
                'device_name',
                'device_id',
                'device_info_display',
                'location_name',
                'ip_address',
                'latitude',
                'longitude'
            )
        }),
        ('Integration', {
            'fields': (
                'created_attendance',
                'attendance_record',
                'created_login_record',
                'login_record'
            )
        }),
        ('Security', {
            'fields': (
                'is_suspicious',
                'spoofing_detected',
                'multiple_face_detected',
                'failure_reason',
                'notes'
            )
        }),
    )
    
    def staff_name(self, obj):
        if obj.staff:
            return obj.staff.user.get_full_name()
        return '-'
    staff_name.short_description = 'Staff'
    
    def biometric_type_display(self, obj):
        return obj.biometric_type.display_name
    biometric_type_display.short_description = 'Biometric Type'
    biometric_type_display.admin_order_field = 'biometric_type__name'
    
    def status_badge(self, obj):
        colors = {
            'success': '#28a745',
            'failed_match': '#dc3545',
            'failed_quality': '#ffc107',
            'failed_liveness': '#fd7e14',
            'failed_locked': '#6c757d',
            'failed_expired': '#e83e8c',
            'failed_spoofing': '#dc3545',
            'failed_error': '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def security_flags(self, obj):
        flags = []
        if obj.is_suspicious:
            flags.append('🚨 Suspicious')
        if obj.spoofing_detected:
            flags.append('⚠️ Spoofing')
        if obj.multiple_face_detected:
            flags.append('👥 Multiple Faces')
        return ', '.join(flags) if flags else '-'
    security_flags.short_description = 'Security Flags'
    
    def device_info_display(self, obj):
        import json
        device_json = json.dumps(obj.device_info, indent=2)
        return format_html('<pre>{}</pre>', device_json)
    device_info_display.short_description = 'Device Information'


@admin.register(BiometricDevice)
class BiometricDeviceAdmin(admin.ModelAdmin):
    list_display = [
        'device_name',
        'device_type',
        'location_name',
        'status_badge',
        'is_online',
        'success_rate_display',
        'total_authentications',
        'last_heartbeat'
    ]
    list_filter = [
        'device_type',
        'is_active',
        'is_online',
        'location_name',
        'department'
    ]
    search_fields = [
        'device_name',
        'device_id',
        'serial_number',
        'location_name',
        'ip_address',
        'mac_address'
    ]
    readonly_fields = [
        'device_id',
        'is_online',
        'last_heartbeat',
        'total_authentications',
        'successful_authentications',
        'failed_authentications',
        'success_rate_display',
        'created',
        'modified'
    ]
    filter_horizontal = ['supported_biometrics']
    
    fieldsets = (
        ('Device Information', {
            'fields': (
                'device_name',
                'device_type',
                'device_id',
                'serial_number',
                'supported_biometrics'
            )
        }),
        ('Location', {
            'fields': (
                'location_name',
                'department'
            )
        }),
        ('Network', {
            'fields': (
                'ip_address',
                'mac_address'
            )
        }),
        ('Device Specifications', {
            'fields': (
                'manufacturer',
                'model_number',
                'firmware_version',
                'sdk_version'
            ),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': (
                'is_active',
                'is_online',
                'last_heartbeat',
                'last_maintenance',
                'next_maintenance'
            )
        }),
        ('Statistics', {
            'fields': (
                'total_authentications',
                'successful_authentications',
                'failed_authentications',
                'success_rate_display'
            )
        }),
        ('Configuration', {
            'fields': ('config_json',),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )
    
    def status_badge(self, obj):
        if not obj.is_active:
            return format_html(
                '<span style="background-color: #6c757d; color: white; padding: 3px 8px; border-radius: 3px;">Inactive</span>'
            )
        elif obj.is_online:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 8px; border-radius: 3px;">🟢 Online</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 8px; border-radius: 3px;">🔴 Offline</span>'
            )
    status_badge.short_description = 'Status'
    
    def success_rate_display(self, obj):
        rate = obj.success_rate
        color = '#28a745' if rate >= 90 else '#ffc107' if rate >= 75 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color,
            rate
        )
    success_rate_display.short_description = 'Success Rate'


@admin.register(BiometricEnrollmentSession)
class BiometricEnrollmentSessionAdmin(admin.ModelAdmin):
    list_display = [
        'session_id',
        'staff',
        'biometric_type_display',
        'status',
        'samples_progress',
        'average_quality_score',
        'started_at',
        'operator'
    ]
    list_filter = ['status', 'biometric_type', 'started_at']
    search_fields = [
        'session_id',
        'staff__user__username',
        'staff__user__first_name',
        'staff__user__last_name'
    ]
    readonly_fields = [
        'session_id',
        'started_at',
        'completed_at',
        'biometric_created',
        'created',
        'modified'
    ]
    date_hierarchy = 'started_at'
    
    fieldsets = (
        ('Session Information', {
            'fields': (
                'session_id',
                'staff',
                'biometric_type',
                'status'
            )
        }),
        ('Progress', {
            'fields': (
                'started_at',
                'completed_at',
                'samples_required',
                'samples_captured',
                'average_quality_score'
            )
        }),
        ('Device & Operator', {
            'fields': (
                'device',
                'operator'
            )
        }),
        ('Result', {
            'fields': (
                'biometric_created',
                'notes',
                'failure_reason'
            )
        }),
    )
    
    def biometric_type_display(self, obj):
        return obj.biometric_type.display_name
    biometric_type_display.short_description = 'Biometric Type'
    biometric_type_display.admin_order_field = 'biometric_type__name'
    
    def samples_progress(self, obj):
        percentage = (obj.samples_captured / obj.samples_required) * 100 if obj.samples_required > 0 else 0
        return format_html(
            '{} / {} ({:.0f}%)',
            obj.samples_captured,
            obj.samples_required,
            percentage
        )
    samples_progress.short_description = 'Samples'


@admin.register(BiometricSecurityAlert)
class BiometricSecurityAlertAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp',
        'alert_type',
        'severity_badge',
        'staff',
        'device',
        'is_resolved',
        'resolved_by'
    ]
    list_filter = [
        'alert_type',
        'severity',
        'is_resolved',
        'timestamp'
    ]
    search_fields = [
        'title',
        'description',
        'staff__user__username',
        'device__device_name'
    ]
    readonly_fields = [
        'timestamp',
        'resolved_at',
        'notification_sent',
        'created',
        'modified',
        'metadata_display'
    ]
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Alert Details', {
            'fields': (
                'timestamp',
                'alert_type',
                'severity',
                'title',
                'description'
            )
        }),
        ('Related Entities', {
            'fields': (
                'staff',
                'device',
                'auth_log'
            )
        }),
        ('Additional Data', {
            'fields': ('metadata_display',),
            'classes': ('collapse',)
        }),
        ('Resolution', {
            'fields': (
                'is_resolved',
                'resolved_at',
                'resolved_by',
                'resolution_notes'
            )
        }),
        ('Notification', {
            'fields': (
                'notification_sent',
                'notification_recipients'
            )
        }),
    )
    
    def severity_badge(self, obj):
        colors = {
            'low': '#17a2b8',
            'medium': '#ffc107',
            'high': '#fd7e14',
            'critical': '#dc3545'
        }
        color = colors.get(obj.severity, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_severity_display().upper()
        )
    severity_badge.short_description = 'Severity'
    
    def metadata_display(self, obj):
        import json
        metadata_json = json.dumps(obj.metadata, indent=2)
        return format_html('<pre>{}</pre>', metadata_json)
    metadata_display.short_description = 'Metadata'
    
    actions = ['mark_as_resolved']
    
    def mark_as_resolved(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(
            is_resolved=True,
            resolved_at=timezone.now(),
            resolved_by=request.user
        )
        self.message_user(request, f'{updated} alert(s) marked as resolved.')
    mark_as_resolved.short_description = 'Mark selected alerts as resolved'


@admin.register(BiometricSystemSettings)
class BiometricSystemSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'system_enabled',
        'require_biometric_for_staff',
        'enable_liveness_detection',
        'face_recognition_provider'
    ]
    
    fieldsets = (
        ('General Settings', {
            'fields': (
                'system_enabled',
                'require_biometric_for_staff',
                'allow_password_fallback'
            )
        }),
        ('Security Settings', {
            'fields': (
                'enable_liveness_detection',
                'enable_anti_spoofing',
                'enable_multimodal_auth',
                'template_expiry_days',
                'auto_lock_after_failures'
            )
        }),
        ('Attendance Integration', {
            'fields': (
                'auto_create_attendance',
                'attendance_check_in_window_minutes'
            )
        }),
        ('Alerts & Notifications', {
            'fields': (
                'enable_security_alerts',
                'alert_on_multiple_failures',
                'alert_failure_threshold',
                'alert_recipients_json'
            )
        }),
        ('API Settings', {
            'fields': (
                'face_recognition_provider',
                'face_recognition_model'
            )
        }),
        ('Performance', {
            'fields': (
                'enable_caching',
                'cache_duration_seconds'
            )
        }),
        ('Audit & Compliance', {
            'fields': (
                'log_retention_days',
                'require_consent_form'
            )
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow one instance
        return not BiometricSystemSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of settings
        return False

