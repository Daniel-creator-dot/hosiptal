"""
Ambulance Service Models
Comprehensive ambulance fleet management and billing system
"""
from django.db import models
from django.utils import timezone
from decimal import Decimal
import uuid

from .models import BaseModel, Patient, Encounter, Staff, Department


class AmbulanceServiceType(BaseModel):
    """
    Ambulance service type configuration
    Defines different types of ambulance services and their charges
    """
    SERVICE_TYPES = [
        ('bls', 'Basic Life Support (BLS)'),
        ('als', 'Advanced Life Support (ALS)'),
        ('cct', 'Critical Care Transport (CCT)'),
        ('neonatal', 'Neonatal/Pediatric Transport'),
        ('transfer', 'Inter-Hospital Transfer'),
        ('mobile_icu', 'Mobile ICU'),
        ('air_ambulance', 'Air Ambulance'),
    ]
    
    service_code = models.CharField(max_length=20, unique=True)
    service_name = models.CharField(max_length=100)
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPES)
    description = models.TextField(blank=True)
    
    # Pricing
    base_charge = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    per_mile_charge = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    emergency_surcharge = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    equipment_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Equipment/Resources included
    equipment_description = models.TextField(blank=True)
    crew_size = models.IntegerField(default=2)  # Paramedic + EMT
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'hospital_ambulance_service_type'
        verbose_name = 'Ambulance Service Type'
        verbose_name_plural = 'Ambulance Service Types'
        ordering = ['service_name']
    
    def __str__(self):
        return f"{self.service_name} (GHS {self.base_charge})"
    
    def calculate_total_charge(self, miles=0, is_emergency=False, additional_fees=None):
        """Calculate total charge for an ambulance service"""
        total = self.base_charge
        total += self.per_mile_charge * Decimal(str(miles))
        
        if is_emergency:
            total += self.emergency_surcharge
        
        total += self.equipment_fee
        
        if additional_fees:
            total += Decimal(str(additional_fees))
        
        return total


class AmbulanceUnit(BaseModel):
    """
    Ambulance units/vehicles in the fleet
    """
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('en_route', 'En Route to Scene'),
        ('on_scene', 'On Scene'),
        ('transporting', 'Transporting Patient'),
        ('returning', 'Returning to Station'),
        ('out_of_service', 'Out of Service'),
        ('maintenance', 'Under Maintenance'),
    ]
    
    unit_number = models.CharField(max_length=20, unique=True)  # e.g., AMB-01
    vehicle_make = models.CharField(max_length=50, blank=True)
    vehicle_model = models.CharField(max_length=50, blank=True)
    license_plate = models.CharField(max_length=20, blank=True)
    year = models.IntegerField(null=True, blank=True)
    
    # Equipment capabilities
    service_capabilities = models.ManyToManyField(AmbulanceServiceType, related_name='capable_units')
    
    # Current status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    current_location = models.CharField(max_length=200, blank=True)
    gps_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    gps_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    
    # Crew assignment
    primary_paramedic = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='ambulance_paramedic')
    primary_emt = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='ambulance_emt')
    
    # Maintenance
    last_maintenance = models.DateTimeField(null=True, blank=True)
    next_maintenance_due = models.DateField(null=True, blank=True)
    mileage = models.IntegerField(default=0, help_text="Total miles/kilometers")
    
    # Station/Base
    home_station = models.CharField(max_length=100, blank=True)
    
    class Meta:
        db_table = 'hospital_ambulance_unit'
        verbose_name = 'Ambulance Unit'
        verbose_name_plural = 'Ambulance Units'
        ordering = ['unit_number']
    
    def __str__(self):
        return f"{self.unit_number} ({self.get_status_display()})"


class AmbulanceDispatch(BaseModel):
    """
    Ambulance dispatch/call records
    Tracks each ambulance deployment
    """
    PRIORITY_LEVELS = [
        ('code_3', 'Code 3 - Lights & Sirens'),
        ('code_2', 'Code 2 - Urgent'),
        ('code_1', 'Code 1 - Non-Emergency'),
    ]
    
    CALL_TYPES = [
        ('trauma', 'Trauma'),
        ('cardiac', 'Cardiac Arrest'),
        ('respiratory', 'Respiratory Distress'),
        ('stroke', 'Stroke Alert'),
        ('overdose', 'Overdose'),
        ('psychiatric', 'Psychiatric Emergency'),
        ('transfer', 'Inter-Facility Transfer'),
        ('other', 'Other'),
    ]
    
    dispatch_number = models.CharField(max_length=50, unique=True)
    ambulance_unit = models.ForeignKey(AmbulanceUnit, on_delete=models.PROTECT, related_name='dispatches')
    
    # Call information
    call_received_at = models.DateTimeField(default=timezone.now)
    dispatch_time = models.DateTimeField(null=True, blank=True)
    arrival_time = models.DateTimeField(null=True, blank=True)
    transport_start_time = models.DateTimeField(null=True, blank=True)
    hospital_arrival_time = models.DateTimeField(null=True, blank=True)
    call_completed_time = models.DateTimeField(null=True, blank=True)
    
    # Location information
    pickup_address = models.TextField()
    pickup_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    pickup_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    
    destination_address = models.TextField(blank=True)
    destination_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    destination_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    
    # Distance
    miles_traveled = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Call details
    call_type = models.CharField(max_length=20, choices=CALL_TYPES, default='other')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='code_2')
    chief_complaint = models.TextField(blank=True)
    
    # Patient information (if applicable)
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True, related_name='ambulance_transports')
    encounter = models.ForeignKey(Encounter, on_delete=models.SET_NULL, null=True, blank=True, related_name='ambulance_transport')
    
    # Pre-hospital care
    pre_hospital_report = models.TextField(blank=True)
    vital_signs_on_scene = models.TextField(blank=True)
    treatments_administered = models.TextField(blank=True)
    
    # Outcome
    patient_transported = models.BooleanField(default=True)
    transport_refused = models.BooleanField(default=False)
    patient_deceased_on_scene = models.BooleanField(default=False)
    
    # Documentation
    pcr_completed = models.BooleanField(default=False, help_text="Patient Care Report")
    run_report_notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'hospital_ambulance_dispatch'
        verbose_name = 'Ambulance Dispatch'
        verbose_name_plural = 'Ambulance Dispatches'
        ordering = ['-call_received_at']
    
    def __str__(self):
        return f"{self.dispatch_number} - {self.ambulance_unit.unit_number}"
    
    @property
    def response_time_minutes(self):
        """Calculate response time (call to arrival)"""
        if self.arrival_time and self.call_received_at:
            delta = self.arrival_time - self.call_received_at
            return int(delta.total_seconds() / 60)
        return None
    
    @property
    def total_call_time_minutes(self):
        """Calculate total call time (call to completion)"""
        if self.call_completed_time and self.call_received_at:
            delta = self.call_completed_time - self.call_received_at
            return int(delta.total_seconds() / 60)
        return None


class AmbulanceBilling(BaseModel):
    """
    Ambulance service billing records
    Links to accounting system for revenue tracking
    """
    BILLING_STATUS = [
        ('pending', 'Pending'),
        ('billed', 'Billed'),
        ('paid', 'Paid'),
        ('insurance_pending', 'Insurance Pending'),
        ('written_off', 'Written Off'),
    ]
    
    dispatch = models.OneToOneField(AmbulanceDispatch, on_delete=models.CASCADE, related_name='billing')
    service_type = models.ForeignKey(AmbulanceServiceType, on_delete=models.PROTECT)
    
    # Patient/Encounter linkage
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True)
    encounter = models.ForeignKey(Encounter, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Billing details
    base_charge = models.DecimalField(max_digits=10, decimal_places=2)
    miles_traveled = models.DecimalField(max_digits=10, decimal_places=2)
    mileage_charge = models.DecimalField(max_digits=10, decimal_places=2)
    emergency_surcharge = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    equipment_fees = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Additional charges
    oxygen_charge = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    iv_fluids_charge = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    medical_supplies_charge = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    wait_time_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    other_charges = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Totals
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Payment tracking
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=BILLING_STATUS, default='pending')
    
    # Insurance
    insurance_claim_filed = models.BooleanField(default=False)
    insurance_approved_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Invoicing
    invoice_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    invoice_date = models.DateTimeField(null=True, blank=True)
    payment_date = models.DateTimeField(null=True, blank=True)
    
    # Notes
    billing_notes = models.TextField(blank=True)
    
    # Department linkage (for revenue tracking)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'hospital_ambulance_billing'
        verbose_name = 'Ambulance Billing'
        verbose_name_plural = 'Ambulance Billings'
        ordering = ['-invoice_date']
    
    def __str__(self):
        return f"Bill {self.invoice_number or self.id} - GHS {self.total_amount}"
    
    def save(self, *args, **kwargs):
        """Auto-generate invoice number and calculate totals"""
        # Generate invoice number if not exists
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        
        # Calculate subtotal
        self.subtotal = (
            self.base_charge + 
            self.mileage_charge + 
            self.emergency_surcharge + 
            self.equipment_fees +
            self.oxygen_charge +
            self.iv_fluids_charge +
            self.medical_supplies_charge +
            self.wait_time_fee +
            self.other_charges
        )
        
        # Calculate total (with tax)
        self.total_amount = self.subtotal + self.tax_amount
        
        # Calculate balance
        self.balance = self.total_amount - self.amount_paid
        
        # Update status based on payment
        if self.balance <= 0:
            self.status = 'paid'
        elif self.amount_paid > 0:
            self.status = 'billed'
        
        super().save(*args, **kwargs)
        
        # Create Revenue record for accounting tracking
        self.create_revenue_record()
    
    def create_revenue_record(self):
        """Create or update Revenue record for accounting integration"""
        from .models_accounting_advanced import Revenue
        
        try:
            # Create/update revenue record
            revenue, created = Revenue.objects.get_or_create(
                reference_type='ambulance_billing',
                reference_id=str(self.id),
                defaults={
                    'amount': self.total_amount,
                    'revenue_date': self.invoice_date or self.created_at,
                    'service_type': 'ambulance',
                    'department': self.department,
                    'patient': self.patient,
                    'description': f"Ambulance Service - {self.service_type.service_name}",
                    'is_recurring': False,
                }
            )
            
            if not created:
                # Update existing record
                revenue.amount = self.total_amount
                revenue.revenue_date = self.invoice_date or self.created_at
                revenue.save()
                
        except Exception as e:
            print(f"Error creating revenue record: {e}")
    
    @staticmethod
    def generate_invoice_number():
        """Generate unique invoice number for ambulance billing"""
        from datetime import datetime
        prefix = "AMB"
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = uuid.uuid4().hex[:4].upper()
        return f"{prefix}-{timestamp}-{random_suffix}"
    
    def record_payment(self, amount, payment_method='cash', notes=''):
        """Record a payment against this bill"""
        from .models import Payment
        
        payment_amount = Decimal(str(amount))
        self.amount_paid += payment_amount
        self.balance = self.total_amount - self.amount_paid
        
        if self.balance <= 0:
            self.status = 'paid'
            self.payment_date = timezone.now()
        
        self.save()
        
        # Create payment record
        payment = Payment.objects.create(
            patient=self.patient,
            amount=payment_amount,
            payment_method=payment_method,
            payment_date=timezone.now(),
            reference_number=self.invoice_number,
            notes=f"Ambulance service payment - {notes}"
        )
        
        return payment


class AmbulanceServiceCharge(BaseModel):
    """
    Additional service charges that can be applied to ambulance bills
    Oxygen, IV fluids, medical supplies, etc.
    """
    CHARGE_TYPES = [
        ('oxygen', 'Oxygen Therapy'),
        ('iv_fluids', 'IV Fluids Administration'),
        ('medications', 'Medications'),
        ('medical_supplies', 'Medical Supplies'),
        ('wait_time', 'Wait Time'),
        ('specialty_equipment', 'Specialty Equipment'),
        ('other', 'Other'),
    ]
    
    charge_code = models.CharField(max_length=20, unique=True)
    charge_name = models.CharField(max_length=100)
    charge_type = models.CharField(max_length=30, choices=CHARGE_TYPES)
    description = models.TextField(blank=True)
    
    # Pricing
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    unit_of_measure = models.CharField(max_length=20, default='each')  # each, hour, liter, etc.
    
    # Status
    is_active = models.BooleanField(default=True)
    requires_documentation = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'hospital_ambulance_service_charge'
        verbose_name = 'Ambulance Service Charge'
        verbose_name_plural = 'Ambulance Service Charges'
        ordering = ['charge_name']
    
    def __str__(self):
        return f"{self.charge_name} (GHS {self.unit_price}/{self.unit_of_measure})"


class AmbulanceBillingItem(BaseModel):
    """
    Line items for ambulance billing
    Links additional charges to bills
    """
    billing = models.ForeignKey(AmbulanceBilling, on_delete=models.CASCADE, related_name='line_items')
    service_charge = models.ForeignKey(AmbulanceServiceCharge, on_delete=models.PROTECT)
    
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'hospital_ambulance_billing_item'
        verbose_name = 'Ambulance Billing Item'
        verbose_name_plural = 'Ambulance Billing Items'
    
    def __str__(self):
        return f"{self.service_charge.charge_name} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        """Auto-calculate total"""
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)

