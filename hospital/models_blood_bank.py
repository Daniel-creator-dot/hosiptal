"""
Blood Bank & Transfusion Management System
State-of-the-art blood inventory, donation, and transfusion tracking
"""
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from datetime import timedelta

from .models import BaseModel, Patient, Staff, Encounter


# Blood Type Choices
BLOOD_GROUP_CHOICES = [
    ('A+', 'A Positive'),
    ('A-', 'A Negative'),
    ('B+', 'B Positive'),
    ('B-', 'B Negative'),
    ('AB+', 'AB Positive'),
    ('AB-', 'AB Negative'),
    ('O+', 'O Positive'),
    ('O-', 'O Negative'),
]

# Blood Component Types
BLOOD_COMPONENT_CHOICES = [
    ('whole_blood', 'Whole Blood'),
    ('packed_rbc', 'Packed Red Blood Cells (PRBC)'),
    ('fresh_frozen_plasma', 'Fresh Frozen Plasma (FFP)'),
    ('platelets', 'Platelet Concentrate'),
    ('cryoprecipitate', 'Cryoprecipitate'),
    ('granulocytes', 'Granulocytes'),
]


class BloodDonor(BaseModel):
    """
    Blood donor registration and tracking
    Can be a registered patient or external donor
    """
    # Donor can be a patient or external
    patient = models.ForeignKey(
        Patient, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='blood_donations'
    )
    
    # External donor details
    donor_id = models.CharField(max_length=20, unique=True, help_text="Unique donor ID")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')])
    
    # Contact
    phone_number = models.CharField(max_length=17, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    
    # Blood type
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES)
    
    # Donor status
    is_active = models.BooleanField(default=True)
    is_regular_donor = models.BooleanField(default=False)
    last_donation_date = models.DateField(null=True, blank=True)
    total_donations = models.PositiveIntegerField(default=0)
    
    # Medical screening
    is_eligible = models.BooleanField(default=True)
    ineligibility_reason = models.TextField(blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    hemoglobin_level = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="g/dL")
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-last_donation_date', 'last_name', 'first_name']
        verbose_name = "Blood Donor"
        verbose_name_plural = "Blood Donors"
    
    def __str__(self):
        return f"{self.donor_id} - {self.first_name} {self.last_name} ({self.blood_group})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def age(self):
        from datetime import date
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
    
    def can_donate(self):
        """Check if donor is eligible to donate (minimum 56 days since last donation)"""
        if not self.is_eligible or not self.is_active:
            return False, "Donor is not eligible"
        
        if self.last_donation_date:
            days_since_last = (timezone.now().date() - self.last_donation_date).days
            if days_since_last < 56:
                return False, f"Must wait {56 - days_since_last} more days since last donation"
        
        return True, "Eligible to donate"


class BloodDonation(BaseModel):
    """
    Individual blood donation record
    """
    donor = models.ForeignKey(BloodDonor, on_delete=models.CASCADE, related_name='donations')
    donation_date = models.DateTimeField(default=timezone.now)
    donation_number = models.CharField(max_length=50, unique=True, help_text="Unique donation identifier")
    
    # Pre-donation screening
    pre_donation_hemoglobin = models.DecimalField(max_digits=4, decimal_places=1, help_text="g/dL")
    pre_donation_weight = models.DecimalField(max_digits=5, decimal_places=2, help_text="kg")
    pre_donation_bp_systolic = models.PositiveIntegerField(help_text="mmHg")
    pre_donation_bp_diastolic = models.PositiveIntegerField(help_text="mmHg")
    pre_donation_temperature = models.DecimalField(max_digits=4, decimal_places=1, help_text="°C")
    
    # Donation details
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES)
    volume_collected_ml = models.PositiveIntegerField(default=450, help_text="milliliters")
    
    # Collection staff
    collected_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name='blood_collections')
    
    # Testing status
    TESTING_STATUS = [
        ('pending', 'Testing Pending'),
        ('in_progress', 'Testing In Progress'),
        ('completed', 'Testing Completed'),
        ('rejected', 'Rejected - Failed Tests'),
    ]
    testing_status = models.CharField(max_length=20, choices=TESTING_STATUS, default='pending')
    
    # Infectious disease testing
    hiv_tested = models.BooleanField(default=False)
    hiv_result = models.CharField(max_length=20, blank=True, choices=[('negative', 'Negative'), ('positive', 'Positive')])
    hbv_tested = models.BooleanField(default=False)
    hbv_result = models.CharField(max_length=20, blank=True)
    hcv_tested = models.BooleanField(default=False)
    hcv_result = models.CharField(max_length=20, blank=True)
    syphilis_tested = models.BooleanField(default=False)
    syphilis_result = models.CharField(max_length=20, blank=True)
    malaria_tested = models.BooleanField(default=False)
    malaria_result = models.CharField(max_length=20, blank=True)
    
    # Approval
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_donations')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Rejection
    rejection_reason = models.TextField(blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-donation_date']
        verbose_name = "Blood Donation"
        verbose_name_plural = "Blood Donations"
    
    def __str__(self):
        return f"{self.donation_number} - {self.donor.full_name} - {self.blood_group}"
    
    def mark_tests_complete(self):
        """Mark all testing as completed"""
        self.testing_status = 'completed'
        self.save(update_fields=['testing_status'])
    
    def approve_donation(self, staff):
        """Approve donation for use"""
        self.is_approved = True
        self.approved_by = staff
        self.approved_at = timezone.now()
        self.testing_status = 'completed'
        self.save()


class BloodInventory(BaseModel):
    """
    Blood inventory management - tracking blood units
    """
    unit_number = models.CharField(max_length=50, unique=True, help_text="Unique unit identifier/bag number")
    donation = models.ForeignKey(BloodDonation, on_delete=models.CASCADE, related_name='blood_units')
    
    # Blood details
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES)
    component_type = models.CharField(max_length=30, choices=BLOOD_COMPONENT_CHOICES, default='whole_blood')
    volume_ml = models.PositiveIntegerField(help_text="Current volume in milliliters")
    
    # Storage and expiry
    collection_date = models.DateField()
    expiry_date = models.DateField()
    storage_location = models.CharField(max_length=100, help_text="Fridge/Freezer location")
    
    # Status
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('reserved', 'Reserved'),
        ('issued', 'Issued'),
        ('expired', 'Expired'),
        ('discarded', 'Discarded'),
        ('quarantine', 'Quarantine'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    
    # Quality control
    temperature_log = models.TextField(blank=True, help_text="Temperature monitoring log")
    
    class Meta:
        ordering = ['expiry_date', 'blood_group']
        verbose_name = "Blood Inventory Unit"
        verbose_name_plural = "Blood Inventory"
    
    def __str__(self):
        return f"{self.unit_number} - {self.blood_group} {self.get_component_type_display()} ({self.status})"
    
    @property
    def is_expired(self):
        return timezone.now().date() > self.expiry_date
    
    @property
    def days_until_expiry(self):
        return (self.expiry_date - timezone.now().date()).days
    
    @property
    def is_expiring_soon(self):
        """Check if expires within 7 days"""
        return 0 <= self.days_until_expiry <= 7
    
    def mark_expired(self):
        """Mark unit as expired"""
        if self.is_expired:
            self.status = 'expired'
            self.save(update_fields=['status'])


class TransfusionRequest(BaseModel):
    """
    Request for blood transfusion from doctor
    """
    request_number = models.CharField(max_length=50, unique=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='transfusion_requests')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='transfusion_requests')
    
    # Request details
    requested_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name='transfusion_requests')
    requested_at = models.DateTimeField(default=timezone.now)
    
    # Blood requirements
    patient_blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES)
    component_type = models.CharField(max_length=30, choices=BLOOD_COMPONENT_CHOICES)
    units_requested = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    
    # Clinical indication
    INDICATION_CHOICES = [
        ('anemia', 'Severe Anemia'),
        ('hemorrhage', 'Hemorrhage/Blood Loss'),
        ('surgery', 'Surgical Procedure'),
        ('trauma', 'Trauma'),
        ('obstetric', 'Obstetric Emergency'),
        ('malignancy', 'Malignancy'),
        ('other', 'Other'),
    ]
    indication = models.CharField(max_length=20, choices=INDICATION_CHOICES)
    clinical_notes = models.TextField()
    
    # Patient vitals before transfusion
    pre_transfusion_hb = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="g/dL")
    pre_transfusion_bp_systolic = models.PositiveIntegerField(null=True, blank=True)
    pre_transfusion_bp_diastolic = models.PositiveIntegerField(null=True, blank=True)
    
    # Urgency
    URGENCY_CHOICES = [
        ('routine', 'Routine'),
        ('urgent', 'Urgent (< 24 hours)'),
        ('emergency', 'Emergency (Immediate)'),
    ]
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='routine')
    
    # Status
    STATUS_CHOICES = [
        ('pending', 'Pending Lab Processing'),
        ('crossmatch_in_progress', 'Crossmatch In Progress'),
        ('approved', 'Approved - Blood Ready'),
        ('issued', 'Blood Issued'),
        ('completed', 'Transfusion Completed'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    
    # Lab processing
    processed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_transfusions')
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Crossmatch
    crossmatch_completed = models.BooleanField(default=False)
    crossmatch_compatible = models.BooleanField(default=False)
    crossmatch_notes = models.TextField(blank=True)
    
    # Approval/Rejection
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_transfusions')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-requested_at']
        verbose_name = "Transfusion Request"
        verbose_name_plural = "Transfusion Requests"
    
    def __str__(self):
        return f"{self.request_number} - {self.patient.full_name} - {self.component_type}"


class BloodCrossmatch(BaseModel):
    """
    Blood crossmatch testing results
    """
    transfusion_request = models.ForeignKey(TransfusionRequest, on_delete=models.CASCADE, related_name='crossmatches')
    blood_unit = models.ForeignKey(BloodInventory, on_delete=models.CASCADE, related_name='crossmatches')
    
    # Testing
    tested_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    tested_at = models.DateTimeField(default=timezone.now)
    
    # Results
    major_crossmatch_result = models.CharField(
        max_length=20, 
        choices=[('compatible', 'Compatible'), ('incompatible', 'Incompatible'), ('pending', 'Pending')]
    )
    minor_crossmatch_result = models.CharField(max_length=20, blank=True)
    
    # Additional testing
    antibody_screen = models.CharField(max_length=50, blank=True)
    
    # Final decision
    is_compatible = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-tested_at']
        verbose_name = "Blood Crossmatch"
        verbose_name_plural = "Blood Crossmatches"
    
    def __str__(self):
        return f"Crossmatch - {self.blood_unit.unit_number} for {self.transfusion_request.patient.full_name}"


class BloodTransfusion(BaseModel):
    """
    Actual blood transfusion administration record
    """
    transfusion_request = models.ForeignKey(TransfusionRequest, on_delete=models.CASCADE, related_name='transfusions')
    blood_unit = models.ForeignKey(BloodInventory, on_delete=models.CASCADE, related_name='transfusions')
    
    # Administration
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    administered_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name='administered_transfusions')
    
    # Volume
    volume_transfused_ml = models.PositiveIntegerField()
    
    # Pre-transfusion vitals
    pre_vital_bp_systolic = models.PositiveIntegerField()
    pre_vital_bp_diastolic = models.PositiveIntegerField()
    pre_vital_temperature = models.DecimalField(max_digits=4, decimal_places=1)
    pre_vital_pulse = models.PositiveIntegerField()
    pre_vital_respiratory_rate = models.PositiveIntegerField()
    
    # Post-transfusion vitals
    post_vital_bp_systolic = models.PositiveIntegerField(null=True, blank=True)
    post_vital_bp_diastolic = models.PositiveIntegerField(null=True, blank=True)
    post_vital_temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    post_vital_pulse = models.PositiveIntegerField(null=True, blank=True)
    post_vital_respiratory_rate = models.PositiveIntegerField(null=True, blank=True)
    
    # Monitoring during transfusion
    transfusion_rate = models.CharField(max_length=50, help_text="e.g., 2-4 mL/kg/hr")
    monitoring_frequency = models.CharField(max_length=50, default="Every 15 minutes")
    
    # Adverse reactions
    adverse_reaction_occurred = models.BooleanField(default=False)
    reaction_type = models.CharField(max_length=100, blank=True)
    reaction_severity = models.CharField(
        max_length=20, 
        blank=True,
        choices=[('mild', 'Mild'), ('moderate', 'Moderate'), ('severe', 'Severe')]
    )
    reaction_management = models.TextField(blank=True)
    
    # Outcome
    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed Successfully'),
        ('stopped', 'Stopped Due to Reaction'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-started_at']
        verbose_name = "Blood Transfusion"
        verbose_name_plural = "Blood Transfusions"
    
    def __str__(self):
        return f"Transfusion - {self.blood_unit.unit_number} to {self.transfusion_request.patient.full_name}"
    
    @property
    def duration_minutes(self):
        if self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() / 60)
        return None


class BloodCompatibilityMatrix(models.Model):
    """
    Blood compatibility rules for transfusion
    """
    recipient_blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES)
    component_type = models.CharField(max_length=30, choices=BLOOD_COMPONENT_CHOICES)
    compatible_donor_groups = models.JSONField(help_text="List of compatible blood groups")
    
    class Meta:
        unique_together = ['recipient_blood_group', 'component_type']
        verbose_name = "Blood Compatibility Matrix"
        verbose_name_plural = "Blood Compatibility Matrix"
    
    def __str__(self):
        return f"{self.recipient_blood_group} - {self.component_type}"
    
    @classmethod
    def get_compatible_groups(cls, recipient_group, component_type):
        """Get list of compatible donor groups"""
        try:
            matrix = cls.objects.get(recipient_blood_group=recipient_group, component_type=component_type)
            return matrix.compatible_donor_groups
        except cls.DoesNotExist:
            # Default compatibility for whole blood/PRBC
            compatibility = {
                'O-': ['O-'],
                'O+': ['O-', 'O+'],
                'A-': ['O-', 'A-'],
                'A+': ['O-', 'O+', 'A-', 'A+'],
                'B-': ['O-', 'B-'],
                'B+': ['O-', 'O+', 'B-', 'B+'],
                'AB-': ['O-', 'A-', 'B-', 'AB-'],
                'AB+': ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'],
            }
            return compatibility.get(recipient_group, [])





















