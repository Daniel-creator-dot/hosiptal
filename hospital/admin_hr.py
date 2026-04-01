"""
Admin configuration for HR models
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models_hr import (
    PayGrade, StaffContract, PayrollPeriod, Payroll, LeaveBalance,
    PerformanceReview, PerformanceKPI, PerformanceKPIRating,
    DisciplinaryAction, TrainingRecord, TrainingProgram,
    StaffDocument, StaffNote,
    AllowanceType, DeductionType, TaxBracket, PayrollConfiguration,
    PayrollAllowance, PayrollDeduction
)
try:
    from .models_hr import StaffShift, ShiftTemplate, StaffQualification, StaffMedicalChit
except ImportError:
    StaffMedicalChit = None


@admin.register(PayGrade)
class PayGradeAdmin(admin.ModelAdmin):
    list_display = ['grade_name', 'level', 'base_salary', 'is_active']
    list_filter = ['is_active', 'level']
    search_fields = ['grade_name']
    ordering = ['level']


@admin.register(StaffContract)
class StaffContractAdmin(admin.ModelAdmin):
    list_display = ['staff_link', 'contract_type_badge', 'job_title', 'department', 'basic_salary', 'total_monthly_salary', 'is_active']
    list_filter = ['contract_type', 'is_active', 'department']
    search_fields = ['staff__user__first_name', 'staff__user__last_name', 'job_title']
    ordering = ['-start_date']
    
    def staff_link(self, obj):
        if obj.staff:
            url = reverse('admin:hospital_staff_change', args=[obj.staff.pk])
            return format_html('<a href="{}">{}</a>', url, obj.staff.user.get_full_name())
        return "-"
    staff_link.short_description = 'Staff'
    
    def contract_type_badge(self, obj):
        colors = {
            'permanent': 'success',
            'contract': 'info',
            'temporary': 'warning',
            'probation': 'secondary',
            'intern': 'primary',
        }
        color = colors.get(obj.contract_type, 'secondary')
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_contract_type_display())
    contract_type_badge.short_description = 'Type'


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ['period_name', 'start_date', 'end_date', 'pay_date', 'is_processed_badge', 'processed_at']
    list_filter = ['is_processed', 'start_date']
    search_fields = ['period_name']
    ordering = ['-start_date']
    
    def is_processed_badge(self, obj):
        color = 'success' if obj.is_processed else 'warning'
        return format_html('<span class="badge bg-{}">{}</span>', color, 'Processed' if obj.is_processed else 'Pending')
    is_processed_badge.short_description = 'Status'


@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ['payroll_number', 'staff_link', 'period', 'total_earnings', 'total_deductions', 'net_pay', 'payment_status_badge']
    list_filter = ['payment_status', 'period']
    search_fields = ['payroll_number', 'staff__user__first_name', 'staff__user__last_name']
    ordering = ['-period__start_date', 'staff']
    readonly_fields = ['payroll_number']
    
    def staff_link(self, obj):
        if obj.staff:
            url = reverse('admin:hospital_staff_change', args=[obj.staff.pk])
            return format_html('<a href="{}">{}</a>', url, obj.staff.user.get_full_name())
        return "-"
    staff_link.short_description = 'Staff'
    
    def payment_status_badge(self, obj):
        colors = {
            'pending': 'warning',
            'processed': 'info',
            'paid': 'success',
        }
        color = colors.get(obj.payment_status, 'secondary')
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_payment_status_display())
    payment_status_badge.short_description = 'Status'


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ['staff_link', 'annual_leave', 'sick_leave', 'casual_leave', 'comp_off', 'last_updated']
    list_filter = ['last_updated']
    search_fields = ['staff__user__first_name', 'staff__user__last_name']
    
    def staff_link(self, obj):
        if obj.staff:
            url = reverse('admin:hospital_staff_change', args=[obj.staff.pk])
            return format_html('<a href="{}">{}</a>', url, obj.staff.user.get_full_name())
        return "-"
    staff_link.short_description = 'Staff'


@admin.register(PerformanceReview)
class PerformanceReviewAdmin(admin.ModelAdmin):
    list_display = ['review_number', 'staff_link', 'review_date', 'overall_rating_badge', 'is_approved']
    list_filter = ['overall_rating', 'is_approved', 'review_date']
    search_fields = ['review_number', 'staff__user__first_name', 'staff__user__last_name']
    ordering = ['-review_date']
    readonly_fields = ['review_number']
    
    def staff_link(self, obj):
        if obj.staff:
            url = reverse('admin:hospital_staff_change', args=[obj.staff.pk])
            return format_html('<a href="{}">{}</a>', url, obj.staff.user.get_full_name())
        return "-"
    staff_link.short_description = 'Staff'
    
    def overall_rating_badge(self, obj):
        colors = {
            'excellent': 'success',
            'good': 'primary',
            'satisfactory': 'info',
            'needs_improvement': 'warning',
            'unsatisfactory': 'danger',
        }
        color = colors.get(obj.overall_rating, 'secondary')
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_overall_rating_display())
    overall_rating_badge.short_description = 'Rating'


@admin.register(DisciplinaryAction)
class DisciplinaryActionAdmin(admin.ModelAdmin):
    list_display = ['action_number', 'staff_link', 'action_type_badge', 'incident_date', 'is_resolved']
    list_filter = ['action_type', 'is_resolved', 'incident_date']
    search_fields = ['action_number', 'staff__user__first_name', 'staff__user__last_name']
    ordering = ['-action_date']
    readonly_fields = ['action_number']
    
    def staff_link(self, obj):
        if obj.staff:
            url = reverse('admin:hospital_staff_change', args=[obj.staff.pk])
            return format_html('<a href="{}">{}</a>', url, obj.staff.user.get_full_name())
        return "-"
    staff_link.short_description = 'Staff'
    
    def action_type_badge(self, obj):
        colors = {
            'verbal_warning': 'warning',
            'written_warning': 'danger',
            'suspension': 'danger',
            'termination': 'dark',
            'other': 'secondary',
        }
        color = colors.get(obj.action_type, 'secondary')
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_action_type_display())
    action_type_badge.short_description = 'Action'


@admin.register(TrainingRecord)
class TrainingRecordAdmin(admin.ModelAdmin):
    list_display = ['record_number', 'staff_link', 'training_title', 'start_date', 'status_badge', 'certificate_issued']
    list_filter = ['status', 'certificate_issued', 'start_date']
    search_fields = ['record_number', 'training_title', 'staff__user__first_name']
    ordering = ['-start_date']
    readonly_fields = ['record_number']
    
    def staff_link(self, obj):
        if obj.staff:
            url = reverse('admin:hospital_staff_change', args=[obj.staff.pk])
            return format_html('<a href="{}">{}</a>', url, obj.staff.user.get_full_name())
        return "-"
    staff_link.short_description = 'Staff'
    
    def status_badge(self, obj):
        colors = {
            'scheduled': 'info',
            'in_progress': 'primary',
            'completed': 'success',
            'cancelled': 'danger',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_status_display())
    status_badge.short_description = 'Status'


@admin.register(StaffDocument)
class StaffDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'staff_link', 'document_type', 'file_link', 'expiry_date', 'is_active']
    list_filter = ['document_type', 'is_active']
    search_fields = ['title', 'staff__user__first_name']
    
    def staff_link(self, obj):
        if obj.staff:
            url = reverse('admin:hospital_staff_change', args=[obj.staff.pk])
            return format_html('<a href="{}">{}</a>', url, obj.staff.user.get_full_name())
        return "-"
    staff_link.short_description = 'Staff'
    
    def file_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">View</a>', obj.file.url)
        return "-"
    file_link.short_description = 'File'


@admin.register(StaffNote)
class StaffNoteAdmin(admin.ModelAdmin):
    list_display = ['title', 'staff_link', 'note_type_badge', 'created_by', 'is_confidential', 'created']
    list_filter = ['note_type', 'is_confidential', 'created']
    search_fields = ['title', 'content', 'staff__user__first_name']
    ordering = ['-created']
    
    def staff_link(self, obj):
        if obj.staff:
            url = reverse('admin:hospital_staff_change', args=[obj.staff.pk])
            return format_html('<a href="{}">{}</a>', url, obj.staff.user.get_full_name())
        return "-"
    staff_link.short_description = 'Staff'
    
    def note_type_badge(self, obj):
        colors = {
            'general': 'secondary',
            'warning': 'warning',
            'commendation': 'success',
            'medical': 'info',
            'other': 'primary',
        }
        color = colors.get(obj.note_type, 'secondary')
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_note_type_display())
    note_type_badge.short_description = 'Type'


# Register new models
try:
    from .models_hr import StaffShift, ShiftTemplate, StaffQualification, LeaveRequestApproval

    @admin.register(StaffShift)
    class StaffShiftAdmin(admin.ModelAdmin):
        list_display = ['staff_link', 'shift_date', 'shift_type_badge', 'start_time', 'end_time', 'department', 'is_confirmed']
        list_filter = ['shift_type', 'shift_date', 'department', 'is_confirmed']
        search_fields = ['staff__user__first_name', 'staff__user__last_name']
        ordering = ['-shift_date', 'start_time']
        
        def staff_link(self, obj):
            if obj.staff:
                url = reverse('admin:hospital_staff_change', args=[obj.staff.pk])
                return format_html('<a href="{}">{}</a>', url, obj.staff.user.get_full_name())
            return "-"
        staff_link.short_description = 'Staff'
        
        def shift_type_badge(self, obj):
            colors = {
                'day': 'info',
                'evening': 'warning',
                'night': 'dark',
                'on_call': 'primary',
                'weekend': 'success',
            }
            color = colors.get(obj.shift_type, 'secondary')
            return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_shift_type_display())
        shift_type_badge.short_description = 'Shift Type'

    @admin.register(ShiftTemplate)
    class ShiftTemplateAdmin(admin.ModelAdmin):
        list_display = ['name', 'shift_type', 'start_time', 'end_time', 'department', 'is_active']
        list_filter = ['shift_type', 'is_active', 'department']
        search_fields = ['name']

    @admin.register(StaffQualification)
    class StaffQualificationAdmin(admin.ModelAdmin):
        list_display = ['title', 'staff_link', 'qualification_type', 'institution', 'issue_date', 'is_active']
        list_filter = ['qualification_type', 'is_active', 'issue_date']
        search_fields = ['title', 'staff__user__first_name']
        
        def staff_link(self, obj):
            if obj.staff:
                url = reverse('admin:hospital_staff_change', args=[obj.staff.pk])
                return format_html('<a href="{}">{}</a>', url, obj.staff.user.get_full_name())
            return "-"
        staff_link.short_description = 'Staff'

    @admin.register(LeaveRequestApproval)
    class LeaveRequestApprovalAdmin(admin.ModelAdmin):
        list_display = ['leave_request_link', 'approval_level', 'status_badge', 'approver', 'approved_at']
        list_filter = ['status', 'approval_level']
        
        def leave_request_link(self, obj):
            if obj.leave_request:
                return str(obj.leave_request)
            return "-"
        leave_request_link.short_description = 'Leave Request'
        
        def status_badge(self, obj):
            colors = {
                'pending': 'warning',
                'approved': 'success',
                'rejected': 'danger',
            }
            color = colors.get(obj.status, 'secondary')
            return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_status_display())
        status_badge.short_description = 'Status'
except ImportError:
    pass


# Payroll Configuration Admin
@admin.register(AllowanceType)
class AllowanceTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'calculation_type', 'default_amount', 'is_taxable', 'is_statutory', 'display_order', 'is_active']
    list_filter = ['calculation_type', 'is_taxable', 'is_statutory', 'is_active']
    search_fields = ['name', 'code', 'description']
    ordering = ['display_order', 'name']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description')
        }),
        ('Calculation', {
            'fields': ('calculation_type', 'default_amount')
        }),
        ('Settings', {
            'fields': ('is_taxable', 'is_statutory', 'display_order', 'is_active')
        }),
    )


@admin.register(DeductionType)
class DeductionTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'calculation_type', 'default_amount', 'is_statutory', 'is_loan', 'display_order', 'is_active']
    list_filter = ['calculation_type', 'is_statutory', 'is_loan', 'is_active']
    search_fields = ['name', 'code', 'description']
    ordering = ['display_order', 'name']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description')
        }),
        ('Calculation', {
            'fields': ('calculation_type', 'default_amount', 'min_amount', 'max_amount')
        }),
        ('Settings', {
            'fields': ('is_statutory', 'is_loan', 'display_order', 'is_active')
        }),
    )


@admin.register(TaxBracket)
class TaxBracketAdmin(admin.ModelAdmin):
    list_display = ['bracket_name', 'min_income', 'max_income', 'tax_rate', 'fixed_amount', 'effective_from', 'effective_to', 'is_active']
    list_filter = ['is_active', 'effective_from', 'effective_to']
    search_fields = ['bracket_name']
    ordering = ['min_income']
    fieldsets = (
        ('Bracket Information', {
            'fields': ('bracket_name', 'min_income', 'max_income')
        }),
        ('Tax Calculation', {
            'fields': ('tax_rate', 'fixed_amount')
        }),
        ('Effective Dates', {
            'fields': ('effective_from', 'effective_to', 'is_active')
        }),
    )


@admin.register(PayrollConfiguration)
class PayrollConfigurationAdmin(admin.ModelAdmin):
    list_display = ['name', 'tax_calculation_method', 'default_tax_rate', 'social_security_rate', 'pension_rate', 'is_default', 'is_active']
    list_filter = ['tax_calculation_method', 'is_default', 'is_active']
    search_fields = ['name', 'notes']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'is_active', 'is_default')
        }),
        ('Tax Settings', {
            'fields': ('tax_calculation_method', 'default_tax_rate', 'tax_free_allowance')
        }),
        ('Social Security', {
            'fields': ('social_security_rate', 'social_security_max_amount')
        }),
        ('Pension', {
            'fields': ('pension_rate', 'pension_max_amount')
        }),
        ('Payroll Period', {
            'fields': ('default_payroll_day',)
        }),
        ('Overtime', {
            'fields': ('regular_hours_per_day', 'overtime_multiplier')
        }),
        ('Currency', {
            'fields': ('currency_symbol', 'currency_code')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )


@admin.register(PayrollAllowance)
class PayrollAllowanceAdmin(admin.ModelAdmin):
    list_display = ['payroll', 'allowance_type', 'amount', 'is_taxable', 'description']
    list_filter = ['allowance_type', 'is_taxable']
    search_fields = ['description', 'allowance_type__name']
    readonly_fields = ['payroll']


@admin.register(PayrollDeduction)
class PayrollDeductionAdmin(admin.ModelAdmin):
    list_display = ['payroll', 'deduction_type', 'amount', 'description']
    list_filter = ['deduction_type']
    search_fields = ['description', 'deduction_type__name']
    readonly_fields = ['payroll']


@admin.register(PerformanceKPI)
class PerformanceKPIAdmin(admin.ModelAdmin):
    list_display = ['kpi_code', 'kpi_name', 'category', 'weight_percentage', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['kpi_code', 'kpi_name']
    ordering = ['category', 'kpi_name']


class PerformanceKPIRatingInline(admin.TabularInline):
    model = PerformanceKPIRating
    extra = 1
    fields = ['kpi', 'score', 'comments']


@admin.register(TrainingProgram)
class TrainingProgramAdmin(admin.ModelAdmin):
    list_display = ['program_code', 'program_name', 'program_type', 'category', 'duration_hours', 'cost_per_person', 'is_active']
    list_filter = ['program_type', 'category', 'is_active']
    search_fields = ['program_code', 'program_name']
    ordering = ['program_name']


if StaffMedicalChit:
    @admin.register(StaffMedicalChit)
    class StaffMedicalChitAdmin(admin.ModelAdmin):
        list_display = ['chit_number', 'staff_link', 'application_date', 'status_badge', 'hr_approved_by', 'hr_approval_date', 'valid_until', 'encounter_link']
        list_filter = ['status', 'application_date', 'hr_approval_date']
        search_fields = ['chit_number', 'staff__user__first_name', 'staff__user__last_name', 'staff__employee_id', 'reason']
        readonly_fields = ['chit_number']
        ordering = ['-application_date', '-created']
        
        fieldsets = (
            ('Chit Information', {
                'fields': ('chit_number', 'staff', 'application_date', 'status')
            }),
            ('Application Details', {
                'fields': ('reason', 'symptoms')
            }),
            ('HR Approval', {
                'fields': ('hr_approved_by', 'hr_approval_date', 'hr_approval_notes', 'hr_rejection_reason', 'authorized_by_name', 'authorized_by_signature')
            }),
            ('Visit Information', {
                'fields': ('encounter', 'visit_created_at', 'visit_created_by')
            }),
            ('Validity', {
                'fields': ('valid_until',)
            }),
            ('SMS Tracking', {
                'fields': ('sms_sent_approval', 'sms_sent_visit_ready')
            }),
            ('Timestamps', {
                'fields': ('created_at', 'updated_at')
            }),
        )
        
        def staff_link(self, obj):
            if obj.staff:
                url = reverse('admin:hospital_staff_change', args=[obj.staff.pk])
                return format_html('<a href="{}">{}</a>', url, obj.staff.user.get_full_name())
            return "-"
        staff_link.short_description = 'Staff'
        
        def status_badge(self, obj):
            colors = {
                'pending': 'warning',
                'approved': 'success',
                'rejected': 'danger',
                'used': 'info',
                'expired': 'secondary',
            }
            color = colors.get(obj.status, 'secondary')
            return format_html(
                '<span class="badge bg-{}">{}</span>',
                color,
                obj.get_status_display()
            )
        status_badge.short_description = 'Status'
        
        def encounter_link(self, obj):
            if obj.encounter:
                url = reverse('admin:hospital_encounter_change', args=[obj.encounter.pk])
                return format_html('<a href="{}">Visit #{}</a>', url, obj.encounter.id)
            return "-"
        encounter_link.short_description = 'Visit'

