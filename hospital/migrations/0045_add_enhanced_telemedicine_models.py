# Generated manually for enhanced telemedicine models

from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields
import uuid


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("hospital", "0044_update_staffleavecounter_fields"),
    ]

    operations = [
        # ==================== Virtual Waiting Room ====================
        migrations.CreateModel(
            name="VirtualWaitingRoom",
            fields=[
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_deleted", models.BooleanField(default=False)),
                ("queue_number", models.PositiveIntegerField()),
                ("check_in_time", models.DateTimeField(auto_now_add=True)),
                ("called_at", models.DateTimeField(null=True, blank=True)),
                ("estimated_wait_minutes", models.PositiveIntegerField(default=15)),
                (
                    "status",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ('waiting', 'Waiting'),
                            ('called', 'Called - Ready for Consultation'),
                            ('in_consultation', 'In Consultation'),
                            ('completed', 'Completed'),
                            ('cancelled', 'Cancelled'),
                        ],
                        default='waiting',
                    ),
                ),
                ("device_ready", models.BooleanField(default=False)),
                ("camera_ready", models.BooleanField(default=False)),
                ("microphone_ready", models.BooleanField(default=False)),
                ("connection_quality", models.CharField(max_length=20, default='unknown')),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="virtual_queue",
                        to="hospital.patient",
                    ),
                ),
                (
                    "consultation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="waiting_room",
                        to="hospital.telemedicineconsultation",
                    ),
                ),
            ],
            options={
                "ordering": ["queue_number", "check_in_time"],
                "verbose_name": "Virtual Waiting Room Entry",
                "verbose_name_plural": "Virtual Waiting Room",
            },
        ),
        
        # ==================== Consultation Analytics ====================
        migrations.CreateModel(
            name="ConsultationAnalytics",
            fields=[
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_deleted", models.BooleanField(default=False)),
                ("actual_wait_time_minutes", models.PositiveIntegerField(default=0)),
                ("consultation_duration_minutes", models.PositiveIntegerField(default=0)),
                ("video_quality_score", models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)),
                ("audio_quality_score", models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)),
                ("connection_drops", models.PositiveIntegerField(default=0)),
                ("average_latency_ms", models.PositiveIntegerField(null=True, blank=True)),
                ("patient_satisfaction_score", models.PositiveIntegerField(null=True, blank=True)),
                ("patient_feedback", models.TextField(blank=True)),
                ("would_recommend", models.BooleanField(null=True, blank=True)),
                ("diagnosis_given", models.BooleanField(default=False)),
                ("prescription_issued", models.BooleanField(default=False)),
                ("lab_ordered", models.BooleanField(default=False)),
                ("follow_up_scheduled", models.BooleanField(default=False)),
                ("ai_features_used", models.JSONField(default=list)),
                ("ai_suggestions_accepted", models.PositiveIntegerField(default=0)),
                ("ai_suggestions_rejected", models.PositiveIntegerField(default=0)),
                (
                    "consultation",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="analytics",
                        to="hospital.telemedicineconsultation",
                    ),
                ),
            ],
            options={
                "verbose_name": "Consultation Analytics",
                "verbose_name_plural": "Consultation Analytics",
            },
        ),
        
        # ==================== AI Symptom Checker ====================
        migrations.CreateModel(
            name="AISymptomChecker",
            fields=[
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_deleted", models.BooleanField(default=False)),
                ("symptoms_described", models.TextField()),
                ("symptom_tags", models.JSONField(default=list)),
                ("duration_days", models.PositiveIntegerField(null=True, blank=True)),
                ("severity_self_rated", models.PositiveIntegerField(null=True, blank=True)),
                (
                    "ai_severity_level",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ('mild', 'Mild - Can Wait'),
                            ('moderate', 'Moderate - Needs Attention'),
                            ('severe', 'Severe - Urgent'),
                            ('critical', 'Critical - Emergency'),
                        ],
                    ),
                ),
                ("ai_confidence", models.DecimalField(max_digits=3, decimal_places=2)),
                ("possible_conditions", models.JSONField(default=list)),
                ("red_flags", models.JSONField(default=list)),
                ("recommended_specialties", models.JSONField(default=list)),
                ("needs_emergency_care", models.BooleanField(default=False)),
                ("can_use_telemedicine", models.BooleanField(default=True)),
                ("recommended_wait_time", models.CharField(max_length=50, blank=True)),
                ("self_care_advice", models.TextField(blank=True)),
                ("suggested_doctor_specialty", models.CharField(max_length=100, blank=True)),
                ("priority_score", models.PositiveIntegerField(default=50)),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="symptom_checks",
                        to="hospital.patient",
                    ),
                ),
                (
                    "consultation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        null=True,
                        blank=True,
                        to="hospital.telemedicineconsultation",
                    ),
                ),
            ],
            options={
                "ordering": ["-created"],
                "verbose_name": "AI Symptom Check",
            },
        ),
        
        # ==================== Consultation Recording ====================
        migrations.CreateModel(
            name="ConsultationRecording",
            fields=[
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_deleted", models.BooleanField(default=False)),
                (
                    "recording_type",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ('video', 'Video Recording'),
                            ('audio', 'Audio Only'),
                            ('screen', 'Screen Recording'),
                        ],
                        default='video',
                    ),
                ),
                ("file_path", models.CharField(max_length=500)),
                ("file_size_mb", models.DecimalField(max_digits=10, decimal_places=2)),
                ("duration_seconds", models.PositiveIntegerField()),
                ("is_encrypted", models.BooleanField(default=True)),
                ("encryption_key_id", models.CharField(max_length=100, blank=True)),
                ("has_transcription", models.BooleanField(default=False)),
                ("transcription_text", models.TextField(blank=True)),
                ("transcription_language", models.CharField(max_length=10, default='en')),
                ("key_topics", models.JSONField(default=list)),
                ("medical_terms_mentioned", models.JSONField(default=list)),
                ("sentiment_analysis", models.JSONField(default=dict)),
                ("expiry_date", models.DateField(null=True, blank=True)),
                (
                    "consultation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="recordings",
                        to="hospital.telemedicineconsultation",
                    ),
                ),
                (
                    "accessible_by",
                    models.ManyToManyField(
                        related_name="accessible_recordings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created"],
            },
        ),
        
        # ==================== Patient Health Data ====================
        migrations.CreateModel(
            name="PatientHealthData",
            fields=[
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_deleted", models.BooleanField(default=False)),
                (
                    "data_source",
                    models.CharField(
                        max_length=50,
                        choices=[
                            ('manual', 'Manual Entry'),
                            ('smartwatch', 'Smartwatch/Fitness Tracker'),
                            ('glucose_meter', 'Glucose Meter'),
                            ('bp_monitor', 'Blood Pressure Monitor'),
                            ('pulse_oximeter', 'Pulse Oximeter'),
                            ('thermometer', 'Smart Thermometer'),
                            ('weight_scale', 'Smart Scale'),
                        ],
                        default='manual',
                    ),
                ),
                ("device_name", models.CharField(max_length=100, blank=True)),
                ("data_type", models.CharField(max_length=50)),
                ("value", models.CharField(max_length=100)),
                ("unit", models.CharField(max_length=20)),
                ("timestamp", models.DateTimeField(default=django.utils.timezone.now)),
                ("notes", models.TextField(blank=True)),
                ("activity_level", models.CharField(max_length=50, blank=True)),
                ("is_abnormal", models.BooleanField(default=False)),
                ("ai_alert_generated", models.BooleanField(default=False)),
                ("alert_message", models.TextField(blank=True)),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="health_data",
                        to="hospital.patient",
                    ),
                ),
                (
                    "consultation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        null=True,
                        blank=True,
                        related_name="patient_data",
                        to="hospital.telemedicineconsultation",
                    ),
                ),
            ],
            options={
                "ordering": ["-timestamp"],
                "verbose_name": "Patient Health Data",
                "verbose_name_plural": "Patient Health Data",
            },
        ),
        
        # ==================== Telemedicine Template ====================
        migrations.CreateModel(
            name="TelemedicineTemplate",
            fields=[
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_deleted", models.BooleanField(default=False)),
                ("template_name", models.CharField(max_length=200)),
                (
                    "category",
                    models.CharField(
                        max_length=50,
                        choices=[
                            ('general', 'General Consultation'),
                            ('follow_up', 'Follow-up Visit'),
                            ('chronic_care', 'Chronic Disease Management'),
                            ('mental_health', 'Mental Health'),
                            ('pediatric', 'Pediatric Care'),
                            ('elderly_care', 'Elderly Care'),
                            ('emergency', 'Emergency Triage'),
                        ],
                    ),
                ),
                ("description", models.TextField()),
                ("questions_checklist", models.JSONField(default=list)),
                ("examination_steps", models.JSONField(default=list)),
                ("common_diagnoses", models.JSONField(default=list)),
                ("standard_prescriptions", models.JSONField(default=list)),
                ("standard_advice", models.TextField(blank=True)),
                ("ai_assisted", models.BooleanField(default=True)),
                ("ai_prompt_template", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("usage_count", models.PositiveIntegerField(default=0)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        null=True,
                        to="hospital.staff",
                    ),
                ),
            ],
            options={
                "ordering": ["category", "template_name"],
            },
        ),
        
        # ==================== Consultation Follow-Up ====================
        migrations.CreateModel(
            name="ConsultationFollowUp",
            fields=[
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_deleted", models.BooleanField(default=False)),
                ("recommended_date", models.DateField()),
                ("reason", models.TextField()),
                ("instructions_for_patient", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ('pending', 'Pending'),
                            ('scheduled', 'Scheduled'),
                            ('completed', 'Completed'),
                            ('missed', 'Missed'),
                            ('cancelled', 'Cancelled'),
                        ],
                        default='pending',
                    ),
                ),
                ("reminder_sent", models.BooleanField(default=False)),
                ("reminder_sent_at", models.DateTimeField(null=True, blank=True)),
                ("patient_confirmed", models.BooleanField(default=False)),
                ("confirmed_at", models.DateTimeField(null=True, blank=True)),
                ("check_these_symptoms", models.JSONField(default=list)),
                ("alert_if_worsening", models.BooleanField(default=False)),
                (
                    "original_consultation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="follow_ups_generated",
                        to="hospital.telemedicineconsultation",
                    ),
                ),
                (
                    "follow_up_consultation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        null=True,
                        blank=True,
                        related_name="follow_up_for",
                        to="hospital.telemedicineconsultation",
                    ),
                ),
            ],
            options={
                "ordering": ["recommended_date"],
                "verbose_name": "Follow-up",
                "verbose_name_plural": "Follow-ups",
            },
        ),
        
        # ==================== Telemedicine Quality Metrics ====================
        migrations.CreateModel(
            name="TelemedicineQualityMetrics",
            fields=[
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_deleted", models.BooleanField(default=False)),
                ("date", models.DateField(unique=True, default=django.utils.timezone.now)),
                ("total_consultations", models.PositiveIntegerField(default=0)),
                ("completed_consultations", models.PositiveIntegerField(default=0)),
                ("cancelled_consultations", models.PositiveIntegerField(default=0)),
                ("no_shows", models.PositiveIntegerField(default=0)),
                ("average_wait_time_minutes", models.DecimalField(max_digits=6, decimal_places=2, default=0)),
                ("average_consultation_duration_minutes", models.DecimalField(max_digits=6, decimal_places=2, default=0)),
                ("average_patient_satisfaction", models.DecimalField(max_digits=3, decimal_places=2, default=0)),
                ("average_video_quality", models.DecimalField(max_digits=3, decimal_places=2, default=0)),
                ("average_audio_quality", models.DecimalField(max_digits=3, decimal_places=2, default=0)),
                ("total_connection_issues", models.PositiveIntegerField(default=0)),
                ("diagnosis_rate", models.DecimalField(max_digits=5, decimal_places=2, default=0)),
                ("prescription_rate", models.DecimalField(max_digits=5, decimal_places=2, default=0)),
                ("lab_order_rate", models.DecimalField(max_digits=5, decimal_places=2, default=0)),
                ("follow_up_rate", models.DecimalField(max_digits=5, decimal_places=2, default=0)),
                ("ai_symptom_checker_uses", models.PositiveIntegerField(default=0)),
                ("ai_triage_accuracy", models.DecimalField(max_digits=5, decimal_places=2, default=0)),
                ("ai_suggestion_acceptance_rate", models.DecimalField(max_digits=5, decimal_places=2, default=0)),
                ("total_revenue", models.DecimalField(max_digits=12, decimal_places=2, default=0)),
                ("average_consultation_fee", models.DecimalField(max_digits=10, decimal_places=2, default=0)),
            ],
            options={
                "ordering": ["-date"],
                "verbose_name": "Quality Metrics",
                "verbose_name_plural": "Quality Metrics",
            },
        ),
        
        # ==================== Patient Self Check-In ====================
        migrations.CreateModel(
            name="PatientSelfCheckIn",
            fields=[
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_deleted", models.BooleanField(default=False)),
                ("reason_for_visit", models.TextField()),
                ("symptoms", models.JSONField(default=list)),
                ("symptom_duration", models.CharField(max_length=100)),
                ("previous_treatments_tried", models.TextField(blank=True)),
                ("temperature", models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)),
                ("heart_rate", models.PositiveIntegerField(null=True, blank=True)),
                ("blood_pressure", models.CharField(max_length=20, blank=True)),
                ("oxygen_saturation", models.PositiveIntegerField(null=True, blank=True)),
                ("insurance_verified", models.BooleanField(default=False)),
                ("payment_method_selected", models.CharField(max_length=50, blank=True)),
                ("co_pay_acknowledged", models.BooleanField(default=False)),
                ("consent_to_telemedicine", models.BooleanField(default=False)),
                ("privacy_policy_agreed", models.BooleanField(default=False)),
                ("signature", models.TextField(blank=True)),
                ("ai_urgency_score", models.PositiveIntegerField(default=50)),
                ("ai_recommended_specialty", models.CharField(max_length=100, blank=True)),
                ("ai_estimated_duration", models.PositiveIntegerField(default=15)),
                ("completed_at", models.DateTimeField(null=True, blank=True)),
                ("is_completed", models.BooleanField(default=False)),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="self_checkins",
                        to="hospital.patient",
                    ),
                ),
                (
                    "consultation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        null=True,
                        blank=True,
                        to="hospital.telemedicineconsultation",
                    ),
                ),
            ],
            options={
                "ordering": ["-created"],
                "verbose_name": "Self Check-in",
                "verbose_name_plural": "Self Check-ins",
            },
        ),
        
        # ==================== Consultation Note ====================
        migrations.CreateModel(
            name="ConsultationNote",
            fields=[
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_deleted", models.BooleanField(default=False)),
                ("subjective", models.TextField(blank=True)),
                ("objective", models.TextField(blank=True)),
                ("assessment", models.TextField(blank=True)),
                ("plan", models.TextField(blank=True)),
                ("ai_generated", models.BooleanField(default=False)),
                ("ai_suggestions", models.JSONField(default=dict)),
                ("medical_codes_suggested", models.JSONField(default=list)),
                ("voice_dictated", models.BooleanField(default=False)),
                ("audio_file", models.FileField(upload_to='consultation_audio/', null=True, blank=True)),
                ("is_finalized", models.BooleanField(default=False)),
                ("finalized_at", models.DateTimeField(null=True, blank=True)),
                (
                    "consultation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="smart_notes",
                        to="hospital.telemedicineconsultation",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "template_used",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        null=True,
                        blank=True,
                        to="hospital.telemedicinetemplate",
                    ),
                ),
            ],
            options={
                "ordering": ["-created"],
            },
        ),
        
        # ==================== Multi-Language Support ====================
        migrations.CreateModel(
            name="MultiLanguageSupport",
            fields=[
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_deleted", models.BooleanField(default=False)),
                ("patient_language", models.CharField(max_length=50, default='en')),
                ("doctor_language", models.CharField(max_length=50, default='en')),
                ("translation_active", models.BooleanField(default=False)),
                ("translation_quality", models.CharField(max_length=20, default='high')),
                ("messages_translated", models.PositiveIntegerField(default=0)),
                ("translation_errors", models.PositiveIntegerField(default=0)),
                (
                    "consultation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="translations",
                        to="hospital.telemedicineconsultation",
                    ),
                ),
            ],
            options={
                "ordering": ["-created"],
            },
        ),
        
        # ==================== Emergency Escalation ====================
        migrations.CreateModel(
            name="EmergencyEscalation",
            fields=[
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_deleted", models.BooleanField(default=False)),
                (
                    "escalation_reason",
                    models.CharField(
                        max_length=50,
                        choices=[
                            ('severe_symptoms', 'Severe Symptoms Detected'),
                            ('vital_signs_critical', 'Critical Vital Signs'),
                            ('patient_distress', 'Patient in Distress'),
                            ('chest_pain', 'Chest Pain'),
                            ('difficulty_breathing', 'Difficulty Breathing'),
                            ('loss_of_consciousness', 'Loss of Consciousness'),
                            ('severe_bleeding', 'Severe Bleeding'),
                            ('other', 'Other Emergency'),
                        ],
                    ),
                ),
                ("description", models.TextField()),
                ("vital_signs_data", models.JSONField(default=dict)),
                ("emergency_services_called", models.BooleanField(default=False)),
                ("ambulance_dispatched", models.BooleanField(default=False)),
                ("nearest_er_notified", models.BooleanField(default=False)),
                ("supervisor_notified", models.BooleanField(default=False)),
                ("response_time_seconds", models.PositiveIntegerField(null=True, blank=True)),
                ("outcome", models.TextField(blank=True)),
                ("resolved_at", models.DateTimeField(null=True, blank=True)),
                (
                    "consultation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="emergency_escalations",
                        to="hospital.telemedicineconsultation",
                    ),
                ),
                (
                    "triggered_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created"],
            },
        ),
    ]























