"""
Admin configuration for Walk-in Pharmacy Sales
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models_pharmacy_walkin import WalkInPharmacySale, WalkInPharmacySaleItem


class WalkInPharmacySaleItemInline(admin.TabularInline):
    model = WalkInPharmacySaleItem
    extra = 0
    readonly_fields = ['line_total']
    fields = ['drug', 'quantity', 'unit_price', 'line_total', 'dosage_instructions']
    

@admin.register(WalkInPharmacySale)
class WalkInPharmacySaleAdmin(admin.ModelAdmin):
    list_display = [
        'sale_number', 'customer_name_display', 'sale_date', 'total_amount_display',
        'payment_status_badge', 'dispensed_badge', 'served_by'
    ]
    list_filter = ['payment_status', 'is_dispensed', 'customer_type', 'sale_date', 'payer']
    search_fields = ['sale_number', 'customer_name', 'customer_phone', 'patient__first_name', 'patient__last_name']
    readonly_fields = [
        'sale_number', 'subtotal', 'total_amount', 'amount_due', 
        'created', 'modified'
    ]
    inlines = [WalkInPharmacySaleItemInline]
    ordering = ['-sale_date']
    date_hierarchy = 'sale_date'
    
    fieldsets = (
        ('Customer Information', {
            'fields': (
                'customer_type', 'customer_name', 'customer_phone', 
                'customer_address', 'patient'
            )
        }),
        ('Sale Details', {
            'fields': ('sale_number', 'sale_date', 'payer', 'served_by')
        }),
        ('Financial', {
            'fields': (
                'subtotal', 'tax_amount', 'discount_amount', 
                'total_amount', 'amount_paid', 'amount_due', 'payment_status'
            )
        }),
        ('Dispensing', {
            'fields': (
                'is_dispensed', 'dispensed_at', 'dispensed_by', 
                'counselling_notes'
            )
        }),
        ('Additional', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    
    def customer_name_display(self, obj):
        if obj.patient:
            url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
            return format_html(
                '<a href="{}">{}</a> <span class="badge badge-info">Registered</span>',
                url, obj.customer_name
            )
        return format_html('{} <span class="badge badge-secondary">Walk-in</span>', obj.customer_name)
    customer_name_display.short_description = 'Customer'
    
    def total_amount_display(self, obj):
        if obj.amount_due > 0:
            return format_html(
                '<strong>GHS {}</strong><br><small class="text-danger">Due: GHS {}</small>',
                obj.total_amount, obj.amount_due
            )
        return format_html('<strong class="text-success">GHS {}</strong>', obj.total_amount)
    total_amount_display.short_description = 'Amount'
    
    def payment_status_badge(self, obj):
        colors = {
            'pending': 'danger',
            'paid': 'success',
            'partial': 'warning',
            'cancelled': 'secondary'
        }
        color = colors.get(obj.payment_status, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_payment_status_display()
        )
    payment_status_badge.short_description = 'Payment'
    
    def dispensed_badge(self, obj):
        if obj.is_dispensed:
            return format_html('<span class="badge badge-success">✓ Yes</span>')
        return format_html('<span class="badge badge-warning">⏳ No</span>')
    dispensed_badge.short_description = 'Dispensed'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'patient', 'served_by', 'dispensed_by'
        )


@admin.register(WalkInPharmacySaleItem)
class WalkInPharmacySaleItemAdmin(admin.ModelAdmin):
    list_display = [
        'sale_link', 'drug_link', 'quantity', 'unit_price', 
        'line_total', 'created'
    ]
    list_filter = ['created', 'drug__form']
    search_fields = ['sale__sale_number', 'drug__name', 'sale__customer_name']
    readonly_fields = ['line_total', 'created', 'modified']
    ordering = ['-created']
    
    fieldsets = (
        ('Sale Information', {
            'fields': ('sale', 'drug')
        }),
        ('Quantity & Pricing', {
            'fields': ('quantity', 'unit_price', 'line_total')
        }),
        ('Batch Information', {
            'fields': ('batch_number', 'expiry_date'),
            'classes': ('collapse',)
        }),
        ('Instructions', {
            'fields': ('dosage_instructions',)
        }),
        ('Timestamps', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    
    def sale_link(self, obj):
        url = reverse('admin:hospital_walkinpharmacysale_change', args=[obj.sale.pk])
        return format_html('<a href="{}">{}</a>', url, obj.sale.sale_number)
    sale_link.short_description = 'Sale'
    
    def drug_link(self, obj):
        url = reverse('admin:hospital_drug_change', args=[obj.drug.pk])
        return format_html('<a href="{}">{}</a>', url, obj.drug.name)
    drug_link.short_description = 'Drug'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('sale', 'drug')






















