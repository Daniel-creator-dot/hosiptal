"""
Admin configuration for enhanced HR models
"""
from django.contrib import admin
from .models_hr_enhanced import (
    StaffEmploymentContract,
    AttendanceCalendar,
    PublicHoliday,
    StaffPerformanceGoal
)


@admin.register(StaffEmploymentContract)
class StaffEmploymentContractAdmin(admin.ModelAdmin):
    list_display = ['staff', 'contract', 'is_current', 'monthly_salary', 'days_until_expiry']
    list_filter = ['is_current', 'health_insurance', 'pension_included']
    search_fields = ['staff__user__first_name', 'staff__user__last_name', 'contract__contract_name']
    readonly_fields = ['created', 'modified']
    
    fieldsets = (
        ('Staff Information', {
            'fields': ('staff', 'contract', 'is_current')
        }),
        ('Employment Details', {
            'fields': ('probation_end_date', 'notice_period_days')
        }),
        ('Salary & Benefits', {
            'fields': (
                ('monthly_salary', 'annual_salary'),
                ('housing_allowance', 'transport_allowance'),
                ('health_insurance', 'pension_included'),
            )
        }),
        ('Leave Entitlements', {
            'fields': (('annual_leave_days', 'sick_leave_days'),)
        }),
    )


@admin.register(AttendanceCalendar)
class AttendanceCalendarAdmin(admin.ModelAdmin):
    list_display = ['staff', 'attendance_date', 'status', 'check_in_time', 'check_out_time', 'total_hours', 'is_late']
    list_filter = ['status', 'attendance_date', 'is_late', 'is_early_departure']
    search_fields = ['staff__user__first_name', 'staff__user__last_name']
    date_hierarchy = 'attendance_date'
    readonly_fields = ['total_hours', 'overtime_hours', 'created', 'modified']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('staff', 'attendance_date', 'status')
        }),
        ('Time Tracking', {
            'fields': (
                ('check_in_time', 'check_out_time'),
                ('total_hours', 'overtime_hours'),
            )
        }),
        ('Late/Early', {
            'fields': (
                ('is_late', 'late_by_minutes'),
                ('is_early_departure', 'early_by_minutes'),
            )
        }),
        ('Notes', {
            'fields': ('notes', 'marked_by')
        }),
    )
    
    actions = ['mark_as_present', 'mark_as_absent', 'calculate_hours_bulk']
    
    def mark_as_present(self, request, queryset):
        queryset.update(status='present')
        self.message_user(request, f'{queryset.count()} records marked as present.')
    mark_as_present.short_description = "Mark selected as Present"
    
    def mark_as_absent(self, request, queryset):
        queryset.update(status='absent')
        self.message_user(request, f'{queryset.count()} records marked as absent.')
    mark_as_absent.short_description = "Mark selected as Absent"
    
    def calculate_hours_bulk(self, request, queryset):
        count = 0
        for record in queryset:
            record.calculate_hours()
            count += 1
        self.message_user(request, f'Hours calculated for {count} records.')
    calculate_hours_bulk.short_description = "Calculate hours for selected"


@admin.register(PublicHoliday)
class PublicHolidayAdmin(admin.ModelAdmin):
    list_display = ['holiday_name', 'holiday_date', 'is_recurring']
    list_filter = ['is_recurring', 'holiday_date']
    search_fields = ['holiday_name', 'description']
    date_hierarchy = 'holiday_date'
    
    fieldsets = (
        ('Holiday Information', {
            'fields': ('holiday_name', 'holiday_date', 'description')
        }),
        ('Settings', {
            'fields': ('is_recurring',)
        }),
    )


@admin.register(StaffPerformanceGoal)
class StaffPerformanceGoalAdmin(admin.ModelAdmin):
    list_display = ['staff', 'goal_title', 'status', 'progress_percentage', 'target_date', 'is_overdue']
    list_filter = ['status', 'target_date', 'set_date']
    search_fields = ['staff__user__first_name', 'staff__user__last_name', 'goal_title', 'description']
    date_hierarchy = 'target_date'
    readonly_fields = ['created', 'modified', 'is_overdue', 'days_remaining']
    
    fieldsets = (
        ('Staff & Goal', {
            'fields': ('staff', 'goal_title', 'description')
        }),
        ('Timeline', {
            'fields': (
                ('set_date', 'target_date', 'completed_date'),
                ('days_remaining', 'is_overdue'),
            )
        }),
        ('Progress', {
            'fields': (
                'status',
                'progress_percentage',
                ('target_value', 'achieved_value'),
            )
        }),
        ('Review', {
            'fields': ('set_by', 'notes')
        }),
    )
    
    actions = ['mark_as_achieved', 'mark_as_in_progress']
    
    def mark_as_achieved(self, request, queryset):
        queryset.update(status='achieved', progress_percentage=100)
        self.message_user(request, f'{queryset.count()} goals marked as achieved.')
    mark_as_achieved.short_description = "Mark selected as Achieved"
    
    def mark_as_in_progress(self, request, queryset):
        queryset.update(status='in_progress')
        self.message_user(request, f'{queryset.count()} goals marked as in progress.')
    mark_as_in_progress.short_description = "Mark selected as In Progress"























