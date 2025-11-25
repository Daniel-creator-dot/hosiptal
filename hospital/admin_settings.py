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






























