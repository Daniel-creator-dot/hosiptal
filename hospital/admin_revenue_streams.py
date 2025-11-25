"""
Admin Interface for Revenue Stream Tracking
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count
from .models_revenue_streams import RevenueStream, DepartmentRevenue


@admin.register(RevenueStream)
class RevenueStreamAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'stream_type_badge', 'department', 'monthly_target_display', 
                    'annual_target_display', 'is_active']
    list_filter = ['stream_type', 'department', 'is_active']
    search_fields = ['code', 'name']
    
    fieldsets = (
        ('Stream Information', {
            'fields': ('code', 'name', 'stream_type', 'department')
        }),
        ('Description', {
            'fields': ('description',)
        }),
        ('Targets', {
            'fields': ('monthly_target', 'annual_target')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def stream_type_badge(self, obj):
        colors = {
            'clinical': '#3b82f6',
            'diagnostic': '#10b981',
            'pharmacy': '#f59e0b',
            'administrative': '#8b5cf6',
            'other': '#6c757d',
        }
        color = colors.get(obj.stream_type, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_stream_type_display()
        )
    stream_type_badge.short_description = 'Type'
    
    def monthly_target_display(self, obj):
        return format_html('GHS {:,.2f}', obj.monthly_target)
    monthly_target_display.short_description = 'Monthly Target'
    
    def annual_target_display(self, obj):
        return format_html('GHS {:,.2f}', obj.annual_target)
    annual_target_display.short_description = 'Annual Target'


@admin.register(DepartmentRevenue)
class DepartmentRevenueAdmin(admin.ModelAdmin):
    list_display = ['date', 'department', 'revenue_stream', 'source_type', 'amount_display', 
                    'transaction_count']
    list_filter = ['date', 'department', 'revenue_stream', 'source_type']
    search_fields = ['department__name', 'revenue_stream__name']
    date_hierarchy = 'date'
    
    def amount_display(self, obj):
        return format_html('<strong style="color: #10b981;">GHS {:,.2f}</strong>', obj.amount)
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'




















