"""
Comprehensive Hospital Management System Models
Complete EMR, Billing, Pharmacy, Lab, Radiology, HR, and Inventory Management
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils import timezone
from model_utils.models import TimeStampedModel
from decimal import Decimal
from datetime import date, datetime, timedelta


class BaseModel(TimeStampedModel):
    """Base model with UUID primary key and soft delete"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        abstract = True


# ==================== PATIENT MANAGEMENT ====================

class Patient(BaseModel):
    """Comprehensive patient management"""
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    BLOOD_TYPE_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-'),
    ]
    
    MARITAL_STATUS_CHOICES = [
        ('single', 'Single'),
        ('married', 'Married'),
        ('divorced', 'Divorced'),
        ('widowed', 'Widowed'),
        ('separated', 'Separated'),
    ]
    
    # Basic Demographics
    mrn = models.CharField(max_length=20, unique=True, verbose_name="Medical Record Number")
    national_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    blood_type = models.CharField(max_length=3, choices=BLOOD_TYPE_CHOICES, blank=True)
    marital_status = models.CharField(max_length=20, choices=MARITAL_STATUS_CHOICES, blank=True)
    
    # Contact Information
    phone_regex = RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be entered in the format: '+999999999'.")
    phone_number = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='Ghana')
    
    # Emergency Contact
    next_of_kin_name = models.CharField(max_length=100, blank=True)
    next_of_kin_phone = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    next_of_kin_relationship = models.CharField(max_length=50, blank=True)
    next_of_kin_address = models.TextField(blank=True)
    
    # Medical Information
    allergies = models.TextField(blank=True)
    chronic_conditions = models.TextField(blank=True)
    current_medications = models.TextField(blank=True)
    family_history = models.TextField(blank=True)
    social_history = models.TextField(blank=True)
    
    # Insurance Information
    primary_insurance = models.ForeignKey('InsuranceProvider', on_delete=models.SET_NULL, null=True, blank=True)
    insurance_policy_number = models.CharField(max_length=100, blank=True)
    insurance_group_number = models.CharField(max_length=100, blank=True)
    insurance_effective_date = models.DateField(null=True, blank=True)
    insurance_expiry_date = models.DateField(null=True, blank=True)
    
    # Profile Picture
    profile_picture = models.ImageField(upload_to='patient_profiles/', blank=True, null=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    registration_date = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['last_name', 'first_name']
        verbose_name = 'Patient'
        verbose_name_plural = 'Patients'
    
    def __str__(self):
        return f"{self.full_name} ({self.mrn})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.middle_name} {self.last_name}".strip()
    
    @property
    def age(self):
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
    
    def save(self, *args, **kwargs):
        if not self.mrn:
            self.mrn = self.generate_mrn()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_mrn():
        """Generate unique MRN"""
        from datetime import datetime
        prefix = "PMC"
        year = datetime.now().year
        last_patient = Patient.objects.filter(mrn__startswith=f"{prefix}{year}").order_by('-mrn').first()
        
        if last_patient and last_patient.mrn:
            try:
                last_num = int(last_patient.mrn.replace(f"{prefix}{year}", ""))
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{year}{new_num:05d}"


class InsuranceProvider(BaseModel):
    """Insurance providers and payers"""
    PAYER_TYPES = [
        ('nhis', 'NHIS'),
        ('private', 'Private Insurance'),
        ('corporate', 'Corporate'),
        ('government', 'Government'),
        ('self_pay', 'Self Pay'),
    ]
    
    name = models.CharField(max_length=200, unique=True)
    payer_type = models.CharField(max_length=20, choices=PAYER_TYPES)
    contact_person = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=17, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


# ==================== STAFF & HR MANAGEMENT ====================

class Department(BaseModel):
    """Hospital departments"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)
    head_of_department = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True, blank=True, related_name='headed_departments')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Staff(BaseModel):
    """Comprehensive staff management"""
    PROFESSION_CHOICES = [
        ('doctor', 'Doctor'),
        ('nurse', 'Nurse'),
        ('pharmacist', 'Pharmacist'),
        ('lab_technician', 'Lab Technician'),
        ('radiologist', 'Radiologist'),
        ('admin', 'Administrator'),
        ('receptionist', 'Receptionist'),
        ('cashier', 'Cashier'),
        ('accountant', 'Accountant'),
        ('hr', 'HR Manager'),
        ('it', 'IT Support'),
        ('maintenance', 'Maintenance'),
        ('security', 'Security'),
        ('cleaner', 'Cleaner'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    employee_id = models.CharField(max_length=20, unique=True)
    profession = models.CharField(max_length=20, choices=PROFESSION_CHOICES)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='staff')
    
    # Personal Information
    phone_number = models.CharField(max_length=17, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=Patient.GENDER_CHOICES, blank=True)
    address = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=100, blank=True)
    emergency_phone = models.CharField(max_length=17, blank=True)
    
    # Employment Information
    date_of_joining = models.DateField(default=date.today)
    employment_type = models.CharField(max_length=20, choices=[
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('intern', 'Intern'),
    ], default='full_time')
    
    # Professional Information
    license_number = models.CharField(max_length=50, blank=True)
    specialization = models.CharField(max_length=100, blank=True)
    qualifications = models.TextField(blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['user__last_name', 'user__first_name']
    
    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_profession_display()})"
    
    @property
    def age(self):
        if self.date_of_birth:
            today = date.today()
            return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return None


# ==================== APPOINTMENT & SCHEDULING ====================

class Appointment(BaseModel):
    """Comprehensive appointment management"""
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
        ('rescheduled', 'Rescheduled'),
    ]
    
    PRIORITY_CHOICES = [
        ('routine', 'Routine'),
        ('urgent', 'Urgent'),
        ('emergency', 'Emergency'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    provider = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='appointments')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='appointments')
    
    # Appointment Details
    appointment_date = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=30)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='routine')
    
    # Clinical Information
    chief_complaint = models.TextField(blank=True)
    reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    # Follow-up
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateTimeField(null=True, blank=True)
    follow_up_notes = models.TextField(blank=True)
    
    # Communication
    reminder_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    email_sent = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-appointment_date']
    
    def __str__(self):
        return f"{self.patient.full_name} - {self.appointment_date.strftime('%Y-%m-%d %H:%M')}"
    
    def is_past_due(self):
        return self.appointment_date < timezone.now() and self.status in ['scheduled', 'confirmed']


class Queue(BaseModel):
    """Patient queue management"""
    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('called', 'Called'),
        ('in_consultation', 'In Consultation'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='queue_entries')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='queues')
    provider = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='queue_entries', null=True, blank=True)
    
    queue_number = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    priority = models.CharField(max_length=20, choices=Appointment.PRIORITY_CHOICES, default='routine')
    
    # Timing
    joined_at = models.DateTimeField(default=timezone.now)
    called_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['queue_number']
    
    def __str__(self):
        return f"Queue #{self.queue_number} - {self.patient.full_name}"


# ==================== CLINICAL MANAGEMENT ====================

class Encounter(BaseModel):
    """Patient encounters/visits"""
    ENCOUNTER_TYPES = [
        ('outpatient', 'Outpatient'),
        ('inpatient', 'Inpatient'),
        ('emergency', 'Emergency'),
        ('surgery', 'Surgery'),
        ('consultation', 'Consultation'),
        ('follow_up', 'Follow-up'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('discharged', 'Discharged'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='encounters')
    encounter_type = models.CharField(max_length=20, choices=ENCOUNTER_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Clinical Information
    chief_complaint = models.TextField(blank=True)
    history_of_present_illness = models.TextField(blank=True)
    review_of_systems = models.TextField(blank=True)
    physical_examination = models.TextField(blank=True)
    assessment = models.TextField(blank=True)
    plan = models.TextField(blank=True)
    diagnosis = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    # Staff
    provider = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='encounters')
    admitting_physician = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='admitted_encounters')
    
    # Timing
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    # Location
    location = models.CharField(max_length=100, blank=True)
    room_number = models.CharField(max_length=20, blank=True)
    bed_number = models.CharField(max_length=20, blank=True)
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.patient.full_name} - {self.get_encounter_type_display()} ({self.started_at.date()})"
    
    def get_duration_minutes(self):
        if self.ended_at:
            delta = self.ended_at - self.started_at
            return int(delta.total_seconds() / 60)
        return None


class VitalSign(BaseModel):
    """Vital signs recording"""
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='vitals')
    recorded_at = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    
    # Vital Signs
    systolic_bp = models.PositiveIntegerField(null=True, blank=True)
    diastolic_bp = models.PositiveIntegerField(null=True, blank=True)
    pulse = models.PositiveIntegerField(null=True, blank=True)
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    spo2 = models.PositiveIntegerField(null=True, blank=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    respiratory_rate = models.PositiveIntegerField(null=True, blank=True)
    
    # Additional Vitals
    pain_score = models.PositiveIntegerField(null=True, blank=True, validators=[MaxValueValidator(10)])
    blood_glucose = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-recorded_at']
    
    def __str__(self):
        return f"Vitals - {self.encounter.patient.full_name} ({self.recorded_at.strftime('%Y-%m-%d %H:%M')})"
    
    @property
    def bmi(self):
        if self.weight and self.height:
            height_m = float(self.height) / 100
            return round(float(self.weight) / (height_m ** 2), 1)
        return None


class ClinicalNote(BaseModel):
    """Clinical notes and documentation"""
    NOTE_TYPES = [
        ('consultation', 'Consultation Note'),
        ('progress', 'Progress Note'),
        ('discharge', 'Discharge Summary'),
        ('surgery', 'Surgery Note'),
        ('nursing', 'Nursing Note'),
        ('pharmacy', 'Pharmacy Note'),
        ('lab', 'Lab Note'),
        ('radiology', 'Radiology Note'),
    ]
    
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='clinical_notes')
    note_type = models.CharField(max_length=20, choices=NOTE_TYPES)
    
    # SOAP Format
    subjective = models.TextField(blank=True)
    objective = models.TextField(blank=True)
    assessment = models.TextField(blank=True)
    plan = models.TextField(blank=True)
    
    # Additional Information
    chief_complaint = models.TextField(blank=True)
    history_of_present_illness = models.TextField(blank=True)
    review_of_systems = models.TextField(blank=True)
    physical_examination = models.TextField(blank=True)
    diagnosis = models.TextField(blank=True)
    treatment_plan = models.TextField(blank=True)
    follow_up_plan = models.TextField(blank=True)
    
    # Staff
    created_by = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='clinical_notes')
    reviewed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_notes')
    
    # Status
    is_finalized = models.BooleanField(default=False)
    finalized_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.get_note_type_display()} - {self.encounter.patient.full_name}"


# ==================== PHARMACY MANAGEMENT ====================

class Drug(BaseModel):
    """Drug formulary and inventory"""
    CATEGORIES = [
        ('antibiotic', 'Antibiotic'),
        ('analgesic', 'Analgesic'),
        ('antihypertensive', 'Antihypertensive'),
        ('diabetic', 'Diabetic'),
        ('cardiac', 'Cardiac'),
        ('respiratory', 'Respiratory'),
        ('gastrointestinal', 'Gastrointestinal'),
        ('neurological', 'Neurological'),
        ('psychiatric', 'Psychiatric'),
        ('vitamin', 'Vitamin'),
        ('supplement', 'Supplement'),
        ('other', 'Other'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=200)
    generic_name = models.CharField(max_length=200, blank=True)
    brand_name = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=30, choices=CATEGORIES)
    
    # Drug Details
    strength = models.CharField(max_length=50)
    form = models.CharField(max_length=50)  # tablet, capsule, injection, etc.
    route = models.CharField(max_length=50, blank=True)  # oral, IV, IM, etc.
    pack_size = models.CharField(max_length=50)
    
    # Regulatory
    ndc_number = models.CharField(max_length=20, blank=True)  # National Drug Code
    atc_code = models.CharField(max_length=20, blank=True)  # ATC Classification
    is_controlled = models.BooleanField(default=False)
    requires_prescription = models.BooleanField(default=True)
    
    # Pricing
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} {self.strength} {self.form}"


class DrugInventory(BaseModel):
    """Drug inventory management"""
    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name='inventory')
    batch_number = models.CharField(max_length=50)
    expiry_date = models.DateField()
    
    # Inventory Details
    quantity_received = models.PositiveIntegerField()
    quantity_available = models.PositiveIntegerField()
    quantity_sold = models.PositiveIntegerField(default=0)
    quantity_damaged = models.PositiveIntegerField(default=0)
    quantity_expired = models.PositiveIntegerField(default=0)
    
    # Location
    location = models.CharField(max_length=100, default='Main Pharmacy')
    shelf_number = models.CharField(max_length=20, blank=True)
    
    # Pricing
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['drug__name', 'expiry_date']
    
    def __str__(self):
        return f"{self.drug.name} - Batch {self.batch_number}"
    
    @property
    def is_expired(self):
        return self.expiry_date < date.today()
    
    @property
    def is_near_expiry(self):
        return self.expiry_date <= date.today() + timedelta(days=30)


class Prescription(BaseModel):
    """Electronic prescriptions"""
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='prescriptions')
    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name='prescriptions')
    
    # Prescription Details
    quantity = models.PositiveIntegerField()
    dose = models.CharField(max_length=100)
    route = models.CharField(max_length=50)
    frequency = models.CharField(max_length=50)
    duration = models.CharField(max_length=50)
    instructions = models.TextField(blank=True)
    
    # Staff
    prescribed_by = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='prescriptions')
    
    # Status
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('dispensed', 'Dispensed'),
        ('cancelled', 'Cancelled'),
    ], default='pending')
    
    # Dispensing
    dispensed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='dispensed_prescriptions')
    dispensed_at = models.DateTimeField(null=True, blank=True)
    dispensing_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.drug.name} - {self.encounter.patient.full_name}"


# ==================== LABORATORY MANAGEMENT ====================

class LabTest(BaseModel):
    """Laboratory test catalog"""
    CATEGORIES = [
        ('hematology', 'Hematology'),
        ('biochemistry', 'Biochemistry'),
        ('microbiology', 'Microbiology'),
        ('immunology', 'Immunology'),
        ('pathology', 'Pathology'),
        ('urinalysis', 'Urinalysis'),
        ('blood_bank', 'Blood Bank'),
        ('molecular', 'Molecular'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    category = models.CharField(max_length=30, choices=CATEGORIES)
    specimen_type = models.CharField(max_length=50)
    collection_method = models.TextField(blank=True)
    preparation_instructions = models.TextField(blank=True)
    
    # Timing
    tat_hours = models.PositiveIntegerField(default=24, verbose_name="Turnaround Time (hours)")
    
    # Pricing
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Reference Ranges
    normal_range = models.CharField(max_length=100, blank=True)
    critical_values = models.TextField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class LabOrder(BaseModel):
    """Laboratory test orders"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('collected', 'Collected'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('routine', 'Routine'),
        ('urgent', 'Urgent'),
        ('stat', 'STAT'),
    ]
    
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='lab_orders')
    order_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='routine')
    
    # Clinical Information
    clinical_notes = models.TextField(blank=True)
    diagnosis = models.CharField(max_length=200, blank=True)
    
    # Staff
    ordered_by = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='lab_orders')
    collected_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='collected_orders')
    
    # Timing
    ordered_at = models.DateTimeField(default=timezone.now)
    collected_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-ordered_at']
    
    def __str__(self):
        return f"Lab Order {self.order_number} - {self.encounter.patient.full_name}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_order_number():
        from datetime import datetime
        prefix = "LAB"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{prefix}{timestamp}"


class LabResult(BaseModel):
    """Laboratory test results"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    lab_order = models.ForeignKey(LabOrder, on_delete=models.CASCADE, related_name='results')
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE, related_name='results')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Results
    value = models.CharField(max_length=100, blank=True)
    units = models.CharField(max_length=20, blank=True)
    reference_range = models.CharField(max_length=100, blank=True)
    is_abnormal = models.BooleanField(default=False)
    is_critical = models.BooleanField(default=False)
    
    # Qualitative Results
    qualitative_result = models.CharField(max_length=50, blank=True)
    
    # Additional Data
    details = models.JSONField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    # Staff
    performed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='performed_tests')
    verified_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_tests')
    
    # Timing
    performed_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.test.name} - {self.lab_order.encounter.patient.full_name}"


# ==================== RADIOLOGY MANAGEMENT ====================

class ImagingStudy(BaseModel):
    """Radiology and imaging studies"""
    STUDY_TYPES = [
        ('xray', 'X-Ray'),
        ('ct', 'CT Scan'),
        ('mri', 'MRI'),
        ('ultrasound', 'Ultrasound'),
        ('mammography', 'Mammography'),
        ('dexa', 'DEXA Scan'),
        ('pet', 'PET Scan'),
        ('nuclear', 'Nuclear Medicine'),
        ('fluoroscopy', 'Fluoroscopy'),
        ('angiography', 'Angiography'),
    ]
    
    BODY_PARTS = [
        ('chest', 'Chest'),
        ('abdomen', 'Abdomen'),
        ('pelvis', 'Pelvis'),
        ('head', 'Head'),
        ('spine', 'Spine'),
        ('extremities', 'Extremities'),
        ('breast', 'Breast'),
        ('cardiac', 'Cardiac'),
        ('other', 'Other'),
    ]
    
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='imaging_studies')
    study_type = models.CharField(max_length=20, choices=STUDY_TYPES)
    body_part = models.CharField(max_length=20, choices=BODY_PARTS)
    
    # Study Details
    study_number = models.CharField(max_length=50, unique=True)
    clinical_indication = models.TextField(blank=True)
    technique = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=[
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='scheduled')
    
    # Staff
    ordered_by = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='ordered_studies')
    performed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='performed_studies')
    reported_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='reported_studies')
    
    # Timing
    scheduled_at = models.DateTimeField(null=True, blank=True)
    performed_at = models.DateTimeField(null=True, blank=True)
    reported_at = models.DateTimeField(null=True, blank=True)
    
    # Report
    findings = models.TextField(blank=True)
    impression = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.get_study_type_display()} - {self.encounter.patient.full_name}"
    
    def save(self, *args, **kwargs):
        if not self.study_number:
            self.study_number = self.generate_study_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_study_number():
        from datetime import datetime
        prefix = "IMG"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{prefix}{timestamp}"


# ==================== BILLING & FINANCIAL MANAGEMENT ====================

class Service(BaseModel):
    """Medical services and procedures"""
    CATEGORIES = [
        ('consultation', 'Consultation'),
        ('procedure', 'Procedure'),
        ('surgery', 'Surgery'),
        ('diagnostic', 'Diagnostic'),
        ('therapeutic', 'Therapeutic'),
        ('emergency', 'Emergency'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    category = models.CharField(max_length=30, choices=CATEGORIES)
    description = models.TextField(blank=True)
    
    # Pricing
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Invoice(BaseModel):
    """Patient billing and invoicing"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('paid', 'Paid'),
        ('partially_paid', 'Partially Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='invoices')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='invoices', null=True, blank=True)
    insurance_provider = models.ForeignKey(InsuranceProvider, on_delete=models.CASCADE, related_name='invoices')
    
    # Invoice Details
    invoice_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Financial Information
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Insurance
    insurance_covered = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    patient_portion = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Dates
    issued_at = models.DateTimeField(default=timezone.now)
    due_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-issued_at']
    
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.patient.full_name}"
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        self.calculate_totals()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_invoice_number():
        from datetime import datetime
        prefix = "INV"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{prefix}{timestamp}"
    
    def calculate_totals(self):
        self.balance = self.total_amount - self.paid_amount
        self.patient_portion = self.total_amount - self.insurance_covered


class InvoiceLine(BaseModel):
    """Invoice line items"""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='invoice_lines')
    
    # Line Details
    description = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        ordering = ['created']
    
    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.description}"
    
    def save(self, *args, **kwargs):
        self.line_total = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class Payment(BaseModel):
    """Payment records"""
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('cheque', 'Cheque'),
        ('insurance', 'Insurance'),
    ]
    
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Staff
    received_by = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='received_payments')
    
    # Timing
    payment_date = models.DateTimeField(default=timezone.now)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"Payment {self.amount} - {self.invoice.invoice_number}"


# ==================== INVENTORY MANAGEMENT ====================

class Supplier(BaseModel):
    """Suppliers and vendors"""
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=17, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    
    # Business Information
    tax_id = models.CharField(max_length=50, blank=True)
    payment_terms = models.CharField(max_length=100, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class InventoryItem(BaseModel):
    """Inventory items and supplies"""
    CATEGORIES = [
        ('medical_supplies', 'Medical Supplies'),
        ('pharmaceutical', 'Pharmaceutical'),
        ('surgical', 'Surgical'),
        ('laboratory', 'Laboratory'),
        ('radiology', 'Radiology'),
        ('office', 'Office Supplies'),
        ('equipment', 'Equipment'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=30, choices=CATEGORIES)
    description = models.TextField(blank=True)
    sku = models.CharField(max_length=50, unique=True)
    
    # Inventory Details
    current_stock = models.PositiveIntegerField(default=0)
    minimum_stock = models.PositiveIntegerField(default=0)
    maximum_stock = models.PositiveIntegerField(default=1000)
    reorder_level = models.PositiveIntegerField(default=10)
    
    # Pricing
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Supplier
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.sku})"
    
    @property
    def is_low_stock(self):
        return self.current_stock <= self.reorder_level


class InventoryTransaction(BaseModel):
    """Inventory movement transactions"""
    TRANSACTION_TYPES = [
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
        ('adjustment', 'Adjustment'),
        ('transfer', 'Transfer'),
        ('damage', 'Damage'),
        ('expiry', 'Expiry'),
    ]
    
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    quantity = models.IntegerField()  # Positive for additions, negative for deductions
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Reference
    reference_number = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    
    # Staff
    processed_by = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='inventory_transactions')
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.item.name}"


# ==================== REPORTING & ANALYTICS ====================

class DashboardMetric(BaseModel):
    """Dashboard metrics and KPIs"""
    METRIC_TYPES = [
        ('patient_count', 'Patient Count'),
        ('appointment_count', 'Appointment Count'),
        ('revenue', 'Revenue'),
        ('inventory_value', 'Inventory Value'),
        ('staff_count', 'Staff Count'),
        ('bed_occupancy', 'Bed Occupancy'),
        ('lab_tests', 'Lab Tests'),
        ('prescriptions', 'Prescriptions'),
    ]
    
    metric_type = models.CharField(max_length=30, choices=METRIC_TYPES)
    value = models.DecimalField(max_digits=15, decimal_places=2)
    period = models.CharField(max_length=20)  # daily, weekly, monthly, yearly
    date = models.DateField()
    
    class Meta:
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.get_metric_type_display()} - {self.date}"


# ==================== NOTIFICATIONS ====================

class Notification(BaseModel):
    """System notifications"""
    NOTIFICATION_TYPES = [
        ('appointment_reminder', 'Appointment Reminder'),
        ('lab_result_ready', 'Lab Result Ready'),
        ('prescription_ready', 'Prescription Ready'),
        ('payment_overdue', 'Payment Overdue'),
        ('inventory_low', 'Low Inventory'),
        ('system_alert', 'System Alert'),
        ('other', 'Other'),
    ]
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Related Objects
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.CharField(max_length=50, blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.title} - {self.recipient.username}"



































