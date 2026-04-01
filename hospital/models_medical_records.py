"""
Medical Records Management System
Comprehensive patient record keeping with complete visit details
"""
from django.db import models
from django.utils import timezone
from .models import BaseModel, Patient, Encounter, Staff


class MedicalRecordSummary(BaseModel):
    """
    Consolidated medical record summary for a patient
    Automatically updated with each visit
    """
    patient = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name='medical_record_summary')
    
    # Record metadata
    record_number = models.CharField(max_length=50, unique=True, help_text="Unique medical record number")
    created_date = models.DateField(default=timezone.now)
    last_updated = models.DateTimeField(auto_now=True)
    
    # Summary statistics
    total_visits = models.PositiveIntegerField(default=0)
    total_admissions = models.PositiveIntegerField(default=0)
    total_emergency_visits = models.PositiveIntegerField(default=0)
    total_prescriptions = models.PositiveIntegerField(default=0)
    total_lab_tests = models.PositiveIntegerField(default=0)
    total_imaging_studies = models.PositiveIntegerField(default=0)
    total_procedures = models.PositiveIntegerField(default=0)
    
    # Latest information
    last_visit_date = models.DateField(null=True, blank=True)
    last_diagnosis = models.TextField(blank=True)
    current_medications = models.TextField(blank=True, help_text="Current active medications")
    
    # Chronic conditions
    chronic_conditions = models.TextField(blank=True, help_text="List of chronic/ongoing conditions")
    allergies = models.TextField(blank=True, help_text="Known allergies")
    
    # Blood type and vitals
    blood_group = models.CharField(max_length=3, blank=True)
    last_weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    last_height_cm = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    last_bp_systolic = models.PositiveIntegerField(null=True, blank=True)
    last_bp_diastolic = models.PositiveIntegerField(null=True, blank=True)
    
    # Family history
    family_medical_history = models.TextField(blank=True)
    
    # Social history
    smoking_status = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('never', 'Never'),
            ('former', 'Former Smoker'),
            ('current', 'Current Smoker'),
        ]
    )
    alcohol_use = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('never', 'Never'),
            ('occasional', 'Occasional'),
            ('moderate', 'Moderate'),
            ('heavy', 'Heavy'),
        ]
    )
    
    # Notes
    special_notes = models.TextField(blank=True, help_text="Important notes, alerts, precautions")
    
    class Meta:
        verbose_name = "Medical Record Summary"
        verbose_name_plural = "Medical Record Summaries"
    
    def __str__(self):
        return f"Medical Record - {self.patient.full_name} ({self.record_number})"
    
    def update_statistics(self):
        """Update summary statistics from patient's encounters"""
        self.total_visits = self.patient.encounters.filter(is_deleted=False).count()
        self.total_admissions = self.patient.encounters.filter(encounter_type='admission', is_deleted=False).count()
        self.total_emergency_visits = self.patient.encounters.filter(encounter_type='emergency', is_deleted=False).count()
        
        # Get latest encounter
        latest_encounter = self.patient.encounters.filter(is_deleted=False).order_by('-started_at').first()
        if latest_encounter:
            self.last_visit_date = latest_encounter.started_at.date()
            self.last_diagnosis = latest_encounter.diagnosis or ''
        
        self.save()


class VisitRecord(BaseModel):
    """
    Detailed record of each patient visit/encounter
    Consolidated view of everything that happened during visit
    """
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='visit_records')
    encounter = models.OneToOneField(Encounter, on_delete=models.CASCADE, related_name='visit_record')
    
    # Visit details
    visit_number = models.CharField(max_length=50, unique=True)
    visit_date = models.DateField()
    visit_time = models.TimeField()
    visit_type = models.CharField(max_length=20, help_text="outpatient/admission/emergency")
    
    # Chief complaint and diagnosis
    chief_complaint = models.TextField()
    final_diagnosis = models.TextField()
    
    # Treatment summary
    treatment_given = models.TextField(blank=True, help_text="Summary of treatment provided")
    medications_prescribed = models.TextField(blank=True)
    procedures_performed = models.TextField(blank=True)
    
    # Tests ordered
    lab_tests_ordered = models.TextField(blank=True)
    imaging_ordered = models.TextField(blank=True)
    
    # Clinical notes summary
    clinical_summary = models.TextField(blank=True, help_text="SOAP notes or clinical summary")
    
    # Outcome
    disposition = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('home', 'Discharged Home'),
            ('admitted', 'Admitted to Hospital'),
            ('transferred', 'Transferred'),
            ('referred', 'Referred'),
            ('died', 'Deceased'),
            ('left_ama', 'Left Against Medical Advice'),
        ]
    )
    
    # Follow-up
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)
    follow_up_instructions = models.TextField(blank=True)
    
    # Provider
    provider = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name='visit_records')
    
    # Duration
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['-visit_date', '-visit_time']
        verbose_name = "Visit Record"
        verbose_name_plural = "Visit Records"
    
    def __str__(self):
        return f"{self.visit_number} - {self.patient.full_name} - {self.visit_date}"


class PatientDocument(BaseModel):
    """
    Documents attached to patient records
    (Lab reports, imaging, consent forms, referral letters, etc.)
    Supports PDF, images (JPG/PNG), and document files for lab/imaging results.
    """
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='documents')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, null=True, blank=True, related_name='documents')
    
    # Link to specific lab result or imaging study (for result file attachments)
    lab_result = models.ForeignKey(
        'LabResult', on_delete=models.CASCADE, null=True, blank=True,
        related_name='attached_documents', help_text='Lab result this document belongs to'
    )
    imaging_study = models.ForeignKey(
        'ImagingStudy', on_delete=models.CASCADE, null=True, blank=True,
        related_name='attached_documents', help_text='Imaging study this document belongs to'
    )
    
    # Document details
    document_type = models.CharField(
        max_length=50,
        choices=[
            ('lab_report', 'Laboratory Report'),
            ('imaging_report', 'Imaging Report'),
            ('external_report', 'External Report / Scan (from other facility)'),
            ('prescription', 'Prescription'),
            ('consent_form', 'Consent Form'),
            ('referral_letter', 'Referral Letter'),
            ('discharge_summary', 'Discharge Summary'),
            ('operative_note', 'Operative Note'),
            ('pathology_report', 'Pathology Report'),
            ('other', 'Other Document'),
        ]
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # File (if scanned/uploaded)
    file = models.FileField(upload_to='medical_records/%Y/%m/', null=True, blank=True)
    
    # Document date
    document_date = models.DateField(default=timezone.now)
    
    # Uploaded by
    uploaded_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name='uploaded_documents')
    
    # Metadata
    file_size = models.PositiveIntegerField(null=True, blank=True, help_text="Size in bytes")
    file_type = models.CharField(max_length=50, blank=True)
    
    # Access control
    is_confidential = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-document_date', '-created']
        verbose_name = "Patient Document"
        verbose_name_plural = "Patient Documents"
    
    def __str__(self):
        return f"{self.title} - {self.patient.full_name}"


class MedicalRecordAccess(BaseModel):
    """
    Track who accessed patient medical records
    For audit and privacy compliance
    """
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='record_access_log')
    accessed_by = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='record_accesses')
    
    # Access details
    access_time = models.DateTimeField(default=timezone.now)
    access_type = models.CharField(
        max_length=20,
        choices=[
            ('view', 'Viewed Record'),
            ('edit', 'Edited Record'),
            ('print', 'Printed Record'),
            ('export', 'Exported Record'),
            ('download', 'Downloaded Document'),
        ]
    )
    
    # What was accessed
    section_accessed = models.CharField(max_length=100, blank=True, help_text="e.g., Lab Results, Medications")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Reason for access
    reason = models.CharField(
        max_length=100,
        blank=True,
        choices=[
            ('treatment', 'Patient Treatment'),
            ('consultation', 'Consultation'),
            ('emergency', 'Emergency Care'),
            ('administrative', 'Administrative'),
            ('research', 'Research (Approved)'),
            ('audit', 'Audit/Quality Review'),
        ]
    )
    
    class Meta:
        ordering = ['-access_time']
        verbose_name = "Medical Record Access Log"
        verbose_name_plural = "Medical Record Access Logs"
    
    def __str__(self):
        return f"{self.accessed_by.get_full_name()} accessed {self.patient.full_name}'s record - {self.access_time.strftime('%Y-%m-%d %H:%M')}"





















