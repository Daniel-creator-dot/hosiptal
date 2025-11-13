"""
Admin configuration for Reminders and SMS
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models_reminders import BirthdayReminder, SMSNotification


@admin.register(BirthdayReminder)
class BirthdayReminderAdmin(admin.ModelAdmin):
    list_display = ['reminder_type_badge', 'recipient_link', 'birthday_date', 'reminder_date', 'notified_badge', 'created']
    list_filter = ['reminder_type', 'notified', 'reminder_date']
    search_fields = ['staff__user__first_name', 'staff__user__last_name', 'patient__first_name', 'patient__last_name']
    ordering = ['reminder_date']
    readonly_fields = ['notified_at']
    
    def reminder_type_badge(self, obj):
        color = 'info' if obj.reminder_type == 'staff' else 'success'
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_reminder_type_display())
    reminder_type_badge.short_description = 'Type'
    
    def recipient_link(self, obj):
        if obj.staff:
            url = reverse('admin:hospital_staff_change', args=[obj.staff.pk])
            return format_html('<a href="{}">{}</a>', url, obj.staff.user.get_full_name())
        elif obj.patient:
            url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
            return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
        return "-"
    recipient_link.short_description = 'Recipient'
    
    def notified_badge(self, obj):
        if obj.notified:
            return format_html('<span class="badge bg-success">✓ Notified</span>')
        return format_html('<span class="badge bg-warning">Pending</span>')
    notified_badge.short_description = 'Status'


@admin.register(SMSNotification)
class SMSNotificationAdmin(admin.ModelAdmin):
    list_display = ['notification_type_badge', 'recipient_name', 'recipient_number', 'status_badge', 'sent_at', 'created']
    list_filter = ['notification_type', 'status', 'sent_at']
    search_fields = ['recipient_name', 'recipient_number', 'message']
    ordering = ['-created']
    readonly_fields = ['sent_at', 'delivered_at']
    
    def notification_type_badge(self, obj):
        colors = {
            'birthday': 'success',
            'appointment': 'info',
            'lab_result': 'primary',
            'payment': 'warning',
            'reminder': 'secondary',
            'other': 'dark',
        }
        color = colors.get(obj.notification_type, 'secondary')
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_notification_type_display())
    notification_type_badge.short_description = 'Type'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'warning',
            'sent': 'info',
            'failed': 'danger',
            'delivered': 'success',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_status_display())
    status_badge.short_description = 'Status'

