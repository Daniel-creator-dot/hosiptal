"""
Admin configuration for Flexible Pricing System
World-class pricing administration
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from .models_flexible_pricing import PricingCategory, ServicePrice, PriceHistory, BulkPriceUpdate


@admin.register(PricingCategory)
class PricingCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'category_type_badge', 'services_count_display', 
                    'is_active', 'priority', 'created']
    list_filter = ['category_type', 'is_active', 'created']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['created', 'modified']
    list_per_page = 25
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'category_type', 'description')
        }),
        ('Linked Insurance', {
            'fields': ('insurance_company',),
            'classes': ('collapse',)
        }),
        ('Pricing Settings', {
            'fields': ('default_discount_percentage', 'priority')
        }),
        ('Display', {
            'fields': ('color_code', 'is_active')
        }),
        ('System Information', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    
    def category_type_badge(self, obj):
        """Display category type with color badge"""
        colors = {
            'cash': 'success',
            'insurance': 'primary',
            'corporate': 'info',
            'government': 'warning',
            'discount': 'secondary',
            'premium': 'danger',
        }
        color = colors.get(obj.category_type, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_category_type_display()
        )
    category_type_badge.short_description = 'Type'
    
    def services_count_display(self, obj):
        """Display number of priced services"""
        count = obj.services_count
        url = reverse('admin:hospital_serviceprice_changelist') + f'?pricing_category__id__exact={obj.id}'
        return format_html(
            '<a href="{}" class="btn btn-sm btn-primary">{} Services</a>',
            url, count
        )
    services_count_display.short_description = 'Priced Services'


@admin.register(ServicePrice)
class ServicePriceAdmin(admin.ModelAdmin):
    list_display = ['service_code', 'pricing_category', 'price_display', 
                    'effective_from', 'effective_to', 'is_current_display', 'is_active']
    list_filter = ['pricing_category', 'is_active', 'effective_from']
    search_fields = ['service_code__code', 'service_code__description', 
                    'pricing_category__name']
    readonly_fields = ['created', 'modified']
    date_hierarchy = 'effective_from'
    list_per_page = 50
    
    fieldsets = (
        ('Service & Category', {
            'fields': ('service_code', 'pricing_category')
        }),
        ('Price', {
            'fields': ('price',)
        }),
        ('Effective Period', {
            'fields': ('effective_from', 'effective_to', 'is_active')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    
    def price_display(self, obj):
        """Display price with currency"""
        return format_html(
            '<strong style="color: #059669; font-size: 14px;">GHS {}</strong>',
            obj.price
        )
    price_display.short_description = 'Price'
    
    def is_current_display(self, obj):
        """Display if price is currently valid"""
        if obj.is_current:
            return format_html('<i class="bi bi-check-circle-fill text-success"></i> Current')
        else:
            return format_html('<i class="bi bi-x-circle-fill text-danger"></i> Inactive/Expired')
    is_current_display.short_description = 'Status'


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ['service_code', 'pricing_category', 'action_badge', 'price_change_display',
                    'changed_by', 'created']
    list_filter = ['action', 'created', 'pricing_category']
    search_fields = ['service_code__code', 'service_code__description', 
                    'pricing_category__name']
    readonly_fields = ['created', 'modified']
    date_hierarchy = 'created'
    list_per_page = 50
    
    fieldsets = (
        ('Reference', {
            'fields': ('service_price', 'service_code', 'pricing_category')
        }),
        ('Action', {
            'fields': ('action',)
        }),
        ('Price Data', {
            'fields': ('old_price', 'new_price')
        }),
        ('Changed By', {
            'fields': ('changed_by', 'notes')
        }),
        ('System Information', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    
    def action_badge(self, obj):
        """Display action with color badge"""
        colors = {
            'created': 'success',
            'updated': 'warning',
            'deleted': 'danger',
            'expired': 'secondary',
        }
        color = colors.get(obj.action, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_action_display()
        )
    action_badge.short_description = 'Action'
    
    def price_change_display(self, obj):
        """Display price change"""
        if obj.old_price and obj.new_price:
            if obj.new_price > obj.old_price:
                return format_html(
                    '<span style="color: #dc2626;"><i class="bi bi-arrow-up"></i> GHS {} → {}</span>',
                    obj.old_price, obj.new_price
                )
            else:
                return format_html(
                    '<span style="color: #059669;"><i class="bi bi-arrow-down"></i> GHS {} → {}</span>',
                    obj.old_price, obj.new_price
                )
        elif obj.new_price:
            return format_html('<span style="color: #059669;">GHS {}</span>', obj.new_price)
        return '-'
    price_change_display.short_description = 'Price Change'


@admin.register(BulkPriceUpdate)
class BulkPriceUpdateAdmin(admin.ModelAdmin):
    list_display = ['name', 'pricing_category', 'update_type', 'status_badge',
                    'services_affected', 'effective_date', 'processed_at']
    list_filter = ['status', 'update_type', 'effective_date']
    search_fields = ['name', 'pricing_category__name']
    readonly_fields = ['created', 'modified', 'processed_at', 'services_affected']
    date_hierarchy = 'created'
    
    fieldsets = (
        ('Update Information', {
            'fields': ('name', 'pricing_category')
        }),
        ('Update Type & Values', {
            'fields': ('update_type', 'percentage_change', 'fixed_amount_change')
        }),
        ('Effective Date', {
            'fields': ('effective_date',)
        }),
        ('Status', {
            'fields': ('status', 'services_affected')
        }),
        ('Processing', {
            'fields': ('processed_at', 'processed_by', 'error_message'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
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
            'pending': 'secondary',
            'processing': 'primary',
            'completed': 'success',
            'failed': 'danger',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    actions = ['execute_bulk_update']
    
    def execute_bulk_update(self, request, queryset):
        """Execute selected bulk updates"""
        for bulk_update in queryset.filter(status='pending'):
            success, message = bulk_update.execute(user=request.user)
            if success:
                self.message_user(request, f'✅ {bulk_update.name}: {message}')
            else:
                self.message_user(request, f'❌ {bulk_update.name}: {message}', level='error')
    execute_bulk_update.short_description = 'Execute selected bulk updates'























