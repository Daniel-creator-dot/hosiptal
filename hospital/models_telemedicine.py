"""
Telemedicine Models
State-of-the-art telemedicine system with AI integration
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import uuid


class BaseModel(models.Model):
    """Base model with common fields"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        abstract = True


class TelemedicineConsultation(BaseModel):
    """Telemedicine consultation session"""
    CONSULTATION_STATUS = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
        ('rescheduled', 'Rescheduled'),
    ]
    
    CONSULTATION_TYPE = [
        ('video', 'Video Call'),
        ('audio', 'Audio Call'),
        ('chat', 'Text Chat'),
        ('hybrid', 'Hybrid (Video + Chat)'),
    ]
    
    PRIORITY_LEVEL = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    # Basic Information
    consultation_id = models.CharField(max_length=20, unique=True)
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE, related_name='telemedicine_consultations')
    doctor = models.ForeignKey('Staff', on_delete=models.CASCADE, related_name='telemedicine_consultations')
    
    # Consultation Details
    consultation_type = models.CharField(max_length=20, choices=CONSULTATION_TYPE, default='video')
    status = models.CharField(max_length=20, choices=CONSULTATION_STATUS, default='scheduled')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVEL, default='medium')
    
    # Scheduling
    scheduled_at = models.DateTimeField()
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    
    # Consultation Content
    chief_complaint = models.TextField(blank=True)
    symptoms = models.JSONField(default=list, blank=True)
    ai_triage_score = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    ai_triage_recommendation = models.TextField(blank=True)
    
    # Medical Information
    diagnosis = models.TextField(blank=True)
    treatment_plan = models.TextField(blank=True)
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateTimeField(null=True, blank=True)
    
    # Technical Details
    meeting_room_id = models.CharField(max_length=100, blank=True)
    meeting_url = models.URLField(blank=True)
    recording_url = models.URLField(blank=True)
    quality_rating = models.PositiveIntegerField(null=True, blank=True)
    
    # Financial
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    payment_status = models.CharField(max_length=20, default='pending')
    payment_method = models.CharField(max_length=50, blank=True)
    
    # AI Features
    ai_symptom_analysis = models.JSONField(default=dict, blank=True)
    ai_diagnosis_suggestions = models.JSONField(default=list, blank=True)
    ai_prescription_suggestions = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-scheduled_at']
    
    def __str__(self):
        return f"Teleconsultation {self.consultation_id} - {self.patient.full_name} with Dr. {self.doctor.user.get_full_name()}"
    
    def get_duration_display(self):
        """Get formatted duration"""
        if self.duration_minutes:
            hours = self.duration_minutes // 60
            minutes = self.duration_minutes % 60
            if hours > 0:
                return f"{hours}h {minutes}m"
            return f"{minutes}m"
        return "N/A"
    
    def is_active(self):
        """Check if consultation is currently active"""
        return self.status == 'in_progress' and self.started_at and not self.ended_at
    
    def can_start(self):
        """Check if consultation can be started"""
        return self.status == 'scheduled' and timezone.now() >= self.scheduled_at


class TelemedicineMessage(BaseModel):
    """Real-time messages during consultation"""
    MESSAGE_TYPE = [
        ('text', 'Text Message'),
        ('image', 'Image'),
        ('file', 'File Attachment'),
        ('prescription', 'Prescription'),
        ('lab_order', 'Lab Order'),
        ('system', 'System Message'),
    ]
    
    consultation = models.ForeignKey(TelemedicineConsultation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE, default='text')
    content = models.TextField()
    attachment = models.FileField(upload_to='telemedicine/attachments/', null=True, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['created']
    
    def __str__(self):
        return f"Message from {self.sender.username} in {self.consultation.consultation_id}"


class TelemedicinePrescription(BaseModel):
    """Prescriptions issued during telemedicine consultation"""
    consultation = models.ForeignKey(TelemedicineConsultation, on_delete=models.CASCADE, related_name='prescriptions')
    drug = models.ForeignKey('Drug', on_delete=models.CASCADE)
    dosage = models.CharField(max_length=100)
    frequency = models.CharField(max_length=100)
    duration = models.CharField(max_length=100)
    instructions = models.TextField(blank=True)
    quantity = models.PositiveIntegerField(default=1)
    is_urgent = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.drug.name} - {self.dosage} for {self.consultation.patient.full_name}"


class TelemedicineLabOrder(BaseModel):
    """Lab orders issued during telemedicine consultation"""
    consultation = models.ForeignKey(TelemedicineConsultation, on_delete=models.CASCADE, related_name='lab_orders')
    test = models.ForeignKey('LabTest', on_delete=models.CASCADE)
    instructions = models.TextField(blank=True)
    is_urgent = models.BooleanField(default=False)
    priority = models.CharField(max_length=20, default='normal')
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.test.name} for {self.consultation.patient.full_name}"


class TelemedicineVitalSigns(BaseModel):
    """Vital signs recorded during telemedicine consultation"""
    consultation = models.ForeignKey(TelemedicineConsultation, on_delete=models.CASCADE, related_name='vital_signs')
    recorded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Vital signs
    blood_pressure_systolic = models.PositiveIntegerField(null=True, blank=True)
    blood_pressure_diastolic = models.PositiveIntegerField(null=True, blank=True)
    heart_rate = models.PositiveIntegerField(null=True, blank=True)
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    oxygen_saturation = models.PositiveIntegerField(null=True, blank=True)
    respiratory_rate = models.PositiveIntegerField(null=True, blank=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"Vitals for {self.consultation.patient.full_name} - {self.created.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def bmi(self):
        """Calculate BMI"""
        if self.weight and self.height:
            height_m = float(self.height) / 100
            return round(float(self.weight) / (height_m ** 2), 1)
        return None


class TelemedicineAIAnalysis(BaseModel):
    """AI-powered analysis and recommendations"""
    consultation = models.ForeignKey(TelemedicineConsultation, on_delete=models.CASCADE, related_name='ai_analyses')
    analysis_type = models.CharField(max_length=50)  # symptom_checker, triage, diagnosis, prescription
    input_data = models.JSONField(default=dict)
    ai_response = models.JSONField(default=dict)
    confidence_score = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"AI {self.analysis_type} for {self.consultation.consultation_id}"


class TelemedicineDevice(BaseModel):
    """Patient devices for telemedicine"""
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE, related_name='telemedicine_devices')
    device_name = models.CharField(max_length=100)
    device_type = models.CharField(max_length=50)  # smartphone, tablet, computer, wearable
    os = models.CharField(max_length=50, blank=True)
    browser = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-last_seen']
    
    def __str__(self):
        return f"{self.device_name} - {self.patient.full_name}"


class TelemedicineNotification(BaseModel):
    """Notifications for telemedicine events"""
    NOTIFICATION_TYPE = [
        ('consultation_scheduled', 'Consultation Scheduled'),
        ('consultation_starting', 'Consultation Starting'),
        ('consultation_reminder', 'Consultation Reminder'),
        ('message_received', 'Message Received'),
        ('prescription_ready', 'Prescription Ready'),
        ('lab_result_ready', 'Lab Result Ready'),
        ('payment_required', 'Payment Required'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='telemedicine_notifications')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPE)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    consultation = models.ForeignKey(TelemedicineConsultation, on_delete=models.CASCADE, null=True, blank=True)
    action_url = models.URLField(blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.notification_type} - {self.user.username}"


class TelemedicinePayment(BaseModel):
    """Payment tracking for telemedicine consultations"""
    consultation = models.ForeignKey(TelemedicineConsultation, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='GHS')
    payment_method = models.CharField(max_length=50)
    payment_status = models.CharField(max_length=20, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True)
    payment_gateway = models.CharField(max_length=50, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"Payment {self.transaction_id} - {self.amount} {self.currency}"




































