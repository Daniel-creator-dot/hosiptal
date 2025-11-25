"""
Blood Bank Admin Registration
"""
from django.contrib import admin
from .models_blood_bank import (
    BloodDonor, BloodDonation, BloodInventory,
    TransfusionRequest, BloodCrossmatch, BloodTransfusion,
    BloodCompatibilityMatrix
)


@admin.register(BloodDonor)
class BloodDonorAdmin(admin.ModelAdmin):
    list_display = ['donor_id', 'full_name', 'blood_group', 'last_donation_date', 'total_donations', 'is_active', 'is_eligible']
    list_filter = ['blood_group', 'is_active', 'is_eligible', 'is_regular_donor']
    search_fields = ['donor_id', 'first_name', 'last_name', 'phone_number']
    readonly_fields = ['created', 'modified']
    
    fieldsets = (
        ('Donor Information', {
            'fields': ('donor_id', 'patient', 'first_name', 'last_name', 'date_of_birth', 'gender')
        }),
        ('Contact', {
            'fields': ('phone_number', 'email', 'address')
        }),
        ('Blood Details', {
            'fields': ('blood_group', 'last_donation_date', 'total_donations')
        }),
        ('Eligibility', {
            'fields': ('is_active', 'is_eligible', 'is_regular_donor', 'ineligibility_reason', 'weight_kg', 'hemoglobin_level')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('created', 'modified', 'is_deleted'),
            'classes': ('collapse',)
        })
    )


@admin.register(BloodDonation)
class BloodDonationAdmin(admin.ModelAdmin):
    list_display = ['donation_number', 'donor', 'blood_group', 'donation_date', 'testing_status', 'is_approved']
    list_filter = ['blood_group', 'testing_status', 'is_approved', 'donation_date']
    search_fields = ['donation_number', 'donor__donor_id', 'donor__first_name', 'donor__last_name']
    readonly_fields = ['created', 'modified', 'approved_at']
    date_hierarchy = 'donation_date'
    
    fieldsets = (
        ('Donation Info', {
            'fields': ('donation_number', 'donor', 'donation_date', 'blood_group', 'volume_collected_ml')
        }),
        ('Pre-Donation Screening', {
            'fields': ('pre_donation_hemoglobin', 'pre_donation_weight', 'pre_donation_bp_systolic', 'pre_donation_bp_diastolic', 'pre_donation_temperature')
        }),
        ('Testing', {
            'fields': ('testing_status', 'hiv_tested', 'hiv_result', 'hbv_tested', 'hbv_result', 'hcv_tested', 'hcv_result', 'syphilis_tested', 'syphilis_result', 'malaria_tested', 'malaria_result')
        }),
        ('Approval', {
            'fields': ('is_approved', 'approved_by', 'approved_at', 'rejection_reason')
        }),
        ('Staff', {
            'fields': ('collected_by',)
        }),
        ('Notes', {
            'fields': ('notes',)
        })
    )


@admin.register(BloodInventory)
class BloodInventoryAdmin(admin.ModelAdmin):
    list_display = ['unit_number', 'blood_group', 'component_type', 'volume_ml', 'collection_date', 'expiry_date', 'status', 'storage_location']
    list_filter = ['blood_group', 'component_type', 'status', 'expiry_date']
    search_fields = ['unit_number', 'donation__donation_number']
    readonly_fields = ['created', 'modified']
    date_hierarchy = 'expiry_date'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('donation', 'donation__donor')


@admin.register(TransfusionRequest)
class TransfusionRequestAdmin(admin.ModelAdmin):
    list_display = ['request_number', 'patient', 'patient_blood_group', 'component_type', 'units_requested', 'urgency', 'status', 'requested_at']
    list_filter = ['status', 'urgency', 'patient_blood_group', 'component_type', 'indication']
    search_fields = ['request_number', 'patient__first_name', 'patient__last_name', 'patient__mrn']
    readonly_fields = ['created', 'modified', 'requested_at', 'processed_at', 'approved_at']
    date_hierarchy = 'requested_at'
    
    fieldsets = (
        ('Request Info', {
            'fields': ('request_number', 'patient', 'encounter', 'requested_by', 'requested_at')
        }),
        ('Blood Requirements', {
            'fields': ('patient_blood_group', 'component_type', 'units_requested', 'urgency')
        }),
        ('Clinical Info', {
            'fields': ('indication', 'clinical_notes', 'pre_transfusion_hb', 'pre_transfusion_bp_systolic', 'pre_transfusion_bp_diastolic')
        }),
        ('Processing', {
            'fields': ('status', 'processed_by', 'processed_at')
        }),
        ('Crossmatch', {
            'fields': ('crossmatch_completed', 'crossmatch_compatible', 'crossmatch_notes')
        }),
        ('Approval', {
            'fields': ('is_approved', 'approved_by', 'approved_at', 'rejection_reason')
        })
    )


@admin.register(BloodCrossmatch)
class BloodCrossmatchAdmin(admin.ModelAdmin):
    list_display = ['transfusion_request', 'blood_unit', 'major_crossmatch_result', 'is_compatible', 'tested_at']
    list_filter = ['major_crossmatch_result', 'is_compatible', 'tested_at']
    search_fields = ['transfusion_request__request_number', 'blood_unit__unit_number']
    readonly_fields = ['created', 'modified', 'tested_at']


@admin.register(BloodTransfusion)
class BloodTransfusionAdmin(admin.ModelAdmin):
    list_display = ['transfusion_request', 'blood_unit', 'started_at', 'completed_at', 'volume_transfused_ml', 'status', 'adverse_reaction_occurred']
    list_filter = ['status', 'adverse_reaction_occurred', 'reaction_severity', 'started_at']
    search_fields = ['transfusion_request__request_number', 'blood_unit__unit_number', 'transfusion_request__patient__first_name', 'transfusion_request__patient__last_name']
    readonly_fields = ['created', 'modified', 'started_at', 'completed_at']
    date_hierarchy = 'started_at'


@admin.register(BloodCompatibilityMatrix)
class BloodCompatibilityMatrixAdmin(admin.ModelAdmin):
    list_display = ['recipient_blood_group', 'component_type', 'compatible_donor_groups']
    list_filter = ['recipient_blood_group', 'component_type']





















