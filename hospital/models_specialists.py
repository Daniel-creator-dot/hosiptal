"""
Specialist/Specialty Models for Medical Specialists
Dental, Cardiology, Ophthalmology, etc.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date
from .models import BaseModel, Patient, Encounter, Staff, Order


# ==================== SPECIALTY & SPECIALIST MODULE ====================

class Specialty(BaseModel):
    """Medical specialties (Cardiology, Dentistry, Ophthalmology, etc.)"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)  # For UI icons
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Specialties'
    
    def __str__(self):
        return self.name


class SpecialistProfile(BaseModel):
    """Specialist doctor profiles"""
    staff = models.OneToOneField(Staff, on_delete=models.CASCADE, related_name='specialist_profile')
    specialty = models.ForeignKey(Specialty, on_delete=models.PROTECT, related_name='specialists')
    qualification = models.CharField(max_length=200, blank=True)
    experience_years = models.IntegerField(default=0)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['specialty', 'staff__user__last_name']
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.specialty.name}"


# ==================== DENTAL MODULE ====================

class DentalProcedureCatalog(BaseModel):
    """Catalog of dental procedures with standard codes and prices"""
    PROCEDURE_TYPES = [
        ('diagnostic', 'Diagnostic'),
        ('preventive', 'Preventive'),
        ('restorative', 'Restorative'),
        ('endodontic', 'Endodontic'),
        ('periodontic', 'Periodontic'),
        ('oral_surgery', 'Oral Surgery'),
        ('prosthodontic', 'Prosthodontic'),
        ('orthodontic', 'Orthodontic'),
        ('cosmetic', 'Cosmetic'),
    ]
    
    code = models.CharField(max_length=50, unique=True, help_text="Procedure code (e.g., D0110)")
    name = models.CharField(max_length=200)
    procedure_type = models.CharField(max_length=30, choices=PROCEDURE_TYPES)
    description = models.TextField(blank=True)
    default_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='GHS')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['code']
        verbose_name = 'Dental Procedure Catalog'
        verbose_name_plural = 'Dental Procedure Catalog'
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class DentalChart(BaseModel):
    """Dental chart for a patient"""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='dental_charts')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='dental_charts', null=True, blank=True)
    chart_date = models.DateField(default=date.today)
    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-chart_date']
    
    def __str__(self):
        return f"Dental Chart - {self.patient.full_name} - {self.chart_date}"


class ToothCondition(BaseModel):
    """Condition/status of individual teeth"""
    CONDITION_TYPES = [
        ('healthy', 'Healthy'),
        ('carious', 'Carious'),
        ('filled', 'Filled'),
        ('missing', 'Missing'),
        ('crown', 'Crown'),
        ('bridge', 'Bridge'),
        ('implant', 'Implant'),
        ('root_canal', 'Root Canal Treated'),
        ('extraction_needed', 'Extraction Needed'),
        ('erupting', 'Erupting'),
        ('impacted', 'Impacted'),
        ('deciduous', 'Deciduous (Baby Tooth)'),
    ]
    
    dental_chart = models.ForeignKey(DentalChart, on_delete=models.CASCADE, related_name='tooth_conditions')
    tooth_number = models.CharField(max_length=10)  # FDI notation: 11-18, 21-28, 31-38, 41-48
    condition_type = models.CharField(max_length=30, choices=CONDITION_TYPES)
    surface = models.CharField(max_length=50, blank=True)  # O, M, D, B, L, etc.
    color_code = models.CharField(max_length=20, blank=True)  # For visual representation
    notes = models.TextField(blank=True)
    procedure_date = models.DateField(null=True, blank=True)
    
    class Meta:
        unique_together = ['dental_chart', 'tooth_number', 'surface']
        ordering = ['tooth_number']
    
    def __str__(self):
        return f"Tooth {self.tooth_number} - {self.get_condition_type_display()}"


class DentalProcedure(BaseModel):
    """Dental procedures/services"""
    PROCEDURE_TYPES = [
        ('diagnostic', 'Diagnostic'),
        ('preventive', 'Preventive'),
        ('restorative', 'Restorative'),
        ('endodontic', 'Endodontic'),
        ('periodontic', 'Periodontic'),
        ('oral_surgery', 'Oral Surgery'),
        ('prosthodontic', 'Prosthodontic'),
        ('orthodontic', 'Orthodontic'),
        ('cosmetic', 'Cosmetic'),
    ]
    
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    dental_chart = models.ForeignKey(DentalChart, on_delete=models.CASCADE, related_name='procedures')
    procedure_code = models.CharField(max_length=50)  # CDT codes or custom
    procedure_name = models.CharField(max_length=200)
    procedure_type = models.CharField(max_length=30, choices=PROCEDURE_TYPES)
    teeth = models.CharField(max_length=100)  # Comma-separated tooth numbers: "11,12,13"
    quantity = models.IntegerField(default=1)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    procedure_date = models.DateField(null=True, blank=True)
    performed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.procedure_name} - {self.dental_chart.patient.full_name}"


# ==================== CARDIOLOGY MODULE ====================

class CardiologyChart(BaseModel):
    """Cardiology-specific patient chart"""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='cardiology_charts')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='cardiology_charts', null=True, blank=True)
    chart_date = models.DateField(default=date.today)
    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    
    # Cardiac metrics
    blood_pressure = models.CharField(max_length=20, blank=True)  # e.g., "120/80"
    heart_rate = models.PositiveIntegerField(null=True, blank=True)
    ejection_fraction = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # %
    
    # History
    cardiac_history = models.TextField(blank=True)
    medications = models.TextField(blank=True)
    allergies = models.TextField(blank=True)
    
    # Findings
    ecg_findings = models.TextField(blank=True)
    echo_findings = models.TextField(blank=True)
    stress_test_results = models.TextField(blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-chart_date']
    
    def __str__(self):
        return f"Cardiology Chart - {self.patient.full_name} - {self.chart_date}"


# ==================== OPHTHALMOLOGY MODULE ====================

class OphthalmologyChart(BaseModel):
    """Ophthalmology/eye chart"""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='ophthalmology_charts')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='ophthalmology_charts', null=True, blank=True)
    chart_date = models.DateField(default=date.today)
    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    
    # Visual Acuity
    visual_acuity_re_right = models.CharField(max_length=20, blank=True)  # e.g., "20/20", "6/6"
    visual_acuity_re_left = models.CharField(max_length=20, blank=True)
    visual_acuity_le_right = models.CharField(max_length=20, blank=True)
    visual_acuity_le_left = models.CharField(max_length=20, blank=True)
    
    # Intraocular Pressure
    iop_right = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # mmHg
    iop_left = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Refraction
    refraction_right = models.CharField(max_length=100, blank=True)
    refraction_left = models.CharField(max_length=100, blank=True)
    
    # Diagnosis
    diagnosis = models.TextField(blank=True)
    treatment_plan = models.TextField(blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-chart_date']
    
    def __str__(self):
        return f"Eye Chart - {self.patient.full_name} - {self.chart_date}"


# ==================== SPECIALIST CONSULTATION ====================

class SpecialistConsultation(BaseModel):
    """Specialist consultation record"""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='specialist_consultations')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='specialist_consultations', null=True, blank=True)
    specialist = models.ForeignKey(SpecialistProfile, on_delete=models.PROTECT, related_name='consultations')
    consultation_date = models.DateTimeField(default=timezone.now)
    
    # Clinical information
    chief_complaint = models.TextField()
    history_of_present_illness = models.TextField(blank=True)
    review_of_systems = models.TextField(blank=True)
    examination_findings = models.TextField(blank=True)
    vitals = models.JSONField(default=dict, blank=True)  # Store vital signs as JSON
    assessment = models.TextField(blank=True)
    differential_diagnosis = models.TextField(blank=True)
    plan = models.TextField(blank=True)
    
    # Follow-up
    follow_up_date = models.DateField(null=True, blank=True)
    follow_up_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    # Related items
    orders = models.ManyToManyField(Order, related_name='specialist_consultations', blank=True)
    prescriptions = models.ManyToManyField('Prescription', related_name='specialist_consultations', blank=True)
    
    class Meta:
        ordering = ['-consultation_date']
    
    def __str__(self):
        return f"Consultation - {self.patient.full_name} - {self.specialist.specialty.name}"


# ==================== REFERRAL SYSTEM ====================

class Referral(BaseModel):
    """Referral from one doctor to a specialist"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('declined', 'Declined'),
    ]
    
    PRIORITY_CHOICES = [
        ('routine', 'Routine'),
        ('urgent', 'Urgent'),
        ('stat', 'STAT'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='referrals')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='referrals', null=True, blank=True)
    referring_doctor = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name='referrals_made')
    specialist = models.ForeignKey(SpecialistProfile, on_delete=models.PROTECT, related_name='referrals_received')
    specialty = models.ForeignKey(Specialty, on_delete=models.PROTECT, related_name='referrals')
    
    # Referral details
    reason = models.TextField(help_text="Reason for referral")
    clinical_summary = models.TextField(blank=True, help_text="Clinical summary and relevant findings")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='routine')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Dates
    referred_date = models.DateTimeField(default=timezone.now)
    appointment_date = models.DateTimeField(null=True, blank=True)
    consultation_date = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)
    
    # Specialist response
    specialist_notes = models.TextField(blank=True, help_text="Specialist's notes and response")
    declined_reason = models.TextField(blank=True, help_text="Reason if referral is declined")
    
    class Meta:
        ordering = ['-referred_date']
    
    def __str__(self):
        return f"Referral - {self.patient.full_name} to {self.specialist.staff.user.get_full_name()}"
    
    def accept(self, appointment_date=None, specialist_notes=''):
        """Accept the referral"""
        self.status = 'accepted'
        if appointment_date:
            self.appointment_date = appointment_date
        if specialist_notes:
            self.specialist_notes = specialist_notes
        self.save()
    
    def decline(self, reason=''):
        """Decline the referral"""
        self.status = 'declined'
        if reason:
            self.declined_reason = reason
        self.save()
    
    def complete(self, specialist_notes=''):
        """Mark referral as completed"""
        self.status = 'completed'
        self.completed_date = timezone.now()
        if specialist_notes:
            self.specialist_notes = specialist_notes
        self.save()
