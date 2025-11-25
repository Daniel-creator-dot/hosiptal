"""
Admin configuration for Telemedicine Models
Comprehensive admin interface for all telemedicine features
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models_telemedicine import (
    TelemedicineConsultation,
    TelemedicineMessage,
    TelemedicinePrescription,
    TelemedicineLabOrder,
    TelemedicineVitalSigns,
    TelemedicineAIAnalysis,
    TelemedicineDevice,
    TelemedicineNotification,
    TelemedicinePayment,
)
from .models_telemedicine_enhanced import (
    VirtualWaitingRoom,
    ConsultationAnalytics,
    AISymptomChecker,
    ConsultationRecording,
    PatientHealthData,
    TelemedicineTemplate,
    ConsultationFollowUp,
    TelemedicineQualityMetrics,
    PatientSelfCheckIn,
    ConsultationNote,
    MultiLanguageSupport,
    EmergencyEscalation,
)


# ==================== INLINE ADMINS ====================

class TelemedicineMessageInline(admin.TabularInline):
    model = TelemedicineMessage
    extra = 0
    readonly_fields = ('created', 'sender', 'message_type', 'is_read')
    fields = ('sender', 'message_type', 'content', 'is_read', 'created')
    can_delete = False


class TelemedicinePrescriptionInline(admin.TabularInline):
    model = TelemedicinePrescription
    extra = 0
    readonly_fields = ('created',)
    fields = ('drug', 'dosage', 'frequency', 'duration', 'quantity', 'is_urgent')


class TelemedicineLabOrderInline(admin.TabularInline):
    model = TelemedicineLabOrder
    extra = 0
    readonly_fields = ('created',)
    fields = ('test', 'priority', 'is_urgent', 'instructions')


class ConsultationAnalyticsInline(admin.StackedInline):
    model = ConsultationAnalytics
    extra = 0
    readonly_fields = ('created', 'modified')
    can_delete = False


# ==================== MAIN ADMINS ====================

@admin.register(TelemedicineConsultation)
class TelemedicineConsultationAdmin(admin.ModelAdmin):
    list_display = (
        'consultation_id',
        'patient_link',
        'doctor_link',
        'consultation_type',
        'status_badge',
        'priority_badge',
        'scheduled_at',
        'duration_display',
        'consultation_fee',
    )
    list_filter = (
        'status',
        'priority',
        'consultation_type',
        'scheduled_at',
        'payment_status',
    )
    search_fields = (
        'consultation_id',
        'patient__first_name',
        'patient__last_name',
        'patient__mrn',
        'doctor__user__first_name',
        'doctor__user__last_name',
        'chief_complaint',
    )
    readonly_fields = (
        'consultation_id',
        'created',
        'modified',
        'duration_minutes',
    )
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'consultation_id',
                'patient',
                'doctor',
                'consultation_type',
                'status',
                'priority',
            )
        }),
        ('Scheduling', {
            'fields': (
                'scheduled_at',
                'started_at',
                'ended_at',
                'duration_minutes',
            )
        }),
        ('Clinical Information', {
            'fields': (
                'chief_complaint',
                'symptoms',
                'diagnosis',
                'treatment_plan',
                'follow_up_required',
                'follow_up_date',
            )
        }),
        ('AI Features', {
            'fields': (
                'ai_triage_score',
                'ai_triage_recommendation',
                'ai_symptom_analysis',
                'ai_diagnosis_suggestions',
                'ai_prescription_suggestions',
            ),
            'classes': ('collapse',)
        }),
        ('Technical Details', {
            'fields': (
                'meeting_room_id',
                'meeting_url',
                'recording_url',
                'quality_rating',
            ),
            'classes': ('collapse',)
        }),
        ('Financial', {
            'fields': (
                'consultation_fee',
                'payment_status',
                'payment_method',
            )
        }),
        ('Metadata', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    inlines = [
        ConsultationAnalyticsInline,
        TelemedicineMessageInline,
        TelemedicinePrescriptionInline,
        TelemedicineLabOrderInline,
    ]
    date_hierarchy = 'scheduled_at'
    
    def patient_link(self, obj):
        if obj.patient:
            url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
            return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
        return '-'
    patient_link.short_description = 'Patient'
    
    def doctor_link(self, obj):
        if obj.doctor:
            url = reverse('admin:hospital_staff_change', args=[obj.doctor.pk])
            return format_html('<a href="{}">{}</a>', url, obj.doctor.user.get_full_name())
        return '-'
    doctor_link.short_description = 'Doctor'
    
    def status_badge(self, obj):
        colors = {
            'scheduled': '#007bff',
            'in_progress': '#28a745',
            'completed': '#6c757d',
            'cancelled': '#dc3545',
            'no_show': '#ffc107',
            'rescheduled': '#17a2b8',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def priority_badge(self, obj):
        colors = {
            'low': '#28a745',
            'medium': '#ffc107',
            'high': '#fd7e14',
            'urgent': '#dc3545',
        }
        color = colors.get(obj.priority, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'
    
    def duration_display(self, obj):
        return obj.get_duration_display()
    duration_display.short_description = 'Duration'


@admin.register(VirtualWaitingRoom)
class VirtualWaitingRoomAdmin(admin.ModelAdmin):
    list_display = (
        'queue_number',
        'patient_link',
        'status_badge',
        'check_in_time',
        'estimated_wait_minutes',
        'device_status',
    )
    list_filter = ('status', 'device_ready', 'check_in_time')
    search_fields = ('patient__first_name', 'patient__last_name', 'patient__mrn')
    readonly_fields = ('check_in_time', 'created', 'modified')
    fieldsets = (
        ('Queue Information', {
            'fields': ('patient', 'consultation', 'queue_number', 'status')
        }),
        ('Timing', {
            'fields': ('check_in_time', 'called_at', 'estimated_wait_minutes')
        }),
        ('Device Readiness', {
            'fields': (
                'device_ready',
                'camera_ready',
                'microphone_ready',
                'connection_quality',
            )
        }),
    )
    ordering = ['queue_number', 'check_in_time']
    
    def patient_link(self, obj):
        if obj.patient:
            url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
            return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
        return '-'
    patient_link.short_description = 'Patient'
    
    def status_badge(self, obj):
        colors = {
            'waiting': '#ffc107',
            'called': '#17a2b8',
            'in_consultation': '#28a745',
            'completed': '#6c757d',
            'cancelled': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def device_status(self, obj):
        if obj.device_ready and obj.camera_ready and obj.microphone_ready:
            return format_html('<span style="color: green;">✓ Ready</span>')
        elif obj.device_ready:
            return format_html('<span style="color: orange;">⚠ Partial</span>')
        return format_html('<span style="color: red;">✗ Not Ready</span>')
    device_status.short_description = 'Device Status'


@admin.register(ConsultationAnalytics)
class ConsultationAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        'consultation',
        'actual_wait_time_minutes',
        'consultation_duration_minutes',
        'patient_satisfaction_score',
        'connection_quality',
    )
    list_filter = ('patient_satisfaction_score', 'would_recommend', 'created')
    search_fields = ('consultation__consultation_id', 'consultation__patient__first_name', 'consultation__patient__last_name')
    readonly_fields = ('created', 'modified')
    fieldsets = (
        ('Consultation', {
            'fields': ('consultation',)
        }),
        ('Time Metrics', {
            'fields': (
                'actual_wait_time_minutes',
                'consultation_duration_minutes',
            )
        }),
        ('Quality Metrics', {
            'fields': (
                'video_quality_score',
                'audio_quality_score',
                'connection_drops',
                'average_latency_ms',
            )
        }),
        ('Patient Satisfaction', {
            'fields': (
                'patient_satisfaction_score',
                'patient_feedback',
                'would_recommend',
            )
        }),
        ('Clinical Metrics', {
            'fields': (
                'diagnosis_given',
                'prescription_issued',
                'lab_ordered',
                'follow_up_scheduled',
            )
        }),
        ('AI Utilization', {
            'fields': (
                'ai_features_used',
                'ai_suggestions_accepted',
                'ai_suggestions_rejected',
            )
        }),
    )
    
    def connection_quality(self, obj):
        if obj.connection_drops == 0:
            return format_html('<span style="color: green;">✓ Stable</span>')
        elif obj.connection_drops < 3:
            return format_html('<span style="color: orange;">⚠ {} drops</span>', obj.connection_drops)
        return format_html('<span style="color: red;">✗ {} drops</span>', obj.connection_drops)
    connection_quality.short_description = 'Connection'


@admin.register(AISymptomChecker)
class AISymptomCheckerAdmin(admin.ModelAdmin):
    list_display = (
        'patient_link',
        'ai_severity_level',
        'ai_confidence',
        'needs_emergency_care',
        'priority_score',
        'created',
    )
    list_filter = ('ai_severity_level', 'needs_emergency_care', 'can_use_telemedicine', 'created')
    search_fields = (
        'patient__first_name',
        'patient__last_name',
        'symptoms_described',
        'symptom_tags',
    )
    readonly_fields = ('created', 'modified')
    fieldsets = (
        ('Patient & Consultation', {
            'fields': ('patient', 'consultation')
        }),
        ('Symptoms', {
            'fields': (
                'symptoms_described',
                'symptom_tags',
                'duration_days',
                'severity_self_rated',
            )
        }),
        ('AI Analysis', {
            'fields': (
                'ai_severity_level',
                'ai_confidence',
                'possible_conditions',
                'red_flags',
                'recommended_specialties',
            )
        }),
        ('Recommendations', {
            'fields': (
                'needs_emergency_care',
                'can_use_telemedicine',
                'recommended_wait_time',
                'self_care_advice',
                'suggested_doctor_specialty',
                'priority_score',
            )
        }),
    )
    
    def patient_link(self, obj):
        if obj.patient:
            url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
            return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
        return '-'
    patient_link.short_description = 'Patient'


@admin.register(ConsultationRecording)
class ConsultationRecordingAdmin(admin.ModelAdmin):
    list_display = (
        'consultation',
        'recording_type',
        'duration_display',
        'file_size_mb',
        'is_encrypted',
        'has_transcription',
        'created',
    )
    list_filter = ('recording_type', 'is_encrypted', 'has_transcription', 'created')
    search_fields = ('consultation__consultation_id', 'transcription_text')
    readonly_fields = ('created', 'modified')
    fieldsets = (
        ('Recording Details', {
            'fields': (
                'consultation',
                'recording_type',
                'file_path',
                'file_size_mb',
                'duration_seconds',
            )
        }),
        ('Security', {
            'fields': (
                'is_encrypted',
                'encryption_key_id',
                'accessible_by',
                'expiry_date',
            )
        }),
        ('Transcription', {
            'fields': (
                'has_transcription',
                'transcription_text',
                'transcription_language',
            )
        }),
        ('AI Analysis', {
            'fields': (
                'key_topics',
                'medical_terms_mentioned',
                'sentiment_analysis',
            ),
            'classes': ('collapse',)
        }),
    )
    
    def duration_display(self, obj):
        minutes = obj.duration_seconds // 60
        seconds = obj.duration_seconds % 60
        return f"{minutes}m {seconds}s"
    duration_display.short_description = 'Duration'


@admin.register(PatientHealthData)
class PatientHealthDataAdmin(admin.ModelAdmin):
    list_display = (
        'patient_link',
        'data_type',
        'value',
        'unit',
        'data_source',
        'timestamp',
        'is_abnormal',
    )
    list_filter = ('data_source', 'data_type', 'is_abnormal', 'ai_alert_generated', 'timestamp')
    search_fields = ('patient__first_name', 'patient__last_name', 'data_type', 'notes')
    readonly_fields = ('created', 'modified')
    date_hierarchy = 'timestamp'
    
    def patient_link(self, obj):
        if obj.patient:
            url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
            return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
        return '-'
    patient_link.short_description = 'Patient'


@admin.register(TelemedicineTemplate)
class TelemedicineTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'template_name',
        'category',
        'ai_assisted',
        'is_active',
        'usage_count',
        'created_by',
    )
    list_filter = ('category', 'ai_assisted', 'is_active', 'created')
    search_fields = ('template_name', 'description')
    readonly_fields = ('created', 'modified', 'usage_count')
    fieldsets = (
        ('Template Information', {
            'fields': (
                'template_name',
                'category',
                'description',
                'created_by',
            )
        }),
        ('Template Content', {
            'fields': (
                'questions_checklist',
                'examination_steps',
                'common_diagnoses',
                'standard_prescriptions',
                'standard_advice',
            )
        }),
        ('AI Configuration', {
            'fields': (
                'ai_assisted',
                'ai_prompt_template',
            )
        }),
        ('Status', {
            'fields': ('is_active', 'usage_count')
        }),
    )


@admin.register(ConsultationFollowUp)
class ConsultationFollowUpAdmin(admin.ModelAdmin):
    list_display = (
        'original_consultation',
        'recommended_date',
        'status',
        'reminder_sent',
        'patient_confirmed',
    )
    list_filter = ('status', 'reminder_sent', 'patient_confirmed', 'recommended_date')
    search_fields = ('original_consultation__consultation_id', 'reason')
    readonly_fields = ('created', 'modified', 'reminder_sent_at', 'confirmed_at')
    date_hierarchy = 'recommended_date'


@admin.register(TelemedicineQualityMetrics)
class TelemedicineQualityMetricsAdmin(admin.ModelAdmin):
    list_display = (
        'date',
        'total_consultations',
        'completed_consultations',
        'average_patient_satisfaction',
        'total_revenue',
    )
    list_filter = ('date',)
    readonly_fields = ('created', 'modified')
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Date', {
            'fields': ('date',)
        }),
        ('Volume Metrics', {
            'fields': (
                'total_consultations',
                'completed_consultations',
                'cancelled_consultations',
                'no_shows',
            )
        }),
        ('Time Metrics', {
            'fields': (
                'average_wait_time_minutes',
                'average_consultation_duration_minutes',
            )
        }),
        ('Quality Metrics', {
            'fields': (
                'average_patient_satisfaction',
                'average_video_quality',
                'average_audio_quality',
                'total_connection_issues',
            )
        }),
        ('Clinical Outcomes', {
            'fields': (
                'diagnosis_rate',
                'prescription_rate',
                'lab_order_rate',
                'follow_up_rate',
            )
        }),
        ('AI Metrics', {
            'fields': (
                'ai_symptom_checker_uses',
                'ai_triage_accuracy',
                'ai_suggestion_acceptance_rate',
            )
        }),
        ('Financial', {
            'fields': (
                'total_revenue',
                'average_consultation_fee',
            )
        }),
    )


@admin.register(PatientSelfCheckIn)
class PatientSelfCheckInAdmin(admin.ModelAdmin):
    list_display = (
        'patient_link',
        'ai_urgency_score',
        'consent_to_telemedicine',
        'is_completed',
        'created',
    )
    list_filter = ('is_completed', 'consent_to_telemedicine', 'insurance_verified', 'created')
    search_fields = ('patient__first_name', 'patient__last_name', 'reason_for_visit')
    readonly_fields = ('created', 'modified', 'completed_at')
    
    def patient_link(self, obj):
        if obj.patient:
            url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
            return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
        return '-'
    patient_link.short_description = 'Patient'


@admin.register(ConsultationNote)
class ConsultationNoteAdmin(admin.ModelAdmin):
    list_display = (
        'consultation',
        'created_by',
        'ai_generated',
        'voice_dictated',
        'is_finalized',
        'created',
    )
    list_filter = ('ai_generated', 'voice_dictated', 'is_finalized', 'created')
    search_fields = (
        'consultation__consultation_id',
        'subjective',
        'objective',
        'assessment',
        'plan',
    )
    readonly_fields = ('created', 'modified', 'finalized_at')
    fieldsets = (
        ('Consultation', {
            'fields': ('consultation', 'created_by', 'template_used')
        }),
        ('SOAP Notes', {
            'fields': (
                'subjective',
                'objective',
                'assessment',
                'plan',
            )
        }),
        ('AI Features', {
            'fields': (
                'ai_generated',
                'ai_suggestions',
                'medical_codes_suggested',
            ),
            'classes': ('collapse',)
        }),
        ('Voice Dictation', {
            'fields': (
                'voice_dictated',
                'audio_file',
            ),
            'classes': ('collapse',)
        }),
        ('Finalization', {
            'fields': ('is_finalized', 'finalized_at')
        }),
    )


@admin.register(MultiLanguageSupport)
class MultiLanguageSupportAdmin(admin.ModelAdmin):
    list_display = (
        'consultation',
        'patient_language',
        'doctor_language',
        'translation_active',
        'messages_translated',
        'translation_errors',
    )
    list_filter = ('translation_active', 'patient_language', 'doctor_language', 'created')
    search_fields = ('consultation__consultation_id',)
    readonly_fields = ('created', 'modified')


@admin.register(EmergencyEscalation)
class EmergencyEscalationAdmin(admin.ModelAdmin):
    list_display = (
        'consultation',
        'escalation_reason',
        'triggered_by',
        'emergency_services_called',
        'ambulance_dispatched',
        'created',
    )
    list_filter = (
        'escalation_reason',
        'emergency_services_called',
        'ambulance_dispatched',
        'nearest_er_notified',
        'created',
    )
    search_fields = ('consultation__consultation_id', 'description')
    readonly_fields = ('created', 'modified', 'resolved_at')
    fieldsets = (
        ('Emergency Details', {
            'fields': (
                'consultation',
                'triggered_by',
                'escalation_reason',
                'description',
                'vital_signs_data',
            )
        }),
        ('Actions Taken', {
            'fields': (
                'emergency_services_called',
                'ambulance_dispatched',
                'nearest_er_notified',
                'supervisor_notified',
            )
        }),
        ('Response', {
            'fields': (
                'response_time_seconds',
                'outcome',
                'resolved_at',
            )
        }),
    )


# ==================== BASE TELEMEDICINE MODELS ====================

@admin.register(TelemedicineMessage)
class TelemedicineMessageAdmin(admin.ModelAdmin):
    list_display = ('consultation', 'sender', 'message_type', 'is_read', 'created')
    list_filter = ('message_type', 'is_read', 'created')
    search_fields = ('consultation__consultation_id', 'sender__username', 'content')
    readonly_fields = ('created', 'modified', 'read_at')


@admin.register(TelemedicinePrescription)
class TelemedicinePrescriptionAdmin(admin.ModelAdmin):
    list_display = ('consultation', 'drug', 'dosage', 'frequency', 'is_urgent', 'created')
    list_filter = ('is_urgent', 'created')
    search_fields = ('consultation__consultation_id', 'drug__name')
    readonly_fields = ('created', 'modified')


@admin.register(TelemedicineLabOrder)
class TelemedicineLabOrderAdmin(admin.ModelAdmin):
    list_display = ('consultation', 'test', 'priority', 'is_urgent', 'created')
    list_filter = ('priority', 'is_urgent', 'created')
    search_fields = ('consultation__consultation_id', 'test__name')
    readonly_fields = ('created', 'modified')


@admin.register(TelemedicineVitalSigns)
class TelemedicineVitalSignsAdmin(admin.ModelAdmin):
    list_display = (
        'consultation',
        'blood_pressure_systolic',
        'blood_pressure_diastolic',
        'heart_rate',
        'temperature',
        'oxygen_saturation',
        'created',
    )
    list_filter = ('created',)
    search_fields = ('consultation__consultation_id',)
    readonly_fields = ('created', 'modified')


@admin.register(TelemedicineAIAnalysis)
class TelemedicineAIAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        'consultation',
        'analysis_type',
        'confidence_score',
        'is_approved',
        'created',
    )
    list_filter = ('analysis_type', 'is_approved', 'created')
    search_fields = ('consultation__consultation_id', 'analysis_type')
    readonly_fields = ('created', 'modified', 'approved_at')


@admin.register(TelemedicineDevice)
class TelemedicineDeviceAdmin(admin.ModelAdmin):
    list_display = ('patient', 'device_name', 'device_type', 'is_active', 'last_seen')
    list_filter = ('device_type', 'is_active', 'last_seen')
    search_fields = ('patient__first_name', 'patient__last_name', 'device_name')
    readonly_fields = ('created', 'modified')


@admin.register(TelemedicineNotification)
class TelemedicineNotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'title', 'is_read', 'created')
    list_filter = ('notification_type', 'is_read', 'created')
    search_fields = ('user__username', 'title', 'message')
    readonly_fields = ('created', 'modified', 'read_at')


@admin.register(TelemedicinePayment)
class TelemedicinePaymentAdmin(admin.ModelAdmin):
    list_display = (
        'consultation',
        'amount',
        'currency',
        'payment_method',
        'payment_status',
        'paid_at',
    )
    list_filter = ('payment_status', 'payment_method', 'currency', 'created')
    search_fields = ('consultation__consultation_id', 'transaction_id')
    readonly_fields = ('created', 'modified')























