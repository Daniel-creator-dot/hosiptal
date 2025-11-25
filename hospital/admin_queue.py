"""
Admin Interface for Queue Management Models
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models_queue import QueueEntry, QueueNotification, QueueConfiguration, HealthTip


@admin.register(QueueEntry)
class QueueEntryAdmin(admin.ModelAdmin):
    """Admin interface for queue entries"""
    
    list_display = [
        'queue_number_display',
        'patient_link',
        'department',
        'status_display',
        'priority_display',
        'position_display',
        'wait_time_display',
        'check_in_time',
    ]
    
    list_filter = [
        'queue_date',
        'department',
        'status',
        'priority',
        'no_show',
    ]
    
    search_fields = [
        'queue_number',
        'patient__first_name',
        'patient__last_name',
        'patient__mrn',
    ]
    
    readonly_fields = [
        'queue_number',
        'queue_date',
        'sequence_number',
        'check_in_time',
        'called_time',
        'started_time',
        'completed_time',
        'actual_wait_minutes',
        'consultation_duration_minutes',
        'sms_sent_at',
        'notification_count',
    ]
    
    fieldsets = (
        ('Queue Information', {
            'fields': (
                'queue_number',
                'queue_date',
                'sequence_number',
                'status',
                'priority',
            )
        }),
        ('Patient & Assignment', {
            'fields': (
                'patient',
                'encounter',
                'department',
                'assigned_doctor',
                'room_number',
            )
        }),
        ('Timestamps', {
            'fields': (
                'check_in_time',
                'called_time',
                'started_time',
                'completed_time',
            )
        }),
        ('Performance Metrics', {
            'fields': (
                'estimated_wait_minutes',
                'actual_wait_minutes',
                'consultation_duration_minutes',
            )
        }),
        ('Notifications', {
            'fields': (
                'sms_sent',
                'sms_sent_at',
                'notification_count',
                'last_notification_sent',
            )
        }),
        ('Additional', {
            'fields': (
                'notes',
                'no_show',
            )
        }),
    )
    
    def queue_number_display(self, obj):
        """Display queue number with icon"""
        icon = '🎫'
        return format_html(
            '<strong style="font-size: 1.1em;">{} {}</strong>',
            icon, obj.queue_number
        )
    queue_number_display.short_description = 'Queue #'
    
    def patient_link(self, obj):
        """Link to patient detail"""
        if obj.patient:
            url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
            return format_html(
                '<a href="{}">{}</a><br><small>{}</small>',
                url,
                obj.patient.full_name,
                obj.patient.mrn
            )
        return '-'
    patient_link.short_description = 'Patient'
    
    def status_display(self, obj):
        """Display status with color"""
        colors = {
            'checked_in': '#17a2b8',  # Blue
            'called': '#ffc107',      # Yellow
            'in_progress': '#28a745', # Green
            'completed': '#6c757d',   # Gray
            'no_show': '#dc3545',     # Red
            'cancelled': '#6c757d',   # Gray
        }
        color = colors.get(obj.status, '#000')
        return format_html(
            '<span style="color: {}; font-weight: 600;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def priority_display(self, obj):
        """Display priority with icon"""
        return format_html(
            '<span>{}</span>',
            obj.get_priority_display()
        )
    priority_display.short_description = 'Priority'
    
    def position_display(self, obj):
        """Display current position in queue"""
        if obj.status in ['checked_in', 'called']:
            from hospital.services.queue_service import queue_service
            position = queue_service.get_position_in_queue(obj)
            return format_html(
                '<strong>#{}</strong>',
                position
            )
        return '-'
    position_display.short_description = 'Position'
    
    def wait_time_display(self, obj):
        """Display wait time"""
        if obj.actual_wait_minutes:
            return f"{obj.actual_wait_minutes} mins"
        elif obj.status in ['checked_in', 'called']:
            current_wait = obj.get_current_wait_time()
            return format_html(
                '<span style="color: #dc3545;">{} mins</span>',
                current_wait
            )
        return '-'
    wait_time_display.short_description = 'Wait Time'


@admin.register(QueueNotification)
class QueueNotificationAdmin(admin.ModelAdmin):
    """Admin interface for queue notifications"""
    
    list_display = [
        'queue_entry',
        'notification_type_display',
        'channel',
        'sent_at',
        'delivered_status',
    ]
    
    list_filter = [
        'notification_type',
        'channel',
        'delivered',
        'sent_at',
    ]
    
    search_fields = [
        'queue_entry__queue_number',
        'queue_entry__patient__first_name',
        'queue_entry__patient__last_name',
        'message_content',
    ]
    
    readonly_fields = [
        'queue_entry',
        'notification_type',
        'channel',
        'message_content',
        'sent_at',
        'delivered',
        'read',
        'external_id',
        'error_message',
    ]
    
    def notification_type_display(self, obj):
        """Display notification type with icon"""
        icons = {
            'check_in': '✅',
            'progress_update': '📊',
            'ready': '📢',
            'no_show_warning': '⚠️',
            'completed': '✓',
        }
        icon = icons.get(obj.notification_type, '📱')
        return format_html(
            '{} {}',
            icon,
            obj.get_notification_type_display()
        )
    notification_type_display.short_description = 'Type'
    
    def delivered_status(self, obj):
        """Display delivery status"""
        if obj.delivered:
            return format_html(
                '<span style="color: #28a745;">✓ Delivered</span>'
            )
        else:
            return format_html(
                '<span style="color: #dc3545;">✗ Failed</span>'
            )
    delivered_status.short_description = 'Status'


@admin.register(QueueConfiguration)
class QueueConfigurationAdmin(admin.ModelAdmin):
    """Admin interface for queue configuration"""
    
    list_display = [
        'department',
        'queue_prefix',
        'enable_queue',
        'average_consultation_minutes',
        'notification_settings',
    ]
    
    list_filter = [
        'enable_queue',
        'send_check_in_sms',
        'send_progress_updates',
        'send_ready_notification',
    ]
    
    fieldsets = (
        ('Department', {
            'fields': (
                'department',
                'queue_prefix',
                'enable_queue',
            )
        }),
        ('Timing Settings', {
            'fields': (
                'average_consultation_minutes',
                'buffer_time_minutes',
            ),
            'description': 'Used to calculate estimated wait times'
        }),
        ('Notification Settings', {
            'fields': (
                'send_check_in_sms',
                'send_progress_updates',
                'send_ready_notification',
                'notification_interval_patients',
            ),
            'description': 'Configure automatic SMS/WhatsApp notifications'
        }),
        ('Display Settings', {
            'fields': (
                'show_on_public_display',
                'display_upcoming_count',
                'default_room_number',
            ),
            'description': 'Settings for public TV displays and room assignment'
        }),
    )
    
    def notification_settings(self, obj):
        """Display notification settings summary"""
        settings_list = []
        if obj.send_check_in_sms:
            settings_list.append('Check-in')
        if obj.send_progress_updates:
            settings_list.append('Progress')
        if obj.send_ready_notification:
            settings_list.append('Ready')
        
        if settings_list:
            return format_html(
                '<span style="color: #28a745;">✓ {}</span>',
                ', '.join(settings_list)
            )
        return format_html(
            '<span style="color: #dc3545;">✗ Disabled</span>'
        )
    notification_settings.short_description = 'Notifications'


@admin.register(HealthTip)
class HealthTipAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'audience', 'is_active', 'display_order', 'start_date', 'end_date']
    list_filter = ['audience', 'is_active', 'category']
    search_fields = ['title', 'message']
    ordering = ['display_order', 'title']




















