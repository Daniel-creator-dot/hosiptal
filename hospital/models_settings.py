"""
Hospital Settings and Configuration Models
"""
from django.db import models
from .models import BaseModel


class HospitalSettings(models.Model):
    """
    Hospital Configuration - Singleton model (only one instance)
    """
    # Basic Information
    hospital_name = models.CharField(max_length=200, default="Hospital Management System")
    hospital_tagline = models.CharField(max_length=200, blank=True, help_text="E.g., 'Quality Healthcare for All'")
    
    # Contact Information
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default="Ghana")
    
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    
    # Logo and Branding
    logo = models.ImageField(upload_to='hospital_settings/', blank=True, null=True, help_text="Hospital logo for reports and letterheads")
    logo_width = models.IntegerField(default=150, help_text="Logo width in pixels for reports")
    logo_height = models.IntegerField(default=150, help_text="Logo height in pixels for reports")
    
    # Report Settings
    report_header_color = models.CharField(max_length=7, default="#2196F3", help_text="Hex color code for report headers")
    report_footer_text = models.TextField(blank=True, help_text="Footer text for printed reports")
    
    # Laboratory Settings
    lab_department_name = models.CharField(max_length=200, default="Clinical Laboratory")
    lab_phone = models.CharField(max_length=50, blank=True)
    lab_email = models.EmailField(blank=True)
    lab_accreditation = models.CharField(max_length=200, blank=True, help_text="E.g., ISO 15189:2012")
    lab_license_number = models.CharField(max_length=100, blank=True)
    
    # Radiology Settings
    radiology_department_name = models.CharField(max_length=200, default="Radiology Department")
    radiology_phone = models.CharField(max_length=50, blank=True)
    radiology_email = models.EmailField(blank=True)
    
    # Pharmacy Settings
    pharmacy_department_name = models.CharField(max_length=200, default="Hospital Pharmacy")
    pharmacy_phone = models.CharField(max_length=50, blank=True)
    pharmacy_license_number = models.CharField(max_length=100, blank=True)
    
    # System Settings
    currency = models.CharField(max_length=10, default="GHS")
    currency_symbol = models.CharField(max_length=5, default="₵")
    date_format = models.CharField(max_length=20, default="%d/%m/%Y", help_text="Python date format")
    time_format = models.CharField(max_length=20, default="%H:%M", help_text="Python time format")
    
    # Metadata
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Hospital Settings"
        verbose_name_plural = "Hospital Settings"
    
    def __str__(self):
        return self.hospital_name
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists (Singleton pattern)
        if not self.pk and HospitalSettings.objects.exists():
            # If trying to create new instance, get the existing one
            existing = HospitalSettings.objects.first()
            self.pk = existing.pk
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create hospital settings"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings
























