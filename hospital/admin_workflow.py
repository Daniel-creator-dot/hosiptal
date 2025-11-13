"""
Admin configuration for workflow models
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models_workflow import (
    PatientFlowStage, WorkflowTemplate, Bill, PaymentRequest, CashierSession
)


@admin.register(PatientFlowStage)
class PatientFlowStageAdmin(admin.ModelAdmin):
    list_display = ['encounter_link', 'stage_type_display', 'status_badge', 'started_at', 'completed_at', 'completed_by_link']
    list_filter = ['stage_type', 'status', 'created']
    search_fields = ['encounter__patient__first_name', 'encounter__patient__last_name', 'notes']
    ordering = ['-created']
    
    def encounter_link(self, obj):
        if obj.encounter:
            url = reverse('admin:hospital_encounter_change', args=[obj.encounter.pk])
            return format_html('<a href="{}">{}</a>', url, obj.encounter)
        return "-"
    encounter_link.short_description = 'Encounter'
    
    def stage_type_display(self, obj):
        return obj.get_stage_type_display()
    stage_type_display.short_description = 'Stage'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'secondary',
            'in_progress': 'primary',
            'completed': 'success',
            'skipped': 'warning',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_status_display())
    status_badge.short_description = 'Status'
    
    def completed_by_link(self, obj):
        if obj.completed_by and obj.completed_by.user:
            url = reverse('admin:hospital_staff_change', args=[obj.completed_by.pk])
            return format_html('<a href="{}">{}</a>', url, obj.completed_by.user.get_full_name())
        return "-"
    completed_by_link.short_description = 'Completed By'


@admin.register(WorkflowTemplate)
class WorkflowTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'encounter_type_display', 'stage_count', 'is_active']
    list_filter = ['encounter_type', 'is_active']
    search_fields = ['name', 'description']
    
    def encounter_type_display(self, obj):
        return obj.get_encounter_type_display()
    encounter_type_display.short_description = 'Encounter Type'
    
    def stage_count(self, obj):
        return len(obj.stages) if obj.stages else 0
    stage_count.short_description = 'Stages'


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ['bill_number', 'patient_link', 'bill_type_badge', 'total_amount', 'insurance_covered', 'patient_portion', 'status_badge', 'issued_at']
    list_filter = ['bill_type', 'status', 'issued_at']
    search_fields = ['bill_number', 'patient__first_name', 'patient__last_name', 'patient__mrn']
    ordering = ['-issued_at']
    readonly_fields = ['bill_number']
    
    def patient_link(self, obj):
        if obj.patient:
            url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
            return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
        return "-"
    patient_link.short_description = 'Patient'
    
    def bill_type_badge(self, obj):
        colors = {
            'cash': 'warning',
            'insurance': 'info',
            'mixed': 'primary',
        }
        color = colors.get(obj.bill_type, 'secondary')
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_bill_type_display())
    bill_type_badge.short_description = 'Type'
    
    def status_badge(self, obj):
        colors = {
            'draft': 'secondary',
            'issued': 'primary',
            'partially_paid': 'warning',
            'paid': 'success',
            'cancelled': 'danger',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_status_display())
    status_badge.short_description = 'Status'


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = ['request_number', 'patient_link', 'invoice_link', 'requested_amount', 'payment_type', 'status_badge', 'requested_at']
    list_filter = ['payment_type', 'status', 'requested_at']
    search_fields = ['request_number', 'patient__first_name', 'patient__last_name']
    ordering = ['-requested_at']
    readonly_fields = ['request_number']
    
    def patient_link(self, obj):
        if obj.patient:
            url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
            return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
        return "-"
    patient_link.short_description = 'Patient'
    
    def invoice_link(self, obj):
        if obj.invoice:
            url = reverse('admin:hospital_invoice_change', args=[obj.invoice.pk])
            return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number)
        return "-"
    invoice_link.short_description = 'Invoice'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'warning',
            'processing': 'info',
            'completed': 'success',
            'cancelled': 'danger',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_status_display())
    status_badge.short_description = 'Status'


@admin.register(CashierSession)
class CashierSessionAdmin(admin.ModelAdmin):
    list_display = ['session_number', 'cashier_link', 'status_badge', 'opened_at', 'closed_at', 'total_payments', 'expected_cash']
    list_filter = ['status', 'opened_at']
    search_fields = ['session_number', 'cashier__username']
    ordering = ['-opened_at']
    readonly_fields = ['session_number']
    
    def cashier_link(self, obj):
        if obj.cashier:
            url = reverse('admin:auth_user_change', args=[obj.cashier.pk])
            return format_html('<a href="{}">{}</a>', url, obj.cashier.username)
        return "-"
    cashier_link.short_description = 'Cashier'
    
    def status_badge(self, obj):
        color = 'success' if obj.status == 'open' else 'secondary'
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_status_display())
    status_badge.short_description = 'Status'

