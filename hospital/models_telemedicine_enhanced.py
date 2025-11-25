"""
Enhanced Telemedicine Models - World-Class Innovations
Next-generation telehealth with AI, analytics, and automation
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from .models import BaseModel, Patient, Staff


class VirtualWaitingRoom(BaseModel):
    """
    Virtual waiting room with live queue management
    Innovative feature: Patients can see their queue position in real-time
    """
    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('called', 'Called - Ready for Consultation'),
        ('in_consultation', 'In Consultation'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='virtual_queue')
    consultation = models.ForeignKey('TelemedicineConsultation', on_delete=models.CASCADE, related_name='waiting_room')
    
    queue_number = models.PositiveIntegerField()
    check_in_time = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)
    estimated_wait_minutes = models.PositiveIntegerField(default=15)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    
    # Patient device info for connectivity check
    device_ready = models.BooleanField(default=False)
    camera_ready = models.BooleanField(default=False)
    microphone_ready = models.BooleanField(default=False)
    connection_quality = models.CharField(max_length=20, default='unknown')  # excellent, good, fair, poor
    
    class Meta:
        ordering = ['queue_number', 'check_in_time']
        verbose_name = 'Virtual Waiting Room Entry'
        verbose_name_plural = 'Virtual Waiting Room'
    
    def __str__(self):
        return f"Queue #{self.queue_number} - {self.patient.full_name}"


class ConsultationAnalytics(BaseModel):
    """
    Comprehensive analytics for telemedicine consultations
    Innovation: Real-time quality metrics and insights
    """
    consultation = models.OneToOneField('TelemedicineConsultation', on_delete=models.CASCADE, related_name='analytics')
    
    # Time metrics
    actual_wait_time_minutes = models.PositiveIntegerField(default=0)
    consultation_duration_minutes = models.PositiveIntegerField(default=0)
    
    # Quality metrics
    video_quality_score = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)  # 0-10
    audio_quality_score = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    connection_drops = models.PositiveIntegerField(default=0)
    average_latency_ms = models.PositiveIntegerField(null=True, blank=True)
    
    # Patient satisfaction
    patient_satisfaction_score = models.PositiveIntegerField(null=True, blank=True)  # 1-5 stars
    patient_feedback = models.TextField(blank=True)
    would_recommend = models.BooleanField(null=True, blank=True)
    
    # Clinical metrics
    diagnosis_given = models.BooleanField(default=False)
    prescription_issued = models.BooleanField(default=False)
    lab_ordered = models.BooleanField(default=False)
    follow_up_scheduled = models.BooleanField(default=False)
    
    # AI utilization
    ai_features_used = models.JSONField(default=list)
    ai_suggestions_accepted = models.PositiveIntegerField(default=0)
    ai_suggestions_rejected = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = 'Consultation Analytics'
        verbose_name_plural = 'Consultation Analytics'
    
    def __str__(self):
        return f"Analytics for {self.consultation.consultation_id}"


class AISymptomChecker(BaseModel):
    """
    Advanced AI-powered symptom checker
    Innovation: Pre-consultation triage and smart routing
    """
    SEVERITY_LEVELS = [
        ('mild', 'Mild - Can Wait'),
        ('moderate', 'Moderate - Needs Attention'),
        ('severe', 'Severe - Urgent'),
        ('critical', 'Critical - Emergency'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='symptom_checks')
    consultation = models.ForeignKey('TelemedicineConsultation', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Symptoms input
    symptoms_described = models.TextField()
    symptom_tags = models.JSONField(default=list)  # ['fever', 'cough', 'headache']
    duration_days = models.PositiveIntegerField(null=True, blank=True)
    severity_self_rated = models.PositiveIntegerField(null=True, blank=True)  # 1-10
    
    # AI Analysis
    ai_severity_level = models.CharField(max_length=20, choices=SEVERITY_LEVELS)
    ai_confidence = models.DecimalField(max_digits=3, decimal_places=2)  # 0.00 - 1.00
    possible_conditions = models.JSONField(default=list)  # [{'name': 'Common Cold', 'probability': 0.85}]
    red_flags = models.JSONField(default=list)  # Warning signs detected
    recommended_specialties = models.JSONField(default=list)
    
    # Recommendations
    needs_emergency_care = models.BooleanField(default=False)
    can_use_telemedicine = models.BooleanField(default=True)
    recommended_wait_time = models.CharField(max_length=50, blank=True)  # 'within 24 hours', 'urgent'
    self_care_advice = models.TextField(blank=True)
    
    # Routing
    suggested_doctor_specialty = models.CharField(max_length=100, blank=True)
    priority_score = models.PositiveIntegerField(default=50)  # 0-100, higher = more urgent
    
    class Meta:
        ordering = ['-created']
        verbose_name = 'AI Symptom Check'
    
    def __str__(self):
        return f"Symptom Check - {self.patient.full_name} ({self.ai_severity_level})"


class ConsultationRecording(BaseModel):
    """
    Secure consultation recordings (video/audio)
    Innovation: Encrypted storage with AI transcription
    """
    consultation = models.ForeignKey('TelemedicineConsultation', on_delete=models.CASCADE, related_name='recordings')
    
    recording_type = models.CharField(max_length=20, choices=[
        ('video', 'Video Recording'),
        ('audio', 'Audio Only'),
        ('screen', 'Screen Recording'),
    ], default='video')
    
    file_path = models.CharField(max_length=500)  # Encrypted file location
    file_size_mb = models.DecimalField(max_digits=10, decimal_places=2)
    duration_seconds = models.PositiveIntegerField()
    
    is_encrypted = models.BooleanField(default=True)
    encryption_key_id = models.CharField(max_length=100, blank=True)
    
    # AI Transcription
    has_transcription = models.BooleanField(default=False)
    transcription_text = models.TextField(blank=True)
    transcription_language = models.CharField(max_length=10, default='en')
    
    # AI Analysis of conversation
    key_topics = models.JSONField(default=list)  # Topics discussed
    medical_terms_mentioned = models.JSONField(default=list)
    sentiment_analysis = models.JSONField(default=dict)
    
    # Access control
    accessible_by = models.ManyToManyField(User, related_name='accessible_recordings')
    expiry_date = models.DateField(null=True, blank=True)  # Auto-delete after certain period
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"Recording - {self.consultation.consultation_id}"


class PatientHealthData(BaseModel):
    """
    Patient-submitted health data from wearables/devices
    Innovation: IoMT (Internet of Medical Things) integration
    """
    DATA_SOURCES = [
        ('manual', 'Manual Entry'),
        ('smartwatch', 'Smartwatch/Fitness Tracker'),
        ('glucose_meter', 'Glucose Meter'),
        ('bp_monitor', 'Blood Pressure Monitor'),
        ('pulse_oximeter', 'Pulse Oximeter'),
        ('thermometer', 'Smart Thermometer'),
        ('weight_scale', 'Smart Scale'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='health_data')
    consultation = models.ForeignKey('TelemedicineConsultation', on_delete=models.CASCADE, null=True, blank=True, related_name='patient_data')
    
    data_source = models.CharField(max_length=50, choices=DATA_SOURCES, default='manual')
    device_name = models.CharField(max_length=100, blank=True)
    
    # Health metrics
    data_type = models.CharField(max_length=50)  # heart_rate, blood_pressure, glucose, etc.
    value = models.CharField(max_length=100)
    unit = models.CharField(max_length=20)
    timestamp = models.DateTimeField(default=timezone.now)
    
    # Contextual data
    notes = models.TextField(blank=True)
    activity_level = models.CharField(max_length=50, blank=True)  # resting, active, sleeping
    
    # AI flagging
    is_abnormal = models.BooleanField(default=False)
    ai_alert_generated = models.BooleanField(default=False)
    alert_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Patient Health Data'
        verbose_name_plural = 'Patient Health Data'
    
    def __str__(self):
        return f"{self.patient.full_name} - {self.data_type}: {self.value} {self.unit}"


class TelemedicineTemplate(BaseModel):
    """
    Consultation templates for common conditions
    Innovation: Smart templates with AI auto-fill
    """
    TEMPLATE_CATEGORIES = [
        ('general', 'General Consultation'),
        ('follow_up', 'Follow-up Visit'),
        ('chronic_care', 'Chronic Disease Management'),
        ('mental_health', 'Mental Health'),
        ('pediatric', 'Pediatric Care'),
        ('elderly_care', 'Elderly Care'),
        ('emergency', 'Emergency Triage'),
    ]
    
    template_name = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=TEMPLATE_CATEGORIES)
    description = models.TextField()
    
    # Template structure
    questions_checklist = models.JSONField(default=list)  # Questions to ask
    examination_steps = models.JSONField(default=list)  # Visual examination steps
    common_diagnoses = models.JSONField(default=list)  # Common diagnoses for this template
    standard_prescriptions = models.JSONField(default=list)  # Commonly prescribed drugs
    standard_advice = models.TextField(blank=True)
    
    # AI enhancement
    ai_assisted = models.BooleanField(default=True)
    ai_prompt_template = models.TextField(blank=True)  # Prompt for AI assistance
    
    is_active = models.BooleanField(default=True)
    usage_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['category', 'template_name']
    
    def __str__(self):
        return f"{self.template_name} ({self.get_category_display()})"


class ConsultationFollowUp(BaseModel):
    """
    Automated follow-up system
    Innovation: Smart follow-up scheduling and reminders
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('missed', 'Missed'),
        ('cancelled', 'Cancelled'),
    ]
    
    original_consultation = models.ForeignKey('TelemedicineConsultation', on_delete=models.CASCADE, related_name='follow_ups_generated')
    follow_up_consultation = models.ForeignKey('TelemedicineConsultation', on_delete=models.SET_NULL, null=True, blank=True, related_name='follow_up_for')
    
    recommended_date = models.DateField()
    reason = models.TextField()
    instructions_for_patient = models.TextField(blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Automated reminders
    reminder_sent = models.BooleanField(default=False)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    patient_confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    
    # Monitoring
    check_these_symptoms = models.JSONField(default=list)  # Symptoms to monitor
    alert_if_worsening = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['recommended_date']
        verbose_name = 'Follow-up'
        verbose_name_plural = 'Follow-ups'
    
    def __str__(self):
        return f"Follow-up for {self.original_consultation.patient.full_name} on {self.recommended_date}"


class TelemedicineQualityMetrics(BaseModel):
    """
    System-wide quality metrics and KPIs
    Innovation: Real-time quality monitoring and improvement tracking
    """
    date = models.DateField(unique=True, default=timezone.now)
    
    # Volume metrics
    total_consultations = models.PositiveIntegerField(default=0)
    completed_consultations = models.PositiveIntegerField(default=0)
    cancelled_consultations = models.PositiveIntegerField(default=0)
    no_shows = models.PositiveIntegerField(default=0)
    
    # Time metrics
    average_wait_time_minutes = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    average_consultation_duration_minutes = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    
    # Quality metrics
    average_patient_satisfaction = models.DecimalField(max_digits=3, decimal_places=2, default=0)  # 0-5 stars
    average_video_quality = models.DecimalField(max_digits=3, decimal_places=2, default=0)  # 0-10
    average_audio_quality = models.DecimalField(max_digits=3, decimal_places=2, default=0)  # 0-10
    total_connection_issues = models.PositiveIntegerField(default=0)
    
    # Clinical outcomes
    diagnosis_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Percentage
    prescription_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    lab_order_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    follow_up_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # AI metrics
    ai_symptom_checker_uses = models.PositiveIntegerField(default=0)
    ai_triage_accuracy = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    ai_suggestion_acceptance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Financial
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    average_consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    class Meta:
        ordering = ['-date']
        verbose_name = 'Quality Metrics'
        verbose_name_plural = 'Quality Metrics'
    
    def __str__(self):
        return f"Telemedicine Metrics - {self.date}"


class PatientSelfCheckIn(BaseModel):
    """
    Patient self-service check-in system
    Innovation: Automated intake with AI assistance
    """
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='self_checkins')
    consultation = models.ForeignKey('TelemedicineConsultation', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Pre-consultation questionnaire
    reason_for_visit = models.TextField()
    symptoms = models.JSONField(default=list)
    symptom_duration = models.CharField(max_length=100)
    previous_treatments_tried = models.TextField(blank=True)
    
    # Self-reported vitals (if available)
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    heart_rate = models.PositiveIntegerField(null=True, blank=True)
    blood_pressure = models.CharField(max_length=20, blank=True)
    oxygen_saturation = models.PositiveIntegerField(null=True, blank=True)
    
    # Insurance & payment
    insurance_verified = models.BooleanField(default=False)
    payment_method_selected = models.CharField(max_length=50, blank=True)
    co_pay_acknowledged = models.BooleanField(default=False)
    
    # Consent & legal
    consent_to_telemedicine = models.BooleanField(default=False)
    privacy_policy_agreed = models.BooleanField(default=False)
    signature = models.TextField(blank=True)  # Digital signature data
    
    # AI pre-screening
    ai_urgency_score = models.PositiveIntegerField(default=50)  # 0-100
    ai_recommended_specialty = models.CharField(max_length=100, blank=True)
    ai_estimated_duration = models.PositiveIntegerField(default=15)  # minutes
    
    completed_at = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created']
        verbose_name = 'Self Check-in'
        verbose_name_plural = 'Self Check-ins'
    
    def __str__(self):
        return f"Check-in - {self.patient.full_name} at {self.created.strftime('%Y-%m-%d %H:%M')}"


class ConsultationNote(BaseModel):
    """
    Smart consultation notes with AI assistance
    Innovation: AI-powered note generation and medical coding
    """
    consultation = models.ForeignKey('TelemedicineConsultation', on_delete=models.CASCADE, related_name='smart_notes')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Note sections (SOAP format)
    subjective = models.TextField(blank=True)  # Patient's description
    objective = models.TextField(blank=True)  # Observable findings
    assessment = models.TextField(blank=True)  # Diagnosis/assessment
    plan = models.TextField(blank=True)  # Treatment plan
    
    # AI enhancements
    ai_generated = models.BooleanField(default=False)
    ai_suggestions = models.JSONField(default=dict)
    medical_codes_suggested = models.JSONField(default=list)  # ICD-10, CPT codes
    
    # Voice-to-text
    voice_dictated = models.BooleanField(default=False)
    audio_file = models.FileField(upload_to='consultation_audio/', null=True, blank=True)
    
    # Templates
    template_used = models.ForeignKey(TelemedicineTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Approval
    is_finalized = models.BooleanField(default=False)
    finalized_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"Note for {self.consultation.consultation_id} by {self.created_by.username}"


class MultiLanguageSupport(BaseModel):
    """
    Real-time translation for multi-language consultations
    Innovation: AI-powered translation for global reach
    """
    consultation = models.ForeignKey('TelemedicineConsultation', on_delete=models.CASCADE, related_name='translations')
    
    patient_language = models.CharField(max_length=50, default='en')
    doctor_language = models.CharField(max_length=50, default='en')
    
    translation_active = models.BooleanField(default=False)
    translation_quality = models.CharField(max_length=20, default='high')  # high, medium, low
    
    # Translation log
    messages_translated = models.PositiveIntegerField(default=0)
    translation_errors = models.PositiveIntegerField(default=0)
    
    # Supported languages
    LANGUAGES = [
        ('en', 'English'),
        ('fr', 'French'),
        ('es', 'Spanish'),
        ('ar', 'Arabic'),
        ('zh', 'Chinese'),
        ('hi', 'Hindi'),
        ('pt', 'Portuguese'),
    ]
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"Translation {self.patient_language} ↔ {self.doctor_language}"


class EmergencyEscalation(BaseModel):
    """
    Emergency escalation system
    Innovation: Automatic detection and escalation of emergencies
    """
    ESCALATION_REASONS = [
        ('severe_symptoms', 'Severe Symptoms Detected'),
        ('vital_signs_critical', 'Critical Vital Signs'),
        ('patient_distress', 'Patient in Distress'),
        ('chest_pain', 'Chest Pain'),
        ('difficulty_breathing', 'Difficulty Breathing'),
        ('loss_of_consciousness', 'Loss of Consciousness'),
        ('severe_bleeding', 'Severe Bleeding'),
        ('other', 'Other Emergency'),
    ]
    
    consultation = models.ForeignKey('TelemedicineConsultation', on_delete=models.CASCADE, related_name='emergency_escalations')
    triggered_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    escalation_reason = models.CharField(max_length=50, choices=ESCALATION_REASONS)
    description = models.TextField()
    vital_signs_data = models.JSONField(default=dict)
    
    # Actions taken
    emergency_services_called = models.BooleanField(default=False)
    ambulance_dispatched = models.BooleanField(default=False)
    nearest_er_notified = models.BooleanField(default=False)
    supervisor_notified = models.BooleanField(default=False)
    
    # Response
    response_time_seconds = models.PositiveIntegerField(null=True, blank=True)
    outcome = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"Emergency Escalation - {self.consultation.consultation_id}"























