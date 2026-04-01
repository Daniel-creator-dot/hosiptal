"""
Queue Management Models
World-class patient queue and ticketing system
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .models import BaseModel


# Queue Priority Levels
PRIORITY_CHOICES = [
    (1, '🔴 Emergency - Immediate'),
    (2, '🟠 Urgent - High Priority'),
    (3, '🟢 Normal - Standard'),
    (4, '🔵 Follow-up - Lower Priority'),
]

# Queue Status
QUEUE_STATUS_CHOICES = [
    ('checked_in', '✅ Checked In - Waiting'),
    ('called', '📢 Called - Please Proceed'),
    ('vitals_completed', '🩺 Vitals Done - Awaiting Consultation'),
    ('in_progress', '👨‍⚕️ In Consultation'),
    ('completed', '✓ Completed'),
    ('no_show', '❌ No Show'),
    ('cancelled', '🚫 Cancelled'),
]

# Notification Types
NOTIFICATION_TYPE_CHOICES = [
    ('check_in', 'Check-in Confirmation'),
    ('progress_update', 'Queue Progress Update'),
    ('ready', 'Ready for Consultation'),
    ('no_show_warning', 'No Show Warning'),
    ('completed', 'Consultation Completed'),
]

# Notification Channels
CHANNEL_CHOICES = [
    ('sms', 'SMS'),
    ('whatsapp', 'WhatsApp'),
    ('email', 'Email'),
]


class QueueEntry(BaseModel):
    """
    Patient queue entry for daily visit management
    Each patient gets a unique queue number when they check in
    """
    
    # Queue Identification
    queue_number = models.CharField(
        max_length=20, 
        unique=True,
        help_text="Unique queue number (e.g., OPD-042)"
    )
    queue_date = models.DateField(
        auto_now_add=True,
        help_text="Date when queue entry was created"
    )
    sequence_number = models.IntegerField(
        help_text="Daily sequence number (resets daily)"
    )
    
    # Relationships
    patient = models.ForeignKey(
        'Patient',
        on_delete=models.CASCADE,
        related_name='queue_entries'
    )
    encounter = models.ForeignKey(
        'Encounter',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='queue_entry'
    )
    department = models.ForeignKey(
        'Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='queue_entries'
    )
    assigned_doctor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_queue_entries',
        limit_choices_to={'groups__name': 'Doctor'}
    )
    
    # Queue Management
    priority = models.IntegerField(
        choices=PRIORITY_CHOICES,
        default=3,
        help_text="Queue priority (1=Emergency, 3=Normal)"
    )
    status = models.CharField(
        max_length=20,
        choices=QUEUE_STATUS_CHOICES,
        default='checked_in'
    )
    
    # Timestamps
    check_in_time = models.DateTimeField(
        auto_now_add=True,
        help_text="When patient checked in"
    )
    called_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When patient was called"
    )
    started_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When consultation started"
    )
    completed_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When consultation completed"
    )
    
    # Wait Time Tracking
    estimated_wait_minutes = models.IntegerField(
        default=0,
        help_text="Estimated wait time in minutes"
    )
    actual_wait_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Actual wait time from check-in to consultation"
    )
    consultation_duration_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Duration of consultation in minutes"
    )
    
    # Notification Tracking
    sms_sent = models.BooleanField(
        default=False,
        help_text="Whether check-in SMS was sent"
    )
    sms_sent_at = models.DateTimeField(
        null=True,
        blank=True
    )
    last_notification_sent = models.DateTimeField(
        null=True,
        blank=True
    )
    notification_count = models.IntegerField(
        default=0,
        help_text="Number of notifications sent"
    )
    
    # Room Assignment
    room_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Consultation room assignment"
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        help_text="Additional notes or special instructions"
    )
    no_show = models.BooleanField(
        default=False,
        help_text="Patient did not show up when called"
    )
    
    class Meta:
        ordering = ['queue_date', 'priority', 'sequence_number']
        verbose_name = 'Queue Entry'
        verbose_name_plural = 'Queue Entries'
        indexes = [
            models.Index(fields=['queue_date', 'department', 'status']),
            models.Index(fields=['queue_number']),
            models.Index(fields=['queue_date', 'status']),
        ]
    
    def __str__(self):
        return f"{self.queue_number} - {self.patient.full_name} ({self.get_status_display()})"
    
    @property
    def is_waiting(self):
        """Check if patient is still waiting"""
        return self.status in ['checked_in', 'called', 'vitals_completed']
    
    @property
    def is_active(self):
        """Check if queue entry is active (not completed/cancelled)"""
        return self.status not in ['completed', 'cancelled', 'no_show']
    
    def get_current_wait_time(self):
        """Calculate current wait time in minutes"""
        if self.status == 'completed' and self.actual_wait_minutes:
            return self.actual_wait_minutes
        
        if self.check_in_time:
            now = timezone.now()
            wait_seconds = (now - self.check_in_time).total_seconds()
            return int(wait_seconds / 60)
        
        return 0

    @property
    def display_ticket_number(self):
        """
        Patient-facing ticket for screens/SMS (e.g. 042).

        Prefer the sequence segment in queue_number (OPD-042 or OPD-042-suffix) so
        SMS matches stickers/boards even when sequence_number was wrong (legacy rows,
        manual creates). Fall back to sequence_number, then digit scraping.
        """
        raw = str(self.queue_number or '').strip()
        if raw:
            parts = raw.split('-')
            if len(parts) >= 2 and parts[1].isdigit():
                n = int(parts[1])
                if 0 < n < 1_000_000:
                    return f"{n:03d}"
            # Non-standard queue_number (e.g. UUID suffix): prefer sequence over digit scraping
            try:
                seq = int(self.sequence_number or 0)
                if seq > 0:
                    return f"{seq:03d}"
            except Exception:
                pass
            digits = ''.join(ch for ch in raw if ch.isdigit())
            if digits:
                return digits[-3:] if len(digits) > 3 else digits
            return raw
        try:
            seq = int(self.sequence_number or 0)
            if seq > 0:
                return f"{seq:03d}"
        except Exception:
            pass
        return '---'

    def get_display_clinician_name(self):
        """Name for public queue boards: assigned doctor, else encounter provider."""
        if self.assigned_doctor_id:
            u = self.assigned_doctor
            return (u.get_full_name() or u.username or '').strip()
        try:
            enc = self.encounter
            if enc and getattr(enc, 'provider_id', None):
                prov = enc.provider
                user = getattr(prov, 'user', None)
                if user:
                    return (user.get_full_name() or user.username or '').strip()
                parts = [
                    getattr(prov, 'first_name', None) or '',
                    getattr(prov, 'last_name', None) or '',
                ]
                name = ' '.join(p for p in parts if p).strip()
                if name:
                    return name
        except Exception:
            pass
        return ''


class QueueNotification(BaseModel):
    """
    Track all queue-related notifications sent to patients
    """
    
    queue_entry = models.ForeignKey(
        'QueueEntry',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    notification_type = models.CharField(
        max_length=30,
        choices=NOTIFICATION_TYPE_CHOICES
    )
    
    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        default='sms'
    )
    
    message_content = models.TextField(
        help_text="Full message content sent"
    )
    
    sent_at = models.DateTimeField(
        auto_now_add=True
    )
    
    delivered = models.BooleanField(
        default=False,
        help_text="Whether message was delivered"
    )
    
    read = models.BooleanField(
        default=False,
        help_text="Whether message was read (if trackable)"
    )
    
    external_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="External provider message ID (for tracking)"
    )
    
    error_message = models.TextField(
        blank=True,
        help_text="Error message if notification failed"
    )
    
    class Meta:
        ordering = ['-sent_at']
        verbose_name = 'Queue Notification'
        verbose_name_plural = 'Queue Notifications'
    
    def __str__(self):
        return f"{self.queue_entry.queue_number} - {self.get_notification_type_display()} via {self.channel}"


class QueueConfiguration(BaseModel):
    """
    Configuration settings for queue management per department
    """
    
    department = models.OneToOneField(
        'Department',
        on_delete=models.CASCADE,
        related_name='queue_config'
    )
    
    # Queue Settings
    queue_prefix = models.CharField(
        max_length=5,
        default='OPD',
        help_text="Prefix for queue numbers (e.g., OPD, EMG, SPL)"
    )
    
    enable_queue = models.BooleanField(
        default=True,
        help_text="Enable queue management for this department"
    )
    
    # Timing Settings
    average_consultation_minutes = models.IntegerField(
        default=15,
        help_text="Average consultation time in minutes"
    )
    
    buffer_time_minutes = models.IntegerField(
        default=5,
        help_text="Buffer time between consultations"
    )
    
    # Notification Settings
    send_check_in_sms = models.BooleanField(
        default=True,
        help_text="Send SMS on check-in"
    )
    
    send_progress_updates = models.BooleanField(
        default=True,
        help_text="Send periodic queue progress updates"
    )
    
    send_ready_notification = models.BooleanField(
        default=True,
        help_text="Send notification when patient's turn is ready"
    )
    
    notification_interval_patients = models.IntegerField(
        default=5,
        help_text="Send update every N patients (e.g., every 5 patients)"
    )
    
    # Display Settings
    show_on_public_display = models.BooleanField(
        default=True,
        help_text="Show queue on public TV displays"
    )
    
    display_upcoming_count = models.IntegerField(
        default=5,
        help_text="Number of upcoming patients to show on display"
    )
    
    # Room Assignment
    default_room_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Default consultation room"
    )
    
    class Meta:
        verbose_name = 'Queue Configuration'
        verbose_name_plural = 'Queue Configurations'
    
    def __str__(self):
        return f"Queue Config - {self.department.name} ({self.queue_prefix})"
    
    def get_estimated_wait(self, position):
        """Calculate estimated wait time based on position"""
        time_per_patient = self.average_consultation_minutes + self.buffer_time_minutes
        return time_per_patient * position


class HealthTip(BaseModel):
    """
    Rotating health tips displayed on the public queue screen.
    """
    AUDIENCE_CHOICES = [
        ('general', 'General'),
        ('opd', 'Outpatient'),
        ('pediatrics', 'Pediatrics'),
        ('maternity', 'Maternity'),
        ('wellness', 'Wellness'),
    ]

    title = models.CharField(max_length=120)
    message = models.TextField()
    category = models.CharField(max_length=50, blank=True)
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default='general')
    icon = models.CharField(max_length=50, blank=True, help_text="Optional emoji or icon class")
    accent_color = models.CharField(max_length=20, default='#10B981')
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['display_order', 'title']
        verbose_name = 'Health Tip'
        verbose_name_plural = 'Health Tips'

    def __str__(self):
        return self.title

    def is_visible(self, reference_date=None):
        reference_date = reference_date or timezone.now().date()
        if not self.is_active:
            return False
        if self.start_date and reference_date < self.start_date:
            return False
        if self.end_date and reference_date > self.end_date:
            return False
        return True

