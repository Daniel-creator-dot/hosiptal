"""
Consulting Room Management Models
Manages 8 consulting rooms and doctor-room assignments
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import BaseModel


class ConsultingRoom(BaseModel):
    """
    Consulting rooms in the hospital (8 rooms total)
    """
    ROOM_STATUS_CHOICES = [
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('maintenance', 'Under Maintenance'),
        ('reserved', 'Reserved'),
    ]
    
    room_number = models.CharField(
        max_length=20,
        unique=True,
        help_text="Room identifier (e.g., Room 1, Room 2, CR-01)"
    )
    room_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional room name (e.g., Cardiology, Pediatrics)"
    )
    department = models.ForeignKey(
        'Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='consulting_rooms',
        help_text="Primary department using this room"
    )
    status = models.CharField(
        max_length=20,
        choices=ROOM_STATUS_CHOICES,
        default='available',
        help_text="Current room status"
    )
    capacity = models.IntegerField(
        default=1,
        help_text="Number of doctors that can work in this room simultaneously"
    )
    equipment = models.TextField(
        blank=True,
        help_text="Available equipment in the room"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the room"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this room is active and available for use"
    )
    
    class Meta:
        ordering = ['room_number']
        verbose_name = 'Consulting Room'
        verbose_name_plural = 'Consulting Rooms'
        indexes = [
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['room_number']),
        ]
    
    def __str__(self):
        name_part = f" - {self.room_name}" if self.room_name else ""
        return f"{self.room_number}{name_part}"
    
    def is_available_now(self):
        """Check if room is currently available for assignment"""
        if not self.is_active or self.status != 'available':
            return False
        
        # Check if any active assignment exists
        now = timezone.now().date()
        active_assignments = DoctorRoomAssignment.objects.filter(
            room=self,
            assignment_date=now,
            is_active=True,
            is_deleted=False
        ).exists()
        
        return not active_assignments or self.capacity > 1
    
    @property
    def current_doctors(self):
        """Get list of doctors currently assigned to this room"""
        now = timezone.now().date()
        assignments = DoctorRoomAssignment.objects.filter(
            room=self,
            assignment_date=now,
            is_active=True,
            is_deleted=False
        ).select_related('doctor')
        
        return [assignment.doctor for assignment in assignments]


class DoctorRoomAssignment(BaseModel):
    """
    Track which room a doctor is using when they come to work
    Doctors can select their room at the start of their shift
    """
    doctor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='room_assignments',
        limit_choices_to={'groups__name': 'Doctor'},  # Only affects form choices, not validation
        help_text="Doctor assigned to this room"
    )
    room = models.ForeignKey(
        ConsultingRoom,
        on_delete=models.CASCADE,
        related_name='doctor_assignments',
        help_text="Consulting room assigned"
    )
    assignment_date = models.DateField(
        default=timezone.now,
        help_text="Date of assignment"
    )
    start_time = models.TimeField(
        default=timezone.now,
        help_text="Time when doctor started using the room"
    )
    end_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Time when doctor finished using the room"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this assignment is currently active"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this assignment"
    )
    
    class Meta:
        ordering = ['-assignment_date', '-start_time']
        verbose_name = 'Doctor Room Assignment'
        verbose_name_plural = 'Doctor Room Assignments'
        indexes = [
            models.Index(fields=['assignment_date', 'is_active']),
            models.Index(fields=['doctor', 'assignment_date', 'is_active']),
            models.Index(fields=['room', 'assignment_date', 'is_active']),
        ]
        # Prevent multiple active assignments for same doctor on same day
        constraints = [
            models.UniqueConstraint(
                fields=['doctor', 'assignment_date'],
                condition=models.Q(is_active=True, is_deleted=False),
                name='unique_active_doctor_assignment_per_day'
            )
        ]
    
    def __str__(self):
        doctor_name = self.doctor.get_full_name() or self.doctor.username
        return f"{doctor_name} - {self.room.room_number} ({self.assignment_date})"
    
    def clean(self):
        """Validate room assignment"""
        # Django ForeignKey automatically validates doctor exists, so we don't need to check here
        # Check if room is available
        if self.room and not self.room.is_available_now():
            if self.room.status != 'available':
                raise ValidationError(f"Room {self.room.room_number} is not available (Status: {self.room.get_status_display()})")
            
            # Check capacity
            if self.is_active and not self.pk:
                active_count = DoctorRoomAssignment.objects.filter(
                    room=self.room,
                    assignment_date=self.assignment_date,
                    is_active=True,
                    is_deleted=False
                ).exclude(pk=self.pk if self.pk else None).count()
                
                if active_count >= self.room.capacity:
                    raise ValidationError(f"Room {self.room.room_number} is at full capacity ({self.room.capacity} doctors)")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def end_assignment(self):
        """Mark assignment as ended"""
        self.is_active = False
        self.end_time = timezone.now().time()
        self.save(update_fields=['is_active', 'end_time', 'modified'])
    
    @property
    def duration_minutes(self):
        """Calculate duration in minutes"""
        if not self.start_time:
            return 0
        
        end = self.end_time or timezone.now().time()
        
        # Convert times to datetime for calculation
        start_dt = timezone.datetime.combine(self.assignment_date, self.start_time)
        end_dt = timezone.datetime.combine(self.assignment_date, end)
        
        # Handle next day
        if end_dt < start_dt:
            end_dt += timezone.timedelta(days=1)
        
        delta = end_dt - start_dt
        return int(delta.total_seconds() / 60)


class RoomAvailability(BaseModel):
    """
    Track room availability schedule (optional - for future scheduling features)
    """
    room = models.ForeignKey(
        ConsultingRoom,
        on_delete=models.CASCADE,
        related_name='availability_schedule'
    )
    day_of_week = models.IntegerField(
        choices=[
            (0, 'Monday'),
            (1, 'Tuesday'),
            (2, 'Wednesday'),
            (3, 'Thursday'),
            (4, 'Friday'),
            (5, 'Saturday'),
            (6, 'Sunday'),
        ],
        help_text="Day of week (0=Monday, 6=Sunday)"
    )
    start_time = models.TimeField(
        help_text="Available start time"
    )
    end_time = models.TimeField(
        help_text="Available end time"
    )
    is_available = models.BooleanField(
        default=True,
        help_text="Whether room is available during this time"
    )
    
    class Meta:
        ordering = ['room', 'day_of_week', 'start_time']
        verbose_name = 'Room Availability'
        verbose_name_plural = 'Room Availability Schedule'
        unique_together = [['room', 'day_of_week', 'start_time', 'end_time']]
    
    def __str__(self):
        return f"{self.room.room_number} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"


