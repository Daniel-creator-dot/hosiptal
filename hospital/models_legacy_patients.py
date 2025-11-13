"""
Legacy Patient Data Model
For the imported patient_data table (35,019 records)
"""

from django.db import models


class LegacyPatient(models.Model):
    """
    Legacy patient records imported from patient_data table
    This is READ-ONLY - represents data from the old hospital system
    """
    
    # Primary keys
    id = models.AutoField(primary_key=True)
    pid = models.IntegerField(default=0, verbose_name="Patient ID")
    
    # Personal Information
    title = models.CharField(max_length=255, blank=True, default='')
    fname = models.CharField(max_length=255, default='', verbose_name="First Name")
    lname = models.CharField(max_length=255, default='', verbose_name="Last Name")
    mname = models.CharField(max_length=255, blank=True, default='', verbose_name="Middle Name")
    DOB = models.CharField(max_length=50, blank=True, null=True, verbose_name="Date of Birth")
    sex = models.CharField(max_length=50, blank=True, default='', verbose_name="Gender")
    
    # Contact Information
    phone_home = models.CharField(max_length=255, blank=True, default='')
    phone_biz = models.CharField(max_length=255, blank=True, default='')
    phone_contact = models.CharField(max_length=255, blank=True, default='')
    phone_cell = models.CharField(max_length=255, blank=True, default='', verbose_name="Mobile Phone")
    email = models.CharField(max_length=255, blank=True, default='')
    email_direct = models.CharField(max_length=255, blank=True, default='')
    
    # Address
    street = models.CharField(max_length=255, blank=True, default='')
    city = models.CharField(max_length=255, blank=True, default='')
    state = models.CharField(max_length=255, blank=True, default='')
    postal_code = models.CharField(max_length=255, blank=True, default='')
    country_code = models.CharField(max_length=255, blank=True, default='')
    county = models.CharField(max_length=40, blank=True, default='')
    
    # Guardian/Emergency Contact
    guardiansname = models.TextField(blank=True, null=True, verbose_name="Guardian Name")
    guardianphone = models.TextField(blank=True, null=True, verbose_name="Guardian Phone")
    guardianemail = models.TextField(blank=True, null=True, verbose_name="Guardian Email")
    guardianrelationship = models.TextField(blank=True, null=True)
    contact_relationship = models.CharField(max_length=255, blank=True, default='')
    mothersname = models.CharField(max_length=255, blank=True, default='')
    
    # Registration
    date = models.CharField(max_length=50, blank=True, null=True, verbose_name="Registration Date")
    regdate = models.TextField(blank=True, null=True)
    pubpid = models.CharField(max_length=255, blank=True, default='', verbose_name="Public ID")
    
    # Provider/Referral
    providerID = models.IntegerField(null=True, blank=True, verbose_name="Provider ID")
    ref_providerID = models.IntegerField(null=True, blank=True, verbose_name="Referring Provider")
    referrer = models.CharField(max_length=255, blank=True, default='')
    referrerID = models.CharField(max_length=255, blank=True, default='')
    referral_source = models.CharField(max_length=30, blank=True, default='')
    
    # Insurance/Financial
    financial = models.CharField(max_length=255, blank=True, default='')
    pricelevel = models.CharField(max_length=200, default='standard', verbose_name="Price Level")
    status = models.CharField(max_length=255, blank=True, default='')
    billing_note = models.TextField(blank=True, null=True)
    
    # Medical
    race = models.CharField(max_length=255, blank=True, default='')
    ethnicity = models.CharField(max_length=255, blank=True, default='')
    religion = models.CharField(max_length=40, blank=True, default='')
    language = models.CharField(max_length=255, blank=True, default='')
    
    # HIPAA/Privacy
    hipaa_allowsms = models.CharField(max_length=3, default='NO')
    hipaa_allowemail = models.CharField(max_length=3, default='NO')
    allow_patient_portal = models.CharField(max_length=31, blank=True, default='')
    
    # Other fields
    drivers_license = models.CharField(max_length=255, blank=True, default='')
    ss = models.CharField(max_length=255, blank=True, default='', verbose_name="Social Security")
    occupation = models.TextField(blank=True, null=True)
    pharmacy_id = models.IntegerField(default=0)
    deceased_date = models.CharField(max_length=50, blank=True, null=True)
    deceased_reason = models.CharField(max_length=255, blank=True, default='')
    
    # System fields
    reg_type = models.TextField(blank=True, null=True)
    nia_pin = models.TextField(blank=True, null=True)
    pmc_mrn = models.CharField(max_length=50, blank=True, null=True, verbose_name="PMC MRN")
    
    class Meta:
        db_table = 'patient_data'
        managed = False  # Don't let Django manage this table (it's legacy data)
        verbose_name = 'Legacy Patient'
        verbose_name_plural = 'Legacy Patients'
        ordering = ['lname', 'fname']
    
    def __str__(self):
        return f"{self.fname} {self.lname} (PID: {self.pid})"
    
    @property
    def full_name(self):
        """Get full name"""
        parts = [self.fname, self.mname, self.lname]
        return ' '.join(p for p in parts if p).strip()
    
    @property
    def display_phone(self):
        """Get primary phone number"""
        return self.phone_cell or self.phone_home or self.phone_contact or ''
    
    @property
    def mrn_display(self):
        """Get MRN with PMC prefix"""
        if self.pmc_mrn:
            return self.pmc_mrn
        else:
            # Fallback to PID format if pmc_mrn not set
            return f"PMC-LEG-{self.pid:06d}" if self.pid else f"PMC-LEG-{self.id:06d}"

