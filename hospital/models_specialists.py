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


# ==================== PSYCHIATRY MODULE ====================

class PsychiatricChart(BaseModel):
    """Comprehensive psychiatric/mental health chart"""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='psychiatric_charts')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='psychiatric_charts', null=True, blank=True)
    chart_date = models.DateField(default=date.today)
    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    
    # Chief Complaint & Presenting Problem
    chief_complaint = models.TextField(blank=True)
    presenting_problem = models.TextField(blank=True)
    duration_of_symptoms = models.CharField(max_length=100, blank=True)
    
    # Mental Status Examination (MSE)
    appearance = models.TextField(blank=True, help_text="General appearance, grooming, dress")
    behavior = models.TextField(blank=True, help_text="Motor activity, eye contact, rapport")
    speech = models.TextField(blank=True, help_text="Rate, rhythm, volume, quality")
    mood = models.CharField(max_length=100, blank=True, help_text="Patient's subjective mood")
    affect = models.CharField(max_length=100, blank=True, help_text="Observed emotional expression")
    thought_process = models.TextField(blank=True, help_text="Form of thought, flow, organization")
    thought_content = models.TextField(blank=True, help_text="Delusions, obsessions, suicidal/homicidal ideation")
    perception = models.TextField(blank=True, help_text="Hallucinations, illusions, depersonalization")
    cognition = models.TextField(blank=True, help_text="Orientation, memory, attention, concentration")
    insight = models.CharField(max_length=50, blank=True, choices=[
        ('poor', 'Poor'),
        ('fair', 'Fair'),
        ('good', 'Good'),
        ('excellent', 'Excellent'),
    ])
    judgment = models.CharField(max_length=50, blank=True, choices=[
        ('poor', 'Poor'),
        ('fair', 'Fair'),
        ('good', 'Good'),
        ('excellent', 'Excellent'),
    ])
    
    # Standardized Assessment Scales (0-27 for PHQ-9, 0-21 for GAD-7)
    phq9_score = models.IntegerField(null=True, blank=True, help_text="PHQ-9 Depression Scale (0-27)")
    gad7_score = models.IntegerField(null=True, blank=True, help_text="GAD-7 Anxiety Scale (0-21)")
    pcl5_score = models.IntegerField(null=True, blank=True, help_text="PCL-5 PTSD Scale (0-80)")
    mmse_score = models.IntegerField(null=True, blank=True, help_text="MMSE Cognitive Assessment (0-30)")
    ybocs_score = models.IntegerField(null=True, blank=True, help_text="Y-BOCS OCD Scale (0-40)")
    
    # Risk Assessment
    suicide_risk = models.CharField(max_length=20, blank=True, choices=[
        ('none', 'None'),
        ('low', 'Low'),
        ('moderate', 'Moderate'),
        ('high', 'High'),
        ('imminent', 'Imminent'),
    ])
    suicide_ideation = models.TextField(blank=True)
    suicide_plan = models.TextField(blank=True)
    suicide_means = models.TextField(blank=True)
    homicide_risk = models.CharField(max_length=20, blank=True, choices=[
        ('none', 'None'),
        ('low', 'Low'),
        ('moderate', 'Moderate'),
        ('high', 'High'),
    ])
    violence_risk = models.CharField(max_length=20, blank=True, choices=[
        ('none', 'None'),
        ('low', 'Low'),
        ('moderate', 'Moderate'),
        ('high', 'High'),
    ])
    self_harm_risk = models.CharField(max_length=20, blank=True, choices=[
        ('none', 'None'),
        ('low', 'Low'),
        ('moderate', 'Moderate'),
        ('high', 'High'),
    ])
    
    # Psychiatric History
    psychiatric_history = models.TextField(blank=True)
    previous_diagnoses = models.TextField(blank=True)
    previous_treatments = models.TextField(blank=True)
    hospitalizations = models.TextField(blank=True)
    family_psychiatric_history = models.TextField(blank=True)
    substance_use_history = models.TextField(blank=True)
    
    # Current Medications
    current_medications = models.TextField(blank=True)
    medication_compliance = models.CharField(max_length=50, blank=True, choices=[
        ('compliant', 'Compliant'),
        ('partial', 'Partially Compliant'),
        ('non_compliant', 'Non-Compliant'),
    ])
    medication_side_effects = models.TextField(blank=True)
    
    # Social History
    living_situation = models.TextField(blank=True)
    occupation = models.CharField(max_length=200, blank=True)
    education = models.CharField(max_length=200, blank=True)
    social_support = models.TextField(blank=True)
    stressors = models.TextField(blank=True)
    coping_mechanisms = models.TextField(blank=True)
    
    # Diagnosis (ICD-10/DSM-5)
    primary_diagnosis = models.CharField(max_length=200, blank=True)
    secondary_diagnosis = models.CharField(max_length=200, blank=True)
    provisional_diagnosis = models.CharField(max_length=200, blank=True)
    differential_diagnosis = models.TextField(blank=True)
    
    # Treatment Plan
    treatment_plan = models.TextField(blank=True)
    psychotherapy_plan = models.TextField(blank=True)
    medication_plan = models.TextField(blank=True)
    behavioral_interventions = models.TextField(blank=True)
    goals = models.TextField(blank=True)
    
    # Progress & Follow-up
    progress_notes = models.TextField(blank=True)
    response_to_treatment = models.CharField(max_length=50, blank=True, choices=[
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('worsening', 'Worsening'),
    ])
    follow_up_date = models.DateField(null=True, blank=True)
    follow_up_instructions = models.TextField(blank=True)
    
    # Additional Notes
    notes = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-chart_date']
    
    def __str__(self):
        return f"Psychiatric Chart - {self.patient.full_name} - {self.chart_date}"
    
    def get_depression_severity(self):
        """Get PHQ-9 depression severity"""
        if not self.phq9_score:
            return None
        if self.phq9_score <= 4:
            return 'Minimal'
        elif self.phq9_score <= 9:
            return 'Mild'
        elif self.phq9_score <= 14:
            return 'Moderate'
        elif self.phq9_score <= 19:
            return 'Moderately Severe'
        else:
            return 'Severe'
    
    def get_anxiety_severity(self):
        """Get GAD-7 anxiety severity"""
        if not self.gad7_score:
            return None
        if self.gad7_score <= 4:
            return 'Minimal'
        elif self.gad7_score <= 9:
            return 'Mild'
        elif self.gad7_score <= 14:
            return 'Moderate'
        else:
            return 'Severe'


# ==================== GYNECOLOGY MODULE ====================

class GynecologyChart(BaseModel):
    """Comprehensive gynecology/obstetrics chart"""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='gynecology_charts')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='gynecology_charts', null=True, blank=True)
    chart_date = models.DateField(default=date.today)
    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    
    # Chief Complaint & History
    chief_complaint = models.TextField(blank=True)
    presenting_problem = models.TextField(blank=True)
    menstrual_history = models.TextField(blank=True, help_text="Menstrual cycle details, LMP, regularity")
    obstetric_history = models.TextField(blank=True, help_text="Gravida, Para, abortions, deliveries")
    gynecological_history = models.TextField(blank=True, help_text="Previous gynecological conditions, surgeries")
    contraceptive_history = models.TextField(blank=True, help_text="Current and past contraceptive methods")
    sexual_history = models.TextField(blank=True, help_text="Sexually active, partners, STI history")
    
    # Current Pregnancy (if applicable)
    is_pregnant = models.BooleanField(default=False)
    gestational_age_weeks = models.IntegerField(null=True, blank=True)
    edd = models.DateField(null=True, blank=True, help_text="Expected Due Date")
    pregnancy_complications = models.TextField(blank=True)
    prenatal_care = models.TextField(blank=True)
    
    # Physical Examination
    general_examination = models.TextField(blank=True)
    abdominal_examination = models.TextField(blank=True)
    pelvic_examination = models.TextField(blank=True, help_text="Inspection, speculum, bimanual findings")
    breast_examination = models.TextField(blank=True)
    cervical_examination = models.TextField(blank=True, help_text="Cervix appearance, discharge, lesions")
    
    # Vital Signs
    blood_pressure = models.CharField(max_length=20, blank=True)
    pulse = models.PositiveIntegerField(null=True, blank=True)
    temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    weight = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="kg")
    height = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="cm")
    bmi = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Investigations
    pap_smear_result = models.CharField(max_length=100, blank=True)
    pap_smear_date = models.DateField(null=True, blank=True)
    hiv_status = models.CharField(max_length=50, blank=True, choices=[
        ('negative', 'Negative'),
        ('positive', 'Positive'),
        ('not_tested', 'Not Tested'),
        ('declined', 'Declined'),
    ])
    hiv_test_date = models.DateField(null=True, blank=True)
    other_investigations = models.TextField(blank=True, help_text="Ultrasound, lab tests, etc.")
    
    # Diagnosis
    primary_diagnosis = models.CharField(max_length=200, blank=True)
    secondary_diagnosis = models.CharField(max_length=200, blank=True)
    provisional_diagnosis = models.CharField(max_length=200, blank=True)
    differential_diagnosis = models.TextField(blank=True)
    
    # Treatment Plan
    treatment_plan = models.TextField(blank=True)
    medications_prescribed = models.TextField(blank=True)
    procedures_planned = models.TextField(blank=True)
    lifestyle_advice = models.TextField(blank=True)
    
    # Follow-up
    follow_up_date = models.DateField(null=True, blank=True)
    follow_up_instructions = models.TextField(blank=True)
    progress_notes = models.TextField(blank=True)
    
    # Additional Notes
    notes = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-chart_date']
    
    def __str__(self):
        return f"Gynecology Chart - {self.patient.full_name} - {self.chart_date}"


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
