"""
Admin interface for Patient Deposit System
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Sum

from .models_patient_deposits import PatientDeposit, DepositApplication


@admin.register(PatientDeposit)
class PatientDepositAdmin(admin.ModelAdmin):
    list_display = [
        'deposit_number', 'patient_link', 'deposit_date', 'deposit_amount', 
        'available_balance', 'used_amount', 'status_badge', 'payment_method', 'received_by'
    ]
    list_filter = ['status', 'payment_method', 'deposit_date', 'created']
    search_fields = ['deposit_number', 'patient__first_name', 'patient__last_name', 'patient__mrn', 'reference_number']
    readonly_fields = [
        'deposit_number', 'created', 'modified', 'available_balance', 'used_amount',
        'transaction_link', 'journal_entry_link', 'applications_summary'
    ]
    date_hierarchy = 'deposit_date'
    ordering = ['-deposit_date', '-deposit_number']
    
    fieldsets = (
        ('Deposit Information', {
            'fields': ('deposit_number', 'patient', 'deposit_date', 'deposit_amount', 'status')
        }),
        ('Balance Information', {
            'fields': ('available_balance', 'used_amount'),
            'classes': ('collapse',)
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'reference_number', 'bank_account')
        }),
        ('Accounting', {
            'fields': ('transaction_link', 'journal_entry_link'),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('notes', 'received_by', 'created_by', 'applications_summary'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('created', 'modified', 'is_deleted'),
            'classes': ('collapse',)
        }),
    )
    
    def patient_link(self, obj):
        if obj.patient:
            url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
            return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
        return '-'
    patient_link.short_description = 'Patient'
    
    def status_badge(self, obj):
        colors = {
            'active': 'success',
            'fully_used': 'info',
            'refunded': 'warning',
            'cancelled': 'danger'
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def transaction_link(self, obj):
        if obj.transaction:
            url = reverse('admin:hospital_transaction_change', args=[obj.transaction.pk])
            return format_html('<a href="{}">{}</a>', url, obj.transaction.transaction_number)
        return '-'
    transaction_link.short_description = 'Transaction'
    
    def journal_entry_link(self, obj):
        if obj.journal_entry:
            url = reverse('admin:hospital_advancedjournalentry_change', args=[obj.journal_entry.pk])
            return format_html('<a href="{}">{}</a>', url, obj.journal_entry.entry_number)
        return '-'
    journal_entry_link.short_description = 'Journal Entry'
    
    def applications_summary(self, obj):
        applications = obj.applications.filter(is_deleted=False)
        if applications.exists():
            total = applications.aggregate(total=Sum('applied_amount'))['total'] or 0
            count = applications.count()
            return format_html(
                '<strong>{} application(s)</strong><br>Total Applied: GHS {:.2f}',
                count,
                total
            )
        return 'No applications yet'
    applications_summary.short_description = 'Applications'
    
    actions = ['mark_as_refunded', 'mark_as_cancelled']
    
    def mark_as_refunded(self, request, queryset):
        count = 0
        for deposit in queryset.filter(status='active', available_balance__gt=0):
            deposit.status = 'refunded'
            deposit.save()
            count += 1
        self.message_user(request, f'{count} deposit(s) marked as refunded.')
    mark_as_refunded.short_description = 'Mark selected as refunded'
    
    def mark_as_cancelled(self, request, queryset):
        count = queryset.update(status='cancelled')
        self.message_user(request, f'{count} deposit(s) marked as cancelled.')
    mark_as_cancelled.short_description = 'Mark selected as cancelled'


@admin.register(DepositApplication)
class DepositApplicationAdmin(admin.ModelAdmin):
    list_display = [
        'deposit_link', 'invoice_link', 'applied_amount', 'applied_date', 'applied_by'
    ]
    list_filter = ['applied_date', 'created']
    search_fields = [
        'deposit__deposit_number', 'invoice__invoice_number',
        'deposit__patient__first_name', 'deposit__patient__last_name'
    ]
    readonly_fields = ['deposit', 'invoice', 'applied_date', 'applied_by', 'created', 'modified']
    date_hierarchy = 'applied_date'
    ordering = ['-applied_date']
    
    fieldsets = (
        ('Application Information', {
            'fields': ('deposit', 'invoice', 'applied_amount', 'applied_date', 'applied_by')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('System Information', {
            'fields': ('created', 'modified', 'is_deleted'),
            'classes': ('collapse',)
        }),
    )
    
    def deposit_link(self, obj):
        if obj.deposit:
            url = reverse('admin:hospital_patientdeposit_change', args=[obj.deposit.pk])
            return format_html('<a href="{}">{}</a>', url, obj.deposit.deposit_number)
        return '-'
    deposit_link.short_description = 'Deposit'
    
    def invoice_link(self, obj):
        if obj.invoice:
            url = reverse('admin:hospital_invoice_change', args=[obj.invoice.pk])
            return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number)
        return '-'
    invoice_link.short_description = 'Invoice'
    
    def has_add_permission(self, request):
        # Prevent manual creation - applications should be created via deposit.apply_to_invoice()
        return False
    
    def has_change_permission(self, request, obj=None):
        # Applications are immutable
        return False





