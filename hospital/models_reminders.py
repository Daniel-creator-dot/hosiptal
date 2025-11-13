"""
Birthday and Reminder Models
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from model_utils.models import TimeStampedModel
from .models import BaseModel, Staff, Patient


class BirthdayReminder(BaseModel):
    """Track birthday reminders for staff and patients"""
    REMINDER_TYPES = [
        ('staff', 'Staff'),
        ('patient', 'Patient'),
    ]
    
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPES)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, null=True, blank=True, related_name='birthday_reminders')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, null=True, blank=True, related_name='birthday_reminders')
    
    birthday_date = models.DateField()
    reminder_date = models.DateField()  # When to send reminder
    notified = models.BooleanField(default=False)
    notified_at = models.DateTimeField(null=True, blank=True)
    notification_sent_to = models.TextField(blank=True)  # Comma-separated list of recipients
    
    class Meta:
        ordering = ['reminder_date']
        unique_together = [['reminder_type', 'staff', 'birthday_date'], ['reminder_type', 'patient', 'birthday_date']]
    
    def __str__(self):
        if self.staff:
            return f"Birthday Reminder: {self.staff.user.get_full_name()} - {self.birthday_date}"
        elif self.patient:
            return f"Birthday Reminder: {self.patient.full_name} - {self.birthday_date}"
        return f"Birthday Reminder: {self.birthday_date}"


class SMSNotification(BaseModel):
    """Track SMS notifications sent"""
    NOTIFICATION_TYPES = [
        ('birthday', 'Birthday'),
        ('appointment', 'Appointment'),
        ('lab_result', 'Lab Result'),
        ('payment', 'Payment'),
        ('reminder', 'Reminder'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('delivered', 'Delivered'),
    ]
    
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    recipient_number = models.CharField(max_length=17)
    recipient_name = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Optional relationships
    staff = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.recipient_number} ({self.get_status_display()})"

