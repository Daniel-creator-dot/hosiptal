"""
Admin configuration for Locum Doctor models
"""
from django.contrib import admin
from .models_locum_doctors import LocumDoctorService, LocumDoctorPaymentBatch


@admin.register(LocumDoctorService)
class LocumDoctorServiceAdmin(admin.ModelAdmin):
    list_display = ['service_date', 'doctor', 'patient', 'service_type', 'service_charge', 
                   'doctor_payment', 'tax_amount', 'net_payment', 'payment_method', 'payment_status']
    list_filter = ['payment_status', 'payment_method', 'service_date', 'doctor']
    search_fields = ['doctor__user__first_name', 'doctor__user__last_name', 
                     'patient__first_name', 'patient__last_name', 'service_type']
    readonly_fields = ['doctor_payment', 'tax_amount', 'net_payment']
    date_hierarchy = 'service_date'
    
    fieldsets = (
        ('Service Information', {
            'fields': ('doctor', 'patient', 'encounter', 'service_date', 'service_type', 'service_description')
        }),
        ('Financial Information', {
            'fields': ('service_charge', 'doctor_payment', 'payment_method', 'tax_amount', 'net_payment')
        }),
        ('Payment Information', {
            'fields': ('payment_status', 'payment_date', 'payment_reference', 'paid_by', 'notes')
        }),
    )


@admin.register(LocumDoctorPaymentBatch)
class LocumDoctorPaymentBatchAdmin(admin.ModelAdmin):
    list_display = ['batch_number', 'doctor', 'period_start', 'period_end', 'total_services',
                   'total_net_payment', 'payment_method', 'payment_status', 'payment_date']
    list_filter = ['payment_status', 'payment_method', 'period_start', 'period_end']
    search_fields = ['batch_number', 'doctor__user__first_name', 'doctor__user__last_name']
    readonly_fields = ['batch_number', 'total_services', 'total_service_charge', 
                      'total_doctor_payment', 'total_tax', 'total_net_payment']
    filter_horizontal = ['services']
    date_hierarchy = 'period_end'
    
    fieldsets = (
        ('Batch Information', {
            'fields': ('batch_number', 'doctor', 'period_start', 'period_end')
        }),
        ('Financial Summary', {
            'fields': ('total_services', 'total_service_charge', 'total_doctor_payment', 
                      'total_tax', 'total_net_payment')
        }),
        ('Payment Information', {
            'fields': ('payment_method', 'payment_status', 'payment_date', 
                      'payment_reference', 'processed_by', 'notes')
        }),
        ('Services', {
            'fields': ('services',)
        }),
    )


