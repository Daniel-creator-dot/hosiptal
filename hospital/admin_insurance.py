"""
Admin configuration for Insurance Claims Management
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Sum
from .models_insurance import InsuranceClaimItem, MonthlyInsuranceClaim


class InsuranceClaimItemInline(admin.TabularInline):
    model = InsuranceClaimItem
    extra = 0
    fields = ['service_description', 'service_date', 'billed_amount', 'approved_amount', 'paid_amount', 'claim_status']
    readonly_fields = ['service_description', 'service_date', 'billed_amount']
    fk_name = 'monthly_claim'
    can_delete = False


@admin.register(InsuranceClaimItem)
class InsuranceClaimItemAdmin(admin.ModelAdmin):
    list_display = ['patient_link', 'payer', 'service_description_preview', 'service_date', 
                   'billed_amount', 'paid_amount', 'claim_status_badge', 'monthly_claim_link']
    list_filter = ['claim_status', 'payer', 'service_date', 'created']
    search_fields = ['patient__first_name', 'patient__last_name', 'patient__mrn', 
                    'patient_insurance_id', 'service_description', 'claim_reference']
    readonly_fields = ['patient', 'payer', 'patient_insurance_id', 'invoice', 'invoice_line', 
                      'encounter', 'service_code', 'service_description', 'service_date',
                      'billed_amount', 'created', 'modified']
    date_hierarchy = 'service_date'
    ordering = ['-service_date', '-created']
    
    fieldsets = (
        ('Patient & Insurance Information', {
            'fields': ('patient', 'payer', 'patient_insurance_id')
        }),
        ('Service Information', {
            'fields': ('service_code', 'service_description', 'service_date', 'encounter')
        }),
        ('Financial Information', {
            'fields': ('billed_amount', 'approved_amount', 'paid_amount', 'outstanding_amount')
        }),
        ('Claim Tracking', {
            'fields': ('claim_status', 'claim_reference', 'monthly_claim', 'invoice', 'invoice_line')
        }),
        ('Dates', {
            'fields': ('submitted_date', 'approved_date', 'paid_date')
        }),
        ('Notes', {
            'fields': ('rejection_reason', 'notes')
        }),
    )
    
    def patient_link(self, obj):
        url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
        return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
    patient_link.short_description = 'Patient'
    
    def service_description_preview(self, obj):
        if len(obj.service_description) > 50:
            return obj.service_description[:50] + '...'
        return obj.service_description
    service_description_preview.short_description = 'Service'
    
    def claim_status_badge(self, obj):
        colors = {
            'pending': 'warning',
            'submitted': 'info',
            'processing': 'primary',
            'approved': 'success',
            'partially_paid': 'secondary',
            'paid': 'success',
            'rejected': 'danger',
            'reversed': 'dark',
        }
        color = colors.get(obj.claim_status, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_claim_status_display()
        )
    claim_status_badge.short_description = 'Status'
    
    def monthly_claim_link(self, obj):
        if obj.monthly_claim:
            url = reverse('admin:hospital_monthlyinsuranceclaim_change', args=[obj.monthly_claim.pk])
            return format_html('<a href="{}">{}</a>', url, obj.monthly_claim.claim_number)
        return '-'
    monthly_claim_link.short_description = 'Monthly Claim'


@admin.register(MonthlyInsuranceClaim)
class MonthlyInsuranceClaimAdmin(admin.ModelAdmin):
    list_display = ['claim_number', 'payer', 'period_display', 'status_badge', 
                   'total_items', 'total_billed_display', 'total_paid_display', 
                   'outstanding_display']
    list_filter = ['status', 'payer', 'claim_year', 'claim_month']
    search_fields = ['claim_number', 'payer__name', 'submission全面的rence', 'payment_reference']
    readonly_fields = ['claim_number', 'total_items', 'total_billed_amount', 
                      'total_approved_amount', 'total_paid_amount', 'created', 'modified']
    date_hierarchy = 'created'
    inlines = [InsuranceClaimItemInline]
    ordering = ['-claim_year', '-claim_month', '-created']
    
    fieldsets = (
        ('Claim Information', {
            'fields': ('claim_number', 'payer', 'claim_month', 'claim_year', 'status')
        }),
        ('Financial Summary', {
            'fields': ('total_items', 'total_billed_amount', 'total_approved_amount', 
                      'total_paid_amount', 'outstanding_amount')
        }),
        ('Submission Tracking', {
            'fields': ('submissionute', 'submission_reference')
        }),
        ('Payment Tracking', {
            'fields': ('payment_date', 'payment_reference')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )
    
    def period_display(self, obj):
        return f"{obj.month_display} {obj.claim_year}"
    period_display.short_description = 'Period'
    
    def status_badge(self, obj):
        colors = {
            'draft': 'secondary',
            'ready_for_submission': 'warning',
            'submitted': 'info',
            'processing': 'primary',
            'partially_paid': ' Loving',
            'fully_paid': 'success',
            'closed': 'dark',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def total_billed_display(self, obj):
        return f"GHS {obj.total_billed_amount:,.2f}"
    total_billed_display.short_description = 'Total Billed'
    
    def total_paid_display(self, obj):
        return f"GHS {obj.total_paid_amount:,.2f}"
    total_paid_display.short_description = 'Total Paid'
    
    def outstanding_display(self, obj):
        outstanding = obj.outstanding_amount
        color = 'danger' if outstanding > 0 else 'success'
        return format_html(
            '<span class="badge badge-{}">GHS {:, .2f}</span>',
            color, outstanding
        )
    outstanding_display.short_description = 'Outstanding'
    
    def save_model(self, request, obj, form, change):
        """Recalculate totals when saving"""
        super().save_model(request, obj, form, change)
        if change:
            obj.calculate_totals()
