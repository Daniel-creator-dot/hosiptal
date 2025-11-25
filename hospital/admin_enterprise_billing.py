"""
Admin Interface for Enterprise Billing & AR Models
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count
from decimal import Decimal
from .models_enterprise_billing import (
    CorporateAccount, CorporateEmployee, MonthlyStatement,
    StatementLine, ServicePricing, ARAgingSnapshot
)


@admin.register(CorporateAccount)
class CorporateAccountAdmin(admin.ModelAdmin):
    """Admin for corporate accounts"""
    
    list_display = [
        'company_code_display',
        'company_name',
        'current_balance_display',
        'credit_limit_display',
        'credit_status_display',
        'employees_count',
        'next_billing_date',
    ]
    
    list_filter = [
        'credit_status',
        'billing_cycle',
        'is_active',
        'contract_start_date',
    ]
    
    search_fields = [
        'company_name',
        'company_code',
        'registration_number',
        'billing_email',
    ]
    
    readonly_fields = [
        'current_balance',
        'total_employees_enrolled',
        'lifetime_revenue',
        'average_monthly_billing',
        'credit_utilization_display',
    ]
    
    fieldsets = (
        ('Company Information', {
            'fields': (
                'company_name',
                'company_code',
                'registration_number',
                'tax_id',
            )
        }),
        ('Contact Details', {
            'fields': (
                'billing_contact_name',
                'billing_email',
                'billing_phone',
                'billing_address',
                'accounts_contact_email',
                'hr_contact_email',
            )
        }),
        ('Financial Terms', {
            'fields': (
                'credit_limit',
                'payment_terms_days',
                'current_balance',
                'credit_status',
                'credit_utilization_display',
            )
        }),
        ('Billing Settings', {
            'fields': (
                'billing_cycle',
                'billing_day_of_month',
                'next_billing_date',
                'last_billing_date',
            )
        }),
        ('Pricing & Discounts', {
            'fields': (
                'price_book',
                'global_discount_percentage',
            )
        }),
        ('Contract', {
            'fields': (
                'contract_start_date',
                'contract_end_date',
                'contract_document',
                'contract_notes',
            )
        }),
        ('Management', {
            'fields': (
                'account_manager',
                'send_statement_email',
                'send_payment_reminders',
                'reminder_days_before_due',
                'is_active',
                'require_pre_authorization',
            )
        }),
        ('Statistics', {
            'fields': (
                'total_employees_enrolled',
                'lifetime_revenue',
                'average_monthly_billing',
            ),
            'classes': ('collapse',)
        }),
    )
    
    def company_code_display(self, obj):
        return format_html(
            '<strong style="color: #0066cc; font-size: 1.1em;">{}</strong>',
            obj.company_code
        )
    company_code_display.short_description = 'Code'
    
    def current_balance_display(self, obj):
        color = '#dc3545' if obj.current_balance > 0 else '#28a745'
        balance_str = "{:,.2f}".format(float(obj.current_balance))
        return format_html(
            '<strong style="color: {};">GHS {}</strong>',
            color, balance_str
        )
    current_balance_display.short_description = 'Balance'
    current_balance_display.admin_order_field = 'current_balance'
    
    def credit_limit_display(self, obj):
        limit_str = "{:,.2f}".format(float(obj.credit_limit))
        return format_html(
            'GHS {}',
            limit_str
        )
    credit_limit_display.short_description = 'Credit Limit'
    
    def credit_status_display(self, obj):
        colors = {
            'active': '#28a745',
            'suspended': '#ffc107',
            'on_hold': '#dc3545',
            'collection': '#6c757d',
            'closed': '#6c757d',
        }
        color = colors.get(obj.credit_status, '#000')
        return format_html(
            '<span style="color: {}; font-weight: 600;">{}</span>',
            color, obj.get_credit_status_display()
        )
    credit_status_display.short_description = 'Status'
    
    def employees_count(self, obj):
        return format_html(
            '<strong>{}</strong> enrolled',
            obj.total_employees_enrolled
        )
    employees_count.short_description = 'Employees'
    
    def credit_utilization_display(self, obj):
        percentage = obj.credit_utilization_percentage
        if percentage >= 90:
            color = '#dc3545'
            icon = '⚠️'
        elif percentage >= 75:
            color = '#ffc107'
            icon = '⚡'
        else:
            color = '#28a745'
            icon = '✓'
        
        return format_html(
            '{} <strong style="color: {};">{:.1f}%</strong> utilized (GHS {:,.2f} / GHS {:,.2f})',
            icon, color, percentage, obj.current_balance, obj.credit_limit
        )
    credit_utilization_display.short_description = 'Credit Utilization'


@admin.register(CorporateEmployee)
class CorporateEmployeeAdmin(admin.ModelAdmin):
    """Admin for corporate employee enrollments"""
    
    list_display = [
        'employee_id',
        'patient_link',
        'corporate_account',
        'is_active',
        'enrollment_date',
        'limit_status',
    ]
    
    list_filter = [
        'is_active',
        'corporate_account',
        'enrollment_date',
        'has_annual_limit',
    ]
    
    search_fields = [
        'employee_id',
        'patient__first_name',
        'patient__last_name',
        'patient__mrn',
        'corporate_account__company_name',
    ]
    
    readonly_fields = [
        'enrollment_date',
        'utilized_amount',
        'remaining_limit_display',
    ]
    
    fieldsets = (
        ('Enrollment', {
            'fields': (
                'corporate_account',
                'patient',
                'employee_id',
                'enrollment_date',
                'is_active',
                'termination_date',
            )
        }),
        ('Employee Details', {
            'fields': (
                'department',
                'designation',
                'employee_email',
            )
        }),
        ('Coverage Limits', {
            'fields': (
                'has_annual_limit',
                'annual_limit',
                'utilized_amount',
                'remaining_limit_display',
                'limit_reset_date',
            )
        }),
        ('Dependents', {
            'fields': (
                'covers_dependents',
                'number_of_dependents',
                'dependent_limit',
            )
        }),
        ('Notes', {
            'fields': ('special_instructions',)
        }),
    )
    
    def patient_link(self, obj):
        url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
        return format_html(
            '<a href="{}">{}</a><br><small>MRN: {}</small>',
            url, obj.patient.full_name, obj.patient.mrn
        )
    patient_link.short_description = 'Patient'
    
    def limit_status(self, obj):
        if not obj.has_annual_limit:
            return format_html('<span style="color: #6c757d;">No Limit</span>')
        
        remaining = obj.remaining_limit
        if remaining and remaining > 0:
            return format_html(
                '<span style="color: #28a745;">GHS {:,.2f} remaining</span>',
                remaining
            )
        else:
            return format_html('<span style="color: #dc3545;">⚠️ Limit Exceeded</span>')
    limit_status.short_description = 'Limit Status'
    
    def remaining_limit_display(self, obj):
        remaining = obj.remaining_limit
        if remaining is None:
            return "No limit set"
        remaining_str = "{:,.2f}".format(float(remaining))
        annual_str = "{:,.2f}".format(float(obj.annual_limit))
        return format_html(
            'GHS {} of GHS {} remaining',
            remaining_str, annual_str
        )
    remaining_limit_display.short_description = 'Remaining Limit'


class StatementLineInline(admin.TabularInline):
    """Inline for statement lines"""
    model = StatementLine
    extra = 0
    readonly_fields = ['service_date', 'patient', 'description', 'line_total']
    fields = ['service_date', 'patient', 'description', 'quantity', 'unit_price', 'line_total']
    can_delete = False


@admin.register(MonthlyStatement)
class MonthlyStatementAdmin(admin.ModelAdmin):
    """Admin for monthly statements"""
    
    list_display = [
        'statement_number',
        'corporate_account_link',
        'period_display',
        'closing_balance_display',
        'due_date',
        'status_display',
        'overdue_display',
    ]
    
    list_filter = [
        'status',
        'statement_date',
        'due_date',
        'sent_via',
    ]
    
    search_fields = [
        'statement_number',
        'corporate_account__company_name',
        'payer__name',
    ]
    
    readonly_fields = [
        'statement_number',
        'statement_date',
        'total_line_items',
        'total_patients_served',
        'sent_date',
        'reminder_count',
        'last_reminder_sent',
        'amount_outstanding_display',
        'days_overdue_display',
    ]
    
    fieldsets = (
        ('Statement Details', {
            'fields': (
                'statement_number',
                'payer',
                'corporate_account',
                'statement_date',
                'period_start',
                'period_end',
            )
        }),
        ('Financial Summary', {
            'fields': (
                'opening_balance',
                'total_charges',
                'total_payments',
                'total_adjustments',
                'tax_amount',
                'closing_balance',
                'amount_outstanding_display',
            )
        }),
        ('Line Items', {
            'fields': (
                'total_line_items',
                'total_patients_served',
            )
        }),
        ('Status & Terms', {
            'fields': (
                'status',
                'due_date',
                'payment_terms',
                'days_overdue_display',
            )
        }),
        ('Distribution', {
            'fields': (
                'sent_date',
                'sent_via',
                'sent_to_email',
                'pdf_file',
            )
        }),
        ('Payment Tracking', {
            'fields': (
                'last_payment_date',
                'last_payment_amount',
            )
        }),
        ('Reminders', {
            'fields': (
                'reminder_count',
                'last_reminder_sent',
            )
        }),
        ('Notes', {
            'fields': (
                'notes',
                'internal_notes',
            )
        }),
    )
    
    inlines = [StatementLineInline]
    
    def corporate_account_link(self, obj):
        if obj.corporate_account:
            return obj.corporate_account.company_name
        return obj.payer.name
    corporate_account_link.short_description = 'Account'
    
    def period_display(self, obj):
        return format_html(
            '{} to {}',
            obj.period_start.strftime('%b %d'),
            obj.period_end.strftime('%b %d, %Y')
        )
    period_display.short_description = 'Period'
    
    def closing_balance_display(self, obj):
        balance_str = "{:,.2f}".format(float(obj.closing_balance))
        return format_html(
            '<strong style="color: #dc3545;">GHS {}</strong>',
            balance_str
        )
    closing_balance_display.short_description = 'Amount Due'
    closing_balance_display.admin_order_field = 'closing_balance'
    
    def status_display(self, obj):
        colors = {
            'draft': '#6c757d',
            'sent': '#0066cc',
            'partially_paid': '#ffc107',
            'paid': '#28a745',
            'overdue': '#dc3545',
            'written_off': '#6c757d',
        }
        color = colors.get(obj.status, '#000')
        return format_html(
            '<span style="color: {}; font-weight: 600;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def overdue_display(self, obj):
        if obj.is_overdue:
            days = obj.days_overdue
            return format_html(
                '<span style="color: #dc3545; font-weight: 600;">⚠️ {} days</span>',
                days
            )
        return format_html('<span style="color: #28a745;">✓ Current</span>')
    overdue_display.short_description = 'Overdue'
    
    def amount_outstanding_display(self, obj):
        amount_str = "{:,.2f}".format(float(obj.amount_outstanding))
        return format_html(
            'GHS {}',
            amount_str
        )
    amount_outstanding_display.short_description = 'Outstanding'
    
    def days_overdue_display(self, obj):
        if obj.is_overdue:
            return format_html(
                '<strong style="color: #dc3545;">{} days overdue</strong>',
                obj.days_overdue
            )
        return "Not overdue"
    days_overdue_display.short_description = 'Days Overdue'


@admin.register(ServicePricing)
class ServicePricingAdmin(admin.ModelAdmin):
    """Admin for service pricing"""
    
    list_display = [
        'service_code',
        'cash_price_display',
        'corporate_price_display',
        'insurance_price_display',
        'payer_display',
        'effective_from',
        'is_active',
    ]
    
    list_filter = [
        'is_active',
        'effective_from',
        'payer',
    ]
    
    search_fields = [
        'service_code__code',
        'service_code__name',
        'payer__name',
    ]
    
    fieldsets = (
        ('Service', {
            'fields': ('service_code',)
        }),
        ('Standard Pricing Tiers', {
            'fields': (
                'cash_price',
                'corporate_price',
                'insurance_price',
            )
        }),
        ('Payer-Specific Override', {
            'fields': (
                'payer',
                'custom_price',
            ),
            'description': 'Set custom price for specific corporate/insurance payer'
        }),
        ('Effective Dates', {
            'fields': (
                'effective_from',
                'effective_to',
                'is_active',
            )
        }),
        ('Notes', {
            'fields': ('pricing_notes',)
        }),
    )
    
    def cash_price_display(self, obj):
        price_str = "{:,.2f}".format(float(obj.cash_price))
        return format_html('GHS {}', price_str)
    cash_price_display.short_description = 'Cash'
    
    def corporate_price_display(self, obj):
        price_str = "{:,.2f}".format(float(obj.corporate_price))
        return format_html('GHS {}', price_str)
    corporate_price_display.short_description = 'Corporate'
    
    def insurance_price_display(self, obj):
        price_str = "{:,.2f}".format(float(obj.insurance_price))
        return format_html('GHS {}', price_str)
    insurance_price_display.short_description = 'Insurance'
    
    def payer_display(self, obj):
        if obj.payer and obj.custom_price:
            return format_html(
                '{} <strong>(GHS {:,.2f})</strong>',
                obj.payer.name, obj.custom_price
            )
        return '-'
    payer_display.short_description = 'Custom Payer'


@admin.register(ARAgingSnapshot)
class ARAgingSnapshotAdmin(admin.ModelAdmin):
    """Admin for AR aging snapshots"""
    
    list_display = [
        'snapshot_date',
        'total_outstanding_display',
        'current_display',
        'overdue_display',
        'overdue_percentage_display',
    ]
    
    readonly_fields = [
        'snapshot_date',
        'current_0_30',
        'days_31_60',
        'days_61_90',
        'days_91_120',
        'days_over_120',
        'total_outstanding',
        'cash_outstanding',
        'corporate_outstanding',
        'insurance_outstanding',
        'total_accounts',
        'overdue_accounts',
    ]
    
    fieldsets = (
        ('Snapshot Date', {
            'fields': ('snapshot_date',)
        }),
        ('Aging Buckets', {
            'fields': (
                'current_0_30',
                'days_31_60',
                'days_61_90',
                'days_91_120',
                'days_over_120',
                'total_outstanding',
            )
        }),
        ('By Payer Type', {
            'fields': (
                'cash_outstanding',
                'corporate_outstanding',
                'insurance_outstanding',
            )
        }),
        ('Accounts', {
            'fields': (
                'total_accounts',
                'overdue_accounts',
            )
        }),
    )
    
    def total_outstanding_display(self, obj):
        total_str = "{:,.2f}".format(float(obj.total_outstanding))
        return format_html(
            '<strong style="color: #dc3545; font-size: 1.2em;">GHS {}</strong>',
            total_str
        )
    total_outstanding_display.short_description = 'Total AR'
    
    def current_display(self, obj):
        amount_str = "{:,.2f}".format(float(obj.current_0_30))
        return format_html('GHS {}', amount_str)
    current_display.short_description = 'Current (0-30)'
    
    def overdue_display(self, obj):
        overdue = obj.days_31_60 + obj.days_61_90 + obj.days_91_120 + obj.days_over_120
        overdue_str = "{:,.2f}".format(float(overdue))
        return format_html(
            '<strong style="color: #dc3545;">GHS {}</strong>',
            overdue_str
        )
    overdue_display.short_description = 'Overdue (31+)'
    
    def overdue_percentage_display(self, obj):
        percentage = obj.overdue_percentage
        color = '#dc3545' if percentage > 30 else ('#ffc107' if percentage > 15 else '#28a745')
        return format_html(
            '<strong style="color: {};">{:.1f}%</strong>',
            color, percentage
        )
    overdue_percentage_display.short_description = 'Overdue %'
























