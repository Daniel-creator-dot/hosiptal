"""
Admin configuration for Insurance Company Management
World-class insurance administration
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from .models_insurance_companies import (
    InsuranceCompany,
    InsurancePlan,
    InsuranceExclusionRule,
    PatientInsurance,
)


@admin.register(InsuranceCompany)
class InsuranceCompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'status_badge', 'active_plans_display', 'enrolled_patients_display', 
                    'payment_terms_days', 'contract_status', 'created']
    list_filter = ['status', 'is_active', 'created']
    search_fields = ['name', 'code', 'email', 'phone_number']
    readonly_fields = ['created', 'modified']
    list_per_page = 25
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'status', 'is_active')
        }),
        ('Contact Information', {
            'fields': ('phone_number', 'email', 'website', 'address')
        }),
        ('Contract Details', {
            'fields': ('contract_number', 'contract_start_date', 'contract_end_date', 
                      'payment_terms_days', 'discount_percentage')
        }),
        ('Billing Contact', {
            'fields': ('billing_contact_name', 'billing_contact_phone', 
                      'billing_contact_email', 'billing_address'),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('notes', 'logo'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        """Display status with color badge"""
        colors = {
            'active': 'success',
            'suspended': 'warning',
            'inactive': 'secondary',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def active_plans_display(self, obj):
        """Display number of active plans with link"""
        count = obj.active_plans_count
        url = reverse('admin:hospital_insuranceplan_changelist') + f'?insurance_company__id__exact={obj.id}&is_active__exact=1'
        return format_html(
            '<a href="{}" class="btn btn-sm btn-primary">{} Plans</a>',
            url, count
        )
    active_plans_display.short_description = 'Active Plans'
    
    def enrolled_patients_display(self, obj):
        """Display number of enrolled patients"""
        count = obj.enrolled_patients_count
        return format_html(
            '<span class="badge bg-info">{} Patients</span>',
            count
        )
    enrolled_patients_display.short_description = 'Enrolled Patients'
    
    def contract_status(self, obj):
        """Display contract status"""
        if obj.is_contract_active:
            return format_html('<span class="badge bg-success"><i class="bi bi-check-circle"></i> Active</span>')
        else:
            return format_html('<span class="badge bg-danger"><i class="bi bi-x-circle"></i> Expired</span>')
    contract_status.short_description = 'Contract'


@admin.register(InsurancePlan)
class InsurancePlanAdmin(admin.ModelAdmin):
    list_display = ['plan_name', 'insurance_company', 'plan_code', 'plan_type', 
                    'coverage_summary', 'enrolled_count_display', 'is_valid_display', 'is_active']
    list_filter = ['insurance_company', 'plan_type', 'is_active', 'requires_pre_authorization']
    search_fields = ['plan_name', 'plan_code', 'insurance_company__name']
    readonly_fields = ['created', 'modified']
    list_per_page = 25
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('insurance_company', 'plan_name', 'plan_code', 'plan_type', 'description')
        }),
        ('Coverage Percentages', {
            'fields': ('consultation_coverage', 'lab_coverage', 'imaging_coverage', 
                      'pharmacy_coverage', 'surgery_coverage', 'admission_coverage')
        }),
        ('Limits & Restrictions', {
            'fields': ('annual_limit', 'consultation_limit_per_year', 
                      'requires_pre_authorization', 'copay_amount')
        }),
        ('Validity Period', {
            'fields': ('is_active', 'effective_date', 'expiry_date')
        }),
        ('Additional Information', {
            'fields': ('exclusions', 'notes'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    
    def coverage_summary(self, obj):
        """Display quick coverage summary"""
        return format_html(
            '<div style="font-size: 11px;">'
            'Consult: {}% | Lab: {}% | Pharmacy: {}%'
            '</div>',
            obj.consultation_coverage, obj.lab_coverage, obj.pharmacy_coverage
        )
    coverage_summary.short_description = 'Coverage'
    
    def enrolled_count_display(self, obj):
        """Display enrolled patients count"""
        count = obj.enrolled_patients_count
        return format_html(
            '<span class="badge bg-info">{}</span>',
            count
        )
    enrolled_count_display.short_description = 'Enrolled'
    
    def is_valid_display(self, obj):
        """Display validity status"""
        if obj.is_valid:
            return format_html('<span class="badge bg-success">Valid</span>')
        else:
            return format_html('<span class="badge bg-danger">Expired/Inactive</span>')
    is_valid_display.short_description = 'Validity'


@admin.register(PatientInsurance)
class PatientInsuranceAdmin(admin.ModelAdmin):
    list_display = ['patient', 'insurance_company', 'insurance_plan', 'member_id', 
                    'status_badge', 'is_primary', 'is_valid_display', 'effective_date', 'expiry_date']
    list_filter = ['insurance_company', 'status', 'is_primary', 'effective_date']
    search_fields = ['patient__first_name', 'patient__last_name', 'patient__mrn', 
                    'member_id', 'policy_number']
    readonly_fields = ['created', 'modified', 'last_verified_date']
    date_hierarchy = 'effective_date'
    list_per_page = 25
    
    fieldsets = (
        ('Patient & Insurance', {
            'fields': ('patient', 'insurance_company', 'insurance_plan')
        }),
        ('Policy Details', {
            'fields': ('policy_number', 'member_id', 'group_number')
        }),
        ('Subscriber Information', {
            'fields': ('is_primary_subscriber', 'relationship_to_subscriber', 
                      'subscriber_name', 'subscriber_dob'),
            'classes': ('collapse',)
        }),
        ('Coverage Period', {
            'fields': ('effective_date', 'expiry_date', 'status', 'is_primary')
        }),
        ('Verification', {
            'fields': ('last_verified_date', 'verification_status'),
            'classes': ('collapse',)
        }),
        ('Usage Tracking', {
            'fields': ('consultations_used', 'amount_used_this_year'),
            'classes': ('collapse',)
        }),
        ('Attachments', {
            'fields': ('insurance_card_front', 'insurance_card_back', 'notes'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        """Display status with color badge"""
        colors = {
            'active': 'success',
            'expired': 'warning',
            'suspended': 'danger',
            'cancelled': 'secondary',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def is_valid_display(self, obj):
        """Display validity with icon"""
        if obj.is_valid:
            return format_html('<i class="bi bi-check-circle-fill text-success"></i> Valid')
        else:
            return format_html('<i class="bi bi-x-circle-fill text-danger"></i> Invalid')
    is_valid_display.short_description = 'Valid'
    
    actions = ['mark_as_verified', 'mark_as_expired']
    
    def mark_as_verified(self, request, queryset):
        """Mark selected insurances as verified"""
        for insurance in queryset:
            insurance.mark_as_verified()
        self.message_user(request, f'{queryset.count()} insurance(s) marked as verified.')
    mark_as_verified.short_description = 'Mark as verified'
    
    def mark_as_expired(self, request, queryset):
        """Mark selected insurances as expired"""
        queryset.update(status='expired')
        self.message_user(request, f'{queryset.count()} insurance(s) marked as expired.')
    mark_as_expired.short_description = 'Mark as expired'


@admin.register(InsuranceExclusionRule)
class InsuranceExclusionRuleAdmin(admin.ModelAdmin):
    list_display = [
        'insurance_company',
        'insurance_plan',
        'rule_type',
        'enforcement_action',
        'describe_target',
        'is_active',
        'effective_from',
        'effective_to',
    ]
    list_filter = ['insurance_company', 'rule_type', 'enforcement_action', 'is_active']
    search_fields = [
        'insurance_company__name',
        'insurance_plan__plan_name',
        'service_category',
        'drug_generic_name',
        'drug__name',
    ]
    readonly_fields = ['created', 'modified']
    fieldsets = (
        ('Scope', {
            'fields': (
                'insurance_company',
                'insurance_plan',
                'apply_to_all_plans',
                'rule_type',
                'enforcement_action',
                'is_active',
            )
        }),
        ('Targets', {
            'fields': (
                'service_code',
                'service_category',
                'drug',
                'drug_generic_name',
                'drug_category',
            )
        }),
        ('Messaging', {
            'fields': ('reason', 'notes'),
            'classes': ('collapse',)
        }),
        ('Validity', {
            'fields': ('effective_from', 'effective_to')
        }),
        ('System Info', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )



















