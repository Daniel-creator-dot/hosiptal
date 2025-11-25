"""
Admin configuration for Multi-Channel Notification System
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models_notification import NotificationPreference, MultiChannelNotificationLog


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        'patient_name', 'patient_mrn', 'active_channels_display', 
        'lab_results_notify', 'appointment_notify', 'payment_notify',
        'send_full_results', 'created', 'modified'
    ]
    list_filter = [
        'sms_enabled', 'whatsapp_enabled', 'email_enabled',
        'lab_results_notify', 'appointment_notify', 'payment_notify',
        'send_full_results', 'created'
    ]
    search_fields = [
        'patient__first_name', 'patient__last_name', 'patient__mrn',
        'patient__phone_number', 'patient__email',
        'sms_phone_number', 'whatsapp_phone_number', 'email_address'
    ]
    readonly_fields = ['created', 'modified']
    
    fieldsets = (
        ('Patient Information', {
            'fields': ('patient',)
        }),
        ('Channel Preferences', {
            'fields': (
                ('sms_enabled', 'whatsapp_enabled', 'email_enabled'),
            ),
            'description': 'Enable/disable notification channels'
        }),
        ('Contact Details (Optional - Override Patient Defaults)', {
            'fields': (
                'sms_phone_number',
                'whatsapp_phone_number',
                'email_address',
            ),
            'classes': ('collapse',)
        }),
        ('Notification Types', {
            'fields': (
                'lab_results_notify',
                'appointment_notify',
                'payment_notify',
                'prescription_notify',
            )
        }),
        ('Additional Preferences', {
            'fields': ('send_full_results',)
        }),
        ('Timestamps', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    
    def patient_name(self, obj):
        """Display patient name with link"""
        if obj.patient:
            url = reverse('admin:hospital_patient_change', args=[obj.patient.id])
            return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
        return '-'
    patient_name.short_description = 'Patient'
    patient_name.admin_order_field = 'patient__last_name'
    
    def patient_mrn(self, obj):
        """Display patient MRN"""
        return obj.patient.mrn if obj.patient else '-'
    patient_mrn.short_description = 'MRN'
    patient_mrn.admin_order_field = 'patient__mrn'
    
    def active_channels_display(self, obj):
        """Display active channels with badges"""
        channels = []
        if obj.sms_enabled:
            channels.append('<span style="background-color: #28a745; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">SMS</span>')
        if obj.whatsapp_enabled:
            channels.append('<span style="background-color: #25D366; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">WhatsApp</span>')
        if obj.email_enabled:
            channels.append('<span style="background-color: #007bff; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">Email</span>')
        
        return mark_safe(' '.join(channels)) if channels else mark_safe('<span style="color: #999;">None</span>')
    active_channels_display.short_description = 'Active Channels'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('patient')


@admin.register(MultiChannelNotificationLog)
class MultiChannelNotificationLogAdmin(admin.ModelAdmin):
    list_display = [
        'patient_name', 'notification_type_display', 'subject',
        'channels_display', 'status_display', 'success_rate_display',
        'sent_at', 'created'
    ]
    list_filter = [
        'notification_type', 'status', 'created', 'sent_at',
        'channels_attempted', 'channels_successful'
    ]
    search_fields = [
        'patient__first_name', 'patient__last_name', 'patient__mrn',
        'subject', 'message_body', 'related_object_type', 'related_object_id'
    ]
    readonly_fields = [
        'patient', 'notification_type', 'subject', 'message_body',
        'channels_attempted', 'channels_successful', 'channels_failed',
        'status', 'sent_at', 'related_object_id', 'related_object_type',
        'channel_responses_display', 'success_rate_display', 'created', 'modified'
    ]
    
    date_hierarchy = 'created'
    
    fieldsets = (
        ('Notification Details', {
            'fields': (
                'patient',
                'notification_type',
                'subject',
                'message_body',
            )
        }),
        ('Channel Status', {
            'fields': (
                'status',
                'channels_attempted',
                'channels_successful',
                'channels_failed',
                'success_rate_display',
                'sent_at',
            )
        }),
        ('Channel Responses (Technical Details)', {
            'fields': ('channel_responses_display',),
            'classes': ('collapse',)
        }),
        ('Related Object', {
            'fields': (
                'related_object_type',
                'related_object_id',
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Disable manual creation - logs are auto-generated"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion for cleanup"""
        return request.user.is_superuser
    
    def patient_name(self, obj):
        """Display patient name with link"""
        if obj.patient:
            url = reverse('admin:hospital_patient_change', args=[obj.patient.id])
            return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
        return '-'
    patient_name.short_description = 'Patient'
    patient_name.admin_order_field = 'patient__last_name'
    
    def notification_type_display(self, obj):
        """Display notification type with icon"""
        icons = {
            'lab_result': '🧪',
            'appointment_reminder': '📅',
            'payment_reminder': '💰',
            'prescription_ready': '💊',
            'general': '📢'
        }
        icon = icons.get(obj.notification_type, '📬')
        return f"{icon} {obj.get_notification_type_display()}"
    notification_type_display.short_description = 'Type'
    notification_type_display.admin_order_field = 'notification_type'
    
    def channels_display(self, obj):
        """Display channels with status indicators"""
        html_parts = []
        
        for channel in obj.channels_attempted:
            if channel in obj.channels_successful:
                # Success - green
                html_parts.append(f'<span style="background-color: #28a745; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px; margin-right: 3px;">✓ {channel.upper()}</span>')
            elif channel in obj.channels_failed:
                # Failed - red
                html_parts.append(f'<span style="background-color: #dc3545; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px; margin-right: 3px;">✗ {channel.upper()}</span>')
            else:
                # Pending - gray
                html_parts.append(f'<span style="background-color: #6c757d; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px; margin-right: 3px;">⏳ {channel.upper()}</span>')
        
        return mark_safe(''.join(html_parts)) if html_parts else '-'
    channels_display.short_description = 'Channels'
    
    def status_display(self, obj):
        """Display status with color badge"""
        colors = {
            'pending': '#6c757d',
            'sent': '#28a745',
            'delivered': '#17a2b8',
            'failed': '#dc3545',
            'partial': '#ffc107'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 10px; border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display().upper()
        )
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'
    
    def success_rate_display(self, obj):
        """Display success rate with progress bar"""
        rate = obj.get_success_rate()
        
        if rate >= 100:
            color = '#28a745'
        elif rate >= 50:
            color = '#ffc107'
        else:
            color = '#dc3545'
        
        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0; border-radius: 10px; overflow: hidden;">'
            '<div style="width: {}%; background-color: {}; height: 20px; line-height: 20px; color: white; text-align: center; font-size: 11px; font-weight: bold;">'
            '{}%'
            '</div>'
            '</div>',
            rate, color, rate
        )
    success_rate_display.short_description = 'Success Rate'
    
    def channel_responses_display(self, obj):
        """Display detailed channel responses in readable format"""
        import json
        if not obj.channel_responses:
            return '-'
        
        # Format JSON for display
        formatted_json = json.dumps(obj.channel_responses, indent=2)
        return format_html(
            '<pre style="background-color: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; max-height: 400px;">{}</pre>',
            formatted_json
        )
    channel_responses_display.short_description = 'Channel Responses'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('patient')
    
    actions = ['resend_notification']
    
    def resend_notification(self, request, queryset):
        """Admin action to resend failed notifications"""
        from .services.multichannel_notification_service import multichannel_service
        
        resent_count = 0
        for log in queryset:
            if log.channels_failed and log.patient:
                # Resend only to failed channels
                try:
                    if log.notification_type == 'lab_result' and log.related_object_id:
                        from .models import LabResult
                        try:
                            lab_result = LabResult.objects.get(id=log.related_object_id)
                            multichannel_service.send_lab_result_notification(
                                lab_result,
                                force_channels=log.channels_failed
                            )
                            resent_count += 1
                        except LabResult.DoesNotExist:
                            pass
                except Exception as e:
                    self.message_user(request, f"Error resending to {log.patient.full_name}: {str(e)}", level='error')
        
        self.message_user(request, f"Successfully resent {resent_count} notifications", level='success')
    resend_notification.short_description = "Resend to Failed Channels"
























