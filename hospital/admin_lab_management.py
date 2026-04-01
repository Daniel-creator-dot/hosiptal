"""
Admin interfaces for Lab Management models
"""
from django.contrib import admin
from .models_lab_management import (
    LabEquipment, EquipmentMaintenanceLog, LabReagent, ReagentTransaction,
    QualityControlTest, QCAlert
)


@admin.register(LabEquipment)
class LabEquipmentAdmin(admin.ModelAdmin):
    list_display = ['equipment_code', 'name', 'equipment_type', 'status', 'location', 'needs_maintenance', 'needs_calibration', 'total_tests_run']
    list_filter = ['equipment_type', 'status', 'department']
    search_fields = ['equipment_code', 'name', 'manufacturer', 'model', 'serial_number']
    readonly_fields = ['total_tests_run', 'last_used_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('equipment_code', 'name', 'equipment_type', 'manufacturer', 'model', 'serial_number')
        }),
        ('Location & Assignment', {
            'fields': ('location', 'department', 'assigned_to', 'status')
        }),
        ('Purchase & Warranty', {
            'fields': ('purchase_date', 'purchase_cost', 'warranty_expiry')
        }),
        ('Maintenance', {
            'fields': ('last_maintenance', 'next_maintenance_due', 'last_calibration', 'next_calibration_due', 'calibration_interval_days')
        }),
        ('Usage', {
            'fields': ('total_tests_run', 'last_used_at')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )


@admin.register(EquipmentMaintenanceLog)
class EquipmentMaintenanceLogAdmin(admin.ModelAdmin):
    list_display = ['equipment', 'maintenance_type', 'service_date', 'technician', 'cost', 'next_service_due']
    list_filter = ['maintenance_type', 'service_date', 'is_calibration']
    search_fields = ['equipment__name', 'equipment__equipment_code', 'technician__user__username']
    date_hierarchy = 'service_date'
    readonly_fields = ['created', 'modified']


@admin.register(LabReagent)
class LabReagentAdmin(admin.ModelAdmin):
    list_display = ['item_code', 'name', 'category', 'quantity_on_hand', 'unit', 'is_low_stock', 'is_expired', 'is_expiring_soon', 'expiry_date']
    list_filter = ['category', 'supplier', 'expiry_date']
    search_fields = ['item_code', 'name', 'manufacturer', 'catalog_number', 'batch_number']
    readonly_fields = ['total_used', 'last_used_at', 'stock_value']
    fieldsets = (
        ('Basic Information', {
            'fields': ('item_code', 'name', 'category', 'manufacturer', 'catalog_number')
        }),
        ('Inventory', {
            'fields': ('quantity_on_hand', 'unit', 'reorder_level', 'reorder_quantity', 'location')
        }),
        ('Pricing & Supplier', {
            'fields': ('unit_cost', 'supplier', 'stock_value')
        }),
        ('Batch & Expiry', {
            'fields': ('batch_number', 'expiry_date', 'storage_conditions')
        }),
        ('Usage', {
            'fields': ('total_used', 'last_used_at')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )


@admin.register(ReagentTransaction)
class ReagentTransactionAdmin(admin.ModelAdmin):
    list_display = ['reagent', 'transaction_type', 'quantity', 'batch_number', 'performed_by', 'created']
    list_filter = ['transaction_type', 'created']
    search_fields = ['reagent__name', 'reagent__item_code', 'batch_number', 'reference']
    date_hierarchy = 'created'
    readonly_fields = ['created', 'modified']


@admin.register(QualityControlTest)
class QualityControlTestAdmin(admin.ModelAdmin):
    list_display = ['equipment', 'test_name', 'qc_type', 'test_date', 'status', 'within_range', 'has_violations', 'performed_by']
    list_filter = ['qc_type', 'status', 'test_date', 'rule_1_2s', 'rule_1_3s', 'rule_2_2s']
    search_fields = ['equipment__name', 'test_name', 'batch_number']
    date_hierarchy = 'test_date'
    readonly_fields = ['has_violations', 'is_critical_failure', 'created', 'modified']
    fieldsets = (
        ('Test Information', {
            'fields': ('equipment', 'qc_type', 'test_date', 'test_time', 'test_name')
        }),
        ('Control Material', {
            'fields': ('control_material', 'batch_number')
        }),
        ('Results', {
            'fields': ('expected_value', 'observed_value', 'units', 'within_range')
        }),
        ('QC Rules', {
            'fields': ('rule_1_2s', 'rule_1_3s', 'rule_2_2s', 'rule_r_4s', 'rule_4_1s', 'rule_10x', 'has_violations', 'is_critical_failure')
        }),
        ('Status & Review', {
            'fields': ('status', 'performed_by', 'reviewed_by', 'reviewed_at')
        }),
        ('Actions', {
            'fields': ('corrective_action', 'equipment_status_after_qc')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )


@admin.register(QCAlert)
class QCAlertAdmin(admin.ModelAdmin):
    list_display = ['alert_type', 'priority', 'title', 'is_resolved', 'created', 'resolved_at', 'resolved_by']
    list_filter = ['alert_type', 'priority', 'is_resolved', 'created']
    search_fields = ['title', 'message']
    date_hierarchy = 'created'
    readonly_fields = ['created', 'modified']
    fieldsets = (
        ('Alert Information', {
            'fields': ('alert_type', 'priority', 'title', 'message')
        }),
        ('Related Objects', {
            'fields': ('equipment', 'reagent', 'qc_test')
        }),
        ('Resolution', {
            'fields': ('is_resolved', 'resolved_at', 'resolved_by', 'resolution_notes')
        }),
        ('Notifications', {
            'fields': ('notified_staff',)
        }),
    )










