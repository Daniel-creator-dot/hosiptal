"""
Admin interface for Hospital Settings
"""
from django.contrib import admin
from .models_settings import HospitalSettings


@admin.register(HospitalSettings)
class HospitalSettingsAdmin(admin.ModelAdmin):
    """Admin for Hospital Settings - Singleton"""
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('hospital_name', 'hospital_tagline')
        }),
        ('Contact Information', {
            'fields': ('address', 'city', 'state', 'postal_code', 'country', 'phone', 'email', 'website')
        }),
        ('Logo & Branding', {
            'fields': ('logo', 'logo_width', 'logo_height', 'report_header_color', 'report_footer_text')
        }),
        ('Printer & POS Receipt', {
            'fields': (
                'pos_receipt_width_mm', 'pos_receipt_printable_width_mm', 'pos_receipt_length_mm', 'pos_receipt_font_size_body', 'pos_receipt_font_size_header',
                'pos_receipt_font_size_footer', 'pos_receipt_margin_mm', 'pos_receipt_padding_mm',
                'pos_receipt_show_qr', 'pos_receipt_qr_size_px',
                'default_print_copies', 'invoice_paper_size', 'label_printer_width_mm',
                'report_paper_orientation', 'default_printer_name',
            ),
            'classes': ('collapse',)
        }),
        ('Session & Security', {
            'fields': ('session_timeout_minutes', 'require_login_for_receipt_verify', 'max_login_attempts', 'lockout_duration_minutes'),
            'classes': ('collapse',)
        }),
        ('Business & Display', {
            'fields': ('timezone', 'business_hours_start', 'business_hours_end'),
            'classes': ('collapse',)
        }),
        ('Notifications & Integrations', {
            'fields': ('sms_enabled', 'email_notifications_enabled', 'patient_portal_enabled', 'show_prices_to_patient', 'backup_retention_days'),
            'classes': ('collapse',)
        }),
        ('Laboratory Department', {
            'fields': ('lab_department_name', 'lab_phone', 'lab_email', 'lab_accreditation', 'lab_license_number'),
            'classes': ('collapse',)
        }),
        ('Radiology Department', {
            'fields': ('radiology_department_name', 'radiology_phone', 'radiology_email'),
            'classes': ('collapse',)
        }),
        ('Pharmacy Department', {
            'fields': ('pharmacy_department_name', 'pharmacy_phone', 'pharmacy_license_number'),
            'classes': ('collapse',)
        }),
        ('System Settings', {
            'fields': ('currency', 'currency_symbol', 'date_format', 'time_format'),
            'classes': ('collapse',)
        }),
    )
    
    list_display = ['hospital_name', 'city', 'phone', 'updated_at']
    
    def has_add_permission(self, request):
        # Only allow one instance
        return not HospitalSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion
        return False
    
    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)






























