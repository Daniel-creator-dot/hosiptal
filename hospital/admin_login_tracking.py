"""
Login Tracking Admin
"""
from django.contrib import admin
from django.utils import timezone
from .models_login_tracking import LoginHistory, SecurityAlert, TrustedLocation, TrustedDevice
from .models_login_attempts import LoginAttempt


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'login_time', 'ip_address', 'city', 'country', 'device_type', 'browser', 'status', 'is_suspicious']
    list_filter = ['status', 'is_suspicious', 'is_new_location', 'device_type', 'country', 'login_time']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'ip_address', 'city', 'country']
    readonly_fields = ['created', 'modified', 'login_time', 'logout_time']
    date_hierarchy = 'login_time'
    
    fieldsets = (
        ('User & Session', {
            'fields': ('user', 'staff', 'login_time', 'logout_time', 'session_key', 'status')
        }),
        ('Location', {
            'fields': ('ip_address', 'city', 'region', 'country', 'country_code', 'latitude', 'longitude', 'timezone_name')
        }),
        ('Network', {
            'fields': ('isp', 'organization')
        }),
        ('Device', {
            'fields': ('browser', 'browser_version', 'os', 'os_version', 'device_type', 'device_name', 'user_agent')
        }),
        ('Security', {
            'fields': ('is_suspicious', 'is_new_location', 'is_new_device', 'failure_reason')
        }),
        ('Raw Data', {
            'fields': ('geo_api_response', 'notes'),
            'classes': ('collapse',)
        })
    )
    
    def has_add_permission(self, request):
        # Login history should only be created by system
        return False


@admin.register(SecurityAlert)
class SecurityAlertAdmin(admin.ModelAdmin):
    list_display = ['user', 'alert_type', 'severity', 'alert_time', 'location', 'is_resolved']
    list_filter = ['alert_type', 'severity', 'is_resolved', 'alert_time']
    search_fields = ['user__username', 'description', 'location']
    readonly_fields = ['created', 'modified', 'alert_time', 'resolved_at']
    date_hierarchy = 'alert_time'
    
    fieldsets = (
        ('Alert Info', {
            'fields': ('user', 'login_history', 'alert_time', 'alert_type', 'severity')
        }),
        ('Details', {
            'fields': ('description', 'ip_address', 'location')
        }),
        ('Resolution', {
            'fields': ('is_resolved', 'resolved_by', 'resolved_at', 'resolution_notes')
        }),
        ('Notification', {
            'fields': ('notification_sent',)
        })
    )
    
    actions = ['mark_resolved']
    
    def mark_resolved(self, request, queryset):
        for alert in queryset:
            alert.is_resolved = True
            alert.resolved_by = request.user
            alert.resolved_at = timezone.now()
            alert.save()
        self.message_user(request, f"{queryset.count()} alert(s) marked as resolved.")
    mark_resolved.short_description = "Mark selected alerts as resolved"


@admin.register(TrustedLocation)
class TrustedLocationAdmin(admin.ModelAdmin):
    list_display = ['user', 'location_name', 'city', 'country', 'is_active', 'last_used']
    list_filter = ['is_active', 'country']
    search_fields = ['user__username', 'location_name', 'city', 'country']
    readonly_fields = ['created', 'modified', 'last_used']


@admin.register(TrustedDevice)
class TrustedDeviceAdmin(admin.ModelAdmin):
    list_display = ['user', 'device_name', 'os', 'browser', 'device_type', 'is_active', 'last_seen']
    list_filter = ['is_active', 'device_type', 'os']
    search_fields = ['user__username', 'device_name', 'device_fingerprint']
    readonly_fields = ['created', 'modified', 'first_seen', 'last_seen', 'device_fingerprint']


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ['username', 'failed_attempts', 'is_locked', 'locked_until', 'manually_blocked', 'block_expires_at', 'last_attempt_at']
    list_filter = ['is_locked', 'manually_blocked', 'blocked_by']
    search_fields = ['username', 'ip_address']
    readonly_fields = ['created', 'modified', 'last_attempt_at', 'blocked_by', 'blocked_at', 'unblocked_by', 'unblocked_at']
    fieldsets = (
        ('Account', {
            'fields': ('username', 'failed_attempts', 'is_locked', 'locked_until', 'last_attempt_at')
        }),
        ('Manual Block', {
            'fields': ('manually_blocked', 'block_reason', 'block_expires_at', 'blocked_by', 'blocked_at', 'unblocked_by', 'unblocked_at', 'unblock_note')
        }),
        ('Request Metadata', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
    )
    actions = ['block_accounts', 'unblock_accounts', 'reset_attempts']

    @admin.action(description="Block selected accounts")
    def block_accounts(self, request, queryset):
        count = 0
        for attempt in queryset:
            attempt.block(blocked_by=request.user, reason=attempt.block_reason or "Blocked via admin action")
            count += 1
        self.message_user(request, f"{count} account(s) blocked and prevented from logging in.")

    @admin.action(description="Unblock selected accounts")
    def unblock_accounts(self, request, queryset):
        count = 0
        for attempt in queryset:
            if attempt.manually_blocked or attempt.is_locked:
                attempt.unblock(unblocked_by=request.user, note="Unblocked via admin action")
                count += 1
        self.message_user(request, f"{count} account(s) reactivated.")

    @admin.action(description="Reset failed attempt counters")
    def reset_attempts(self, request, queryset):
        for attempt in queryset:
            attempt.reset_attempts()
        self.message_user(request, f"{queryset.count()} login attempt record(s) reset.")















