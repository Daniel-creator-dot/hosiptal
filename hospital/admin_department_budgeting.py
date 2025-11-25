"""
Admin Interface for Department Budgeting System
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from django.urls import reverse
from django.utils.safestring import mark_safe
from decimal import Decimal

from .models_department_budgeting import (
    BudgetPeriod, DepartmentBudget, BudgetLineItem,
    BudgetExpense, BudgetTransfer, BudgetVariance,
    BudgetAlert, BudgetRevision, BudgetReport
)


# ==================== INLINE ADMIN CLASSES ====================

class DepartmentBudgetInline(admin.TabularInline):
    model = DepartmentBudget
    extra = 0
    fields = ['department', 'allocated_amount', 'spent_amount', 'status_badge']
    readonly_fields = ['status_badge']
    
    def status_badge(self, obj):
        colors = {
            'draft': 'secondary',
            'submitted': 'info',
            'approved': 'success',
            'rejected': 'danger',
            'active': 'primary',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


class BudgetLineItemInline(admin.TabularInline):
    model = BudgetLineItem
    extra = 1
    fields = ['category', 'item_name', 'budgeted_amount', 'spent_amount', 'remaining_display']
    readonly_fields = ['remaining_display']
    
    def remaining_display(self, obj):
        if obj.pk:
            remaining = obj.get_remaining()
            color = 'success' if remaining >= 0 else 'danger'
            return format_html(
                '<span class="badge bg-{}">GHS {}</span>',
                color, remaining
            )
        return '—'
    remaining_display.short_description = 'Remaining'


class BudgetExpenseInline(admin.TabularInline):
    model = BudgetExpense
    extra = 0
    fields = ['expense_date', 'description', 'amount', 'expense_category']
    readonly_fields = ['expense_date']


# ==================== ADMIN CLASSES ====================

@admin.register(BudgetPeriod)
class BudgetPeriodAdmin(admin.ModelAdmin):
    list_display = ['name', 'period_type', 'start_date', 'end_date', 'total_budget_display', 'utilization_display', 'status_badge', 'approved_badge']
    list_filter = ['status', 'period_type', 'start_date']
    search_fields = ['name']
    readonly_fields = ['total_allocated', 'approved_at', 'approved_by']
    inlines = [DepartmentBudgetInline]
    
    fieldsets = (
        ('Period Information', {
            'fields': ('name', 'period_type', 'start_date', 'end_date')
        }),
        ('Budget Summary', {
            'fields': ('total_budget', 'total_allocated', 'status')
        }),
        ('Approval', {
            'fields': ('approved_by', 'approved_at')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    def total_budget_display(self, obj):
        return format_html(
            '<strong style="color: #1976d2;">GHS {:,}</strong>',
            obj.total_budget
        )
    total_budget_display.short_description = 'Total Budget'
    
    def utilization_display(self, obj):
        percentage = obj.get_utilization_percentage()
        if percentage >= 100:
            color = 'danger'
        elif percentage >= 80:
            color = 'warning'
        else:
            color = 'success'
        
        return format_html(
            '<div style="width: 100px; background: #f0f0f0; border-radius: 8px; overflow: hidden;">'
            '<div style="width: {}%; background: {}; padding: 4px 8px; color: white; font-size: 11px; font-weight: bold; text-align: center;">{:.1f}%</div>'
            '</div>',
            min(percentage, 100), 
            f'var(--bs-{color})',
            percentage
        )
    utilization_display.short_description = 'Utilization'
    
    def status_badge(self, obj):
        colors = {
            'draft': 'secondary',
            'approved': 'success',
            'active': 'primary',
            'closed': 'dark',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def approved_badge(self, obj):
        if obj.approved_at:
            return format_html('<span class="badge bg-success">✓ Approved</span>')
        return format_html('<span class="badge bg-warning">Pending</span>')
    approved_badge.short_description = 'Approval'


@admin.register(DepartmentBudget)
class DepartmentBudgetAdmin(admin.ModelAdmin):
    list_display = ['department', 'budget_period', 'allocated_display', 'spent_display', 'available_display', 'utilization_bar', 'status_badge']
    list_filter = ['status', 'budget_period', 'department']
    search_fields = ['department__name', 'budget_period__name']
    readonly_fields = ['allocated_amount', 'spent_amount', 'committed_amount', 'approved_at', 'approved_by']
    inlines = [BudgetLineItemInline, BudgetExpenseInline]
    
    fieldsets = (
        ('Budget Assignment', {
            'fields': ('budget_period', 'department', 'status')
        }),
        ('Budget Categories', {
            'fields': ('personnel_budget', 'operational_budget', 'supplies_budget', 'capital_budget')
        }),
        ('Budget Totals', {
            'fields': ('allocated_amount', 'spent_amount', 'committed_amount')
        }),
        ('Justification', {
            'fields': ('justification',)
        }),
        ('Approval', {
            'fields': ('submitted_by', 'submitted_at', 'approved_by', 'approved_at'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    def allocated_display(self, obj):
        return format_html('<strong>GHS {:,}</strong>', obj.allocated_amount)
    allocated_display.short_description = 'Allocated'
    
    def spent_display(self, obj):
        color = 'danger' if obj.is_overbudget() else 'success'
        return format_html('<span style="color: var(--bs-{});">GHS {:,}</span>', color, obj.spent_amount)
    spent_display.short_description = 'Spent'
    
    def available_display(self, obj):
        available = obj.get_available_amount()
        color = 'success' if available > 0 else 'danger'
        return format_html('<span style="color: var(--bs-{});">GHS {:,}</span>', color, available)
    available_display.short_description = 'Available'
    
    def utilization_bar(self, obj):
        percentage = obj.get_utilization_percentage()
        
        if percentage >= 100:
            color = '#dc3545'  # danger
        elif percentage >= 90:
            color = '#fd7e14'  # warning-orange
        elif percentage >= 75:
            color = '#ffc107'  # warning
        else:
            color = '#28a745'  # success
        
        return format_html(
            '<div style="width: 120px; background: #e9ecef; border-radius: 10px; overflow: hidden; height: 20px;">'
            '<div style="width: {}%; background: {}; height: 100%; display: flex; align-items: center; justify-content: center; color: white; font-size: 10px; font-weight: bold;">'
            '{:.0f}%'
            '</div>'
            '</div>',
            min(percentage, 100),
            color,
            percentage
        )
    utilization_bar.short_description = 'Utilization'
    
    def status_badge(self, obj):
        colors = {
            'draft': 'secondary',
            'submitted': 'info',
            'approved': 'success',
            'rejected': 'danger',
            'active': 'primary',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_status_display())
    status_badge.short_description = 'Status'


@admin.register(BudgetLineItem)
class BudgetLineItemAdmin(admin.ModelAdmin):
    list_display = ['item_name', 'department_display', 'category', 'budgeted_amount_display', 'spent_amount_display', 'remaining_display', 'utilization_display']
    list_filter = ['category', 'department_budget__department', 'department_budget__budget_period']
    search_fields = ['item_name', 'description']
    
    def department_display(self, obj):
        return obj.department_budget.department.name
    department_display.short_description = 'Department'
    
    def budgeted_amount_display(self, obj):
        return format_html('GHS {:,}', obj.budgeted_amount)
    budgeted_amount_display.short_description = 'Budget'
    
    def spent_amount_display(self, obj):
        return format_html('GHS {:,}', obj.spent_amount)
    spent_amount_display.short_description = 'Spent'
    
    def remaining_display(self, obj):
        remaining = obj.get_remaining()
        color = 'success' if remaining >= 0 else 'danger'
        return format_html('<span class="badge bg-{}">GHS {:,}</span>', color, remaining)
    remaining_display.short_description = 'Remaining'
    
    def utilization_display(self, obj):
        percentage = obj.get_utilization_percentage()
        if percentage >= 100:
            color = 'danger'
        elif percentage >= 75:
            color = 'warning'
        else:
            color = 'success'
        return format_html('<span class="badge bg-{}">{:.1f}%</span>', color, percentage)
    utilization_display.short_description = 'Utilization'


@admin.register(BudgetExpense)
class BudgetExpenseAdmin(admin.ModelAdmin):
    list_display = ['description', 'department_display', 'expense_date', 'amount_display', 'expense_category', 'approved_badge']
    list_filter = ['expense_category', 'expense_date', 'department_budget__department']
    search_fields = ['description', 'vendor', 'reference_number']
    date_hierarchy = 'expense_date'
    
    def department_display(self, obj):
        return obj.department_budget.department.name
    department_display.short_description = 'Department'
    
    def amount_display(self, obj):
        return format_html('<strong>GHS {:,}</strong>', obj.amount)
    amount_display.short_description = 'Amount'
    
    def approved_badge(self, obj):
        if obj.approved_at:
            return format_html('<span class="badge bg-success">✓</span>')
        return format_html('<span class="badge bg-warning">Pending</span>')
    approved_badge.short_description = 'Approved'


@admin.register(BudgetTransfer)
class BudgetTransferAdmin(admin.ModelAdmin):
    list_display = ['transfer_date', 'from_dept', 'to_dept', 'amount_display', 'status_badge', 'approved_badge']
    list_filter = ['status', 'transfer_date']
    search_fields = ['reason', 'from_department_budget__department__name', 'to_department_budget__department__name']
    readonly_fields = ['approved_at', 'approved_by']
    
    fieldsets = (
        ('Transfer Details', {
            'fields': ('transfer_date', 'amount')
        }),
        ('From', {
            'fields': ('from_department_budget', 'from_line_item')
        }),
        ('To', {
            'fields': ('to_department_budget', 'to_line_item')
        }),
        ('Justification', {
            'fields': ('reason', 'status')
        }),
        ('Approval', {
            'fields': ('requested_by', 'approved_by', 'approved_at'),
            'classes': ('collapse',)
        }),
    )
    
    def from_dept(self, obj):
        return obj.from_department_budget.department.name
    from_dept.short_description = 'From Department'
    
    def to_dept(self, obj):
        return obj.to_department_budget.department.name
    to_dept.short_description = 'To Department'
    
    def amount_display(self, obj):
        return format_html('<strong>GHS {:,}</strong>', obj.amount)
    amount_display.short_description = 'Amount'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'warning',
            'approved': 'success',
            'rejected': 'danger',
            'completed': 'primary',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_status_display())
    status_badge.short_description = 'Status'
    
    def approved_badge(self, obj):
        if obj.approved_at:
            return format_html('<span class="badge bg-success">✓ {}</span>', obj.approved_at.strftime('%m/%d'))
        return format_html('<span class="badge bg-warning">Pending</span>')
    approved_badge.short_description = 'Approval'


@admin.register(BudgetVariance)
class BudgetVarianceAdmin(admin.ModelAdmin):
    list_display = ['department_display', 'variance_date', 'variance_amount_display', 'variance_type_badge', 'variance_percentage']
    list_filter = ['variance_type', 'variance_date', 'department_budget__department']
    search_fields = ['explanation', 'corrective_action']
    
    def department_display(self, obj):
        return obj.department_budget.department.name
    department_display.short_description = 'Department'
    
    def variance_amount_display(self, obj):
        color = 'success' if obj.variance_type == 'favorable' else 'danger'
        return format_html('<span style="color: var(--bs-{});">GHS {:,}</span>', color, obj.variance_amount)
    variance_amount_display.short_description = 'Variance'
    
    def variance_type_badge(self, obj):
        color = 'success' if obj.variance_type == 'favorable' else 'danger'
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_variance_type_display())
    variance_type_badge.short_description = 'Type'


@admin.register(BudgetAlert)
class BudgetAlertAdmin(admin.ModelAdmin):
    list_display = ['department_display', 'alert_type', 'severity_badge', 'current_utilization', 'acknowledged_badge', 'created']
    list_filter = ['severity', 'alert_type', 'is_acknowledged', 'department_budget__department']
    search_fields = ['message', 'action_taken']
    readonly_fields = ['acknowledged_at', 'acknowledged_by']
    
    def department_display(self, obj):
        return obj.department_budget.department.name
    department_display.short_description = 'Department'
    
    def severity_badge(self, obj):
        colors = {
            'info': 'info',
            'warning': 'warning',
            'critical': 'danger',
        }
        color = colors.get(obj.severity, 'secondary')
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_severity_display())
    severity_badge.short_description = 'Severity'
    
    def acknowledged_badge(self, obj):
        if obj.is_acknowledged:
            return format_html('<span class="badge bg-success">✓ Acknowledged</span>')
        return format_html('<span class="badge bg-warning">⚠ Pending</span>')
    acknowledged_badge.short_description = 'Status'


@admin.register(BudgetRevision)
class BudgetRevisionAdmin(admin.ModelAdmin):
    list_display = ['department_display', 'revision_number', 'revision_date', 'old_amount', 'new_amount', 'change_display', 'approved_badge']
    list_filter = ['is_approved', 'revision_date', 'department_budget__department']
    search_fields = ['reason', 'justification']
    readonly_fields = ['change_amount', 'approved_at', 'approved_by']
    
    def department_display(self, obj):
        return obj.department_budget.department.name
    department_display.short_description = 'Department'
    
    def old_amount(self, obj):
        return format_html('GHS {:,}', obj.old_allocated_amount)
    old_amount.short_description = 'Old Budget'
    
    def new_amount(self, obj):
        return format_html('GHS {:,}', obj.new_allocated_amount)
    new_amount.short_description = 'New Budget'
    
    def change_display(self, obj):
        color = 'success' if obj.change_amount > 0 else 'danger'
        sign = '+' if obj.change_amount > 0 else ''
        return format_html('<span style="color: var(--bs-{});">{} GHS {:,}</span>', color, sign, obj.change_amount)
    change_display.short_description = 'Change'
    
    def approved_badge(self, obj):
        if obj.is_approved:
            return format_html('<span class="badge bg-success">✓ Approved</span>')
        return format_html('<span class="badge bg-warning">Pending</span>')
    approved_badge.short_description = 'Approval'


@admin.register(BudgetReport)
class BudgetReportAdmin(admin.ModelAdmin):
    list_display = ['report_type', 'report_period', 'department', 'report_date', 'total_budget_display', 'utilization_display', 'generated_by']
    list_filter = ['report_type', 'report_date', 'department']
    search_fields = ['notes']
    readonly_fields = ['report_data']
    
    def total_budget_display(self, obj):
        return format_html('GHS {:,}', obj.total_budget)
    total_budget_display.short_description = 'Budget'
    
    def utilization_display(self, obj):
        percentage = obj.utilization_percentage
        if percentage >= 100:
            color = 'danger'
        elif percentage >= 75:
            color = 'warning'
        else:
            color = 'success'
        return format_html('<span class="badge bg-{}">{:.1f}%</span>', color, percentage)
    utilization_display.short_description = 'Utilization'













