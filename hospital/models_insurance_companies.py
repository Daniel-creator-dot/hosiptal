"""
World-Class Insurance Company Management System
Comprehensive insurance company and plan management
"""
import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from .models import BaseModel, Patient, ServiceCode, Drug


class InsuranceCompany(BaseModel):
    """
    Insurance Company Master - Manage all insurance providers
    """
    COMPANY_STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('inactive', 'Inactive'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=200, unique=True, verbose_name="Company Name")
    code = models.CharField(max_length=20, unique=True, 
                           help_text="Short code for the company (e.g., NHIS, GLICO)")
    
    # Contact Information
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    address = models.TextField(blank=True)
    
    # Contract Details
    contract_number = models.CharField(max_length=100, blank=True, 
                                      help_text="Contract/Agreement number with hospital")
    contract_start_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    
    # Financial Terms
    payment_terms_days = models.IntegerField(default=30, 
                                             validators=[MinValueValidator(0)],
                                             help_text="Number of days for payment (e.g., NET 30)")
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'),
                                             validators=[MinValueValidator(Decimal('0')), 
                                                       MaxValueValidator(Decimal('100'))],
                                             help_text="General discount % offered by hospital")
    
    # Billing Contact
    billing_contact_name = models.CharField(max_length=200, blank=True)
    billing_contact_phone = models.CharField(max_length=20, blank=True)
    billing_contact_email = models.EmailField(blank=True)
    billing_address = models.TextField(blank=True, help_text="Address for sending claims")
    
    # Status
    status = models.CharField(max_length=20, choices=COMPANY_STATUS_CHOICES, default='active')
    is_active = models.BooleanField(default=True, 
                                    help_text="Can patients register with this insurance?")
    
    # Notes
    notes = models.TextField(blank=True, help_text="Internal notes about this insurance company")
    
    # Logo
    logo = models.ImageField(upload_to='insurance_logos/', blank=True, null=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Insurance Company'
        verbose_name_plural = 'Insurance Companies'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    @property
    def is_contract_active(self):
        """Check if contract is currently valid"""
        if not self.contract_start_date:
            return True  # No contract date = always valid
        
        today = timezone.now().date()
        
        if self.contract_end_date:
            return self.contract_start_date <= today <= self.contract_end_date
        else:
            return self.contract_start_date <= today
    
    @property
    def active_plans_count(self):
        """Count active insurance plans"""
        return self.plans.filter(is_active=True, is_deleted=False).count()
    
    @property
    def enrolled_patients_count(self):
        """Count patients enrolled with this company"""
        return PatientInsurance.objects.filter(
            insurance_company=self,
            status='active',
            is_deleted=False
        ).count()
    
    @property
    def total_outstanding_claims(self):
        """Total outstanding claims amount"""
        from .models_insurance import InsuranceClaimItem
        from .insurance_claim_query import insurance_claim_item_deduped_q

        outstanding = (
            InsuranceClaimItem.objects.filter(
                payer__name=self.name,
                claim_status__in=['pending', 'submitted', 'processing', 'approved', 'partially_paid'],
                is_deleted=False,
            )
            .filter(insurance_claim_item_deduped_q())
            .aggregate(
                total=models.Sum(models.F('billed_amount') - models.F('paid_amount'))
            )['total']
            or Decimal('0.00')
        )

        return outstanding


class InsurancePlan(BaseModel):
    """
    Insurance Plans - Different coverage plans offered by insurance companies
    """
    PLAN_TYPE_CHOICES = [
        ('basic', 'Basic Coverage'),
        ('standard', 'Standard Coverage'),
        ('premium', 'Premium Coverage'),
        ('corporate', 'Corporate Plan'),
        ('family', 'Family Plan'),
        ('individual', 'Individual Plan'),
    ]
    
    # Basic Information
    insurance_company = models.ForeignKey(InsuranceCompany, on_delete=models.CASCADE, 
                                         related_name='plans')
    plan_name = models.CharField(max_length=200)
    plan_code = models.CharField(max_length=50, unique=True, 
                                help_text="Unique code for this plan")
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPE_CHOICES, default='individual')
    
    # Coverage Details
    description = models.TextField(blank=True, help_text="What this plan covers")
    
    # Coverage Percentages (What insurance pays, rest is copay)
    consultation_coverage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'),
                                               validators=[MinValueValidator(Decimal('0')), 
                                                         MaxValueValidator(Decimal('100'))],
                                               help_text="% covered for consultations")
    lab_coverage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'),
                                      validators=[MinValueValidator(Decimal('0')), 
                                                MaxValueValidator(Decimal('100'))],
                                      help_text="% covered for lab tests")
    imaging_coverage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'),
                                          validators=[MinValueValidator(Decimal('0')), 
                                                    MaxValueValidator(Decimal('100'))],
                                          help_text="% covered for imaging/X-rays")
    pharmacy_coverage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('80.00'),
                                           validators=[MinValueValidator(Decimal('0')), 
                                                     MaxValueValidator(Decimal('100'))],
                                           help_text="% covered for medications")
    surgery_coverage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('90.00'),
                                          validators=[MinValueValidator(Decimal('0')), 
                                                    MaxValueValidator(Decimal('100'))],
                                          help_text="% covered for surgical procedures")
    admission_coverage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'),
                                            validators=[MinValueValidator(Decimal('0')), 
                                                      MaxValueValidator(Decimal('100'))],
                                            help_text="% covered for hospital admissions")
    
    # Limits
    annual_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                      help_text="Maximum coverage per year (GHS). Leave blank for unlimited.")
    consultation_limit_per_year = models.IntegerField(null=True, blank=True,
                                                      help_text="Max consultations per year. Leave blank for unlimited.")
    requires_pre_authorization = models.BooleanField(default=False,
                                                     help_text="Does this plan require pre-authorization?")
    
    # Copay
    copay_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'),
                                      help_text="Fixed copay amount per visit (GHS)")
    
    # Status
    is_active = models.BooleanField(default=True)
    effective_date = models.DateField(help_text="Date this plan becomes effective")
    expiry_date = models.DateField(null=True, blank=True, 
                                  help_text="Date this plan expires (leave blank for no expiry)")
    
    # Notes
    exclusions = models.TextField(blank=True, help_text="What is NOT covered by this plan")
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['insurance_company', 'plan_name']
        unique_together = ['insurance_company', 'plan_name']
        verbose_name = 'Insurance Plan'
        verbose_name_plural = 'Insurance Plans'
        indexes = [
            models.Index(fields=['insurance_company', 'is_active']),
            models.Index(fields=['plan_code']),
        ]
    
    def __str__(self):
        return f"{self.insurance_company.name} - {self.plan_name}"
    
    @property
    def is_valid(self):
        """Check if plan is currently valid"""
        if not self.is_active:
            return False
        
        today = timezone.now().date()
        
        if self.expiry_date:
            return self.effective_date <= today <= self.expiry_date
        else:
            return self.effective_date <= today
    
    @property
    def enrolled_patients_count(self):
        """Count patients enrolled in this plan"""
        return PatientInsurance.objects.filter(
            insurance_plan=self,
            status='active',
            is_deleted=False
        ).count()
    
    def get_coverage_percentage(self, service_type):
        """Get coverage % for a specific service type"""
        coverage_map = {
            'consultation': self.consultation_coverage,
            'lab': self.lab_coverage,
            'lab_test': self.lab_coverage,
            'imaging': self.imaging_coverage,
            'imaging_study': self.imaging_coverage,
            'pharmacy': self.pharmacy_coverage,
            'pharmacy_prescription': self.pharmacy_coverage,
            'medication': self.pharmacy_coverage,
            'surgery': self.surgery_coverage,
            'admission': self.admission_coverage,
        }
        return coverage_map.get(service_type, Decimal('0.00'))
    
    def calculate_coverage(self, amount, service_type):
        """
        Calculate insurance coverage and patient copay
        Returns: (insurance_pays, patient_pays)
        """
        coverage_pct = self.get_coverage_percentage(service_type)
        insurance_pays = (amount * coverage_pct) / Decimal('100')
        patient_pays = amount - insurance_pays + self.copay_amount
        
        return (insurance_pays, patient_pays)


class InsuranceExclusionRule(BaseModel):
    """
    Declarative exclusion rules for services/drugs that a plan or company will not cover.
    """
    RULE_TYPES = [
        ('service_code', 'Specific Service Code'),
        ('service_category', 'Service Category'),
        ('drug', 'Specific Drug'),
        ('drug_generic', 'Drug Generic Name'),
        ('drug_category', 'Drug Category'),
    ]
    
    ENFORCEMENT_CHOICES = [
        ('block', 'Block billing'),
        ('patient_pay', 'Charge patient/self-pay'),
        ('warn', 'Warn only'),
    ]
    
    insurance_company = models.ForeignKey(
        InsuranceCompany,
        on_delete=models.CASCADE,
        related_name='exclusion_rules',
        help_text="Which insurance company provided this exclusion list"
    )
    insurance_plan = models.ForeignKey(
        InsurancePlan,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='exclusion_rules',
        help_text="Limit rule to a specific plan (optional)"
    )
    apply_to_all_plans = models.BooleanField(
        default=False,
        help_text="If checked, this rule applies to every plan for the insurance company"
    )
    
    rule_type = models.CharField(max_length=30, choices=RULE_TYPES)
    service_code = models.ForeignKey(
        ServiceCode,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='insurance_exclusion_rules'
    )
    service_category = models.CharField(
        max_length=100,
        blank=True,
        help_text="Category name to match ServiceCode.category (case-insensitive)"
    )
    drug = models.ForeignKey(
        Drug,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='insurance_exclusion_rules'
    )
    drug_generic_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Matches Drug.generic_name (case-insensitive)"
    )
    drug_category = models.CharField(
        max_length=100,
        blank=True,
        help_text="Custom grouping for drugs (e.g., antibiotics, antimalarials)"
    )
    
    enforcement_action = models.CharField(
        max_length=20,
        choices=ENFORCEMENT_CHOICES,
        default='block',
        help_text="What the billing team should do when this rule hits"
    )
    reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Short reason the front desk sees"
    )
    notes = models.TextField(blank=True)
    
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['insurance_company', 'rule_type', 'created']
        indexes = [
            models.Index(fields=['insurance_company', 'rule_type']),
            models.Index(fields=['rule_type', 'enforcement_action']),
        ]
        verbose_name = "Insurance Exclusion Rule"
        verbose_name_plural = "Insurance Exclusion Rules"
    
    def __str__(self):
        target = self.describe_target()
        plan = f" - {self.insurance_plan.plan_name}" if self.insurance_plan else ''
        return f"{self.insurance_company.name}{plan}: {target}"
    
    def describe_target(self):
        if self.rule_type == 'service_code' and self.service_code:
            return f"Service {self.service_code.code}"
        if self.rule_type == 'service_category' and self.service_category:
            return f"Category {self.service_category}"
        if self.rule_type == 'drug' and self.drug:
            return f"Drug {self.drug.name}"
        if self.rule_type == 'drug_generic' and self.drug_generic_name:
            return f"Generic {self.drug_generic_name}"
        if self.rule_type == 'drug_category' and self.drug_category:
            return f"Drug Category {self.drug_category}"
        return "Unspecified target"
    
    def is_effective(self, reference_date=None):
        from django.utils import timezone
        if not self.is_active:
            return False
        reference_date = reference_date or timezone.now().date()
        if self.effective_from and reference_date < self.effective_from:
            return False
        if self.effective_to and reference_date > self.effective_to:
            return False
        return True
    
    def matches_target(self, service_code=None, drug=None):
        if self.rule_type == 'service_code' and service_code:
            return self.service_code_id == service_code.id
        if self.rule_type == 'service_category' and service_code:
            if not self.service_category:
                return False
            return (service_code.category or '').lower() == self.service_category.lower()
        if self.rule_type == 'drug' and drug:
            return self.drug_id == drug.id
        if self.rule_type == 'drug_generic' and drug:
            if not self.drug_generic_name:
                return False
            return (drug.generic_name or '').lower() == self.drug_generic_name.lower()
        if self.rule_type == 'drug_category' and drug:
            if not self.drug_category:
                return False
            return (drug.form or '').lower() == self.drug_category.lower()
        return False
    
    def formatted_reason(self, service_code=None, drug=None):
        if self.reason:
            return self.reason
        target = service_code.description if service_code and self.rule_type.startswith('service') else ''
        if drug and self.rule_type.startswith('drug'):
            target = drug.name
        target = target or self.describe_target()
        return f"{self.insurance_company.name} does not cover {target}"


class PatientInsurance(BaseModel):
    """
    Patient Insurance Enrollment - Track which patients are enrolled in which plans
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('suspended', 'Suspended'),
        ('cancelled', 'Cancelled'),
    ]
    
    RELATIONSHIP_CHOICES = [
        ('self', 'Self'),
        ('spouse', 'Spouse'),
        ('child', 'Child'),
        ('parent', 'Parent'),
        ('dependent', 'Other Dependent'),
    ]
    
    # Patient Information
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='insurances')
    
    # Insurance Information
    insurance_company = models.ForeignKey(InsuranceCompany, on_delete=models.PROTECT, 
                                         related_name='patient_enrollments')
    insurance_plan = models.ForeignKey(InsurancePlan, on_delete=models.PROTECT, 
                                      related_name='patient_enrollments', 
                                      null=True, blank=True)
    
    # Policy Details
    policy_number = models.CharField(max_length=100, help_text="Insurance policy number")
    member_id = models.CharField(max_length=100, help_text="Member/subscriber ID")
    group_number = models.CharField(max_length=100, blank=True, help_text="Group/employer number")
    
    # Subscriber Information (if patient is a dependent)
    is_primary_subscriber = models.BooleanField(default=True, 
                                                help_text="Is patient the primary policy holder?")
    relationship_to_subscriber = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES, 
                                                  default='self')
    subscriber_name = models.CharField(max_length=200, blank=True, 
                                      help_text="Name of primary policy holder")
    subscriber_dob = models.DateField(null=True, blank=True, 
                                     help_text="Date of birth of primary subscriber")
    
    # Coverage Period
    effective_date = models.DateField(help_text="Date insurance coverage starts")
    expiry_date = models.DateField(null=True, blank=True, 
                                  help_text="Date insurance coverage ends")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    is_primary = models.BooleanField(default=True, 
                                     help_text="Is this the patient's primary insurance?")
    
    # Verification
    last_verified_date = models.DateField(null=True, blank=True, 
                                         help_text="Last date insurance was verified")
    verification_status = models.CharField(max_length=50, blank=True, 
                                          help_text="Result of last verification")
    
    # Usage Tracking
    consultations_used = models.IntegerField(default=0, 
                                            help_text="Number of consultations used this year")
    amount_used_this_year = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'),
                                               help_text="Total amount claimed this year")
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Attachments
    insurance_card_front = models.ImageField(upload_to='insurance_cards/', blank=True, null=True,
                                            help_text="Front of insurance card")
    insurance_card_back = models.ImageField(upload_to='insurance_cards/', blank=True, null=True,
                                           help_text="Back of insurance card")
    
    class Meta:
        ordering = ['-is_primary', '-effective_date']
        verbose_name = 'Patient Insurance'
        verbose_name_plural = 'Patient Insurances'
        indexes = [
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['insurance_company', 'status']),
            models.Index(fields=['policy_number']),
            models.Index(fields=['member_id']),
        ]
    
    def __str__(self):
        return f"{self.patient.full_name} - {self.insurance_company.name} ({self.member_id})"
    
    @property
    def is_valid(self):
        """Check if insurance is currently valid"""
        if self.status != 'active':
            return False
        
        today = timezone.now().date()
        
        if self.expiry_date:
            return self.effective_date <= today <= self.expiry_date
        else:
            return self.effective_date <= today
    
    @property
    def remaining_annual_limit(self):
        """Calculate remaining annual limit if applicable"""
        if not self.insurance_plan or not self.insurance_plan.annual_limit:
            return None  # Unlimited
        
        return self.insurance_plan.annual_limit - self.amount_used_this_year
    
    @property
    def remaining_consultations(self):
        """Calculate remaining consultations if limited"""
        if not self.insurance_plan or not self.insurance_plan.consultation_limit_per_year:
            return None  # Unlimited
        
        return self.insurance_plan.consultation_limit_per_year - self.consultations_used
    
    def verify_coverage(self):
        """Verify that insurance is valid and has available coverage"""
        errors = []
        
        if not self.is_valid:
            errors.append("Insurance is not active or has expired")
        
        if self.insurance_plan:
            if not self.insurance_plan.is_valid:
                errors.append("Insurance plan is no longer valid")
            
            remaining = self.remaining_annual_limit
            if remaining is not None and remaining <= 0:
                errors.append("Annual limit exceeded")
            
            remaining_consults = self.remaining_consultations
            if remaining_consults is not None and remaining_consults <= 0:
                errors.append("Consultation limit exceeded")
        
        if not self.insurance_company.is_contract_active:
            errors.append("Hospital contract with insurance company has expired")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors
        }
    
    def add_usage(self, amount, is_consultation=False):
        """Track usage of insurance"""
        self.amount_used_this_year += amount
        if is_consultation:
            self.consultations_used += 1
        self.save(update_fields=['amount_used_this_year', 'consultations_used'])
    
    def mark_as_verified(self, status="Verified"):
        """Mark insurance as verified"""
        self.last_verified_date = timezone.now().date()
        self.verification_status = status
        self.save(update_fields=['last_verified_date', 'verification_status'])



















