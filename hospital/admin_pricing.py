"""
Admin interfaces for Pricing Configuration
"""
from django.contrib import admin
from django.utils.html import format_html
from .models_pricing import DefaultPrice, PayerPrice


@admin.register(DefaultPrice)
class DefaultPriceAdmin(admin.ModelAdmin):
    list_display = ['service_code_display', 'description', 'price_display', 'currency', 'is_active', 'last_updated']
    list_filter = ['is_active', 'currency']
    search_fields = ['description', 'service_code']
    fieldsets = (
        ('Service Information', {
            'fields': ('service_code', 'description')
        }),
        ('Pricing', {
            'fields': ('default_price', 'currency')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def service_code_display(self, obj):
        return obj.get_service_code_display()
    service_code_display.short_description = 'Service'
    
    def price_display(self, obj):
        return format_html('<strong style="color: #10b981; font-size: 14px;">{:.2f} {}</strong>', obj.default_price, obj.currency)
    price_display.short_description = 'Price'
    
    actions = ['activate_prices', 'deactivate_prices']
    
    def activate_prices(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} price(s) activated")
    activate_prices.short_description = "Activate selected prices"
    
    def deactivate_prices(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} price(s) deactivated")
    deactivate_prices.short_description = "Deactivate selected prices"


@admin.register(PayerPrice)
class PayerPriceAdmin(admin.ModelAdmin):
    list_display = ['payer', 'service_code_display', 'custom_price_display', 'currency', 'is_active', 'effective_date', 'expiry_date']
    list_filter = ['payer', 'service_code', 'is_active', 'currency']
    search_fields = ['payer__name', 'service_code']
    fieldsets = (
        ('Payer & Service', {
            'fields': ('payer', 'service_code')
        }),
        ('Pricing', {
            'fields': ('custom_price', 'currency')
        }),
        ('Validity Period', {
            'fields': ('effective_date', 'expiry_date')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def service_code_display(self, obj):
        return obj.get_service_code_display()
    service_code_display.short_description = 'Service'
    
    def custom_price_display(self, obj):
        return format_html('<strong style="color: #f59e0b; font-size: 14px;">{:.2f} {}</strong>', obj.custom_price, obj.currency)
    custom_price_display.short_description = 'Custom Price'

