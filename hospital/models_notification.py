"""
Multi-Channel Notification Preferences & Logs
Supports SMS, WhatsApp, and Email delivery for lab results and other notifications
"""
from django.db import models
from django.utils import timezone
from .models import BaseModel, Patient


class NotificationPreference(BaseModel):
    """
    Patient notification channel preferences
    Allows patients to choose how they want to receive lab results and other notifications
    """
    patient = models.OneToOneField(
        Patient, 
        on_delete=models.CASCADE, 
        related_name='notification_preference'
    )
    
    # Channel preferences (patient can enable multiple channels)
    sms_enabled = models.BooleanField(default=True, help_text="Receive SMS notifications")
    whatsapp_enabled = models.BooleanField(default=False, help_text="Receive WhatsApp messages")
    email_enabled = models.BooleanField(default=False, help_text="Receive email notifications")
    
    # Contact details for each channel (can override patient's default contact)
    sms_phone_number = models.CharField(
        max_length=17, 
        blank=True, 
        help_text="Phone number for SMS (uses patient phone if empty)"
    )
    whatsapp_phone_number = models.CharField(
        max_length=17, 
        blank=True, 
        help_text="WhatsApp number (uses SMS phone if empty)"
    )
    email_address = models.EmailField(
        blank=True, 
        help_text="Email address (uses patient email if empty)"
    )
    
    # Notification types preferences
    lab_results_notify = models.BooleanField(default=True, help_text="Notify when lab results are ready")
    appointment_notify = models.BooleanField(default=True, help_text="Appointment reminders")
    payment_notify = models.BooleanField(default=True, help_text="Payment reminders")
    prescription_notify = models.BooleanField(default=True, help_text="Prescription ready notifications")
    
    # Preferences
    send_full_results = models.BooleanField(
        default=False, 
        help_text="Include full lab results in notification (if false, just notify that results are ready)"
    )
    
    class Meta:
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences"
        ordering = ['-created']
    
    def __str__(self):
        channels = []
        if self.sms_enabled:
            channels.append("SMS")
        if self.whatsapp_enabled:
            channels.append("WhatsApp")
        if self.email_enabled:
            channels.append("Email")
        
        channel_str = ", ".join(channels) if channels else "None"
        return f"{self.patient.full_name} - Channels: {channel_str}"
    
    def get_active_channels(self):
        """Return list of enabled channels"""
        channels = []
        if self.sms_enabled:
            channels.append('sms')
        if self.whatsapp_enabled:
            channels.append('whatsapp')
        if self.email_enabled:
            channels.append('email')
        return channels
    
    def get_sms_number(self):
        """Get SMS phone number (uses patient phone if not specified)"""
        return self.sms_phone_number or self.patient.phone_number
    
    def get_whatsapp_number(self):
        """Get WhatsApp number (fallback to SMS number then patient phone)"""
        return self.whatsapp_phone_number or self.sms_phone_number or self.patient.phone_number
    
    def get_email(self):
        """Get email address (uses patient email if not specified)"""
        return self.email_address or self.patient.email


class MultiChannelNotificationLog(BaseModel):
    """
    Log for multi-channel notifications (tracks all channels used for a single notification event)
    """
    NOTIFICATION_TYPES = [
        ('lab_result', 'Lab Result Ready'),
        ('appointment_reminder', 'Appointment Reminder'),
        ('payment_reminder', 'Payment Reminder'),
        ('prescription_ready', 'Prescription Ready'),
        ('general', 'General Notification'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent (at least one channel)'),
        ('delivered', 'Delivered (at least one channel)'),
        ('failed', 'Failed (all channels)'),
        ('partial', 'Partial (some channels failed)'),
    ]
    
    patient = models.ForeignKey(
        Patient, 
        on_delete=models.CASCADE, 
        related_name='multi_notifications',
        null=True,
        blank=True
    )
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    subject = models.CharField(max_length=200, blank=True)
    message_body = models.TextField(help_text="Main notification message")
    
    # Channels attempted
    channels_attempted = models.JSONField(
        default=list, 
        help_text="List of channels tried: ['sms', 'whatsapp', 'email']"
    )
    channels_successful = models.JSONField(
        default=list,
        help_text="List of channels that succeeded"
    )
    channels_failed = models.JSONField(
        default=list,
        help_text="List of channels that failed"
    )
    
    # Overall status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Related object info
    related_object_id = models.CharField(max_length=100, blank=True)
    related_object_type = models.CharField(max_length=50, blank=True)
    
    # Detailed responses from each channel
    channel_responses = models.JSONField(
        default=dict,
        help_text="Detailed responses from each channel: {'sms': {...}, 'whatsapp': {...}, 'email': {...}}"
    )
    
    class Meta:
        verbose_name = "Multi-Channel Notification Log"
        verbose_name_plural = "Multi-Channel Notification Logs"
        ordering = ['-created']
        indexes = [
            models.Index(fields=['-created', 'notification_type']),
            models.Index(fields=['patient', '-created']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        patient_name = self.patient.full_name if self.patient else "Unknown"
        return f"{patient_name} - {self.get_notification_type_display()} ({self.status})"
    
    def mark_sent(self):
        """Mark notification as sent"""
        if not self.sent_at:
            self.sent_at = timezone.now()
        
        # Update status based on channel results
        if self.channels_successful and not self.channels_failed:
            self.status = 'sent'
        elif self.channels_successful and self.channels_failed:
            self.status = 'partial'
        elif not self.channels_successful and self.channels_failed:
            self.status = 'failed'
        
        self.save()
    
    def get_success_rate(self):
        """Calculate success rate percentage"""
        total = len(self.channels_attempted)
        if total == 0:
            return 0
        success = len(self.channels_successful)
        return round((success / total) * 100, 2)
























