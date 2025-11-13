"""
Advanced Hospital Management System Models
Extends base models with comprehensive clinical and operational features
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from model_utils.models import TimeStampedModel
from .models import BaseModel, Patient, Encounter, Staff, Department, Ward, Bed, Order, Drug, Prescription, Payer, ServiceCode, InvoiceLine


# ==================== CLINICAL NOTES & CARE PLANS ====================

class ClinicalNote(BaseModel):
    """Clinical documentation/notes"""
    NOTE_TYPES = [
        ('soap', 'SOAP Note'),
        ('progress', 'Progress Note'),
        ('consultation', 'Consultation Note'),
        ('discharge', 'Discharge Summary'),
        ('procedure', 'Procedure Note'),
        ('operation', 'Operation Note'),
    ]
    
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='clinical_notes')
    note_type = models.CharField(max_length=20, choices=NOTE_TYPES)
    subjective = models.TextField(blank=True)  # S in SOAP
    objective = models.TextField(blank=True)   # O in SOAP
    assessment = models.TextField(blank=True)  # A in SOAP
    plan = models.TextField(blank=True)        # P in SOAP
    notes = models.TextField()
    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='clinical_notes')
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.get_note_type_display()} - {self.encounter.patient.full_name}"
    
    def save(self, *args, **kwargs):
        """Auto-add consultation charge when consultation note is saved"""
        is_new = self.pk is None
        
        # Determine if this is a consultation note (first time)
        if is_new and self.note_type == 'consultation':
            # Add consultation charge automatically
            from .utils_billing import add_consultation_charge
            # Determine if specialist consultation (based on department or doctor profession)
            consultation_type = 'general'
            if self.created_by:
                # Check if specialist department
                if hasattr(self.created_by, 'department') and self.created_by.department:
                    dept_name = self.created_by.department.name.lower()
                    if any(keyword in dept_name for keyword in ['specialist', 'cardio', 'dental', 'ortho', 'neuro', 'ophthal']):
                        consultation_type = 'specialist'
                # Check profession
                elif self.created_by.profession in ['specialist']:
                    consultation_type = 'specialist'
            
            try:
                add_consultation_charge(self.encounter, consultation_type)
            except Exception:
                pass  # Don't break note saving if billing fails
        
        super().save(*args, **kwargs)


class CarePlan(BaseModel):
    """Patient care plans"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='care_plans')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='care_plans', null=True, blank=True)
    diagnosis = models.CharField(max_length=200)
    goals = models.TextField()
    interventions = models.TextField()
    expected_outcomes = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"Care Plan - {self.patient.full_name} - {self.diagnosis}"


class ProblemList(BaseModel):
    """Patient problem list (active problems, diagnoses)"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('resolved', 'Resolved'),
        ('chronic', 'Chronic'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='problems')
    encounter = models.ForeignKey(Encounter, on_delete=models.SET_NULL, null=True, blank=True, related_name='problems')
    icd10_code = models.CharField(max_length=20, blank=True)  # ICD-10 diagnosis code
    problem = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    onset_date = models.DateField(null=True, blank=True)
    resolved_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.problem} - {self.patient.full_name}"


class Diagnosis(BaseModel):
    """Patient diagnoses"""
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='diagnoses')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='diagnoses')
    icd10_code = models.CharField(max_length=20, blank=True)
    diagnosis = models.CharField(max_length=200)
    diagnosis_type = models.CharField(max_length=50, default='primary')  # primary, secondary, differential
    description = models.TextField(blank=True)
    diagnosed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    diagnosis_date = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-diagnosis_date']
        verbose_name_plural = 'Diagnoses'
    
    def __str__(self):
        return f"{self.diagnosis} - {self.patient.full_name}"


class Procedure(BaseModel):
    """Medical procedures performed"""
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='procedures')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='procedures')
    procedure_code = models.CharField(max_length=50, blank=True)
    procedure_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    performed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='procedures_performed')
    procedure_date = models.DateTimeField(default=timezone.now)
    location = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-procedure_date']
    
    def __str__(self):
        return f"{self.procedure_name} - {self.patient.full_name}"


class Allergy(BaseModel):
    """Patient allergies"""
    SEVERITY_CHOICES = [
        ('mild', 'Mild'),
        ('moderate', 'Moderate'),
        ('severe', 'Severe'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='allergy_records')
    allergen = models.CharField(max_length=200)
    allergy_type = models.CharField(max_length=50, default='drug')  # drug, food, environmental
    reaction = models.TextField(blank=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='moderate')
    onset_date = models.DateField(null=True, blank=True)
    recorded_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['patient', '-severity']
        verbose_name_plural = 'Allergies'
    
    def __str__(self):
        return f"{self.allergen} - {self.patient.full_name}"


# ==================== SCHEDULING & QUEUES ====================

class ProviderSchedule(BaseModel):
    """Provider/doctor schedules and availability"""
    provider = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='schedules')
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_available = models.BooleanField(default=True)
    session_type = models.CharField(max_length=50, default='clinic')  # clinic, theatre, ward_rounds
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['date', 'start_time']
        unique_together = ['provider', 'date', 'start_time']
    
    def __str__(self):
        return f"{self.provider.user.get_full_name()} - {self.date} {self.start_time}"


class Queue(BaseModel):
    """Patient queue management"""
    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
    ]
    
    PRIORITY_CHOICES = [
        ('normal', 'Normal'),
        ('urgent', 'Urgent'),
        ('stat', 'STAT'),
    ]
    
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='queues')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='queues')
    location = models.CharField(max_length=100)  # clinic, ward, theatre, etc.
    queue_number = models.IntegerField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    checked_in_at = models.DateTimeField(default=timezone.now)
    called_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    estimated_wait_time = models.IntegerField(null=True, blank=True)  # in minutes
    
    class Meta:
        ordering = ['priority', 'queue_number']
    
    def __str__(self):
        return f"Queue #{self.queue_number} - {self.encounter.patient.full_name}"


class Triage(BaseModel):
    """ER/Urgent Care triage"""
    TRIAGE_SCALES = [
        ('esi_1', 'ESI Level 1 - Resuscitation'),
        ('esi_2', 'ESI Level 2 - Emergent'),
        ('esi_3', 'ESI Level 3 - Urgent'),
        ('esi_4', 'ESI Level 4 - Less Urgent'),
        ('esi_5', 'ESI Level 5 - Non Urgent'),
        ('mts_red', 'MTS Red - Immediate'),
        ('mts_orange', 'MTS Orange - Very Urgent'),
        ('mts_yellow', 'MTS Yellow - Urgent'),
        ('mts_green', 'MTS Green - Standard'),
        ('mts_blue', 'MTS Blue - Non Urgent'),
    ]
    
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='triage')
    triage_level = models.CharField(max_length=20, choices=TRIAGE_SCALES)
    chief_complaint = models.TextField()
    vital_signs = models.JSONField(default=dict, blank=True)  # Store vitals
    pain_scale = models.IntegerField(null=True, blank=True)  # 0-10
    triaged_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    triage_time = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['triage_time']
    
    def __str__(self):
        return f"Triage {self.get_triage_level_display()} - {self.encounter.patient.full_name}"


# ==================== IMAGING/RADIOLOGY ====================

class ImagingStudy(BaseModel):
    """World-Class Imaging/Radiology System with Advanced Features"""
    MODALITY_CHOICES = [
        ('xray', 'X-Ray'),
        ('ct', 'CT Scan'),
        ('mri', 'MRI'),
        ('ultrasound', 'Ultrasound'),
        ('mammography', 'Mammography'),
        ('fluoroscopy', 'Fluoroscopy'),
        ('nuclear', 'Nuclear Medicine'),
        ('pet', 'PET Scan'),
        ('dexa', 'DEXA Scan'),
    ]
    
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('arrived', 'Patient Arrived'),
        ('in_progress', 'Scan In Progress'),
        ('completed', 'Scan Completed'),
        ('quality_check', 'Quality Check'),
        ('awaiting_report', 'Awaiting Report'),
        ('reporting', 'Being Reported'),
        ('reported', 'Report Complete'),
        ('verified', 'Report Verified'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('routine', 'Routine'),
        ('urgent', 'Urgent'),
        ('stat', 'STAT'),
    ]
    
    QUALITY_CHOICES = [
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('adequate', 'Adequate'),
        ('poor', 'Poor'),
        ('unacceptable', 'Unacceptable'),
    ]
    
    # Core Fields
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='imaging_studies')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='imaging_studies')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='imaging_studies', null=True, blank=True)
    modality = models.CharField(max_length=20, choices=MODALITY_CHOICES)
    body_part = models.CharField(max_length=100)
    study_type = models.CharField(max_length=100)
    
    # Scheduling & Timing
    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True, help_text='When study acquisition started')
    performed_at = models.DateTimeField(null=True, blank=True)
    
    # Status & Priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='routine')
    
    # Staff Assignment
    technician = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='performed_studies', help_text='Technician who performed the study')
    assigned_radiologist = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name='assigned_studies', help_text='Radiologist assigned to read this study')
    
    # Technical Details
    dicom_uid = models.CharField(max_length=200, blank=True)  # DICOM Study UID
    pacs_id = models.CharField(max_length=100, blank=True)  # PACS system reference
    clinical_indication = models.TextField(blank=True)
    
    # Quality Control
    image_quality = models.CharField(max_length=20, choices=QUALITY_CHOICES, blank=True)
    quality_notes = models.TextField(blank=True, help_text='Notes about image quality')
    rejection_reason = models.TextField(blank=True, help_text='Reason if study was rejected')
    repeat_reason = models.TextField(blank=True, help_text='Reason if study needed to be repeated')
    
    # Reporting
    report_started_at = models.DateTimeField(null=True, blank=True, help_text='When reporting started')
    report_text = models.TextField(blank=True)
    findings = models.TextField(blank=True)
    impression = models.TextField(blank=True)
    measurements = models.TextField(blank=True, help_text='Key measurements from the study')
    report_dictated_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='dictated_reports')
    report_verified_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_reports')
    report_verified_at = models.DateTimeField(null=True, blank=True)
    turnaround_time_minutes = models.IntegerField(null=True, blank=True, help_text='Time from completion to report')
    
    # Critical Findings
    has_critical_findings = models.BooleanField(default=False, help_text='Flag for critical/urgent findings')
    critical_findings = models.TextField(blank=True, help_text='Description of critical findings')
    referring_physician_notified = models.BooleanField(default=False, help_text='Referring physician notified of critical findings')
    notification_time = models.DateTimeField(null=True, blank=True)
    
    # Comparison with Prior Studies
    compared_with_prior = models.BooleanField(default=False, help_text='Compared with prior studies')
    prior_study_date = models.DateField(null=True, blank=True)
    
    # Contrast Usage
    contrast_used = models.BooleanField(default=False)
    contrast_type = models.CharField(max_length=100, blank=True)
    contrast_volume = models.CharField(max_length=50, blank=True)
    
    # Payment Tracking
    is_paid = models.BooleanField(default=False, help_text='Whether payment has been received')
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_receipt_number = models.CharField(max_length=50, blank=True, help_text='Receipt number for payment')
    
    class Meta:
        ordering = ['-scheduled_at', '-created']
        verbose_name_plural = 'Imaging Studies'
    
    def __str__(self):
        return f"{self.get_modality_display()} - {self.patient.full_name} - {self.body_part}"
    
    @property
    def is_stat(self):
        """Check if this is a STAT (urgent) order"""
        return self.priority == 'stat'
    
    @property
    def needs_payment(self):
        """Check if payment is still needed"""
        return not self.is_paid
    
    def mark_as_paid(self, amount, receipt_number=''):
        """Mark study as paid"""
        from django.utils import timezone
        self.is_paid = True
        self.paid_amount = amount
        self.paid_at = timezone.now()
        if receipt_number:
            self.payment_receipt_number = receipt_number
        self.save()
    
    def calculate_turnaround_time(self):
        """Calculate turnaround time from completion to report"""
        if self.performed_at and self.report_verified_at:
            delta = self.report_verified_at - self.performed_at
            self.turnaround_time_minutes = int(delta.total_seconds() / 60)
            self.save(update_fields=['turnaround_time_minutes'])
        return self.turnaround_time_minutes


class ImagingImage(BaseModel):
    """Images associated with imaging studies"""
    imaging_study = models.ForeignKey(ImagingStudy, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='imaging_studies/%Y/%m/%d/', help_text='Upload medical imaging picture')
    description = models.CharField(max_length=200, blank=True, help_text='Brief description of this image')
    sequence_number = models.PositiveIntegerField(default=1, help_text='Order/sequence of this image in the study')
    uploaded_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_images')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['imaging_study', 'sequence_number', 'uploaded_at']
        unique_together = ['imaging_study', 'sequence_number']
        verbose_name_plural = 'Imaging Images'
    
    def __str__(self):
        return f"Image {self.sequence_number} - {self.imaging_study}"


# ==================== THEATRE/PROCEDURES ====================

class TheatreSchedule(BaseModel):
    """Operating theatre schedules"""
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='theatre_schedules')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='theatre_schedules')
    theatre_name = models.CharField(max_length=100)
    procedure = models.CharField(max_length=200)
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    surgeon = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name='surgeries')
    anaesthetist = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='anaesthetics')
    scrub_nurse = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='scrub_nurse_duties')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['scheduled_start']
    
    def __str__(self):
        return f"{self.procedure} - {self.patient.full_name} - {self.scheduled_start}"


class SurgicalChecklist(BaseModel):
    """Pre-operative surgical safety checklist"""
    theatre_schedule = models.OneToOneField(TheatreSchedule, on_delete=models.CASCADE, related_name='checklist')
    pre_op_checks = models.JSONField(default=dict)  # Before induction
    pre_incision_checks = models.JSONField(default=dict)  # Before incision
    pre_signout_checks = models.JSONField(default=dict)  # Before patient leaves
    completed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Checklist - {self.theatre_schedule.patient.full_name}"


class AnaesthesiaRecord(BaseModel):
    """Anaesthesia records"""
    theatre_schedule = models.ForeignKey(TheatreSchedule, on_delete=models.CASCADE, related_name='anaesthesia_records')
    anaesthetist = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    anaesthesia_type = models.CharField(max_length=50)  # General, Regional, Local, etc.
    medications = models.JSONField(default=dict)
    vital_signs = models.JSONField(default=dict)
    complications = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"Anaesthesia - {self.theatre_schedule.patient.full_name}"


# ==================== NURSING WORKFLOWS ====================

class MedicationAdministrationRecord(BaseModel):
    """MAR - Medication Administration Record"""
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('given', 'Given'),
        ('missed', 'Missed'),
        ('refused', 'Refused'),
        ('held', 'Held'),
    ]
    
    prescription = models.ForeignKey('Prescription', on_delete=models.CASCADE, related_name='mar_entries')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='mar_entries')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='mar_entries')
    scheduled_time = models.DateTimeField()
    administered_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    administered_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    dose_given = models.CharField(max_length=50, blank=True)
    route = models.CharField(max_length=50, blank=True)
    site = models.CharField(max_length=50, blank=True)  # For injections
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['scheduled_time']
    
    def __str__(self):
        return f"MAR - {self.patient.full_name} - {self.scheduled_time}"


class HandoverSheet(BaseModel):
    """Nursing handover sheets"""
    shift_type = models.CharField(max_length=20)  # day, night, evening
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name='handovers')
    date = models.DateField()
    shift_start = models.DateTimeField()
    shift_end = models.DateTimeField()
    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    handover_notes = models.TextField()
    critical_patients = models.JSONField(default=list)
    tasks = models.JSONField(default=list)
    
    class Meta:
        ordering = ['-date', '-shift_start']
    
    def __str__(self):
        return f"Handover - {self.ward.name} - {self.date} {self.shift_type}"


class FallRiskAssessment(BaseModel):
    """Fall risk assessment tool"""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='fall_risk_assessments')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='fall_risk_assessments', null=True, blank=True)
    assessment_date = models.DateTimeField(default=timezone.now)
    assessed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    risk_score = models.IntegerField()  # Total score
    risk_level = models.CharField(max_length=20)  # low, moderate, high
    factors = models.JSONField(default=dict)  # Risk factors and scores
    interventions = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-assessment_date']
    
    def __str__(self):
        return f"Fall Risk - {self.patient.full_name} - {self.risk_level}"


class PressureUlcerRiskAssessment(BaseModel):
    """Pressure ulcer risk assessment (Braden Scale, etc.)"""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='pressure_ulcer_assessments')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='pressure_ulcer_assessments', null=True, blank=True)
    assessment_date = models.DateTimeField(default=timezone.now)
    assessed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    risk_score = models.IntegerField()
    risk_level = models.CharField(max_length=20)
    factors = models.JSONField(default=dict)
    interventions = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-assessment_date']
    
    def __str__(self):
        return f"PU Risk - {self.patient.full_name} - {self.risk_level}"


# ==================== ER WORKFLOWS ====================

class CrashCartCheck(BaseModel):
    """Emergency crash cart checks"""
    location = models.CharField(max_length=100)  # ER, ICU, Ward name
    checked_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    check_date = models.DateTimeField(default=timezone.now)
    items_checked = models.JSONField(default=dict)  # Item: status
    missing_items = models.JSONField(default=list)
    expiry_items = models.JSONField(default=list)
    status = models.CharField(max_length=20, default='complete')  # complete, incomplete
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-check_date']
    
    def __str__(self):
        return f"Crash Cart Check - {self.location} - {self.check_date}"


class IncidentLog(BaseModel):
    """Incident/accident reporting"""
    SEVERITY_CHOICES = [
        ('minor', 'Minor'),
        ('moderate', 'Moderate'),
        ('major', 'Major'),
        ('critical', 'Critical'),
    ]
    
    TYPE_CHOICES = [
        ('patient_fall', 'Patient Fall'),
        ('medication_error', 'Medication Error'),
        ('equipment_failure', 'Equipment Failure'),
        ('security', 'Security Incident'),
        ('infection', 'Infection Control'),
        ('other', 'Other'),
    ]
    
    incident_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    location = models.CharField(max_length=100)
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True, related_name='incidents')
    staff = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='reported_incidents')
    incident_date = models.DateTimeField(default=timezone.now)
    reported_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name='incidents_reported')
    description = models.TextField()
    immediate_action = models.TextField(blank=True)
    follow_up = models.TextField(blank=True)
    status = models.CharField(max_length=20, default='reported')  # reported, investigating, resolved
    
    class Meta:
        ordering = ['-incident_date']
    
    def __str__(self):
        return f"{self.get_incident_type_display()} - {self.location} - {self.incident_date}"


# ==================== MATERIALS & ASSETS ====================

class MedicalEquipment(BaseModel):
    """Medical equipment registry"""
    EQUIPMENT_TYPES = [
        ('monitor', 'Patient Monitor'),
        ('ventilator', 'Ventilator'),
        ('defibrillator', 'Defibrillator'),
        ('infusion_pump', 'Infusion Pump'),
        ('xray', 'X-Ray Machine'),
        ('ultrasound', 'Ultrasound Machine'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('in_use', 'In Use'),
        ('maintenance', 'Under Maintenance'),
        ('out_of_order', 'Out of Order'),
    ]
    
    equipment_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    equipment_type = models.CharField(max_length=20, choices=EQUIPMENT_TYPES)
    manufacturer = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=100)  # Ward, department
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    purchase_date = models.DateField(null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True)
    last_maintenance = models.DateField(null=True, blank=True)
    next_maintenance_due = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.equipment_code})"


class MaintenanceLog(BaseModel):
    """Equipment maintenance records"""
    equipment = models.ForeignKey(MedicalEquipment, on_delete=models.CASCADE, related_name='maintenance_logs')
    maintenance_type = models.CharField(max_length=50)  # preventive, corrective, calibration
    service_date = models.DateField()
    service_provider = models.CharField(max_length=100, blank=True)
    technician = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField()
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    next_service_due = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['-service_date']
    
    def __str__(self):
        return f"{self.equipment.name} - {self.maintenance_type} - {self.service_date}"


class ConsumablesInventory(BaseModel):
    """Consumables inventory management"""
    item_code = models.CharField(max_length=50)
    item_name = models.CharField(max_length=200)
    category = models.CharField(max_length=50)  # gloves, syringes, dressings, etc.
    location = models.CharField(max_length=100)  # store, ward, department
    unit = models.CharField(max_length=20)  # box, pack, unit
    quantity_on_hand = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reorder_level = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    class Meta:
        unique_together = ['item_code', 'location']
        ordering = ['item_name']
    
    def __str__(self):
        return f"{self.item_name} - {self.location} ({self.quantity_on_hand} {self.unit})"
    
    @property
    def is_low_stock(self):
        return self.quantity_on_hand <= self.reorder_level


# ==================== HR & ROSTERS ====================

class DutyRoster(BaseModel):
    """Staff duty rosters/shifts"""
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='rosters')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='rosters')
    shift_date = models.DateField()
    shift_type = models.CharField(max_length=20)  # morning, afternoon, night, on_call
    start_time = models.TimeField()
    end_time = models.TimeField()
    location = models.CharField(max_length=100, blank=True)  # ward, clinic, etc.
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['shift_date', 'start_time']
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.shift_date} {self.get_shift_type_display()}"


class LeaveRequest(BaseModel):
    """Staff leave management with enhanced workflow"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    
    LEAVE_TYPES = [
        ('annual', 'Annual Leave'),
        ('sick', 'Sick Leave'),
        ('maternity', 'Maternity Leave'),
        ('paternity', 'Paternity Leave'),
        ('emergency', 'Emergency Leave'),
        ('study', 'Study Leave'),
        ('bereavement', 'Bereavement Leave'),
        ('compensatory', 'Compensatory Leave'),
        ('unpaid', 'Unpaid Leave'),
    ]
    
    request_number = models.CharField(max_length=50, unique=True, blank=True)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    days_requested = models.DecimalField(max_digits=5, decimal_places=1, default=1)  # Support half days
    reason = models.TextField(blank=True)
    contact_during_leave = models.CharField(max_length=200, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    submitted_at = models.DateTimeField(null=True, blank=True)
    
    # Approval tracking
    approved_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Coverage
    covering_staff = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='covering_for')
    handover_notes = models.TextField(blank=True)
    
    # Attachments (for sick leave, etc.)
    attachment = models.FileField(upload_to='leave_attachments/', null=True, blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.request_number or 'DRAFT'} - {self.staff.user.get_full_name()} - {self.get_leave_type_display()}"
    
    def save(self, *args, **kwargs):
        if not self.request_number and self.status != 'draft':
            self.request_number = self.generate_request_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_request_number():
        """Generate unique leave request number"""
        from datetime import datetime
        prefix = "LVE"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{prefix}{timestamp}"
    
    @staticmethod
    def calculate_working_days(start_date, end_date):
        """Calculate working days between two dates (excluding weekends)"""
        from datetime import timedelta
        
        if start_date > end_date:
            return 0
        
        working_days = 0
        current_date = start_date
        
        while current_date <= end_date:
            # Monday = 0, Sunday = 6
            # Count only Monday-Friday (0-4)
            if current_date.weekday() < 5:
                working_days += 1
            current_date += timedelta(days=1)
        
        return working_days
    
    @staticmethod
    def get_next_working_day(date):
        """Get the next working day after a given date (excluding weekends)"""
        from datetime import timedelta
        
        next_day = date + timedelta(days=1)
        
        # If next day is Saturday (5) or Sunday (6), move to Monday
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        
        return next_day
    
    @property
    def total_days(self):
        """Calculate total days including weekends"""
        if self.start_date and self.end_date:
            delta = self.end_date - self.start_date
            return delta.days + 1
        return 0
    
    @property
    def working_days(self):
        """Calculate working days (excluding weekends)"""
        if self.start_date and self.end_date:
            return self.calculate_working_days(self.start_date, self.end_date)
        return 0
    
    @property
    def return_date(self):
        """Calculate return date (next working day after leave ends)"""
        if self.end_date:
            return self.get_next_working_day(self.end_date)
        return None
    
    def send_approval_sms(self):
        """Send SMS to staff when leave is approved with return date"""
        try:
            from .services.sms_service import send_sms
            
            # Get staff phone number
            staff_phone = self.staff.phone_number or self.staff.user.username
            
            # Format dates
            start = self.start_date.strftime('%a, %b %d, %Y')
            end = self.end_date.strftime('%a, %b %d, %Y')
            return_date_obj = self.return_date
            return_str = return_date_obj.strftime('%a, %b %d, %Y') if return_date_obj else 'TBD'
            
            # Get working days
            working_days = self.working_days
            staff_name = self.staff.user.get_full_name()
            
            # Craft message for staff
            staff_message = (
                f"Your {self.get_leave_type_display()} has been APPROVED!\n"
                f"From: {start}\n"
                f"To: {end}\n"
                f"Working days: {working_days} (weekends excluded)\n"
                f"Report back on: {return_str}\n"
                f"Enjoy your leave!"
            )
            
            # Craft message for admin
            admin_message = (
                f"LEAVE APPROVED - {staff_name}\n"
                f"Type: {self.get_leave_type_display()}\n"
                f"From: {start}\n"
                f"To: {end}\n"
                f"Working days: {working_days}\n"
                f"Return: {return_str}\n"
                f"Request: {self.request_number}"
            )
            
            # Send SMS to staff
            staff_result = send_sms(staff_phone, staff_message)
            
            # Send confirmation SMS to admin
            admin_phone = "0247904675"  # Admin number
            admin_result = send_sms(admin_phone, admin_message)
            
            return staff_result.get('success', False)
        except Exception as e:
            print(f"Failed to send leave approval SMS: {e}")
            return False
    
    def submit(self):
        """Submit leave request for approval and notify manager"""
        if self.status == 'draft':
            self.status = 'pending'
            self.submitted_at = timezone.now()
            if not self.request_number:
                self.request_number = self.generate_request_number()
            self.save()
            
            # Send SMS notification to manager
            try:
                from ..services.sms_service import sms_service
                sms_service.send_leave_submitted(self)
            except Exception as e:
                # Log error but don't fail the submission
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send leave submission SMS to manager: {str(e)}")
            
            return True
        return False
    
    def approve(self, approver_staff, comments=''):
        """Approve leave request and send SMS notification"""
        from .models_hr import LeaveBalance
        import logging
        logger = logging.getLogger(__name__)
        
        # Allow approval from pending or draft status
        if self.status in ['pending', 'draft']:
            logger.info(f"Approving leave request {self.pk} for {self.staff.user.username}")
            
            self.status = 'approved'
            self.approved_by = approver_staff
            self.approved_at = timezone.now()
            
            # Generate request number if not exists
            if not self.request_number:
                self.request_number = self.generate_request_number()
            
            self.save()
            logger.info(f"Leave request {self.pk} status updated to approved")
            
            # Deduct from leave balance
            try:
                from decimal import Decimal
                balance = LeaveBalance.objects.get(staff=self.staff)
                days_decimal = Decimal(str(self.days_requested)) if self.days_requested else Decimal('0')
                
                if self.leave_type == 'annual':
                    balance.annual_leave -= days_decimal
                elif self.leave_type == 'sick':
                    balance.sick_leave -= days_decimal
                elif self.leave_type == 'casual':
                    balance.casual_leave -= days_decimal
                balance.save()
                logger.info(f"Leave balance deducted for {self.staff.user.username}")
            except LeaveBalance.DoesNotExist:
                logger.warning(f"No leave balance found for {self.staff.user.username}")
            
            # Send SMS notification
            try:
                from ..services.sms_service import sms_service
                sms_service.send_leave_approved(self)
                logger.info(f"SMS notification sent for leave approval")
            except Exception as e:
                logger.error(f"Failed to send leave approval SMS: {str(e)}")
            
            return True
        else:
            logger.warning(f"Cannot approve leave request {self.pk} with status {self.status}")
        return False
    
    def reject(self, approver_staff, reason):
        """Reject leave request and send SMS notification"""
        if self.status == 'pending':
            self.status = 'rejected'
            self.approved_by = approver_staff
            self.approved_at = timezone.now()
            self.rejection_reason = reason
            self.save()
            
            # Send SMS notification
            try:
                from ..services.sms_service import sms_service
                sms_service.send_leave_rejected(self)
            except Exception as e:
                # Log error but don't fail the rejection
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send leave rejection SMS: {str(e)}")
            
            return True
        return False


class Attendance(BaseModel):
    """Staff attendance tracking"""
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='attendance')
    date = models.DateField()
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default='present')  # present, absent, late, on_leave
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['staff', 'date']
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.date} - {self.status}"


# ==================== ENHANCED BILLING ====================

class InsurancePreAuthorization(BaseModel):
    """Insurance pre-authorization requests"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('partial', 'Partially Approved'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='pre_authorizations')
    payer = models.ForeignKey('Payer', on_delete=models.CASCADE, related_name='pre_authorizations')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='pre_authorizations', null=True, blank=True)
    auth_number = models.CharField(max_length=50, blank=True)  # Authorization number from payer
    requested_amount = models.DecimalField(max_digits=10, decimal_places=2)
    approved_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    requested_date = models.DateTimeField(default=timezone.now)
    approval_date = models.DateTimeField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    diagnosis = models.CharField(max_length=200)
    procedure_codes = models.JSONField(default=list)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-requested_date']
    
    def __str__(self):
        return f"Pre-Auth {self.auth_number or 'Pending'} - {self.patient.full_name}"


class ClaimsBatch(BaseModel):
    """Insurance claims batch processing"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid'),
    ]
    
    batch_number = models.CharField(max_length=50, unique=True)
    payer = models.ForeignKey('Payer', on_delete=models.CASCADE, related_name='claims_batches')
    submission_date = models.DateTimeField(null=True, blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    total_claims = models.IntegerField(default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    remittance_date = models.DateField(null=True, blank=True)
    remittance_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"Batch {self.batch_number} - {self.payer.name}"


class ChargeCapture(BaseModel):
    """Charge capture for procedures, bed days, consumables"""
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='charge_captures')
    service_code = models.ForeignKey('ServiceCode', on_delete=models.CASCADE, related_name='charge_captures')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    charge_date = models.DateTimeField(default=timezone.now)
    charged_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    invoice_line = models.ForeignKey('InvoiceLine', on_delete=models.SET_NULL, null=True, blank=True, related_name='charge_captures')
    
    class Meta:
        ordering = ['-charge_date']
    
    def __str__(self):
        return f"Charge - {self.service_code.description} - {self.total_amount}"


# ==================== LAB ENHANCEMENTS ====================

class LabTestPanel(BaseModel):
    """Laboratory test panels/groups"""
    panel_code = models.CharField(max_length=50, unique=True)
    panel_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    tests = models.ManyToManyField('LabTest', related_name='panels')
    
    class Meta:
        ordering = ['panel_name']
    
    def __str__(self):
        return f"{self.panel_name} ({self.panel_code})"


class SampleCollection(BaseModel):
    """Sample collection and tracking"""
    STATUS_CHOICES = [
        ('pending', 'Pending Collection'),
        ('collected', 'Collected'),
        ('sent_to_lab', 'Sent to Lab'),
        ('received', 'Received at Lab'),
        ('rejected', 'Rejected'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='samples')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='samples')
    sample_type = models.CharField(max_length=50)  # blood, urine, stool, etc.
    sample_id = models.CharField(max_length=50, unique=True)  # Barcode/ID
    collection_time = models.DateTimeField(null=True, blank=True)
    collected_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"Sample {self.sample_id} - {self.patient.full_name}"


# ==================== SMS & INTEGRATIONS ====================

class SMSLog(BaseModel):
    """SMS sending log"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('delivered', 'Delivered'),
    ]
    
    recipient_phone = models.CharField(max_length=20)
    recipient_name = models.CharField(max_length=100, blank=True)
    message = models.TextField()
    message_type = models.CharField(max_length=50)  # appointment_reminder, result_ready, etc.
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    related_object_id = models.UUIDField(null=True, blank=True)
    related_object_type = models.CharField(max_length=50, blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"SMS to {self.recipient_phone} - {self.status}"

