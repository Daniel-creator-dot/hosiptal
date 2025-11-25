"""
Login Location Tracking & Security Monitoring
Tracks where users login from with accurate geolocation
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .models import BaseModel, Staff


class LoginHistory(BaseModel):
    """
    Complete login history with location tracking
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    staff = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='login_history')
    
    # Login details
    login_time = models.DateTimeField(default=timezone.now)
    logout_time = models.DateTimeField(null=True, blank=True)
    session_key = models.CharField(max_length=255, blank=True)
    
    # IP and Network Info
    ip_address = models.GenericIPAddressField(help_text="User's IP address")
    
    # Geolocation Data
    country = models.CharField(max_length=100, blank=True)
    country_code = models.CharField(max_length=10, blank=True)
    region = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    timezone_name = models.CharField(max_length=100, blank=True)
    
    # ISP Info
    isp = models.CharField(max_length=255, blank=True, help_text="Internet Service Provider")
    organization = models.CharField(max_length=255, blank=True)
    
    # Device & Browser Info
    user_agent = models.TextField(blank=True)
    browser = models.CharField(max_length=100, blank=True)
    browser_version = models.CharField(max_length=50, blank=True)
    os = models.CharField(max_length=100, blank=True)
    os_version = models.CharField(max_length=50, blank=True)
    device_type = models.CharField(
        max_length=20,
        choices=[
            ('desktop', 'Desktop'),
            ('mobile', 'Mobile'),
            ('tablet', 'Tablet'),
            ('unknown', 'Unknown')
        ],
        default='unknown'
    )
    device_name = models.CharField(max_length=100, blank=True)
    
    # Login Status
    STATUS_CHOICES = [
        ('success', 'Successful Login'),
        ('failed', 'Failed Login'),
        ('blocked', 'Blocked Login'),
        ('suspicious', 'Suspicious Activity'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='success')
    
    # Security Flags
    is_suspicious = models.BooleanField(default=False)
    is_new_location = models.BooleanField(default=False)
    is_new_device = models.BooleanField(default=False)
    
    # Failure details (if failed login)
    failure_reason = models.CharField(max_length=255, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Geolocation API response (for debugging)
    geo_api_response = models.JSONField(null=True, blank=True)
    
    class Meta:
        ordering = ['-login_time']
        verbose_name = "Login History"
        verbose_name_plural = "Login History"
        indexes = [
            models.Index(fields=['-login_time']),
            models.Index(fields=['user', '-login_time']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['is_suspicious']),
        ]
    
    def __str__(self):
        location = f"{self.city}, {self.country}" if self.city and self.country else self.ip_address
        return f"{self.user.username} - {location} - {self.login_time.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def location_display(self):
        """Human-readable location"""
        if self.city and self.country:
            return f"{self.city}, {self.region}, {self.country}"
        elif self.country:
            return self.country
        else:
            return "Unknown Location"
    
    @property
    def session_duration(self):
        """Calculate session duration in minutes"""
        if self.logout_time:
            duration = (self.logout_time - self.login_time).total_seconds() / 60
            return int(duration)
        return None


class SecurityAlert(BaseModel):
    """
    Security alerts for suspicious login activities
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='security_alerts')
    login_history = models.ForeignKey(LoginHistory, on_delete=models.CASCADE, related_name='security_alerts', null=True, blank=True)
    
    # Alert details
    alert_time = models.DateTimeField(default=timezone.now)
    alert_type = models.CharField(
        max_length=50,
        choices=[
            ('new_location', 'Login from New Location'),
            ('new_device', 'Login from New Device'),
            ('multiple_failures', 'Multiple Failed Login Attempts'),
            ('unusual_time', 'Login at Unusual Time'),
            ('impossible_travel', 'Impossible Travel Detected'),
            ('suspicious_ip', 'Suspicious IP Address'),
        ]
    )
    severity = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical')
        ],
        default='medium'
    )
    
    # Details
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    
    # Status
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_alerts')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # Notification
    notification_sent = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-alert_time']
        verbose_name = "Security Alert"
        verbose_name_plural = "Security Alerts"
    
    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.user.username} - {self.alert_time.strftime('%Y-%m-%d %H:%M')}"


class TrustedLocation(BaseModel):
    """
    User's trusted locations
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trusted_locations')
    
    # Location
    location_name = models.CharField(max_length=255, help_text="e.g., Home, Office, Hospital")
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    
    # IP range (optional)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    ip_range_start = models.GenericIPAddressField(null=True, blank=True)
    ip_range_end = models.GenericIPAddressField(null=True, blank=True)
    
    # Coordinates (approximate)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    radius_km = models.DecimalField(max_digits=6, decimal_places=2, default=10, help_text="Trusted radius in km")
    
    # Status
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-last_used', 'location_name']
        verbose_name = "Trusted Location"
        verbose_name_plural = "Trusted Locations"
    
    def __str__(self):
        return f"{self.user.username} - {self.location_name}"


class TrustedDevice(BaseModel):
    """
    User's trusted devices
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trusted_devices')
    
    # Device identification
    device_name = models.CharField(max_length=255, help_text="e.g., iPhone 12, Windows PC")
    device_fingerprint = models.CharField(max_length=255, unique=True, help_text="Unique device identifier")
    
    # Device details
    os = models.CharField(max_length=100, blank=True)
    browser = models.CharField(max_length=100, blank=True)
    device_type = models.CharField(max_length=20, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    first_seen = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-last_seen']
        verbose_name = "Trusted Device"
        verbose_name_plural = "Trusted Devices"
    
    def __str__(self):
        return f"{self.user.username} - {self.device_name}"





















