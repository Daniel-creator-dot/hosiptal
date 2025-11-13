"""
World-Class Biometric Authentication System
Integrated with HR, Staff Management, and Attendance Tracking
Features: Face ID, Fingerprint, Liveness Detection, Anti-Spoofing
"""
import uuid
import hashlib
import json
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from .models import BaseModel, Staff
from decimal import Decimal


class BiometricType(BaseModel):
    """
    Types of biometric authentication supported
    """
    TYPE_CHOICES = [
        ('face', 'Face Recognition'),
        ('fingerprint', 'Fingerprint'),
        ('iris', 'Iris Scan'),
        ('voice', 'Voice Recognition'),
        ('palm', 'Palm Print'),
    ]
    
    name = models.CharField(max_length=50, choices=TYPE_CHOICES, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # Security settings
    requires_liveness_check = models.BooleanField(default=True)
    min_confidence_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('85.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Minimum confidence score for successful authentication (0-100)"
    )
    max_failed_attempts = models.IntegerField(default=3)
    lockout_duration_minutes = models.IntegerField(default=15)
    
    # Configuration
    config_json = models.JSONField(default=dict, blank=True, help_text="Algorithm-specific configuration")
    
    class Meta:
        ordering = ['name']
        verbose_name = "Biometric Type"
        verbose_name_plural = "Biometric Types"
    
    def __str__(self):
        return f"{self.display_name}"


class StaffBiometric(BaseModel):
    """
    Staff biometric enrollment data
    Stores encrypted biometric templates for authentication
    """
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='biometrics')
    biometric_type = models.ForeignKey(BiometricType, on_delete=models.PROTECT, related_name='staff_biometrics')
    
    # Biometric data (encrypted)
    template_hash = models.CharField(
        max_length=512, 
        unique=True,
        help_text="SHA-256 hash of biometric template for matching"
    )
    template_data = models.BinaryField(
        help_text="Encrypted biometric template data (face embeddings, fingerprint minutiae, etc.)"
    )
    template_metadata = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Metadata about template (capture date, device, quality score, etc.)"
    )
    
    # Enrollment details
    enrolled_at = models.DateTimeField(default=timezone.now)
    enrolled_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='biometric_enrollments'
    )
    enrollment_device = models.CharField(max_length=255, blank=True)
    enrollment_location = models.CharField(max_length=255, blank=True)
    
    # Quality metrics
    quality_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Quality score of biometric sample (0-100)"
    )
    
    # Multi-sample support (for improved accuracy)
    sample_count = models.IntegerField(default=1, help_text="Number of samples used in this template")
    
    # Status
    is_active = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False, help_text="Primary biometric for this type")
    expires_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Expiration date for re-enrollment (security best practice)"
    )
    
    # Security
    last_verified = models.DateTimeField(null=True, blank=True)
    verification_count = models.IntegerField(default=0)
    failed_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    
    # Backup/Recovery
    backup_method = models.CharField(
        max_length=50, 
        choices=[
            ('password', 'Password'),
            ('pin', 'PIN'),
            ('otp', 'One-Time Password'),
            ('none', 'None'),
        ],
        default='password'
    )
    
    class Meta:
        ordering = ['-enrolled_at']
        unique_together = [['staff', 'biometric_type', 'template_hash']]
        verbose_name = "Staff Biometric"
        verbose_name_plural = "Staff Biometrics"
        indexes = [
            models.Index(fields=['staff', 'biometric_type', 'is_active']),
            models.Index(fields=['template_hash']),
            models.Index(fields=['is_active', 'expires_at']),
        ]
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.biometric_type.display_name}"
    
    @property
    def is_expired(self):
        """Check if biometric template has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def is_locked(self):
        """Check if biometric is temporarily locked due to failed attempts"""
        if self.locked_until:
            if timezone.now() < self.locked_until:
                return True
            else:
                # Auto-unlock
                self.locked_until = None
                self.failed_attempts = 0
                self.save(update_fields=['locked_until', 'failed_attempts'])
        return False
    
    def lock_biometric(self):
        """Lock biometric after max failed attempts"""
        lockout_duration = self.biometric_type.lockout_duration_minutes
        self.locked_until = timezone.now() + timezone.timedelta(minutes=lockout_duration)
        self.save(update_fields=['locked_until'])
    
    def record_successful_verification(self):
        """Record successful biometric verification"""
        self.last_verified = timezone.now()
        self.verification_count += 1
        self.failed_attempts = 0
        self.locked_until = None
        self.save(update_fields=['last_verified', 'verification_count', 'failed_attempts', 'locked_until'])
    
    def record_failed_attempt(self):
        """Record failed biometric verification attempt"""
        self.failed_attempts += 1
        if self.failed_attempts >= self.biometric_type.max_failed_attempts:
            self.lock_biometric()
        else:
            self.save(update_fields=['failed_attempts'])


class BiometricAuthenticationLog(BaseModel):
    """
    Comprehensive audit log for all biometric authentication attempts
    Meets compliance requirements (HIPAA, GDPR, etc.)
    """
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='biometric_auth_logs')
    biometric = models.ForeignKey(
        StaffBiometric, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='auth_logs'
    )
    biometric_type = models.ForeignKey(BiometricType, on_delete=models.PROTECT, related_name='auth_logs')
    
    # Authentication details
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    
    STATUS_CHOICES = [
        ('success', 'Successful Authentication'),
        ('failed_match', 'Failed - No Match'),
        ('failed_quality', 'Failed - Poor Quality'),
        ('failed_liveness', 'Failed - Liveness Check'),
        ('failed_locked', 'Failed - Account Locked'),
        ('failed_expired', 'Failed - Template Expired'),
        ('failed_spoofing', 'Failed - Spoofing Detected'),
        ('failed_error', 'Failed - System Error'),
    ]
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, db_index=True)
    
    # Confidence and quality metrics
    confidence_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    quality_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    liveness_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Score indicating likelihood of live person vs photo/video"
    )
    
    # Device and location
    device_info = models.JSONField(default=dict, blank=True)
    device_id = models.CharField(max_length=255, blank=True)
    device_name = models.CharField(max_length=255, blank=True)
    
    # Location data
    location_name = models.CharField(max_length=255, blank=True, help_text="e.g., Front Desk, HR Office")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    
    # Integration with attendance
    created_attendance = models.BooleanField(default=False)
    attendance_record = models.ForeignKey(
        'Attendance',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='biometric_logs'
    )
    
    # Integration with login tracking
    created_login_record = models.BooleanField(default=False)
    login_record = models.ForeignKey(
        'LoginHistory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='biometric_logs'
    )
    
    # Security flags
    is_suspicious = models.BooleanField(default=False)
    spoofing_detected = models.BooleanField(default=False)
    multiple_face_detected = models.BooleanField(default=False)
    
    # Additional details
    failure_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    # Processing time (for performance monitoring)
    processing_time_ms = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Time taken to process authentication (milliseconds)"
    )
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Biometric Authentication Log"
        verbose_name_plural = "Biometric Authentication Logs"
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['staff', '-timestamp']),
            models.Index(fields=['status', '-timestamp']),
            models.Index(fields=['is_suspicious']),
        ]
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.get_status_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


class BiometricDevice(BaseModel):
    """
    Biometric capture devices registered in the system
    """
    DEVICE_TYPES = [
        ('face_camera', 'Face Recognition Camera'),
        ('fingerprint_scanner', 'Fingerprint Scanner'),
        ('iris_scanner', 'Iris Scanner'),
        ('palm_reader', 'Palm Print Reader'),
        ('multimodal', 'Multimodal Device'),
    ]
    
    device_name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=30, choices=DEVICE_TYPES)
    device_id = models.CharField(max_length=255, unique=True)
    serial_number = models.CharField(max_length=255, blank=True)
    
    # Supported biometric types
    supported_biometrics = models.ManyToManyField(BiometricType, related_name='devices')
    
    # Location
    location_name = models.CharField(max_length=255, help_text="e.g., Front Desk, Main Entrance")
    department = models.ForeignKey(
        'Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='biometric_devices'
    )
    
    # Network info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    mac_address = models.CharField(max_length=17, blank=True)
    
    # Device specs
    manufacturer = models.CharField(max_length=255, blank=True)
    model_number = models.CharField(max_length=255, blank=True)
    firmware_version = models.CharField(max_length=100, blank=True)
    sdk_version = models.CharField(max_length=100, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_online = models.BooleanField(default=False)
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    last_maintenance = models.DateField(null=True, blank=True)
    next_maintenance = models.DateField(null=True, blank=True)
    
    # Statistics
    total_authentications = models.IntegerField(default=0)
    successful_authentications = models.IntegerField(default=0)
    failed_authentications = models.IntegerField(default=0)
    
    # Configuration
    config_json = models.JSONField(default=dict, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['location_name', 'device_name']
        verbose_name = "Biometric Device"
        verbose_name_plural = "Biometric Devices"
    
    def __str__(self):
        return f"{self.device_name} - {self.location_name}"
    
    @property
    def success_rate(self):
        """Calculate authentication success rate"""
        if self.total_authentications > 0:
            return (self.successful_authentications / self.total_authentications) * 100
        return 0


class BiometricEnrollmentSession(BaseModel):
    """
    Tracks biometric enrollment sessions
    Multiple samples may be captured in one session for better accuracy
    """
    SESSION_STATUS = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='enrollment_sessions')
    biometric_type = models.ForeignKey(BiometricType, on_delete=models.PROTECT, related_name='enrollment_sessions')
    
    session_id = models.UUIDField(default=uuid.uuid4, unique=True)
    status = models.CharField(max_length=20, choices=SESSION_STATUS, default='in_progress')
    
    # Session details
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Device and operator
    device = models.ForeignKey(
        BiometricDevice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enrollment_sessions'
    )
    operator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='operated_enrollments'
    )
    
    # Samples captured
    samples_required = models.IntegerField(default=3, help_text="Number of samples needed")
    samples_captured = models.IntegerField(default=0)
    
    # Quality tracking
    average_quality_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Result
    biometric_created = models.ForeignKey(
        StaffBiometric,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enrollment_session'
    )
    
    # Notes
    notes = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-started_at']
        verbose_name = "Biometric Enrollment Session"
        verbose_name_plural = "Biometric Enrollment Sessions"
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.biometric_type.display_name} - {self.get_status_display()}"


class BiometricSecurityAlert(BaseModel):
    """
    Security alerts for biometric system anomalies
    """
    ALERT_TYPES = [
        ('multiple_failures', 'Multiple Failed Attempts'),
        ('spoofing_attempt', 'Spoofing Attempt Detected'),
        ('unusual_location', 'Authentication from Unusual Location'),
        ('unusual_time', 'Authentication at Unusual Time'),
        ('template_tampering', 'Template Tampering Detected'),
        ('device_offline', 'Biometric Device Offline'),
        ('device_malfunction', 'Device Malfunction'),
        ('unauthorized_enrollment', 'Unauthorized Enrollment Attempt'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='medium')
    
    # Related entities
    staff = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='biometric_alerts'
    )
    device = models.ForeignKey(
        BiometricDevice,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='security_alerts'
    )
    auth_log = models.ForeignKey(
        BiometricAuthenticationLog,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='security_alerts'
    )
    
    # Alert details
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    
    # Additional data
    metadata = models.JSONField(default=dict, blank=True)
    
    # Resolution
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_biometric_alerts'
    )
    resolution_notes = models.TextField(blank=True)
    
    # Notification
    notification_sent = models.BooleanField(default=False)
    notification_recipients = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Biometric Security Alert"
        verbose_name_plural = "Biometric Security Alerts"
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['severity', 'is_resolved']),
        ]
    
    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.get_severity_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class BiometricSystemSettings(BaseModel):
    """
    Global settings for biometric authentication system
    Singleton model - only one instance should exist
    """
    # General settings
    system_enabled = models.BooleanField(default=True)
    require_biometric_for_staff = models.BooleanField(
        default=False,
        help_text="Require all staff to enroll biometrics"
    )
    allow_password_fallback = models.BooleanField(
        default=True,
        help_text="Allow password login if biometric fails"
    )
    
    # Security settings
    enable_liveness_detection = models.BooleanField(default=True)
    enable_anti_spoofing = models.BooleanField(default=True)
    enable_multimodal_auth = models.BooleanField(
        default=False,
        help_text="Require multiple biometric types for high-security areas"
    )
    
    # Template management
    template_expiry_days = models.IntegerField(
        default=365,
        help_text="Days until biometric template expires (0 = never expires)"
    )
    auto_lock_after_failures = models.BooleanField(default=True)
    
    # Attendance integration
    auto_create_attendance = models.BooleanField(
        default=True,
        help_text="Automatically create attendance record on successful biometric login"
    )
    attendance_check_in_window_minutes = models.IntegerField(
        default=30,
        help_text="Minutes before/after shift start time to allow check-in"
    )
    
    # Alerts and notifications
    enable_security_alerts = models.BooleanField(default=True)
    alert_on_multiple_failures = models.BooleanField(default=True)
    alert_failure_threshold = models.IntegerField(default=5)
    alert_recipients_json = models.JSONField(
        default=list,
        blank=True,
        help_text="List of user IDs to receive security alerts"
    )
    
    # API settings
    face_recognition_provider = models.CharField(
        max_length=50,
        choices=[
            ('facenet', 'FaceNet (TensorFlow)'),
            ('dlib', 'Dlib'),
            ('opencv', 'OpenCV'),
            ('azure', 'Azure Face API'),
            ('aws', 'AWS Rekognition'),
            ('deepface', 'DeepFace'),
        ],
        default='deepface'
    )
    face_recognition_model = models.CharField(
        max_length=50,
        choices=[
            ('VGG-Face', 'VGG-Face'),
            ('Facenet', 'Facenet'),
            ('Facenet512', 'Facenet512'),
            ('OpenFace', 'OpenFace'),
            ('DeepFace', 'DeepFace'),
            ('DeepID', 'DeepID'),
            ('ArcFace', 'ArcFace'),
            ('Dlib', 'Dlib'),
        ],
        default='Facenet512'
    )
    
    # Performance
    enable_caching = models.BooleanField(default=True)
    cache_duration_seconds = models.IntegerField(default=300)
    
    # Audit and compliance
    log_retention_days = models.IntegerField(
        default=90,
        help_text="Days to retain biometric authentication logs"
    )
    require_consent_form = models.BooleanField(
        default=True,
        help_text="Require staff to sign biometric consent form"
    )
    
    class Meta:
        verbose_name = "Biometric System Settings"
        verbose_name_plural = "Biometric System Settings"
    
    def __str__(self):
        return "Biometric System Settings"
    
    def save(self, *args, **kwargs):
        """Ensure only one instance exists"""
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create singleton settings instance"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj








