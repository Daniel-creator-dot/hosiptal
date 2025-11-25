"""
Admin configuration for Contract and Certificate Management
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models_contracts import Contract, Certificate, ContractCategory, ContractRenewal


@admin.register(ContractCategory)
class ContractCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category_type', 'is_active']
    list_filter = ['category_type', 'is_active']
    search_fields = ['name']


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ['contract_number', 'contract_name', 'company_name', 'category',
                    'start_date', 'end_date', 'days_left_display', 'status_badge']
    list_filter = ['status', 'category', 'auto_renew', 'start_date']
    search_fields = ['contract_number', 'contract_name', 'company_name']
    date_hierarchy = 'end_date'
    readonly_fields = ['created', 'modified']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('contract_number', 'contract_name', 'category', 'description')
        }),
        ('Other Party', {
            'fields': ('company_name', 'company_contact_person', 'company_phone', 
                      'company_email')
        }),
        ('Contract Terms', {
            'fields': ('start_date', 'end_date', 'renewal_date', 'value_amount', 
                      'payment_terms', 'auto_renew')
        }),
        ('Alerts & Status', {
            'fields': ('status', 'alert_days_before', 'last_alert_sent')
        }),
        ('Documents', {
            'fields': ('contract_document', 'supporting_documents')
        }),
        ('Management', {
            'fields': ('responsible_person', 'created_by', 'notes')
        }),
        ('System', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'draft': 'secondary',
            'active': 'success',
            'expiring_soon': 'warning',
            'expired': 'danger',
            'terminated': 'dark',
            'renewed': 'info',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def days_left_display(self, obj):
        days = obj.days_until_expiry
        if days is None:
            return '-'
        
        if days < 0:
            return format_html('<span class="badge bg-danger">Expired</span>')
        elif days <= 7:
            return format_html('<span class="badge bg-danger">{} days</span>', days)
        elif days <= 30:
            return format_html('<span class="badge bg-warning">{} days</span>', days)
        else:
            return format_html('<span class="badge bg-success">{} days</span>', days)
    days_left_display.short_description = 'Days Left'


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ['certificate_number', 'certificate_name', 'certificate_type', 
                    'issuing_authority', 'issue_date', 'expiry_date', 'days_left_display', 'status_badge']
    list_filter = ['status', 'certificate_type', 'expiry_date']
    search_fields = ['certificate_number', 'certificate_name', 'issuing_authority']
    date_hierarchy = 'expiry_date'
    readonly_fields = ['created', 'modified']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('certificate_number', 'certificate_name', 'certificate_type', 'description')
        }),
        ('Issuing Authority', {
            'fields': ('issuing_authority', 'authority_contact', 'authority_phone', 'authority_email')
        }),
        ('Dates', {
            'fields': ('issue_date', 'expiry_date', 'renewal_date')
        }),
        ('Alerts & Status', {
            'fields': ('status', 'alert_days_before', 'last_alert_sent')
        }),
        ('Documents', {
            'fields': ('certificate_document', 'supporting_documents')
        }),
        ('Related', {
            'fields': ('staff_member', 'contract')
        }),
        ('Management', {
            'fields': ('responsible_person', 'created_by', 'notes', 'renewal_process')
        }),
        ('System', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'valid': 'success',
            'expiring_soon': 'warning',
            'expired': 'danger',
            'pending_renewal': 'info',
            'cancelled': 'secondary',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def days_left_display(self, obj):
        days = obj.days_until_expiry
        if days is None:
            return '-'
        
        if days < 0:
            return format_html('<span class="badge bg-danger">Expired</span>')
        elif days <= 14:
            return format_html('<span class="badge bg-danger">{} days</span>', days)
        elif days <= 60:
            return format_html('<span class="badge bg-warning">{} days</span>', days)
        else:
            return format_html('<span class="badge bg-success">{} days</span>', days)
    days_left_display.short_description = 'Days Left'


@admin.register(ContractRenewal)
class ContractRenewalAdmin(admin.ModelAdmin):
    list_display = ['contract', 'renewal_date', 'previous_end_date', 'new_end_date', 'processed_by']
    list_filter = ['renewal_date']
    search_fields = ['contract__contract_name', 'contract__contract_number']
    date_hierarchy = 'renewal_date'























