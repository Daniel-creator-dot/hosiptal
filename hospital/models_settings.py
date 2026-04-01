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
    
    # ========== Printer & POS Receipt Settings ==========
    # POS / Thermal receipt (payment receipts at cashier)
    pos_receipt_width_mm = models.PositiveSmallIntegerField(
        default=80,
        help_text="Receipt paper width in mm. Standard: 80mm (common) or 58mm (narrow)."
    )
    pos_receipt_printable_width_mm = models.FloatField(
        default=78,
        help_text="Printable area width in mm. Use 78 for 80mm paper to fill width; 72 if content is cut off."
    )
    pos_receipt_length_mm = models.PositiveIntegerField(
        default=810,
        help_text="Receipt length in mm. Standard default 810 for 80×810mm thermal roll."
    )
    pos_receipt_font_size_body = models.PositiveSmallIntegerField(
        default=12,
        help_text="Body text size in px for POS receipt (e.g. 12–14 for readable print)."
    )
    pos_receipt_font_size_header = models.PositiveSmallIntegerField(
        default=14,
        help_text="Header/title font size in px for POS receipt (e.g. 14–16 for readable print)."
    )
    pos_receipt_font_size_footer = models.PositiveSmallIntegerField(
        default=10,
        help_text="Footer text size in px for POS receipt (e.g. 9–11 for readable print)."
    )
    pos_receipt_margin_mm = models.PositiveSmallIntegerField(
        default=4,
        help_text="Left/right margin in mm for POS receipt."
    )
    pos_receipt_padding_mm = models.PositiveSmallIntegerField(
        default=3,
        help_text="Inner padding in mm for POS receipt."
    )
    pos_receipt_show_qr = models.BooleanField(
        default=True,
        help_text="Show QR code on POS receipt for verification."
    )
    pos_receipt_qr_size_px = models.PositiveSmallIntegerField(
        default=56,
        help_text="QR code size in pixels on POS receipt (e.g. 50–64)."
    )
    # General printing
    default_print_copies = models.PositiveSmallIntegerField(
        default=1,
        help_text="Default number of copies when printing documents."
    )
    invoice_paper_size = models.CharField(
        max_length=20,
        default="A4",
        choices=[("A4", "A4"), ("Letter", "Letter")],
        help_text="Paper size for invoices and full-page reports."
    )
    label_printer_width_mm = models.PositiveSmallIntegerField(
        default=60,
        help_text="Default label width in mm for pharmacy labels (e.g. 40–70)."
    )
    report_paper_orientation = models.CharField(
        max_length=10,
        default="portrait",
        choices=[("portrait", "Portrait"), ("landscape", "Landscape")],
        help_text="Default orientation for reports."
    )
    # Optional: printer name / tray (for future use)
    default_printer_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional: default printer name (as in OS). Leave blank for system default."
    )
    
    # ========== Session & Security ==========
    session_timeout_minutes = models.PositiveSmallIntegerField(
        default=30,
        help_text="Minutes of inactivity before session timeout (e.g. 15–120)."
    )
    require_login_for_receipt_verify = models.BooleanField(
        default=False,
        help_text="Require login to verify receipt by number/QR (public verify can still work if disabled)."
    )
    
    # ========== Business & Display ==========
    timezone = models.CharField(
        max_length=50,
        default="Africa/Accra",
        help_text="Timezone for display (e.g. Africa/Accra, UTC)."
    )
    business_hours_start = models.CharField(
        max_length=5,
        default="08:00",
        help_text="Opening time (HH:MM, 24h)."
    )
    business_hours_end = models.CharField(
        max_length=5,
        default="17:00",
        help_text="Closing time (HH:MM, 24h)."
    )
    max_login_attempts = models.PositiveSmallIntegerField(
        default=5,
        help_text="Max failed login attempts before lockout."
    )
    lockout_duration_minutes = models.PositiveSmallIntegerField(
        default=15,
        help_text="Account lockout duration in minutes."
    )
    
    # ========== Notifications & Integrations ==========
    sms_enabled = models.BooleanField(default=False, help_text="Enable SMS notifications.")
    email_notifications_enabled = models.BooleanField(default=True, help_text="Enable email notifications.")
    backup_retention_days = models.PositiveSmallIntegerField(
        default=30,
        help_text="Keep backups for this many days (0 = no auto cleanup)."
    )
    patient_portal_enabled = models.BooleanField(default=True, help_text="Allow patients to use the portal.")
    show_prices_to_patient = models.BooleanField(
        default=True,
        help_text="Show service/item prices to patient on receipts and portal where applicable."
    )
    
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






























