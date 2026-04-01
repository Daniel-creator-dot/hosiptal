"""
Admin configuration for advanced HMS models
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models_advanced import (
    ClinicalNote, CarePlan, ProblemList, ProviderSchedule, Queue, Triage,
    ImagingStudy, ImagingImage, ImagingCatalog, ProcedureCatalog, TheatreSchedule, SurgicalChecklist, AnaesthesiaRecord,
    MedicationAdministrationRecord, HandoverSheet, FallRiskAssessment,
    PressureUlcerRiskAssessment, CrashCartCheck, IncidentLog,
    MedicalEquipment, MaintenanceLog, ConsumablesInventory,
    DutyRoster, LeaveRequest, Attendance,
    InsurancePreAuthorization, ClaimsBatch, ChargeCapture,
    LabTestPanel, SampleCollection, SMSLog
)
from .models_telemedicine import (
    TelemedicineConsultation, TelemedicineMessage, TelemedicinePrescription,
    TelemedicineLabOrder, TelemedicineVitalSigns, TelemedicineAIAnalysis,
    TelemedicineDevice, TelemedicineNotification, TelemedicinePayment
)


# ==================== CLINICAL MODULES ====================

@admin.register(ClinicalNote)
class ClinicalNoteAdmin(admin.ModelAdmin):
    list_display = ['encounter', 'note_type', 'created_by', 'created']
    list_filter = ['note_type', 'created']
    search_fields = ['encounter__patient__first_name', 'encounter__patient__last_name', 'notes']
    readonly_fields = ['created', 'modified']
    date_hierarchy = 'created'


@admin.register(CarePlan)
class CarePlanAdmin(admin.ModelAdmin):
    list_display = ['patient', 'diagnosis', 'status', 'created_by', 'start_date']
    list_filter = ['status', 'created']
    search_fields = ['patient__first_name', 'patient__last_name', 'diagnosis']
    readonly_fields = ['created', 'modified']
    date_hierarchy = 'start_date'


@admin.register(ProblemList)
class ProblemListAdmin(admin.ModelAdmin):
    list_display = ['patient', 'problem', 'icd10_code', 'status', 'created_by']
    list_filter = ['status', 'created']
    search_fields = ['patient__first_name', 'patient__last_name', 'problem', 'icd10_code']
    readonly_fields = ['created', 'modified']


# ==================== SCHEDULING ====================

@admin.register(ProviderSchedule)
class ProviderScheduleAdmin(admin.ModelAdmin):
    list_display = ['provider', 'department', 'date', 'start_time', 'end_time', 'is_available']
    list_filter = ['date', 'is_available', 'session_type']
    search_fields = ['provider__user__first_name', 'provider__user__last_name']
    date_hierarchy = 'date'


@admin.register(Queue)
class QueueAdmin(admin.ModelAdmin):
    list_display = ['queue_number', 'encounter', 'department', 'priority', 'status', 'checked_in_at']
    list_filter = ['status', 'priority', 'department', 'checked_in_at']
    search_fields = ['encounter__patient__first_name', 'encounter__patient__last_name']
    readonly_fields = ['checked_in_at']
    date_hierarchy = 'checked_in_at'


@admin.register(Triage)
class TriageAdmin(admin.ModelAdmin):
    list_display = ['encounter', 'triage_level', 'chief_complaint', 'triaged_by', 'triage_time']
    list_filter = ['triage_level', 'triage_time']
    search_fields = ['encounter__patient__first_name', 'encounter__patient__last_name', 'chief_complaint']
    readonly_fields = ['triage_time']
    date_hierarchy = 'triage_time'


# ==================== IMAGING ====================

@admin.register(ImagingStudy)
class ImagingStudyAdmin(admin.ModelAdmin):
    list_display = ['patient', 'modality', 'body_part', 'status', 'scheduled_at', 'performed_at', 'image_count']
    list_filter = ['modality', 'status', 'priority', 'scheduled_at']
    search_fields = ['patient__first_name', 'patient__last_name', 'dicom_uid', 'pacs_id']
    readonly_fields = ['created', 'modified']
    date_hierarchy = 'scheduled_at'
    
    def image_count(self, obj):
        count = obj.images.filter(is_deleted=False).count()
        if count > 0:
            return format_html('<a href="{}" target="_blank">{}</a>', 
                             reverse('hospital:imaging_study_detail', args=[obj.pk]), 
                             f'{count} image(s)')
        return 'No images'
    image_count.short_description = 'Images'


@admin.register(ImagingImage)
class ImagingImageAdmin(admin.ModelAdmin):
    list_display = ['imaging_study', 'sequence_number', 'description', 'uploaded_by', 'uploaded_at', 'image_preview']
    list_filter = ['uploaded_at', 'imaging_study__modality']
    search_fields = ['imaging_study__patient__first_name', 'imaging_study__patient__last_name', 'description']
    readonly_fields = ['uploaded_at', 'created', 'modified']
    date_hierarchy = 'uploaded_at'
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width: 100px; max-height: 100px;" />', obj.image.url)
        return '-'
    image_preview.short_description = 'Preview'


@admin.register(ImagingCatalog)
class ImagingCatalogAdmin(admin.ModelAdmin):
    """Admin for Imaging Catalog - only actual imaging services"""
    list_display = ['code', 'name', 'modality', 'body_part', 'price', 'is_active']
    list_filter = ['modality', 'is_active', 'created']
    search_fields = ['code', 'name', 'body_part', 'study_type']
    list_editable = ['is_active', 'price']
    readonly_fields = ['created', 'modified']
    ordering = ['modality', 'name']
    
    fieldsets = (
        ('Imaging Study Information', {
            'fields': ('code', 'name', 'modality', 'body_part', 'study_type', 'description')
        }),
        ('Pricing', {
            'fields': ('price',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )


@admin.register(ProcedureCatalog)
class ProcedureCatalogAdmin(admin.ModelAdmin):
    """Admin for Procedure Catalog - medical procedures (separate from imaging)"""
    list_display = ['code', 'name', 'category', 'price', 'estimated_duration_minutes', 'requires_theatre', 'is_active']
    list_filter = ['category', 'requires_anesthesia', 'requires_theatre', 'is_active', 'created']
    search_fields = ['code', 'name', 'description']
    list_editable = ['is_active', 'price']
    readonly_fields = ['created', 'modified']
    ordering = ['category', 'name']
    
    fieldsets = (
        ('Procedure Information', {
            'fields': ('code', 'name', 'category', 'description')
        }),
        ('Pricing & Details', {
            'fields': ('price', 'estimated_duration_minutes', 'requires_anesthesia', 'requires_theatre')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )


# ==================== THEATRE ====================

@admin.register(TheatreSchedule)
class TheatreScheduleAdmin(admin.ModelAdmin):
    list_display = ['patient', 'procedure', 'theatre_name', 'scheduled_start', 'status', 'surgeon']
    list_filter = ['status', 'theatre_name', 'scheduled_start']
    search_fields = ['patient__first_name', 'patient__last_name', 'procedure']
    date_hierarchy = 'scheduled_start'


@admin.register(SurgicalChecklist)
class SurgicalChecklistAdmin(admin.ModelAdmin):
    list_display = ['theatre_schedule', 'completed_by', 'completed_at']
    list_filter = ['completed_at']
    search_fields = ['theatre_schedule__patient__first_name']


@admin.register(AnaesthesiaRecord)
class AnaesthesiaRecordAdmin(admin.ModelAdmin):
    list_display = ['theatre_schedule', 'anaesthetist', 'anaesthesia_type', 'created']
    list_filter = ['anaesthesia_type', 'created']
    search_fields = ['theatre_schedule__patient__first_name']


# ==================== NURSING ====================

@admin.register(MedicationAdministrationRecord)
class MedicationAdministrationRecordAdmin(admin.ModelAdmin):
    list_display = ['patient', 'prescription', 'scheduled_time', 'administered_time', 'status', 'administered_by']
    list_filter = ['status', 'scheduled_time']
    search_fields = ['patient__first_name', 'patient__last_name']
    readonly_fields = ['created', 'modified']
    date_hierarchy = 'scheduled_time'


@admin.register(HandoverSheet)
class HandoverSheetAdmin(admin.ModelAdmin):
    list_display = ['ward', 'date', 'shift_type', 'shift_start', 'created_by']
    list_filter = ['shift_type', 'date', 'ward']
    search_fields = ['ward__name']
    date_hierarchy = 'date'


@admin.register(FallRiskAssessment)
class FallRiskAssessmentAdmin(admin.ModelAdmin):
    list_display = ['patient', 'risk_score', 'risk_level', 'assessed_by', 'assessment_date']
    list_filter = ['risk_level', 'assessment_date']
    search_fields = ['patient__first_name', 'patient__last_name']
    readonly_fields = ['assessment_date']


@admin.register(PressureUlcerRiskAssessment)
class PressureUlcerRiskAssessmentAdmin(admin.ModelAdmin):
    list_display = ['patient', 'risk_score', 'risk_level', 'assessed_by', 'assessment_date']
    list_filter = ['risk_level', 'assessment_date']
    search_fields = ['patient__first_name', 'patient__last_name']


# ==================== ER ====================

@admin.register(CrashCartCheck)
class CrashCartCheckAdmin(admin.ModelAdmin):
    list_display = ['location', 'checked_by', 'check_date', 'status']
    list_filter = ['status', 'check_date', 'location']
    search_fields = ['location']
    readonly_fields = ['check_date']
    date_hierarchy = 'check_date'


@admin.register(IncidentLog)
class IncidentLogAdmin(admin.ModelAdmin):
    list_display = ['incident_type', 'severity', 'location', 'incident_date', 'reported_by', 'status']
    list_filter = ['incident_type', 'severity', 'status', 'incident_date']
    search_fields = ['location', 'description']
    readonly_fields = ['incident_date']
    date_hierarchy = 'incident_date'


# ==================== MATERIALS & ASSETS ====================

@admin.register(MedicalEquipment)
class MedicalEquipmentAdmin(admin.ModelAdmin):
    list_display = ['equipment_code', 'name', 'equipment_type', 'location', 'status', 'next_maintenance_due']
    list_filter = ['equipment_type', 'status', 'location']
    search_fields = ['equipment_code', 'name', 'serial_number']
    readonly_fields = ['created', 'modified']


@admin.register(MaintenanceLog)
class MaintenanceLogAdmin(admin.ModelAdmin):
    list_display = ['equipment', 'maintenance_type', 'service_date', 'service_provider', 'cost']
    list_filter = ['maintenance_type', 'service_date']
    search_fields = ['equipment__name']
    date_hierarchy = 'service_date'


@admin.register(ConsumablesInventory)
class ConsumablesInventoryAdmin(admin.ModelAdmin):
    list_display = ['item_name', 'category', 'location', 'quantity_on_hand', 'reorder_level', 'is_low_stock']
    list_filter = ['category', 'location']
    search_fields = ['item_code', 'item_name']
    readonly_fields = ['created', 'modified']
    
    def is_low_stock(self, obj):
        return obj.is_low_stock
    is_low_stock.boolean = True
    is_low_stock.short_description = 'Low Stock'


# ==================== HR ====================

@admin.register(DutyRoster)
class DutyRosterAdmin(admin.ModelAdmin):
    list_display = ['staff', 'department', 'shift_date', 'shift_type', 'start_time', 'end_time']
    list_filter = ['shift_type', 'shift_date', 'department']
    search_fields = ['staff__user__first_name', 'staff__user__last_name']
    date_hierarchy = 'shift_date'


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['staff', 'leave_type', 'start_date', 'end_date', 'days_requested', 'status', 'approved_by']
    list_filter = ['leave_type', 'status', 'start_date']
    search_fields = ['staff__user__first_name', 'staff__user__last_name']
    date_hierarchy = 'start_date'


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['staff', 'date', 'check_in', 'check_out', 'status']
    list_filter = ['status', 'date']
    search_fields = ['staff__user__first_name', 'staff__user__last_name']
    readonly_fields = ['created', 'modified']
    date_hierarchy = 'date'


# ==================== ENHANCED BILLING ====================

@admin.register(InsurancePreAuthorization)
class InsurancePreAuthorizationAdmin(admin.ModelAdmin):
    list_display = ['patient', 'payer', 'auth_number', 'requested_amount', 'approved_amount', 'status', 'requested_date']
    list_filter = ['status', 'requested_date']
    search_fields = ['patient__first_name', 'patient__last_name', 'auth_number']
    readonly_fields = ['requested_date']
    date_hierarchy = 'requested_date'


@admin.register(ClaimsBatch)
class ClaimsBatchAdmin(admin.ModelAdmin):
    list_display = ['batch_number', 'payer', 'submission_date', 'total_claims', 'total_amount', 'status']
    list_filter = ['status', 'submission_date']
    search_fields = ['batch_number']
    readonly_fields = ['created', 'modified']
    date_hierarchy = 'submission_date'


@admin.register(ChargeCapture)
class ChargeCaptureAdmin(admin.ModelAdmin):
    list_display = ['encounter', 'service_code', 'quantity', 'unit_price', 'total_amount', 'charge_date', 'charged_by']
    list_filter = ['charge_date']
    search_fields = ['encounter__patient__first_name', 'service_code__code']
    readonly_fields = ['created', 'modified']
    date_hierarchy = 'charge_date'


# ==================== LAB ENHANCEMENTS ====================

@admin.register(LabTestPanel)
class LabTestPanelAdmin(admin.ModelAdmin):
    list_display = ['panel_code', 'panel_name', 'test_count']
    search_fields = ['panel_code', 'panel_name']
    filter_horizontal = ['tests']
    
    def test_count(self, obj):
        return obj.tests.count()
    test_count.short_description = 'Number of Tests'


@admin.register(SampleCollection)
class SampleCollectionAdmin(admin.ModelAdmin):
    list_display = ['sample_id', 'patient', 'sample_type', 'collection_time', 'status', 'collected_by']
    list_filter = ['sample_type', 'status', 'collection_time']
    search_fields = ['sample_id', 'patient__first_name', 'patient__last_name']
    readonly_fields = ['created', 'modified']
    date_hierarchy = 'collection_time'


# ==================== SMS ====================

@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ['recipient_phone', 'recipient_name', 'message_type', 'status', 'sent_at', 'created']
    list_filter = ['status', 'message_type', 'sent_at', 'created']
    search_fields = ['recipient_phone', 'recipient_name', 'message']
    readonly_fields = ['created', 'modified', 'sent_at', 'provider_response']
    date_hierarchy = 'created'
    
    def has_add_permission(self, request):
        return False  # SMS logs are created automatically


# ==================== TELEMEDICINE ====================
# Telemedicine admin has been moved to admin_telemedicine.py for better organization
# All telemedicine models (base and enhanced) are now registered there

# @admin.register(TelemedicineConsultation)
# class TelemedicineConsultationAdmin(admin.ModelAdmin):
#     list_display = ['consultation_id', 'patient', 'doctor', 'consultation_type', 'status', 'scheduled_at', 'duration_display']
#     list_filter = ['status', 'consultation_type', 'priority', 'scheduled_at', 'created']
#     search_fields = ['consultation_id', 'patient__first_name', 'patient__last_name', 'doctor__user__first_name', 'doctor__user__last_name']
#     readonly_fields = ['consultation_id', 'created', 'modified', 'meeting_room_id', 'meeting_url']
#     date_hierarchy = 'scheduled_at'
#     ordering = ['-scheduled_at']
#     
#     def duration_display(self, obj):
#         return obj.get_duration_display()
#     duration_display.short_description = 'Duration'
#     
#     fieldsets = (
#         ('Basic Information', {
#             'fields': ('consultation_id', 'patient', 'doctor', 'consultation_type', 'status', 'priority')
#         }),
#         ('Scheduling', {
#             'fields': ('scheduled_at', 'started_at', 'ended_at', 'duration_minutes')
#         }),
#         ('Medical Information', {
#             'fields': ('chief_complaint', 'symptoms', 'diagnosis', 'treatment_plan', 'follow_up_required', 'follow_up_date')
#         }),
#         ('Technical Details', {
#             'fields': ('meeting_room_id', 'meeting_url', 'recording_url', 'quality_rating')
#         }),
#         ('Financial', {
#             'fields': ('consultation_fee', 'payment_status', 'payment_method')
#         }),
#         ('AI Features', {
#             'fields': ('ai_triage_score', 'ai_triage_recommendation', 'ai_symptom_analysis', 'ai_diagnosis_suggestions', 'ai_prescription_suggestions'),
#             'classes': ('collapse',)
#         })
#     )


# @admin.register(TelemedicineMessage)
# class TelemedicineMessageAdmin(admin.ModelAdmin):
#     list_display = ['consultation', 'sender', 'message_type', 'content_preview', 'is_read', 'created']
#     list_filter = ['message_type', 'is_read', 'created']
#     search_fields = ['consultation__consultation_id', 'sender__username', 'content']
#     readonly_fields = ['created', 'modified']
#     date_hierarchy = 'created'
#     
#     def content_preview(self, obj):
#         return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
#     content_preview.short_description = 'Content Preview'


# @admin.register(TelemedicinePrescription)
# class TelemedicinePrescriptionAdmin(admin.ModelAdmin):
#     list_display = ['consultation', 'drug', 'dosage', 'frequency', 'duration', 'is_urgent', 'created']
#     list_filter = ['is_urgent', 'created']
#     search_fields = ['consultation__consultation_id', 'drug__name', 'consultation__patient__first_name']
#     readonly_fields = ['created', 'modified']
#     date_hierarchy = 'created'


# @admin.register(TelemedicineLabOrder)
# class TelemedicineLabOrderAdmin(admin.ModelAdmin):
#     list_display = ['consultation', 'test', 'is_urgent', 'priority', 'created']
#     list_filter = ['is_urgent', 'priority', 'created']
#     search_fields = ['consultation__consultation_id', 'test__name', 'consultation__patient__first_name']
#     readonly_fields = ['created', 'modified']
#     date_hierarchy = 'created'


# @admin.register(TelemedicineVitalSigns)
# class TelemedicineVitalSignsAdmin(admin.ModelAdmin):
#     list_display = ['consultation', 'recorded_by', 'blood_pressure_display', 'heart_rate', 'temperature', 'created']
#     list_filter = ['created']
#     search_fields = ['consultation__consultation_id', 'consultation__patient__first_name']
#     readonly_fields = ['created', 'modified', 'bmi']
#     date_hierarchy = 'created'
#     
#     def blood_pressure_display(self, obj):
#         if obj.blood_pressure_systolic and obj.blood_pressure_diastolic:
#             return f"{obj.blood_pressure_systolic}/{obj.blood_pressure_diastolic}"
#         return "-"
#     blood_pressure_display.short_description = 'Blood Pressure'


# @admin.register(TelemedicineAIAnalysis)
# class TelemedicineAIAnalysisAdmin(admin.ModelAdmin):
#     list_display = ['consultation', 'analysis_type', 'confidence_score', 'is_approved', 'created']
#     list_filter = ['analysis_type', 'is_approved', 'created']
#     search_fields = ['consultation__consultation_id', 'analysis_type']
#     readonly_fields = ['created', 'modified', 'approved_at']
#     date_hierarchy = 'created'


# @admin.register(TelemedicineDevice)
# class TelemedicineDeviceAdmin(admin.ModelAdmin):
#     list_display = ['patient', 'device_name', 'device_type', 'is_active', 'last_seen']
#     list_filter = ['device_type', 'is_active', 'last_seen']
#     search_fields = ['patient__first_name', 'patient__last_name', 'device_name']
#     readonly_fields = ['created', 'modified', 'last_seen']
#     date_hierarchy = 'last_seen'


# @admin.register(TelemedicineNotification)
# class TelemedicineNotificationAdmin(admin.ModelAdmin):
#     list_display = ['user', 'notification_type', 'title', 'is_read', 'created']
#     list_filter = ['notification_type', 'is_read', 'created']
#     search_fields = ['user__username', 'title', 'message']
#     readonly_fields = ['created', 'modified', 'read_at']
#     date_hierarchy = 'created'


# @admin.register(TelemedicinePayment)
# class TelemedicinePaymentAdmin(admin.ModelAdmin):
#     list_display = ['consultation', 'amount', 'currency', 'payment_method', 'payment_status', 'paid_at']
#     list_filter = ['payment_status', 'payment_method', 'paid_at', 'created']
#     search_fields = ['consultation__consultation_id', 'transaction_id']
#     readonly_fields = ['created', 'modified', 'paid_at']
#     date_hierarchy = 'created'

