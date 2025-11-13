"""
Simple Admin for HOD
"""

from django.contrib import admin
from django.utils.html import format_html
from .models_hod_simple import HeadOfDepartment


@admin.register(HeadOfDepartment)
class HeadOfDepartmentAdmin(admin.ModelAdmin):
    list_display = ['staff_name', 'department', 'appointed_date', 'is_active_badge', 'authorities']
    list_filter = ['department', 'is_active']
    search_fields = ['staff__user__first_name', 'staff__user__last_name', 'staff__user__username', 'department__name']
    
    fieldsets = (
        ('HOD Designation', {
            'fields': ('staff', 'department')
        }),
        ('Authorities', {
            'fields': (
                'can_manage_schedules',
                'can_approve_procurement',
                'can_approve_leave',
            )
        }),
        ('Status', {
            'fields': ('appointed_date', 'is_active')
        }),
    )
    
    def staff_name(self, obj):
        return obj.staff.user.get_full_name() or obj.staff.user.username
    staff_name.short_description = 'Staff'
    
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">● Active</span>')
        return format_html('<span style="color: red;">● Inactive</span>')
    is_active_badge.short_description = 'Status'
    
    def authorities(self, obj):
        perms = []
        if obj.can_manage_schedules:
            perms.append('Schedules')
        if obj.can_approve_procurement:
            perms.append('Procurement')
        if obj.can_approve_leave:
            perms.append('Leave')
        return ', '.join(perms) if perms else 'None'
    authorities.short_description = 'Can Approve'

