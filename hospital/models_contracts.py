"""
Contract and Certificate Management System
Track all contracts, agreements, and certificates with expiry alerts
"""
import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from datetime import timedelta
from .models import BaseModel


class ContractCategory(BaseModel):
    """Categories for organizing contracts"""
    CATEGORY_TYPES = [
        ('corporate', 'Corporate Contract'),
        ('insurance', 'Insurance Companies'),
        ('supplier', 'Suppliers/Vendors'),
        ('service', 'Service Providers'),
        ('employment', 'Employment Contracts'),
        ('lease', 'Lease/Rental'),
        ('maintenance', 'Maintenance Agreements'),
        ('partnership', 'Partnerships'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=200, unique=True)
    category_type = models.CharField(max_length=50, choices=CATEGORY_TYPES, default='other')
    description = models.TextField(blank=True)
    color_code = models.CharField(max_length=7, default='#3b82f6', help_text="Hex color for UI")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Contract Category'
        verbose_name_plural = 'Contract Categories'
    
    def __str__(self):
        return self.name


class Contract(BaseModel):
    """
    Contracts with external companies, vendors, and partners
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expiring_soon', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
        ('renewed', 'Renewed'),
    ]
    
    ALERT_PERIODS = [
        (7, '7 days before'),
        (14, '14 days before'),
        (30, '30 days before'),
        (60, '60 days before'),
        (90, '90 days before'),
    ]
    
    # Basic Information
    contract_number = models.CharField(max_length=100, unique=True, 
                                      help_text="Unique contract reference number")
    contract_name = models.CharField(max_length=300, 
                                    help_text="Name/Title of the contract")
    category = models.ForeignKey(ContractCategory, on_delete=models.PROTECT,
                                 related_name='contracts')
    
    # Parties Involved
    company_name = models.CharField(max_length=300, 
                                   help_text="Name of the other party (company/vendor)")
    company_contact_person = models.CharField(max_length=200, blank=True)
    company_phone = models.CharField(max_length=20, blank=True)
    company_email = models.EmailField(blank=True)
    company_address = models.TextField(blank=True)
    
    # Contract Details
    description = models.TextField(help_text="What this contract covers")
    value_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True,
                                      help_text="Contract value in GHS")
    payment_terms = models.CharField(max_length=200, blank=True,
                                    help_text="e.g., NET 30, Monthly, Quarterly")
    
    # Dates
    start_date = models.DateField(help_text="Contract start date")
    end_date = models.DateField(help_text="Contract end date")
    renewal_date = models.DateField(null=True, blank=True,
                                   help_text="Date for renewal consideration")
    
    # Status & Alerts
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    auto_renew = models.BooleanField(default=False, 
                                     help_text="Does this contract auto-renew?")
    alert_days_before = models.IntegerField(default=30, choices=ALERT_PERIODS,
                                           help_text="Alert X days before expiry")
    last_alert_sent = models.DateField(null=True, blank=True)
    
    # Documents
    contract_document = models.FileField(upload_to='contracts/', blank=True, null=True,
                                        validators=[FileExtensionValidator(['pdf', 'doc', 'docx'])],
                                        help_text="Upload contract PDF/DOC")
    supporting_documents = models.FileField(upload_to='contracts/supporting/', blank=True, null=True,
                                           help_text="Additional documents")
    
    # Responsible Person
    responsible_person = models.ForeignKey('auth.User', on_delete=models.SET_NULL, 
                                          null=True, blank=True,
                                          related_name='managed_contracts',
                                          help_text="Hospital staff responsible for this contract")
    
    # Notes
    notes = models.TextField(blank=True, help_text="Internal notes and comments")
    terms_and_conditions = models.TextField(blank=True)
    
    # Tracking
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
                                  null=True, related_name='created_contracts')
    
    class Meta:
        ordering = ['-end_date', '-start_date']
        verbose_name = 'Contract'
        verbose_name_plural = 'Contracts'
        indexes = [
            models.Index(fields=['contract_number']),
            models.Index(fields=['company_name']),
            models.Index(fields=['status']),
            models.Index(fields=['end_date']),
        ]
    
    def __str__(self):
        return f"{self.contract_number} - {self.contract_name}"
    
    @property
    def days_until_expiry(self):
        """Calculate days until contract expires"""
        if not self.end_date:
            return None
        
        today = timezone.now().date()
        delta = self.end_date - today
        return delta.days
    
    @property
    def is_expiring_soon(self):
        """Check if contract is expiring within alert period"""
        days = self.days_until_expiry
        if days is None:
            return False
        return 0 <= days <= self.alert_days_before
    
    @property
    def is_expired(self):
        """Check if contract has expired"""
        if not self.end_date:
            return False
        return self.end_date < timezone.now().date()
    
    @property
    def is_active_contract(self):
        """Check if contract is currently active"""
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date and self.status == 'active'
    
    def update_status(self):
        """Automatically update contract status based on dates"""
        if self.is_expired:
            self.status = 'expired'
        elif self.is_expiring_soon:
            self.status = 'expiring_soon'
        elif self.is_active_contract:
            self.status = 'active'
        self.save(update_fields=['status'])
    
    def send_expiry_alert(self):
        """Send expiry alert notification"""
        # This can be extended to send SMS/Email
        from .models_notification import Notification
        
        if self.is_expiring_soon and (not self.last_alert_sent or 
                                     (timezone.now().date() - self.last_alert_sent).days >= 7):
            Notification.objects.create(
                recipient=self.responsible_person,
                title=f'Contract Expiring Soon: {self.contract_name}',
                message=f'Contract with {self.company_name} expires in {self.days_until_expiry} days on {self.end_date}',
                notification_type='contract_expiry',
                priority='high',
            )
            self.last_alert_sent = timezone.now().date()
            self.save(update_fields=['last_alert_sent'])


class Certificate(BaseModel):
    """
    Certificates, licenses, accreditations, and compliance documents
    """
    CERTIFICATE_TYPES = [
        ('license', 'Operating License'),
        ('accreditation', 'Accreditation'),
        ('certification', 'Certification'),
        ('permit', 'Permit'),
        ('registration', 'Registration'),
        ('insurance', 'Insurance Policy'),
        ('compliance', 'Compliance Document'),
        ('quality', 'Quality Certification'),
        ('staff', 'Staff License/Certification'),
        ('equipment', 'Equipment Certification'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('valid', 'Valid'),
        ('expiring_soon', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('pending_renewal', 'Pending Renewal'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Basic Information
    certificate_number = models.CharField(max_length=100, unique=True,
                                         help_text="Certificate/License number")
    certificate_name = models.CharField(max_length=300)
    certificate_type = models.CharField(max_length=50, choices=CERTIFICATE_TYPES, default='other')
    
    # Issuing Authority
    issuing_authority = models.CharField(max_length=300,
                                        help_text="Organization that issued this certificate")
    authority_contact = models.CharField(max_length=200, blank=True)
    authority_phone = models.CharField(max_length=20, blank=True)
    authority_email = models.EmailField(blank=True)
    
    # Details
    description = models.TextField(help_text="What this certificate covers")
    scope = models.TextField(blank=True, help_text="Scope of certification/license")
    
    # Dates
    issue_date = models.DateField(help_text="Date certificate was issued")
    expiry_date = models.DateField(help_text="Date certificate expires")
    renewal_date = models.DateField(null=True, blank=True,
                                   help_text="When to start renewal process")
    
    # Status & Alerts
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='valid')
    alert_days_before = models.IntegerField(default=60,
                                           help_text="Alert X days before expiry")
    last_alert_sent = models.DateField(null=True, blank=True)
    
    # Documents
    certificate_document = models.FileField(upload_to='certificates/', blank=True, null=True,
                                           validators=[FileExtensionValidator(['pdf', 'jpg', 'jpeg', 'png'])],
                                           help_text="Upload certificate scan/PDF")
    supporting_documents = models.FileField(upload_to='certificates/supporting/', 
                                           blank=True, null=True)
    
    # Related Entities
    staff_member = models.ForeignKey('Staff', on_delete=models.SET_NULL, 
                                    null=True, blank=True,
                                    related_name='certificates',
                                    help_text="If this is a staff member's certificate")
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL,
                                null=True, blank=True,
                                related_name='certificates',
                                help_text="If linked to a contract")
    
    # Responsible Person
    responsible_person = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
                                          null=True, blank=True,
                                          related_name='managed_certificates',
                                          help_text="Person responsible for renewal")
    
    # Notes
    notes = models.TextField(blank=True)
    renewal_process = models.TextField(blank=True, 
                                      help_text="Steps required for renewal")
    
    # Tracking
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
                                  null=True, related_name='created_certificates')
    
    class Meta:
        ordering = ['expiry_date', 'certificate_name']
        verbose_name = 'Certificate'
        verbose_name_plural = 'Certificates'
        indexes = [
            models.Index(fields=['certificate_number']),
            models.Index(fields=['certificate_type']),
            models.Index(fields=['status']),
            models.Index(fields=['expiry_date']),
        ]
    
    def __str__(self):
        return f"{self.certificate_name} ({self.certificate_number})"
    
    @property
    def days_until_expiry(self):
        """Calculate days until certificate expires"""
        if not self.expiry_date:
            return None
        
        today = timezone.now().date()
        delta = self.expiry_date - today
        return delta.days
    
    @property
    def is_expiring_soon(self):
        """Check if certificate is expiring within alert period"""
        days = self.days_until_expiry
        if days is None:
            return False
        return 0 <= days <= self.alert_days_before
    
    @property
    def is_expired(self):
        """Check if certificate has expired"""
        if not self.expiry_date:
            return False
        return self.expiry_date < timezone.now().date()
    
    @property
    def is_valid(self):
        """Check if certificate is currently valid"""
        today = timezone.now().date()
        return self.issue_date <= today <= self.expiry_date and self.status == 'valid'
    
    def update_status(self):
        """Automatically update certificate status based on dates"""
        if self.is_expired:
            self.status = 'expired'
        elif self.is_expiring_soon:
            self.status = 'expiring_soon'
        elif self.is_valid:
            self.status = 'valid'
        self.save(update_fields=['status'])
    
    def send_expiry_alert(self):
        """Send expiry alert notification"""
        from .models_notification import Notification
        
        if self.is_expiring_soon and (not self.last_alert_sent or 
                                     (timezone.now().date() - self.last_alert_sent).days >= 7):
            Notification.objects.create(
                recipient=self.responsible_person,
                title=f'Certificate Expiring Soon: {self.certificate_name}',
                message=f'{self.certificate_type} expires in {self.days_until_expiry} days on {self.expiry_date}',
                notification_type='certificate_expiry',
                priority='high',
            )
            self.last_alert_sent = timezone.now().date()
            self.save(update_fields=['last_alert_sent'])


class ContractRenewal(BaseModel):
    """Track contract renewal history"""
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, 
                                related_name='renewals')
    
    # Renewal Details
    previous_end_date = models.DateField(help_text="Previous contract end date")
    new_end_date = models.DateField(help_text="New contract end date")
    renewal_date = models.DateField(default=timezone.now, 
                                   help_text="Date renewal was processed")
    
    # Financial Changes
    previous_value = models.DecimalField(max_digits=15, decimal_places=2, 
                                        null=True, blank=True)
    new_value = models.DecimalField(max_digits=15, decimal_places=2,
                                   null=True, blank=True)
    
    # Renewal Terms
    changes_made = models.TextField(blank=True, 
                                   help_text="What changed in the renewal")
    renewal_document = models.FileField(upload_to='contracts/renewals/', 
                                       blank=True, null=True)
    
    # Processed By
    processed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
                                    null=True, related_name='processed_renewals')
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-renewal_date']
        verbose_name = 'Contract Renewal'
        verbose_name_plural = 'Contract Renewals'
    
    def __str__(self):
        return f"Renewal: {self.contract.contract_name} - {self.renewal_date}"























