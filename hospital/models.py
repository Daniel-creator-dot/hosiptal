import uuid
import secrets
import json
import re
import hashlib
from datetime import date
from io import BytesIO
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from model_utils.models import TimeStampedModel
from django.db.models import Q, Sum
from django.core.files.base import ContentFile
from PIL import Image, ImageOps
import qrcode

# Import login attempts model
from .models_login_attempts import LoginAttempt


class BaseModel(TimeStampedModel):
    """Base model with UUID primary key and soft delete"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        abstract = True


class UserSession(BaseModel):
    """
    Tracks user login sessions for auditing.
    One record per browser/session_key; closed when user logs out or times out.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=40, db_index=True)
    login_time = models.DateTimeField(default=timezone.now)
    logout_time = models.DateTimeField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    is_locum = models.BooleanField(default=False, help_text='Mark as locum/visiting staff for payment tracking')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f"Session {self.session_key} for {self.user.username}"

    def end(self):
        """Mark this session as ended."""
        if not self.logout_time:
            self.logout_time = timezone.now()
        self.is_active = False
        self.save(update_fields=['logout_time', 'is_active', 'modified'])


# ==================== PATIENT & EMR MODULE ====================

class Patient(BaseModel):
    """Patient registration and demographics"""
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    BLOOD_TYPE_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-'),
    ]
    
    mrn = models.CharField(max_length=20, unique=True, default='', verbose_name="Medical Record Number")
    national_id = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="National ID")
    first_name = models.CharField(max_length=100, default='')
    last_name = models.CharField(max_length=100, default='')
    middle_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(default='2000-01-01')
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='M')
    blood_type = models.CharField(max_length=3, choices=BLOOD_TYPE_CHOICES, blank=True)
    
    # Updated phone regex to accept Ghana numbers (024, 050, 020, etc.) and international format
    # Accepts: 0241234567, +233241234567, 233241234567, or any 9-15 digit number
    phone_regex = RegexValidator(regex=r'^(\+?233|0)?[0-9]{9,15}$', message="Phone number must be entered in the format: '+233241234567' or '0241234567'. Up to 15 digits allowed.")
    phone_number = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(default='')
    
    # Emergency contact
    next_of_kin_name = models.CharField(max_length=100, default='')
    next_of_kin_phone = models.CharField(validators=[phone_regex], max_length=17, blank=True, default='')
    next_of_kin_relationship = models.CharField(max_length=50, default='')
    
    # Medical information
    allergies = models.TextField(blank=True)
    chronic_conditions = models.TextField(blank=True)
    medications = models.TextField(blank=True)
    
    # Insurance information (primary payer)
    primary_insurance = models.ForeignKey('Payer', on_delete=models.SET_NULL, null=True, blank=True, related_name='primary_patients')
    insurance_company = models.CharField(max_length=200, blank=True, verbose_name="Insurance Company Name")
    insurance_id = models.CharField(max_length=100, blank=True, verbose_name="Insurance ID/Policy Number")
    insurance_member_id = models.CharField(max_length=100, blank=True, verbose_name="Insurance Member ID")
    insurance_policy_number = models.CharField(max_length=100, blank=True, verbose_name="Policy Number (Legacy)")
    insurance_group_number = models.CharField(max_length=100, blank=True, verbose_name="Group Number")
    
    # Profile picture
    profile_picture = models.ImageField(upload_to='patient_profiles/', blank=True, null=True)
    
    # Optional notes (e.g. cash receiving point, admin notes)
    notes = models.TextField(blank=True, default='', null=True)
    
    class Meta:
        ordering = ['last_name', 'first_name']
        # Add indexes to speed up duplicate detection queries
        indexes = [
            models.Index(fields=['first_name', 'last_name', 'date_of_birth'], name='patient_name_dob_idx'),
            models.Index(fields=['first_name', 'last_name', 'phone_number'], name='patient_name_phone_idx'),
            models.Index(fields=['email'], name='patient_email_idx'),
            models.Index(fields=['national_id'], name='patient_national_id_idx'),
            models.Index(fields=['phone_number'], name='patient_phone_idx'),
        ]
        # Database-level guard against rapid duplicate patient creation
        # NOTE: This constraint is commented out as it's too strict and blocks legitimate registrations
        # (e.g., family members sharing phone numbers). Duplicate prevention is handled in model.save() instead.
        # constraints = [
        #     models.UniqueConstraint(
        #         fields=['first_name', 'last_name', 'phone_number', 'date_of_birth'],
        #         condition=models.Q(is_deleted=False) & ~models.Q(date_of_birth='2000-01-01'),
        #         name='uniq_patient_name_phone_dob_active'
        #     ),
        # ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.mrn})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.middle_name} {self.last_name}".strip()
    
    @property
    def age(self):
        today = timezone.now().date()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
    
    @property
    def deposit_balance(self):
        """Get total available deposit balance for this patient (all active deposits add up, bank-style)."""
        try:
            from .models_patient_deposits import PatientDeposit
            from decimal import Decimal
            result = PatientDeposit.objects.filter(
                patient=self,
                status='active',
                is_deleted=False
            ).aggregate(total=Sum('available_balance'))
            return result['total'] or Decimal('0.00')
        except Exception:
            from decimal import Decimal
            return Decimal('0.00')
    
    def save(self, *args, **kwargs):
        """Auto-generate Patient ID (MRN) if not provided
        CRITICAL: Also checks for duplicates BEFORE saving (final safety net)
        Handles duplicate MRN errors with retry logic for concurrent environments
        """
        from django.db import IntegrityError, transaction
        import time
        import logging
        
        logger = logging.getLogger(__name__)
        
        is_new = self.pk is None
        
        # Normalize national_id: convert empty strings to None (for unique constraint)
        if self.national_id == '':
            self.national_id = None
        
        # CRITICAL: Check for duplicates BEFORE saving (catches API, admin, and any other bypasses)
        # Use savepoint to allow nested transactions (if called from within a transaction)
        if is_new:  # Only check for new patients
            def normalize_phone(phone):
                if not phone:
                    return ''
                phone = str(phone).strip()
                phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
                if phone.startswith('0') and len(phone) == 10:
                    phone = '233' + phone[1:]
                elif phone.startswith('+'):
                    phone = phone[1:]
                return phone
            
            normalized_phone = normalize_phone(self.phone_number)
            
            # CRITICAL: Use savepoint to handle nested transactions properly
            # If we're already in a transaction, use savepoint; otherwise create new transaction
            try:
                # Check if we're already in a transaction
                from django.db import connection
                in_transaction = connection.in_atomic_block
            except:
                in_transaction = False
            
            if in_transaction:
                # Already in transaction - use savepoint for duplicate checks
                sid = transaction.savepoint()
                try:
                    # RELAXED: Only check for strong duplicates (name + DOB + phone)
                    # Phone-only or name-only matches are allowed (family members can share phones/names)
                    # CRITICAL FIX: Exclude current instance (self.pk) to prevent false positives
                    # For new patients (is_new=True), self.pk is None, so exclude(None) does nothing (safe)
                    # For existing patients, this prevents matching against itself during updates
                    exclude_current = {} if is_new else {'pk': self.pk}
                    
                    if self.first_name and self.last_name and normalized_phone and self.date_of_birth and self.date_of_birth != '2000-01-01':
                        # Strong match: name + DOB + phone - this is likely a duplicate
                        candidates = Patient.objects.select_for_update().filter(
                            first_name__iexact=self.first_name,
                            last_name__iexact=self.last_name,
                            date_of_birth=self.date_of_birth,
                            is_deleted=False
                        ).exclude(**exclude_current)
                        
                        for candidate in candidates:
                            existing_normalized = normalize_phone(candidate.phone_number)
                            if existing_normalized == normalized_phone:
                                logger.error(
                                    f"DUPLICATE PATIENT BLOCKED IN MODEL.SAVE(): "
                                    f"Trying to create {self.first_name} {self.last_name} with phone {self.phone_number} and DOB {self.date_of_birth}, "
                                    f"but {candidate.mrn} already exists!"
                                )
                                from django.core.exceptions import ValidationError
                                raise ValidationError(
                                    f"Duplicate patient detected! A patient with the same name ({self.first_name} {self.last_name}), "
                                    f"date of birth ({self.date_of_birth}), and phone number ({self.phone_number}) already exists. MRN: {candidate.mrn}"
                                )
                    
                    # Check by email
                    if self.email:
                        existing = Patient.objects.select_for_update().filter(
                            email__iexact=self.email,
                            is_deleted=False
                        ).exclude(**exclude_current).first()
                        if existing:
                            logger.error(
                                f"DUPLICATE PATIENT BLOCKED IN MODEL.SAVE(): "
                                f"Trying to create patient with email {self.email}, "
                                f"but {existing.mrn} already exists!"
                            )
                            from django.core.exceptions import ValidationError
                            raise ValidationError(
                                f"Duplicate patient detected! A patient with email {self.email} already exists. MRN: {existing.mrn}"
                            )
                    
                    # Check by national_id
                    if self.national_id:
                        existing = Patient.objects.select_for_update().filter(
                            national_id=self.national_id,
                            is_deleted=False
                        ).exclude(**exclude_current).first()
                        if existing:
                            logger.error(
                                f"DUPLICATE PATIENT BLOCKED IN MODEL.SAVE(): "
                                f"Trying to create patient with national_id {self.national_id}, "
                                f"but {existing.mrn} already exists!"
                            )
                            from django.core.exceptions import ValidationError
                            raise ValidationError(
                                f"Duplicate patient detected! A patient with National ID {self.national_id} already exists. MRN: {existing.mrn}"
                            )
                    
                    # All checks passed - release savepoint
                    transaction.savepoint_commit(sid)
                except ValidationError:
                    # Rollback savepoint and re-raise
                    transaction.savepoint_rollback(sid)
                    raise
            else:
                # Not in transaction - create new transaction for duplicate checks
                with transaction.atomic():
                    # RELAXED: Only check for strong duplicates (name + DOB + phone)
                    # Phone-only or name-only matches are allowed (family members can share phones/names)
                    # CRITICAL FIX: Exclude current instance (self.pk) to prevent false positives
                    # For new patients (is_new=True), self.pk is None, so exclude(None) does nothing (safe)
                    # For existing patients, this prevents matching against itself during updates
                    exclude_current = {} if is_new else {'pk': self.pk}
                    
                    if self.first_name and self.last_name and normalized_phone and self.date_of_birth and self.date_of_birth != '2000-01-01':
                        # Strong match: name + DOB + phone - this is likely a duplicate
                        candidates = Patient.objects.select_for_update().filter(
                            first_name__iexact=self.first_name,
                            last_name__iexact=self.last_name,
                            date_of_birth=self.date_of_birth,
                            is_deleted=False
                        ).exclude(**exclude_current)
                        
                        for candidate in candidates:
                            existing_normalized = normalize_phone(candidate.phone_number)
                            if existing_normalized == normalized_phone:
                                logger.error(
                                    f"DUPLICATE PATIENT BLOCKED IN MODEL.SAVE(): "
                                    f"Trying to create {self.first_name} {self.last_name} with phone {self.phone_number} and DOB {self.date_of_birth}, "
                                    f"but {candidate.mrn} already exists!"
                                )
                                from django.core.exceptions import ValidationError
                                raise ValidationError(
                                    f"Duplicate patient detected! A patient with the same name ({self.first_name} {self.last_name}), "
                                    f"date of birth ({self.date_of_birth}), and phone number ({self.phone_number}) already exists. MRN: {candidate.mrn}"
                                )
                    
                    # Check by email
                    if self.email:
                        existing = Patient.objects.select_for_update().filter(
                            email__iexact=self.email,
                            is_deleted=False
                        ).exclude(**exclude_current).first()
                        if existing:
                            logger.error(
                                f"DUPLICATE PATIENT BLOCKED IN MODEL.SAVE(): "
                                f"Trying to create patient with email {self.email}, "
                                f"but {existing.mrn} already exists!"
                            )
                            from django.core.exceptions import ValidationError
                            raise ValidationError(
                                f"Duplicate patient detected! A patient with email {self.email} already exists. MRN: {existing.mrn}"
                            )
                    
                    # Check by national_id
                    if self.national_id:
                        existing = Patient.objects.select_for_update().filter(
                            national_id=self.national_id,
                            is_deleted=False
                        ).exclude(**exclude_current).first()
                        if existing:
                            logger.error(
                                f"DUPLICATE PATIENT BLOCKED IN MODEL.SAVE(): "
                                f"Trying to create patient with national_id {self.national_id}, "
                                f"but {existing.mrn} already exists!"
                            )
                            from django.core.exceptions import ValidationError
                            raise ValidationError(
                                f"Duplicate patient detected! A patient with National ID {self.national_id} already exists. MRN: {existing.mrn}"
                            )
        
        # Generate MRN if not provided
        if not self.mrn or self.mrn == '':
            self.mrn = self.generate_mrn()
        
        # CRITICAL: Only save once - remove duplicate save logic that was causing duplicates
        # Retry logic for handling duplicate MRN errors (race conditions)
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                super().save(*args, **kwargs)
                # If save successful, break out of retry loop - DO NOT SAVE AGAIN
                break
            except IntegrityError as e:
                # Check if it's a duplicate MRN error
                error_str = str(e).lower()
                if 'mrn' in error_str or 'unique' in error_str:
                    retry_count += 1
                    if retry_count >= max_retries:
                        # Last retry failed, raise the error
                        raise
                    # Generate a new MRN and retry
                    self.mrn = self.generate_mrn()
                    # Small delay to reduce collision probability
                    time.sleep(0.1 * retry_count)
                else:
                    # Not a duplicate MRN error, re-raise
                    raise
        
        # REMOVED: The duplicate save logic below was causing patients to be saved twice
        # The MRN is already generated above and saved in the main save() call
        # No need for additional save() calls that could trigger duplicate creation
    
    @staticmethod
    def generate_mrn():
        """Generate a unique Patient ID (Medical Record Number) for PrimeCare Medical Center
        Uses database-level locking to prevent race conditions in concurrent environments (Docker, etc.)
        """
        from datetime import datetime
        from django.db import transaction
        from django.db.models import F
        
        prefix = "PMC"  # PrimeCare Medical Center
        year = datetime.now().year
        
        # Use database-level locking to prevent race conditions
        # This is critical for Docker environments with multiple workers
        with transaction.atomic():
            # Use SELECT FOR UPDATE to lock the row and prevent concurrent access
            last_patient = Patient.objects.filter(
                mrn__startswith=f"{prefix}{year}",
                is_deleted=False
            ).select_for_update().order_by('-mrn').first()
            
            if last_patient and last_patient.mrn:
                try:
                    last_num = int(last_patient.mrn.replace(f"{prefix}{year}", ""))
                    new_num = last_num + 1
                except ValueError:
                    new_num = 1
            else:
                new_num = 1
            
            # Check if the generated MRN already exists (safety check)
            max_retries = 10
            retry_count = 0
            while retry_count < max_retries:
                candidate_mrn = f"{prefix}{year}{new_num:06d}"
                if not Patient.objects.filter(mrn=candidate_mrn, is_deleted=False).exists():
                    return candidate_mrn
                # If exists, increment and try again
                new_num += 1
                retry_count += 1
            
            # Fallback: use timestamp-based suffix if all sequential numbers are taken
            import time
            timestamp_suffix = str(int(time.time()))[-4:]  # Last 4 digits of timestamp
            return f"{prefix}{year}{new_num:06d}{timestamp_suffix}"
    
    def get_active_encounters(self):
        """Get all active encounters for this patient"""
        return self.encounters.filter(status='active', is_deleted=False)
    
    def get_total_invoice_amount(self):
        """Get total amount from all invoices"""
        result = self.invoices.filter(is_deleted=False).aggregate(
            total=Sum('total_amount')
        )
        return result['total'] or 0
    
    def get_outstanding_balance(self):
        """Get total outstanding balance. Uses app-wide patient_outstanding_service so same as everywhere."""
        try:
            from hospital.services.patient_outstanding_service import get_patient_outstanding
            return get_patient_outstanding(self)['total_outstanding']
        except Exception:
            result = self.invoices.filter(
                is_deleted=False,
                status__in=['issued', 'partially_paid', 'overdue']
            ).aggregate(total=Sum('balance'))
            return result['total'] or 0
    
    def get_active_insurance(self):
        """Get active insurance information"""
        from .models_insurance import PatientInsurance
        from django.db.models import Q
        return PatientInsurance.objects.filter(
            patient=self,
            is_active=True,
            is_deleted=False
        ).filter(
            effective_date__lte=timezone.now().date()
        ).filter(
            Q(expiry_date__isnull=True) | Q(expiry_date__gte=timezone.now().date())
        ).order_by('priority_order').first()
    
    def has_insurance(self):
        """Check if patient has active insurance"""
        insurance = self.get_active_insurance()
        return insurance is not None
    
    def ensure_qr_profile(self, regenerate=False):
        """Ensure patient has an active QR profile for ID cards"""
        qr_profile, _ = PatientQRCode.objects.get_or_create(patient=self)
        if regenerate or not qr_profile.qr_code_image or not qr_profile.qr_token:
            qr_profile.refresh_qr(force_token=True)
        return qr_profile


class PatientQRCode(BaseModel):
    """Secure QR code profile for patient ID cards"""
    QR_PREFIX = "PCMCARD"
    MRN_PATTERN = re.compile(r'PMC\d{6,}', re.IGNORECASE)
    TOKEN_PATTERN = re.compile(r'[A-Za-z0-9]{8,64}')
    
    patient = models.OneToOneField(
        Patient,
        on_delete=models.CASCADE,
        related_name='qr_profile'
    )
    # CRITICAL: qr_token must be unique - always generate on save if missing (blank=True allows empty during creation)
    qr_token = models.CharField(max_length=64, unique=True, blank=True)
    qr_code_data = models.TextField(blank=True)  # Changed to TextField to support longer payloads
    qr_code_image = models.ImageField(upload_to='patient_qr_codes/', null=True, blank=True)
    scan_count = models.PositiveIntegerField(default=0)
    last_generated_at = models.DateTimeField(null=True, blank=True)
    last_scanned_at = models.DateTimeField(null=True, blank=True)
    last_scanned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='patient_qr_scans'
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created']
        verbose_name = "Patient QR Code"
        verbose_name_plural = "Patient QR Codes"
    
    def __str__(self):
        return f"QR Card - {self.patient.full_name} ({self.patient.mrn})"
    
    def build_payload(self):
        """Return the encoded payload for the QR card with secure authentication"""
        # Create a structured, secure payload with authentication hash
        payload_data = {
            'patient_uuid': str(self.patient_id),
            'mrn': self.patient.mrn,
            'token': self.qr_token or secrets.token_urlsafe(16),
            'v': '2'  # Version 2 for enhanced authentication
        }
        
        # Generate authentication hash for security
        auth_string = f"{payload_data['patient_uuid']}:{payload_data['token']}:{payload_data['mrn']}"
        payload_data['hash'] = hashlib.sha256(auth_string.encode()).hexdigest()[:16]
        
        # Return as compact JSON for QR encoding efficiency
        return json.dumps(payload_data, separators=(',', ':'))
    
    def refresh_qr(self, force_token=False, save=True):
        """Generate or refresh the QR credentials and image with enhanced security"""
        # CRITICAL: Always ensure token exists (required for unique constraint)
        if force_token or not self.qr_token or self.qr_token == '':
            self.qr_token = secrets.token_urlsafe(32)  # Longer token for better security
        
        # Store structured payload with authentication
        self.qr_code_data = self.build_payload()
        self.last_generated_at = timezone.now()
        self.is_active = True
        self._generate_qr_image()
        if save:
            self.save()
    
    def _generate_qr_image(self):
        """Render a high-contrast, professional QR code image optimized for printing and scanning."""
        qr = qrcode.QRCode(
            version=None,  # Auto-select optimal version for payload
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # Highest error correction for durability
            box_size=14,  # Larger boxes for better scanning reliability
            border=4,  # Quiet zone for better scanning
        )
        qr.add_data(self.qr_code_data)
        qr.make(fit=True)

        # Create high-contrast QR image
        pil_img = qr.make_image(fill_color="#000000", back_color="#FFFFFF").get_image()
        
        # Add white border for better scanning (quiet zone)
        pil_img = ImageOps.expand(pil_img, border=20, fill="#FFFFFF")

        # High-resolution for printing (1200x1200 for crisp printing)
        target_size = 1200
        if pil_img.size[0] != target_size:
            pil_img = pil_img.resize((target_size, target_size), Image.LANCZOS)  # Better quality resampling

        buffer = BytesIO()
        pil_img.save(buffer, format="PNG", optimize=True, dpi=(300, 300))  # Print quality
        buffer.seek(0)
        filename = f"patient_card_{self.patient.mrn or self.patient.id}_{int(timezone.now().timestamp())}.png"
        self.qr_code_image.save(filename, ContentFile(buffer.getvalue()), save=False)
        buffer.close()
    
    def save(self, *args, **kwargs):
        """Ensure qr_token is always set before saving"""
        # CRITICAL: Generate token if missing to prevent unique constraint violations
        if not self.qr_token or self.qr_token == '':
            self.qr_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)
    
    def mark_scan(self, user=None, save=True):
        """Record a QR scan event for audit"""
        self.scan_count = (self.scan_count or 0) + 1
        self.last_scanned_at = timezone.now()
        self.last_scanned_by = user
        if save:
            self.save(update_fields=['scan_count', 'last_scanned_at', 'last_scanned_by', 'modified'])
    
    @staticmethod
    def _try_parse_uuid(value):
        if not value:
            return None
        try:
            return uuid.UUID(str(value).strip())
        except (ValueError, AttributeError, TypeError):
            return None
    
    @classmethod
    def parse_qr_payload(cls, payload):
        """
        SIMPLIFIED: Parse QR payload - just extract patient UUID from any format.
        Supports: direct UUID, JSON with patient_uuid, pipe-delimited, MRN lookup.
        """
        result = {
            'raw': payload,
            'patient_uuid': None,
            'mrn': None,
            'token': None,
        }
        if not payload:
            return result
        
        payload = payload.strip()
        result['raw'] = payload
        
        # Method 1: Try direct UUID (most common case)
        maybe_uuid = cls._try_parse_uuid(payload)
        if maybe_uuid:
            result['patient_uuid'] = maybe_uuid
            return result
        
        # Method 2: Try JSON format (new structured format and backward compatibility)
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                result['patient_uuid'] = cls._try_parse_uuid(
                    parsed.get('patient_uuid') or parsed.get('patientId') or parsed.get('patient_id')
                )
                if parsed.get('mrn'):
                    result['mrn'] = str(parsed.get('mrn')).strip()
                if parsed.get('token'):
                    result['token'] = str(parsed.get('token')).strip()
                if parsed.get('hash'):
                    result['hash'] = str(parsed.get('hash')).strip()
                if parsed.get('v'):
                    result['version'] = str(parsed.get('v')).strip()
                return result
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        
        # Method 3: Pipe-delimited format (legacy)
        if '|' in payload:
            parts = [p.strip() for p in payload.split('|') if p.strip()]
            if parts and parts[0].upper() == cls.QR_PREFIX:
                parts = parts[1:]
            for part in parts:
                maybe_uuid = cls._try_parse_uuid(part)
                if maybe_uuid:
                    result['patient_uuid'] = maybe_uuid
                    break
                match = cls.MRN_PATTERN.search(part)
                if match:
                    result['mrn'] = match.group().upper()
            return result
        
        # Method 4: Extract UUID from anywhere in the string
        uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        uuid_match = re.search(uuid_pattern, payload, re.IGNORECASE)
        if uuid_match:
            result['patient_uuid'] = cls._try_parse_uuid(uuid_match.group())
            return result
        
        # Method 5: MRN pattern
        mrn_match = cls.MRN_PATTERN.search(payload)
        if mrn_match:
            result['mrn'] = mrn_match.group().upper()
        
        return result
    
    @classmethod
    def extract_patient_uuid(cls, payload):
        """Backward-compatible helper used by older code paths."""
        parsed = cls.parse_qr_payload(payload)
        return parsed.get('patient_uuid')
    
    @classmethod
    def find_by_qr_data(cls, scanned_data):
        """
        Robust lookup that supports multiple QR formats.
        """
        if not scanned_data:
            return None
        
        scanned_data = scanned_data.strip()
        parsed = cls.parse_qr_payload(scanned_data)
        
        # 1. Exact stored payload
        match = cls.objects.filter(qr_code_data=scanned_data, is_active=True).first()
        if match:
            return match
        
        # 2. Case-insensitive match
        match = cls.objects.filter(qr_code_data__iexact=scanned_data, is_active=True).first()
        if match:
            return match
        
        # 3. Token match
        token = parsed.get('token')
        if token:
            match = cls.objects.filter(qr_token=token, is_active=True).first()
            if match:
                return match
        
        # 4. Patient UUID match
        patient_uuid = parsed.get('patient_uuid')
        if patient_uuid:
            match = cls.objects.filter(patient_id=patient_uuid, is_active=True).first()
            if match:
                return match
        
        # 5. MRN match via patient relationship
        mrn = parsed.get('mrn')
        if mrn:
            patient = Patient.objects.filter(mrn__iexact=mrn, is_deleted=False).first()
            if patient and hasattr(patient, 'qr_profile'):
                return patient.qr_profile
        
        # 6. Partial match fallback
        return cls.objects.filter(qr_code_data__icontains=scanned_data, is_active=True).first()
    
    def verify_qr_data(self, scanned_data):
        """
        Enhanced QR verification with authentication hash validation.
        Supports both new structured format and legacy UUID-only format.
        """
        if not scanned_data:
            return False, "No QR data provided"
        
        scanned_data = scanned_data.strip()
        
        # Method 1: Exact match with stored qr_code_data
        if self.qr_code_data:
            if scanned_data == self.qr_code_data:
                return True, "QR data exact match"
            if scanned_data.lower() == self.qr_code_data.lower():
                return True, "QR data match (case-insensitive)"
        
        # Method 2: Parse structured payload (version 2 with hash)
        try:
            parsed_json = json.loads(scanned_data)
            if isinstance(parsed_json, dict):
                # Verify authentication hash
                if parsed_json.get('hash'):
                    auth_string = f"{parsed_json.get('patient_uuid')}:{parsed_json.get('token')}:{parsed_json.get('mrn')}"
                    expected_hash = hashlib.sha256(auth_string.encode()).hexdigest()[:16]
                    if parsed_json.get('hash') == expected_hash:
                        # Verify patient UUID matches
                        if str(parsed_json.get('patient_uuid')) == str(self.patient_id):
                            return True, "QR verified with authentication hash"
                
                # Fallback: verify UUID and token match
                if parsed_json.get('patient_uuid') == str(self.patient_id):
                    if parsed_json.get('token') == self.qr_token:
                        return True, "QR verified (UUID and token match)"
                    return True, "QR verified (UUID match, token not validated)"
        except (json.JSONDecodeError, TypeError, ValueError):
            pass  # Not JSON format, continue to other methods
        
        # Method 3: Extract UUID from scanned data and compare
        parsed = self.parse_qr_payload(scanned_data)
        patient_uuid = parsed.get('patient_uuid')
        
        if patient_uuid and str(patient_uuid) == str(self.patient_id):
            return True, "Patient UUID verified"
        
        # Method 4: Direct UUID comparison (backward compatibility)
        if str(self.patient_id) in scanned_data or scanned_data in str(self.patient_id):
            return True, "Patient UUID found in scanned data"
        
        # Method 5: MRN fallback
        mrn = parsed.get('mrn')
        if mrn and self.patient.mrn and mrn.upper() == self.patient.mrn.upper():
            return True, "Patient MRN verified"
        
        return False, f"QR verification failed - Patient UUID: {self.patient_id}, Scanned: {scanned_data[:50]}"


class Encounter(BaseModel):
    """Patient encounters/visits"""
    ENCOUNTER_TYPES = [
        ('outpatient', 'Outpatient'),
        ('specialist', 'Special Consultation'),
        ('antenatal', 'Antenatal'),
        ('gynae', 'Gynae / Special'),
        ('inpatient', 'Inpatient'),
        ('er', 'Emergency'),
        ('surgery', 'Surgery'),
        ('pre_employment', 'Pre-employment (Company)'),
        ('pre_admission', 'Pre-admission (School)'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='encounters')
    encounter_type = models.CharField(max_length=20, choices=ENCOUNTER_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    billing_closed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When set, no new invoice lines may be added for this encounter (e.g. after discharge).',
    )
    location = models.ForeignKey('Ward', on_delete=models.SET_NULL, null=True, blank=True)
    provider = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True, blank=True)
    chief_complaint = models.TextField()
    diagnosis = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    # Note: This field requires migration 0015 to be applied
    # Run: python manage.py migrate
    current_activity = models.CharField(max_length=50, blank=True, null=True, help_text='Current department activity: Consulting, Lab, Pharmacy', db_column='current_activity')
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['patient', 'status', 'is_deleted']),
            models.Index(fields=['status', 'is_deleted']),
            models.Index(fields=['provider', 'status', 'is_deleted']),
            models.Index(fields=['started_at']),
        ]
    
    def __str__(self):
        # Include time to make duplicates distinguishable
        if self.started_at:
            time_str = self.started_at.strftime('%Y-%m-%d %H:%M')
        else:
            time_str = self.created.strftime('%Y-%m-%d %H:%M') if self.created else 'Unknown'
        return f"{self.patient.full_name} - {self.get_encounter_type_display()} ({time_str})"
    
    def save(self, *args, **kwargs):
        """Override save to prevent duplicate encounters and ensure required fields"""
        # CRITICAL: Ensure chief_complaint is not empty (required field)
        if not self.chief_complaint or not self.chief_complaint.strip():
            if hasattr(self, '_state') and self._state.adding:
                # New encounter - must have chief_complaint
                self.chief_complaint = 'Consultation in progress'  # Default value
            elif self.pk:
                # Existing encounter - preserve existing value if available
                try:
                    existing = Encounter.objects.get(pk=self.pk)
                    if existing.chief_complaint:
                        self.chief_complaint = existing.chief_complaint
                    else:
                        self.chief_complaint = 'Consultation in progress'
                except Encounter.DoesNotExist:
                    self.chief_complaint = 'Consultation in progress'
            else:
                self.chief_complaint = 'Consultation in progress'
        
        # Only check for duplicates on new objects
        if not self.pk:
            from django.db import transaction
            from django.core.exceptions import ValidationError
            
            # Use savepoint if already in transaction, otherwise create new transaction
            try:
                # Check if we're already in a transaction
                from django.db import connection
                from datetime import timedelta
                if connection.in_atomic_block:
                    # Already in transaction - just check for duplicates without creating new transaction
                    five_minutes_ago = timezone.now() - timedelta(minutes=5)
                    existing = Encounter.objects.select_for_update().filter(
                        patient=self.patient,
                        encounter_type=self.encounter_type,
                        chief_complaint=self.chief_complaint,
                        status='active',
                        started_at__gte=five_minutes_ago,
                        is_deleted=False
                    ).exclude(pk=self.pk).order_by('-created').first()
                    
                    if existing:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(
                            f"DUPLICATE ENCOUNTER BLOCKED IN MODEL.SAVE(): "
                            f"Trying to create encounter for {self.patient.full_name} "
                            f"but encounter {existing.id} already exists (created: {existing.created})"
                        )
                        # Instead of raising error, reuse existing encounter
                        # This prevents errors but still prevents duplicates
                        self.pk = existing.pk
                        self.id = existing.id
                        # Don't call super().save() - we're using the existing record
                        return
                else:
                    # Not in transaction - create one for duplicate check
                    with transaction.atomic():
                        from datetime import timedelta
                        five_minutes_ago = timezone.now() - timedelta(minutes=5)
                        existing = Encounter.objects.select_for_update().filter(
                            patient=self.patient,
                            encounter_type=self.encounter_type,
                            chief_complaint=self.chief_complaint,
                            status='active',
                            started_at__gte=five_minutes_ago,
                            is_deleted=False
                        ).exclude(pk=self.pk).order_by('-created').first()
                        
                        if existing:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.warning(
                                f"DUPLICATE ENCOUNTER BLOCKED IN MODEL.SAVE(): "
                                f"Trying to create encounter for {self.patient.full_name} "
                                f"but encounter {existing.id} already exists (created: {existing.created})"
                            )
                            # Instead of raising error, reuse existing encounter
                            self.pk = existing.pk
                            self.id = existing.id
                            # Don't call super().save() - we're using the existing record
                            return
            except Exception as e:
                # If duplicate check fails, log but continue with save
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error during duplicate check in Encounter.save(): {str(e)}")
                # Continue with normal save
        
        super().save(*args, **kwargs)
    
    def complete(self):
        """Mark encounter as completed"""
        if self.status != 'completed':
            self.status = 'completed'
            self.ended_at = timezone.now()
            self.save()
    
    def update_activity(self, activity_type):
        """Update current department activity"""
        # Check if field exists in database (migration might not be applied yet)
        try:
            activity_mapping = {
                'consulting': 'Consulting',
                'lab': 'Lab',
                'pharmacy': 'Pharmacy',
                'imaging': 'Imaging',
            }
            activity_display = activity_mapping.get(activity_type.lower(), activity_type)
            
            # Update activity if not already set or if it's a logical progression
            if not self.current_activity:
                self.current_activity = activity_display
            elif activity_display not in self.current_activity:
                # Append if multiple activities
                activities = [a.strip() for a in self.current_activity.split(',')]
                if activity_display not in activities:
                    activities.append(activity_display)
                    self.current_activity = ', '.join(activities)
            self.save(update_fields=['current_activity', 'modified'])
        except Exception:
            # Field doesn't exist yet - migration not applied
            # Just update notes instead
            pass
    
    def get_activities_list(self):
        """Get list of active department activities"""
        try:
            if not self.current_activity:
                return []
            return [a.strip() for a in self.current_activity.split(',')]
        except AttributeError:
            # Field doesn't exist yet - migration not applied
            return []
    
    def has_activity(self, activity_type):
        """Check if encounter has a specific activity"""
        try:
            activity_mapping = {
                'consulting': 'Consulting',
                'lab': 'Lab',
                'pharmacy': 'Pharmacy',
                'imaging': 'Imaging',
            }
            activity_display = activity_mapping.get(activity_type.lower(), activity_type)
            return activity_display in (self.current_activity or '')
        except AttributeError:
            # Field doesn't exist yet - migration not applied
            return False
    
    def get_duration_minutes(self):
        """Get encounter duration in minutes"""
        if self.ended_at:
            delta = self.ended_at - self.started_at
            return int(delta.total_seconds() / 60)
        return None
    
    def consultation_expired(self):
        """
        Consultation expires at end of the day AFTER completion.
        E.g. completed Monday → expires end of Tuesday (can reopen until Tue 23:59).
        """
        if self.status != 'completed' or not self.ended_at:
            return False
        from datetime import timedelta
        expiry_date = self.ended_at.date() + timedelta(days=1)
        return timezone.now().date() > expiry_date
    
    def can_reopen_consultation(self):
        """True if doctor can go back to this completed consultation (not yet expired)."""
        return self.status == 'completed' and not self.consultation_expired()
    
    def get_latest_vitals(self):
        """Get the most recent vital signs"""
        return self.vitals.filter(is_deleted=False).order_by('-recorded_at').first()
    
    def get_total_cost(self):
        """Calculate total cost for this encounter"""
        from decimal import Decimal
        total = Decimal('0.00')
        # Sum all orders' associated costs
        for order in self.orders.filter(is_deleted=False):
            if order.order_type == 'lab':
                for result in order.lab_results.filter(is_deleted=False):
                    if result.test.price:
                        total += result.test.price
            elif order.order_type == 'medication':
                for prescription in order.prescriptions.filter(is_deleted=False):
                    # Could add drug price calculation here
                    pass
        return total


class VitalSign(BaseModel):
    """
    World-Class Vital Signs System with Advanced Clinical Features
    Includes NEWS2 scoring, consciousness assessment, pain scale, and more
    """
    CONSCIOUSNESS_CHOICES = [
        ('alert', 'Alert'),
        ('cvpu', 'Confusion/New Disorientation'),
        ('voice', 'Responds to Voice'),
        ('pain', 'Responds to Pain'),
        ('unresponsive', 'Unresponsive'),
    ]
    
    PAIN_SCALE_CHOICES = [
        (0, '0 - No Pain'),
        (1, '1 - Minimal'),
        (2, '2 - Mild'),
        (3, '3 - Uncomfortable'),
        (4, '4 - Moderate'),
        (5, '5 - Distressing'),
        (6, '6 - Severe'),
        (7, '7 - Very Severe'),
        (8, '8 - Intense'),
        (9, '9 - Excruciating'),
        (10, '10 - Unbearable'),
    ]
    
    POSITION_CHOICES = [
        ('sitting', 'Sitting'),
        ('standing', 'Standing'),
        ('lying', 'Lying'),
        ('supine', 'Supine'),
    ]
    
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='vitals')
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)
    recorded_by = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True)
    
    # Core Vital Signs
    systolic_bp = models.PositiveIntegerField(null=True, blank=True, verbose_name="Systolic BP", 
                                              help_text="mmHg")
    diastolic_bp = models.PositiveIntegerField(null=True, blank=True, verbose_name="Diastolic BP",
                                               help_text="mmHg")
    pulse = models.PositiveIntegerField(null=True, blank=True, verbose_name="Heart Rate/Pulse",
                                        help_text="beats per minute")
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True,
                                     help_text="°C")
    spo2 = models.PositiveIntegerField(null=True, blank=True, verbose_name="SpO2 (Oxygen Saturation)",
                                       help_text="percentage")
    respiratory_rate = models.PositiveIntegerField(null=True, blank=True, verbose_name="Respiratory Rate",
                                                   help_text="breaths per minute")
    
    # Extended Vitals
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                 help_text="kg")
    height = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                 help_text="cm")
    blood_glucose = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True,
                                       verbose_name="Blood Glucose", help_text="mmol/L or mg/dL")
    
    # Clinical Assessment
    consciousness_level = models.CharField(max_length=20, choices=CONSCIOUSNESS_CHOICES, 
                                          default='alert', verbose_name="Level of Consciousness")
    pain_score = models.PositiveIntegerField(null=True, blank=True, choices=PAIN_SCALE_CHOICES,
                                            verbose_name="Pain Score (0-10)")
    supplemental_oxygen = models.BooleanField(default=False, verbose_name="On Supplemental O2")
    oxygen_flow_rate = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True,
                                          help_text="L/min")
    
    # Additional Context
    position = models.CharField(max_length=20, choices=POSITION_CHOICES, blank=True,
                               help_text="Patient position during measurement")
    capillary_refill = models.PositiveIntegerField(null=True, blank=True, 
                                                   help_text="seconds")
    
    # Calculated Scores (auto-calculated)
    news2_score = models.PositiveIntegerField(null=True, blank=True, 
                                             verbose_name="NEWS2 Score",
                                             help_text="National Early Warning Score 2")
    mews_score = models.PositiveIntegerField(null=True, blank=True,
                                            verbose_name="MEWS Score", 
                                            help_text="Modified Early Warning Score")
    
    # Flags
    is_critical = models.BooleanField(default=False, db_index=True,
                                     help_text="Flagged as critical/abnormal")
    requires_escalation = models.BooleanField(default=False, db_index=True,
                                             help_text="Requires immediate medical attention")
    
    notes = models.TextField(blank=True, verbose_name="Clinical Notes")
    
    class Meta:
        ordering = ['-recorded_at']
        verbose_name = "Vital Signs"
        verbose_name_plural = "Vital Signs"
        indexes = [
            models.Index(fields=['-recorded_at', 'encounter']),
            models.Index(fields=['is_critical', 'requires_escalation']),
        ]
    
    def __str__(self):
        return f"{self.encounter.patient.full_name} - Vitals ({self.recorded_at.strftime('%Y-%m-%d %H:%M')})"
    
    @property
    def bmi(self):
        """Calculate BMI if weight and height are available"""
        if self.weight and self.height:
            # BMI = weight (kg) / height (m)²
            height_m = float(self.height) / 100
            return round(float(self.weight) / (height_m ** 2), 1)
        return None
    
    @property
    def bmi_category(self):
        """Get BMI category"""
        bmi = self.bmi
        if not bmi:
            return None
        if bmi < 18.5:
            return "Underweight"
        elif bmi < 25:
            return "Normal"
        elif bmi < 30:
            return "Overweight"
        else:
            return "Obese"
    
    @property
    def map_pressure(self):
        """Calculate Mean Arterial Pressure"""
        if self.systolic_bp and self.diastolic_bp:
            return round((2 * self.diastolic_bp + self.systolic_bp) / 3, 1)
        return None
    
    def calculate_news2_score(self):
        """
        Calculate NEWS2 (National Early Warning Score 2)
        Used in UK hospitals for detecting deterioration
        """
        score = 0
        
        # Respiratory Rate
        if self.respiratory_rate:
            if self.respiratory_rate <= 8:
                score += 3
            elif self.respiratory_rate <= 11:
                score += 1
            elif self.respiratory_rate <= 20:
                score += 0
            elif self.respiratory_rate <= 24:
                score += 2
            else:
                score += 3
        
        # SpO2
        if self.spo2:
            if self.supplemental_oxygen:
                # Scale 2 for patients on oxygen
                if self.spo2 <= 83:
                    score += 3
                elif self.spo2 <= 85:
                    score += 2
                elif self.spo2 <= 87:
                    score += 1
                elif self.spo2 <= 92:
                    score += 0
                elif self.spo2 <= 94:
                    score += 1
                elif self.spo2 <= 96:
                    score += 2
                else:
                    score += 3
            else:
                # Scale 1 for patients breathing air
                if self.spo2 <= 91:
                    score += 3
                elif self.spo2 <= 93:
                    score += 2
                elif self.spo2 <= 95:
                    score += 1
                else:
                    score += 0
        
        # Supplemental Oxygen
        if self.supplemental_oxygen:
            score += 2
        
        # Temperature
        if self.temperature:
            temp = float(self.temperature)
            if temp <= 35.0:
                score += 3
            elif temp <= 36.0:
                score += 1
            elif temp <= 38.0:
                score += 0
            elif temp <= 39.0:
                score += 1
            else:
                score += 2
        
        # Systolic BP
        if self.systolic_bp:
            if self.systolic_bp <= 90:
                score += 3
            elif self.systolic_bp <= 100:
                score += 2
            elif self.systolic_bp <= 110:
                score += 1
            elif self.systolic_bp <= 219:
                score += 0
            else:
                score += 3
        
        # Heart Rate
        if self.pulse:
            if self.pulse <= 40:
                score += 3
            elif self.pulse <= 50:
                score += 1
            elif self.pulse <= 90:
                score += 0
            elif self.pulse <= 110:
                score += 1
            elif self.pulse <= 130:
                score += 2
            else:
                score += 3
        
        # Consciousness
        if self.consciousness_level and self.consciousness_level != 'alert':
            score += 3
        
        return score
    
    def calculate_mews_score(self):
        """Calculate Modified Early Warning Score"""
        score = 0
        
        # Respiratory Rate
        if self.respiratory_rate:
            if self.respiratory_rate < 9:
                score += 2
            elif self.respiratory_rate <= 14:
                score += 0
            elif self.respiratory_rate <= 20:
                score += 1
            elif self.respiratory_rate <= 29:
                score += 2
            else:
                score += 3
        
        # Heart Rate
        if self.pulse:
            if self.pulse < 40:
                score += 2
            elif self.pulse <= 50:
                score += 1
            elif self.pulse <= 100:
                score += 0
            elif self.pulse <= 110:
                score += 1
            elif self.pulse <= 129:
                score += 2
            else:
                score += 3
        
        # Systolic BP
        if self.systolic_bp:
            if self.systolic_bp < 70:
                score += 3
            elif self.systolic_bp <= 80:
                score += 2
            elif self.systolic_bp <= 100:
                score += 1
            elif self.systolic_bp <= 199:
                score += 0
            else:
                score += 2
        
        # Temperature
        if self.temperature:
            temp = float(self.temperature)
            if temp < 35:
                score += 2
            elif temp <= 38.4:
                score += 0
            else:
                score += 2
        
        # Consciousness
        if self.consciousness_level:
            if self.consciousness_level == 'alert':
                score += 0
            elif self.consciousness_level in ['voice', 'cvpu']:
                score += 1
            elif self.consciousness_level == 'pain':
                score += 2
            else:  # unresponsive
                score += 3
        
        return score
    
    def check_critical_values(self):
        """Check if any vital signs are in critical range"""
        critical = False
        escalate = False
        
        # Critical Vital Ranges
        if self.systolic_bp:
            if self.systolic_bp < 90 or self.systolic_bp > 180:
                critical = True
            if self.systolic_bp < 70 or self.systolic_bp > 200:
                escalate = True
        
        if self.pulse:
            if self.pulse < 50 or self.pulse > 120:
                critical = True
            if self.pulse < 40 or self.pulse > 140:
                escalate = True
        
        if self.temperature:
            temp = float(self.temperature)
            if temp < 36.0 or temp > 38.5:
                critical = True
            if temp < 35.0 or temp > 40.0:
                escalate = True
        
        if self.spo2:
            if self.spo2 < 92:
                critical = True
            if self.spo2 < 88:
                escalate = True
        
        if self.respiratory_rate:
            if self.respiratory_rate < 12 or self.respiratory_rate > 20:
                critical = True
            if self.respiratory_rate < 8 or self.respiratory_rate > 30:
                escalate = True
        
        if self.consciousness_level and self.consciousness_level not in ['alert', 'cvpu']:
            critical = True
            escalate = True
        
        return critical, escalate
    
    def save(self, *args, **kwargs):
        """Auto-calculate scores and flags before saving"""
        # Calculate early warning scores
        self.news2_score = self.calculate_news2_score()
        self.mews_score = self.calculate_mews_score()
        
        # Check for critical values
        self.is_critical, self.requires_escalation = self.check_critical_values()
        
        super().save(*args, **kwargs)


# ==================== STAFF & HR MODULE ====================

class Department(BaseModel):
    """Hospital departments"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True, blank=True)
    description = models.TextField(blank=True)
    head_of_department = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True, blank=True, related_name='headed_departments')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Staff(BaseModel):
    """Staff profiles - Enhanced with auto-ID generation"""
    PROFESSION_CHOICES = [
        ('doctor', 'Doctor'),
        ('nurse', 'Nurse'),
        ('midwife', 'Midwife'),
        ('pharmacist', 'Pharmacist'),
        ('lab_technician', 'Lab Technician'),
        ('radiologist', 'Radiologist'),
        ('admin', 'Administrator'),
        ('receptionist', 'Receptionist'),
        ('cashier', 'Cashier'),
        ('hr_manager', 'HR Manager'),
        ('accountant', 'Accountant'),
        ('account_personnel', 'Account Personnel'),
        ('account_officer', 'Account Officer'),
        ('inventory_manager', 'Inventory Manager'),
        ('store_manager', 'Store Manager'),
        ('procurement_officer', 'Procurement Officer'),
        ('marketer', 'Marketer'),
        ('business_development', 'Business Development'),
    ]
    
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('O+', 'O+'),
        ('O-', 'O-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
    ]
    
    MARITAL_STATUS_CHOICES = [
        ('single', 'Single'),
        ('married', 'Married'),
        ('divorced', 'Divorced'),
        ('widowed', 'Widowed'),
    ]
    
    # Basic Information
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff')
    employee_id = models.CharField(max_length=20, unique=True, blank=True)
    profession = models.CharField(max_length=20, choices=PROFESSION_CHOICES)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='staff')
    
    # Professional Details
    registration_number = models.CharField(max_length=50, blank=True, help_text='Medical council registration number')
    license_number = models.CharField(max_length=50, blank=True, help_text='Professional license number')
    specialization = models.CharField(max_length=200, blank=True, help_text='Area of specialization')
    
    # Contact Information
    phone_number = models.CharField(max_length=17, blank=True)
    personal_email = models.EmailField(blank=True, help_text='Personal email address')
    address = models.TextField(blank=True, help_text='Residential address')
    city = models.CharField(max_length=100, blank=True)
    
    # Personal Details
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ], blank=True)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, blank=True)
    marital_status = models.CharField(max_length=20, choices=MARITAL_STATUS_CHOICES, blank=True)
    
    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_relationship = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=17, blank=True)
    
    # Employment Details
    date_of_joining = models.DateField(null=True, blank=True)
    employment_status = models.CharField(max_length=20, choices=[
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated'),
        ('retired', 'Retired'),
    ], default='active')
    
    # Banking Details (for payroll)
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=50, blank=True)
    bank_branch = models.CharField(max_length=100, blank=True)
    
    # Additional
    is_locum = models.BooleanField(
        default=False,
        help_text='Mark as locum/visiting staff for payment tracking'
    )
    is_active = models.BooleanField(default=True)
    staff_notes = models.TextField(blank=True, help_text='Additional notes about staff member')
    
    class Meta:
        ordering = ['user__last_name', 'user__first_name']
    
    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_profession_display()})"
    
    def save(self, *args, **kwargs):
        """Auto-generate employee ID if not provided"""
        if not self.employee_id:
            self.employee_id = self.generate_employee_id()
        super().save(*args, **kwargs)
    
    def generate_employee_id(self):
        """Generate employee ID: PCMC-DEPT-PROF-NUMBER (PrimeCare Medical Center)"""
        # Institution prefix
        institution_prefix = 'PCMC'
        
        # Get department code (first 3 letters of name if no code)
        if self.department and self.department.code:
            dept_code = self.department.code[:3].upper()
        elif self.department:
            dept_code = self.department.name[:3].upper().replace(' ', '')
        else:
            dept_code = 'GEN'
        
        # Get profession code - includes ALL professions
        profession_codes = {
            'doctor': 'DOC',
            'nurse': 'NUR',
            'pharmacist': 'PHA',
            'lab_technician': 'LAB',
            'radiologist': 'RAD',
            'admin': 'ADM',
            'receptionist': 'REC',
            'cashier': 'CSH',
            'hr_manager': 'HRM',
            'accountant': 'ACC',
            'account_personnel': 'ACP',
            'account_officer': 'ACO',
            'inventory_manager': 'INV',
            'store_manager': 'STM',
            'procurement_officer': 'PRO',
        }
        prof_code = profession_codes.get(self.profession, 'STF')
        
        # Get next sequential number for this institution-department-profession combination
        prefix = f"{institution_prefix}-{dept_code}-{prof_code}"
        
        # Find highest existing number with this prefix
        existing = Staff.objects.filter(
            employee_id__startswith=prefix,
            is_deleted=False
        ).order_by('-employee_id').first()
        
        if existing and existing.employee_id:
            try:
                # Extract number from employee_id (format: PCMC-DEPT-PROF-NUMBER)
                parts = existing.employee_id.split('-')
                if len(parts) >= 4:
                    last_num = int(parts[3])
                    new_num = last_num + 1
                else:
                    new_num = 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}-{new_num:04d}"
    
    @property
    def phone(self):
        """Alias for phone_number for compatibility"""
        return self.phone_number
    
    @property
    def age(self):
        """Calculate age from date of birth"""
        if self.date_of_birth:
            from datetime import date
            today = date.today()
            return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return None
    
    @property
    def years_of_service(self):
        """Calculate years of service"""
        if self.date_of_joining:
            from datetime import date
            today = date.today()
            return today.year - self.date_of_joining.year - ((today.month, today.day) < (self.date_of_joining.month, self.date_of_joining.day))
        return None
    
    @property
    def years_until_retirement(self):
        """Calculate years until retirement (assuming retirement at 60)"""
        if self.date_of_birth:
            from datetime import date
            today = date.today()
            retirement_age = 60
            current_age = self.age or 0
            years_left = retirement_age - current_age
            return max(0, years_left) if years_left > 0 else 0
        return None
    
    @property
    def retirement_date(self):
        """Calculate retirement date (assuming retirement at 60)"""
        if self.date_of_birth:
            from datetime import date
            retirement_age = 60
            birth_year = self.date_of_birth.year
            retirement_year = birth_year + retirement_age
            return date(retirement_year, self.date_of_birth.month, self.date_of_birth.day)
        return None
    
    def is_birthday_today(self):
        """Check if today is staff's birthday"""
        if self.date_of_birth:
            from datetime import date
            today = date.today()
            return (today.month == self.date_of_birth.month and 
                    today.day == self.date_of_birth.day)
        return False
    
    def is_birthday_soon(self, days=7):
        """Check if birthday is within next N days"""
        if self.date_of_birth:
            from datetime import date, timedelta
            today = date.today()
            
            # Create this year's birthday
            this_year_birthday = date(today.year, self.date_of_birth.month, self.date_of_birth.day)
            
            # If birthday already passed this year, check next year
            if this_year_birthday < today:
                this_year_birthday = date(today.year + 1, self.date_of_birth.month, self.date_of_birth.day)
            
            # Check if within next N days
            days_until = (this_year_birthday - today).days
            return 0 <= days_until <= days
        return False
    
    def days_until_birthday(self):
        """Calculate days until next birthday"""
        if self.date_of_birth:
            from datetime import date
            today = date.today()
            
            # Create this year's birthday
            this_year_birthday = date(today.year, self.date_of_birth.month, self.date_of_birth.day)
            
            # If birthday already passed this year, use next year
            if this_year_birthday < today:
                this_year_birthday = date(today.year + 1, self.date_of_birth.month, self.date_of_birth.day)
            
            return (this_year_birthday - today).days
        return None
    
    @staticmethod
    def get_birthdays_today():
        """Get all staff with birthdays today"""
        from datetime import date
        today = date.today()
        return Staff.objects.filter(
            date_of_birth__month=today.month,
            date_of_birth__day=today.day,
            is_active=True,
            is_deleted=False
        )
    
    @staticmethod
    def get_upcoming_birthdays(days=7):
        """Get staff with birthdays in next N days"""
        from datetime import date, timedelta
        today = date.today()
        upcoming = []
        
        # Get all active staff with birthdays
        staff_with_birthdays = Staff.objects.filter(
            date_of_birth__isnull=False,
            is_active=True,
            is_deleted=False
        )
        
        for staff in staff_with_birthdays:
            if staff.is_birthday_soon(days):
                upcoming.append(staff)
        
        return upcoming


# ==================== FACILITY & BEDS MODULE ====================

class Ward(BaseModel):
    """Hospital wards"""
    WARD_TYPES = [
        ('general', 'General Ward'),
        ('icu', 'ICU'),
        ('hdu', 'HDU'),
        ('maternity', 'Maternity'),
        ('paediatric', 'Paediatric'),
        ('surgery', 'Surgery'),
        ('emergency', 'Emergency'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True, blank=True)
    ward_type = models.CharField(max_length=20, choices=WARD_TYPES)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='wards')
    capacity = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_ward_type_display()})"


class Bed(BaseModel):
    """Hospital beds"""
    BED_TYPES = [
        ('general', 'General'),
        ('icu', 'ICU'),
        ('hdu', 'HDU'),
        ('maternity', 'Maternity'),
        ('paediatric', 'Paediatric'),
    ]
    
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('maintenance', 'Maintenance'),
        ('reserved', 'Reserved'),
    ]
    
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name='beds')
    bed_number = models.CharField(max_length=50)
    bed_type = models.CharField(max_length=20, choices=BED_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['ward', 'bed_number']
        unique_together = ['ward', 'bed_number']
    
    def __str__(self):
        return f"{self.ward.name} - Bed {self.bed_number}"
    
    def is_available(self):
        """Check if bed is available"""
        return self.status == 'available' and self.is_active
    
    def occupy(self):
        """Mark bed as occupied"""
        self.status = 'occupied'
        self.save()
    
    def vacate(self):
        """Mark bed as available"""
        self.status = 'available'
        self.save()


class Admission(BaseModel):
    """Patient admissions"""
    STATUS_CHOICES = [
        ('admitted', 'Admitted'),
        ('discharged', 'Discharged'),
        ('transferred', 'Transferred'),
    ]
    
    encounter = models.OneToOneField(Encounter, on_delete=models.CASCADE, related_name='admission', null=True, blank=True)
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name='admissions', null=True, blank=True)
    bed = models.ForeignKey(Bed, on_delete=models.CASCADE, related_name='admissions', null=True, blank=True)
    admit_date = models.DateTimeField(default=timezone.now)
    discharge_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='admitted')
    admitting_doctor = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    diagnosis_icd10 = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-admit_date']
    
    def __str__(self):
        patient_name = self.encounter.patient.full_name if self.encounter else "Unknown"
        ward_name = self.ward.name if self.ward else "Unknown"
        return f"{patient_name} - {ward_name}"
    
    def discharge(self):
        """Discharge patient and free up bed"""
        self.status = 'discharged'
        self.discharge_date = timezone.now()
        
        if self.bed:
            self.bed.vacate()
        
        if self.encounter:
            self.encounter.complete()
        
        self.save()
    
    def get_duration_days(self):
        """Get admission duration in days"""
        if self.discharge_date:
            delta = self.discharge_date - self.admit_date
            return delta.days
        else:
            delta = timezone.now() - self.admit_date
            return delta.days


# ==================== ORDERS & LAB MODULE ====================

class Order(BaseModel):
    """Medical orders (lab, imaging, medications)"""
    ORDER_TYPES = [
        ('lab', 'Laboratory'),
        ('imaging', 'Imaging'),
        ('medication', 'Medication'),
        ('procedure', 'Procedure'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('routine', 'Routine'),
        ('urgent', 'Urgent'),
        ('stat', 'STAT'),
    ]
    
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='orders')
    order_type = models.CharField(max_length=20, choices=ORDER_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='routine')
    requested_by = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='orders_requested')
    notes = models.TextField(blank=True)
    requested_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['encounter', 'order_type', 'is_deleted']),
            models.Index(fields=['encounter', 'status', 'is_deleted']),
            models.Index(fields=['order_type', 'status', 'is_deleted']),
            models.Index(fields=['requested_at']),
        ]

    def __str__(self):
        return f"{self.encounter.patient.full_name} - {self.get_order_type_display()}"
    
    def save(self, *args, **kwargs):
        """Override save to prevent duplicates - only check for very recent duplicates"""
        # Only check for duplicates on new objects and skip if this is a bulk operation
        if not self.pk and not kwargs.get('bulk', False):
            from django.utils import timezone
            from datetime import timedelta
            
            # Check for existing order with same encounter + order_type within last 30 minutes
            # This prevents rapid duplicate creation from double-clicks or form resubmissions
            thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
            
            duplicate = Order.objects.filter(
                encounter=self.encounter,
                order_type=self.order_type,
                is_deleted=False,
                created__gte=thirty_minutes_ago
            ).exclude(pk=self.pk).order_by('-requested_at', '-created').first()
            
            if duplicate:
                # Very recent duplicate found - update existing instead of creating new
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Duplicate Order prevented: Found existing order {duplicate.id} "
                    f"for encounter {self.encounter_id}, order_type {self.order_type}, "
                    f"created {duplicate.created}"
                )
                # Update existing order with new status/priority if better
                if self.status != 'pending' and duplicate.status == 'pending':
                    duplicate.status = self.status
                if self.priority != 'routine' and duplicate.priority == 'routine':
                    duplicate.priority = self.priority
                if self.notes and not duplicate.notes:
                    duplicate.notes = self.notes
                duplicate.save()
                # Set self.pk to existing duplicate to prevent creation
                self.pk = duplicate.pk
                self.id = duplicate.id
                # Don't call super().save() - we're using the existing record
                return
        
        super().save(*args, **kwargs)


class LabTest(BaseModel):
    """Laboratory test catalog"""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    specimen_type = models.CharField(max_length=50)
    tat_minutes = models.PositiveIntegerField(default=60, verbose_name="Turnaround Time (minutes)")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    
    # Reagent requirements (many-to-many relationship)
    # This will be added via a migration to link LabTest to LabReagent
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active', 'is_deleted']),
            models.Index(fields=['name']),
            models.Index(fields=['code']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class LabResult(BaseModel):
    """Laboratory test results"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='lab_results')
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE, related_name='results')
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='pending')
    
    value = models.CharField(max_length=100, blank=True)
    units = models.CharField(max_length=20, blank=True)
    range_low = models.CharField(max_length=20, blank=True)
    range_high = models.CharField(max_length=20, blank=True)
    is_abnormal = models.BooleanField(default=False)
    # Structured details for panel tests (e.g., FBC components) or qualitative outcomes
    details = models.JSONField(null=True, blank=True)
    qualitative_result = models.CharField(max_length=50, blank=True, help_text='For qualitative tests: Reactive/Non-reactive/Positive/Negative')
    
    verified_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    # Expected completion date/time - for tests that take days
    expected_completion_datetime = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text='Expected date and time when this test will be completed (for long-duration tests)'
    )
    
    # Optional file attachment (scanned report, image, PDF, etc.)
    attachment = models.FileField(
        upload_to='lab_results/%Y/%m/',
        blank=True,
        null=True,
        help_text='Optional attachment: scanned report, image, PDF, or external lab document'
    )
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        patient_name = self.order.encounter.patient.full_name if self.order.encounter else "Unknown"
        return f"{patient_name} - {self.test.name}"
    
    def get_expected_completion_display(self):
        """Get human-readable expected completion time"""
        if self.expected_completion_datetime:
            return self.expected_completion_datetime.strftime('%Y-%m-%d %H:%M')
        elif self.test and self.test.tat_minutes:
            from django.utils import timezone
            from datetime import timedelta
            # Calculate from tat_minutes if no explicit datetime set
            start_time = self.created or timezone.now()
            completion_time = start_time + timedelta(minutes=self.test.tat_minutes)
            
            # If more than 24 hours, show date and time
            if self.test.tat_minutes >= 1440:
                return completion_time.strftime('%Y-%m-%d %H:%M')
            else:
                # Show as hours/minutes if less than 24 hours
                hours = self.test.tat_minutes // 60
                minutes = self.test.tat_minutes % 60
                if hours > 0:
                    return f"{hours}h {minutes}m from order time"
                else:
                    return f"{minutes}m from order time"
        return "Not set"
    
    def save(self, *args, **kwargs):
        """Override save to prevent duplicates - only check for very recent duplicates"""
        # Only check for duplicates on new objects and skip if this is a bulk operation
        if not self.pk and not kwargs.get('bulk', False):
            from django.utils import timezone
            from datetime import timedelta
            
            # Check for existing result with same order + test within last 30 minutes
            # This prevents rapid duplicate creation from double-clicks or form resubmissions
            thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
            
            duplicate = LabResult.objects.filter(
                order=self.order,
                test=self.test,
                is_deleted=False,
                created__gte=thirty_minutes_ago
            ).exclude(pk=self.pk).order_by('-created').first()
            
            # Also check within same encounter if available
            if not duplicate and self.order.encounter_id:
                duplicate = LabResult.objects.filter(
                    order__encounter=self.order.encounter,
                    test=self.test,
                    is_deleted=False,
                    created__gte=thirty_minutes_ago
                ).exclude(pk=self.pk).order_by('-created').first()
            
            if duplicate:
                # Very recent duplicate found - update existing instead of creating new
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Duplicate LabResult prevented: Found existing result {duplicate.id} "
                    f"for order {self.order_id}, test {self.test_id}, "
                    f"created {duplicate.created}"
                )
                # Set self.pk to existing duplicate to prevent creation
                self.pk = duplicate.pk
                self.id = duplicate.id
                # Don't call super().save() - we're using the existing record
                return
        
        super().save(*args, **kwargs)


# ==================== PHARMACY MODULE ====================

class Drug(BaseModel):
    """Pharmacy drug formulary"""
    
    # Comprehensive drug categories - logically organized for easy doctor prescription
    # Organized by therapeutic use for quick access during consultations
    CATEGORIES = [
        # ========== PAIN MANAGEMENT & FEVER ==========
        ('analgesic', 'Analgesics - Relieve pain (non-narcotic for mild pain, narcotic for severe pain)'),
        ('antipyretic', 'Antipyretics - Drugs that reduce fever'),
        ('barbiturate', 'Barbiturates - Sleeping drugs (used less commonly than benzodiazepines)'),
        
        # ========== CARDIOVASCULAR SYSTEM ==========
        ('antihypertensive', 'Antihypertensives - Lower blood pressure (includes diuretics, beta-blockers, calcium channel blockers, ACE inhibitors)'),
        ('antiarrhythmic', 'Antiarrhythmics - Control irregularities of heartbeat'),
        ('beta_blocker', 'Beta-Blockers - Reduce oxygen needs of heart by reducing heartbeat rate'),
        ('anticoagulant', 'Anticoagulants - Prevent blood from clotting'),
        ('thrombolytic', 'Thrombolytics - Dissolve and disperse blood clots'),
        ('diuretic', 'Diuretics - Increase urine production, rid body of excess fluid'),
        
        # ========== INFECTIONS & ANTIMICROBIALS ==========
        ('antibiotic', 'Antibiotics - Combat bacterial infections (naturally occurring and synthetic substances)'),
        ('antibacterial', 'Antibacterials - Drugs used to treat infections'),
        ('antiviral', 'Antivirals - Treat viral infections or provide temporary protection (e.g., influenza)'),
        ('antifungal', 'Antifungals - Treat fungal infections (hair, skin, nails, mucous membranes)'),
        
        # ========== NEUROLOGICAL CONDITIONS ==========
        ('anticonvulsant', 'Anticonvulsants - Prevent epileptic seizures'),
        
        # ========== PSYCHIATRIC & MENTAL HEALTH ==========
        ('antipsychotic', 'Antipsychotics - Treat symptoms of severe psychiatric disorders (major tranquilizers)'),
        ('antidepressant', 'Antidepressants - Mood-lifting medications (tricyclics, MAOIs, SSRIs)'),
        ('antianxiety', 'Antianxiety Drugs - Suppress anxiety and relax muscles (anxiolytics, sedatives, minor tranquilizers)'),
        ('tranquilizer', 'Tranquilizers - Drugs with calming or sedative effect (minor = antianxiety, major = antipsychotic)'),
        ('sedative', 'Sedatives - Calming or sedative effect (same as antianxiety drugs)'),
        ('sleeping_drug', 'Sleeping Drugs - Induce sleep (benzodiazepines and barbiturates)'),
        
        # ========== RESPIRATORY SYSTEM ==========
        ('bronchodilator', 'Bronchodilators - Open bronchial tubes in lungs (e.g., for asthma)'),
        ('cough_suppressant', 'Cough Suppressants - Suppress coughing reflex or alter phlegm consistency (includes expectorants, mucolytics)'),
        ('expectorant', 'Expectorants - Stimulate flow of saliva and promote coughing to eliminate phlegm'),
        ('decongestant', 'Decongestants - Reduce swelling of nasal mucous membranes, relieve nasal stuffiness'),
        ('cold_cure', 'Cold Cures - Relieve aches, pains, and fever accompanying colds (aspirin, acetaminophen with decongestant/antihistamine)'),
        
        # ========== GASTROINTESTINAL SYSTEM ==========
        ('antacid', 'Antacids - Relieve indigestion and heartburn by neutralizing stomach acid'),
        ('antidiarrheal', 'Antidiarrheals - Relief of diarrhea (adsorbent substances or drugs that slow bowel contractions)'),
        ('antiemetic', 'Antiemetics - Treat nausea and vomiting'),
        ('laxative', 'Laxatives - Increase frequency and ease of bowel movements (stimulant, bulk, or lubricating)'),
        
        # ========== INFLAMMATION & IMMUNE SYSTEM ==========
        ('anti_inflammatory', 'Anti-Inflammatories - Reduce inflammation (redness, heat, swelling in infections and chronic diseases)'),
        ('corticosteroid', 'Corticosteroids - Hormonal preparations used as anti-inflammatories (arthritis, asthma) or immunosuppressives'),
        ('immunosuppressive', 'Immunosuppressives - Prevent or reduce body\'s reaction to disease or foreign tissues (autoimmune diseases, organ transplants)'),
        ('antihistamine', 'Antihistamines - Counteract effects of histamine (chemical involved in allergic reactions)'),
        
        # ========== CANCER TREATMENT ==========
        ('antineoplastic', 'Antineoplastics - Drugs used to treat cancer'),
        ('cytotoxic', 'Cytotoxics - Kill or damage cells (used as antineoplastics for cancer and as immunosuppressives)'),
        
        # ========== ENDOCRINE SYSTEM & HORMONES ==========
        ('hormone', 'Hormones - Chemicals from endocrine glands, used in hormone replacement therapy'),
        ('female_sex_hormone', 'Female Sex Hormones - Estrogens and progesterone (treat menstrual/menopausal disorders, oral contraceptives)'),
        ('male_sex_hormone', 'Male Sex Hormones - Androgenic hormones like testosterone (compensate deficiency, treat breast cancer)'),
        ('oral_hypoglycemic', 'Oral Hypoglycemics - Lower blood glucose levels (used in diabetes mellitus)'),
        
        # ========== MUSCULOSKELETAL ==========
        ('muscle_relaxant', 'Muscle Relaxants - Relieve muscle spasm (e.g., backache, often antianxiety drugs with muscle-relaxant action)'),
        
        # ========== NUTRITION & SUPPLEMENTS ==========
        ('vitamin', 'Vitamins - Essential chemicals for good health (not manufactured by body, needed in diet or supplements)'),
        
        # ========== OTHER ==========
        ('other', 'Other - Miscellaneous drugs not fitting above categories'),
    ]
    
    atc_code = models.CharField(max_length=20, blank=True, verbose_name="ATC Code")
    name = models.CharField(max_length=200)
    generic_name = models.CharField(max_length=200, blank=True)
    strength = models.CharField(max_length=50)
    form = models.CharField(max_length=50, help_text="tablet, capsule, injection, etc.")
    pack_size = models.CharField(max_length=50)
    category = models.CharField(max_length=50, choices=CATEGORIES, default='other', help_text="Drug category classification")
    is_controlled = models.BooleanField(default=False, help_text="Controlled substance requiring special handling")
    is_active = models.BooleanField(default=True)
    
    # Pricing fields
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Selling price per unit")
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Cost from supplier")
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Drug'
        verbose_name_plural = 'Drugs'
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['name']),
            models.Index(fields=['is_active', 'category']),
        ]
    
    def __str__(self):
        return f"{self.name} {self.strength} {self.form}"
    
    def get_category_display_full(self):
        """Get full category name with description"""
        for code, desc in self.CATEGORIES:
            if code == self.category:
                return desc
        return self.get_category_display()


class PharmacyStock(BaseModel):
    """Pharmacy inventory"""
    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name='stock')
    batch_number = models.CharField(max_length=50)
    expiry_date = models.DateField()
    location = models.CharField(max_length=100, default='Main Pharmacy')
    initial_quantity = models.IntegerField(
        default=0,
        help_text='Initial quantity added for this batch (before any dispensing)',
    )
    quantity_on_hand = models.IntegerField(default=0, help_text='Can be negative when dispensed without stock (shortfall)')
    reorder_level = models.PositiveIntegerField(default=10)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pharmacy_stock_added', editable=False,
        help_text='User (e.g. store manager) who added this stock – visible to account for monitoring'
    )

    class Meta:
        ordering = ['drug__name', 'expiry_date']
    
    def __str__(self):
        return f"{self.drug.name} - Batch {self.batch_number}"

    def save(self, *args, **kwargs):
        # Capture opening balance when a batch is first created.
        if not self.pk and not self.initial_quantity:
            self.initial_quantity = int(self.quantity_on_hand or 0)
        super().save(*args, **kwargs)


class Prescription(BaseModel):
    """E-prescriptions"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='prescriptions')
    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name='prescriptions')
    quantity = models.PositiveIntegerField()
    dose = models.CharField(max_length=100)
    route = models.CharField(max_length=50)  # oral, IV, IM, etc.
    frequency = models.CharField(max_length=50)  # daily, twice daily, etc.
    duration = models.CharField(max_length=50)  # 7 days, 2 weeks, etc.
    instructions = models.TextField(blank=True)
    
    prescribed_by = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='prescriptions')
    
    class Meta:
        ordering = ['-created']
        indexes = [
            models.Index(fields=['order', 'drug', 'is_deleted']),
            models.Index(fields=['order', 'is_deleted']),
            models.Index(fields=['prescribed_by', 'is_deleted']),
        ]
    
    def __str__(self):
        patient_name = self.order.encounter.patient.full_name if self.order.encounter else "Unknown"
        return f"{patient_name} - {self.drug.name}"
    
    def save(self, *args, **kwargs):
        """Override save to prevent duplicates - only check for very recent duplicates"""
        # Only check for duplicates on new objects and skip if this is a bulk operation
        if not self.pk and not kwargs.get('bulk', False):
            from django.utils import timezone
            from datetime import timedelta
            
            # Check for existing prescription with same order + drug within last 30 minutes
            # This prevents rapid duplicate creation from double-clicks or form resubmissions
            thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
            
            duplicate = Prescription.objects.filter(
                order=self.order,
                drug=self.drug,
                is_deleted=False,
                created__gte=thirty_minutes_ago
            ).exclude(pk=self.pk).order_by('-created').first()
            
            # Also check within same encounter if available
            if not duplicate and self.order.encounter_id:
                duplicate = Prescription.objects.filter(
                    order__encounter=self.order.encounter,
                    drug=self.drug,
                    is_deleted=False,
                    created__gte=thirty_minutes_ago
                ).exclude(pk=self.pk).order_by('-created').first()
            
            if duplicate:
                # Very recent duplicate found - update existing instead of creating new
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Duplicate Prescription prevented: Found existing prescription {duplicate.id} "
                    f"for order {self.order_id}, drug {self.drug_id}, "
                    f"created {duplicate.created}"
                )
                # Update quantity if needed (merge quantities)
                if duplicate.quantity < self.quantity:
                    duplicate.quantity = self.quantity
                    duplicate.save(update_fields=['quantity'])
                # Set self.pk to existing duplicate to prevent creation
                self.pk = duplicate.pk
                self.id = duplicate.id
                # Don't call super().save() - we're using the existing record
                return
        
        super().save(*args, **kwargs)
    
    @property
    def total_cost(self):
        """Calculate total cost of prescription"""
        from decimal import Decimal
        unit_price = getattr(self.drug, 'unit_price', Decimal('0.00'))
        return unit_price * self.quantity


# ==================== BILLING MODULE ====================

class Payer(BaseModel):
    """Payers: NHIS, private insurance, cash, corporate."""
    PAYER_TYPES = [
        ('nhis', 'NHIS'),
        ('private', 'Private Insurance'),
        ('cash', 'Cash'),
        ('corporate', 'Corporate'),
    ]
    # Payer types that are insurance (billing, pricing, claims). Include 'insurance' for legacy data.
    INSURANCE_PAYER_TYPES = ('insurance', 'private', 'nhis')

    name = models.CharField(max_length=200)
    payer_type = models.CharField(max_length=20, choices=PAYER_TYPES)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def is_insurance_payer(self):
        """True if this payer is insurance (NHIS or private), for pricing and claims."""
        return self.payer_type in self.INSURANCE_PAYER_TYPES


class ServiceCode(BaseModel):
    """Service codes for billing (code can be short e.g. CON001 or long e.g. DRUG-<uuid>)"""
    code = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=200)
    category = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.description}"


class PriceBook(BaseModel):
    """Pricing for different payers"""
    payer = models.ForeignKey(Payer, on_delete=models.CASCADE, related_name='price_books')
    service_code = models.ForeignKey(ServiceCode, on_delete=models.CASCADE, related_name='price_books')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['payer', 'service_code']
        ordering = ['payer', 'service_code']
    
    def __str__(self):
        return f"{self.payer.name} - {self.service_code.description}"


class Invoice(BaseModel):
    """Patient invoices"""
    # Invoices in this date range are excluded from all lists (write-off period; fresh start March 2026)
    WRITE_OFF_START = date(2025, 12, 1)
    WRITE_OFF_END = date(2026, 2, 28)

    class VisibleManager(models.Manager):
        """Default manager: excludes soft-deleted, write-off period, and zero-amount/empty invoices."""
        def get_queryset(self):
            return super().get_queryset().filter(
                is_deleted=False,
                total_amount__gt=0,  # hide invoices with zero items / zero amount
            ).exclude(
                issued_at__date__gte=Invoice.WRITE_OFF_START,
                issued_at__date__lte=Invoice.WRITE_OFF_END,
            )

    objects = VisibleManager()
    all_objects = models.Manager()

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
    payer = models.ForeignKey(Payer, on_delete=models.CASCADE, related_name='invoices')
    invoice_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    issued_at = models.DateTimeField(default=timezone.now)
    due_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-issued_at']
        constraints = [
            # At most one non-deleted invoice per encounter; walk-in (encounter=None) stays unrestricted.
            models.UniqueConstraint(
                fields=['encounter'],
                condition=Q(encounter__isnull=False, is_deleted=False),
                name='hospital_invoice_one_per_encounter',
            ),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.patient.full_name}"
    
    @property
    def amount_paid(self):
        """Calculate amount paid from total amount and balance"""
        from decimal import Decimal
        return (self.total_amount or Decimal('0.00')) - (self.balance or Decimal('0.00'))

    @property
    def billable_lines(self):
        """Lines for display on invoices (excludes waived - those contribute 0 and should not appear)"""
        return self.lines.filter(is_deleted=False, waived_at__isnull=True)
    
    def save(self, *args, **kwargs):
        """Auto-generate invoice number and set defaults"""
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        
        # Set default due date if not provided (30 days from issue)
        if not self.due_at:
            from datetime import timedelta
            self.due_at = self.issued_at + timedelta(days=30)
        
        # Only calculate totals if invoice has been saved before (has lines)
        # This prevents issues with new invoices that don't have lines yet
        if self.pk:
            self.calculate_totals()
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_invoice_number():
        """Generate a unique invoice number"""
        from datetime import datetime
        prefix = "INV"
        year = datetime.now().year
        month = datetime.now().month
        # Use all_objects so write-off period invoices are included and we don't duplicate numbers
        last_invoice = Invoice.all_objects.filter(
            invoice_number__startswith=f"{prefix}{year}{month:02d}"
        ).order_by('-invoice_number').first()
        
        if last_invoice and last_invoice.invoice_number:
            try:
                last_num = int(last_invoice.invoice_number.replace(f"{prefix}{year}{month:02d}", ""))
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{year}{month:02d}{new_num:05d}"
    
    def calculate_totals(self):
        """Calculate total amount and balance from invoice lines and payments.
        Uses formula (qty*unit_price - discount + tax) per line so waived/discounted
        amounts are correctly excluded from the total.
        Waived lines (waived_at set) always contribute 0 to the total.
        Uses a fresh DB query (not self.lines) so waivers are always reflected
        even when the invoice was loaded with prefetch_related('lines').
        """
        from decimal import Decimal
        
        total = Decimal('0.00')
        try:
            # Fresh query so waived lines are always reflected (avoids stale prefetch cache)
            for line in InvoiceLine.objects.filter(invoice=self, is_deleted=False):
                if getattr(line, 'waived_at', None):
                    # Waived lines contribute nothing to invoice total
                    line_total = Decimal('0.00')
                else:
                    subtotal = Decimal(str(line.quantity)) * Decimal(str(line.unit_price))
                    line_total = subtotal - Decimal(str(line.discount_amount or 0)) + Decimal(str(line.tax_amount or 0))
                total += line_total
        except Exception:
            pass
        
        self.total_amount = total

        # Calculate payments made against this invoice
        total_paid = Decimal('0.00')
        try:
            from .models_accounting import PaymentReceipt
            receipts = list(PaymentReceipt.objects.filter(
                invoice=self,
                is_deleted=False
            ).exclude(notes__icontains='Part of combined bill').exclude(
                notes__icontains='Combined payment (summary)'
            ))
            total_paid = sum([r.amount_paid for r in receipts], Decimal('0.00'))
            # Include combined-payment allocations (one Transaction, one Receipt; allocation splits by invoice)
            try:
                from .models_accounting import PaymentAllocation
                allocation_sum = PaymentAllocation.objects.filter(
                    invoice=self,
                    is_deleted=False,
                    payment_transaction__transaction_type='payment_received',
                    payment_transaction__is_deleted=False,
                ).aggregate(s=Sum('allocated_amount'))['s'] or Decimal('0.00')
                total_paid += allocation_sum
            except Exception:
                pass
            try:
                from .models_patient_deposits import DepositApplication
                deposit_applied = DepositApplication.objects.filter(
                    invoice=self, is_deleted=False
                ).aggregate(s=Sum('applied_amount'))['s'] or Decimal('0.00')
                deposit_in_receipts = sum(
                    [r.amount_paid for r in receipts if r.payment_method == 'deposit' or
                     (getattr(r, 'service_details') and isinstance(r.service_details, dict) and r.service_details.get('deposit_applied'))],
                    Decimal('0.00')
                )
                total_paid += max(Decimal('0.00'), deposit_applied - deposit_in_receipts)
            except Exception:
                pass
            # Subtract refunds so that refund_issued increases balance (reduces credit)
            from .models_accounting import Transaction
            refund_sum = Transaction.objects.filter(
                invoice=self,
                transaction_type='refund_issued',
                is_deleted=False
            ).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
            total_paid -= refund_sum
        except Exception:
            try:
                from .models_accounting import Transaction
                transactions = Transaction.objects.filter(
                    invoice=self,
                    transaction_type='payment_received',
                    is_deleted=False
                )
                total_paid = sum([t.amount for t in transactions], Decimal('0.00'))
                refund_sum = Transaction.objects.filter(
                    invoice=self,
                    transaction_type='refund_issued',
                    is_deleted=False
                ).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
                total_paid -= refund_sum
            except Exception:
                pass

        # Balance = Total - Payments Made (can be negative = credit)
        self.balance = total - total_paid

        # Terminal / removed rows: do not let balance math reopen them (e.g. Remove from bill
        # sets cancelled, then update_totals must not overwrite with partially_paid or the
        # invoice reappears on Total Bill).
        if getattr(self, 'status', None) == 'cancelled':
            return
        if getattr(self, 'is_deleted', False):
            return

        # Auto-update status based on balance
        if self.balance <= 0 and total > 0:
            self.status = 'paid'
        elif self.balance < total and self.balance > 0:
            self.status = 'partially_paid'
        elif self.status == 'draft' and total > 0:
            pass

    def _sync_pharmacy_after_totals_saved(self, receipt=None, verified_by_user=None):
        """
        When invoice is fully settled, move prescription dispensing and prescribe (walk-in)
        sales out of pending. Safe to call after save(); does not call update_totals().
        """
        from decimal import Decimal as _D

        try:
            bal = self.balance or _D('0')
            tot = self.total_amount or _D('0')
            if bal > _D('0') or tot <= _D('0'):
                return
            if getattr(self, 'status', None) == 'cancelled' or getattr(self, 'is_deleted', False):
                return
            from hospital.services.pharmacy_invoice_payment_link import (
                link_pharmacy_dispensing_when_invoice_paid,
                link_walkin_sales_when_invoice_paid,
            )

            link_pharmacy_dispensing_when_invoice_paid(
                self,
                receipt=receipt,
                verified_by_user=verified_by_user,
                refresh_invoice=False,
            )
            link_walkin_sales_when_invoice_paid(self, receipt=receipt, refresh_invoice=False)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                'Pharmacy sync after invoice totals failed for %s', getattr(self, 'invoice_number', self.pk)
            )
    
    def update_totals(self):
        """Calculate and save totals"""
        self.calculate_totals()
        self.save(update_fields=['total_amount', 'balance', 'status'])
        self._sync_pharmacy_after_totals_saved()
    
    def mark_as_paid(self, amount=None, payment_method='cash', processed_by=None, reference_number='', validate=True):
        """
        Mark invoice as paid and create proper accounting entries
        
        Args:
            amount: Payment amount (None = full balance)
            payment_method: Payment method ('cash', 'card', etc.)
            processed_by: User processing the payment
            reference_number: Payment reference number
            validate: If True, validate payment before processing
        
        Returns:
            Transaction object
        """
        from decimal import Decimal
        from .models_accounting import Transaction, PaymentReceipt
        from django.db import transaction as db_transaction
        
        if amount is None:
            amount = self.balance
        
        amount = Decimal(str(amount))
        
        # Validate payment before processing
        if validate:
            validation = self.validate_before_payment(amount, payment_method)
            if not validation['valid']:
                from django.core.exceptions import ValidationError
                raise ValidationError(f"Payment validation failed: {', '.join(validation['errors'])}")
            if validation['warnings']:
                import logging
                logger = logging.getLogger(__name__)
                for warning in validation['warnings']:
                    logger.warning(f"Payment warning for invoice {self.invoice_number}: {warning}")
        
        # Process payment in transaction to ensure consistency
        with db_transaction.atomic():
            # Check for duplicate transaction (prevent duplicate payments)
            from datetime import timedelta
            recent_cutoff = timezone.now() - timedelta(minutes=1)
            
            existing_transaction = Transaction.objects.filter(
                transaction_type='payment_received',
                invoice=self,
                amount=amount,
                payment_method=payment_method,
                transaction_date__gte=recent_cutoff,
                is_deleted=False
            ).first()
            
            if existing_transaction:
                # Duplicate found - return existing transaction instead of creating new
                logger.warning(
                    f"Duplicate payment transaction detected for invoice {self.invoice_number}. "
                    f"Using existing transaction {existing_transaction.id}"
                )
                try:
                    from .models_accounting import PaymentReceipt

                    rec = PaymentReceipt.objects.filter(
                        transaction=existing_transaction, invoice=self, is_deleted=False
                    ).first()
                    self.calculate_totals()
                    self.save(update_fields=['balance', 'status', 'total_amount'])
                    self._sync_pharmacy_after_totals_saved(
                        receipt=rec, verified_by_user=processed_by
                    )
                except Exception:
                    pass
                return existing_transaction
            
            # Record the payment as a Transaction
            transaction = Transaction.objects.create(
                transaction_type='payment_received',
                invoice=self,
                patient=self.patient,
                amount=amount,
                payment_method=payment_method,
                reference_number=reference_number,
                processed_by=processed_by,
                transaction_date=timezone.now(),
                notes=f'Payment for Invoice {self.invoice_number}'
            )
            
            # Check for duplicate receipt before creating
            existing_receipt = PaymentReceipt.objects.filter(
                transaction=transaction,
                invoice=self,
                is_deleted=False
            ).first()
            
            if not existing_receipt:
                # Create payment receipt
                PaymentReceipt.objects.create(
                    transaction=transaction,
                    invoice=self,
                    patient=self.patient,
                    amount_paid=amount,
                    payment_method=payment_method,
                    received_by=processed_by,
                    receipt_date=timezone.now(),
                    notes=f'Payment for Invoice {self.invoice_number}'
                )
            
            # Recalculate totals to ensure accuracy
            self.calculate_totals()
            self.save(update_fields=['balance', 'status', 'total_amount'])

            try:
                rec = PaymentReceipt.objects.filter(
                    transaction=transaction, invoice=self, is_deleted=False
                ).first()
                self._sync_pharmacy_after_totals_saved(
                    receipt=rec, verified_by_user=processed_by
                )
            except Exception:
                pass
        
        return transaction
    
    def get_days_overdue(self):
        """Get number of days overdue"""
        if self.status == 'overdue' or (self.status in ['issued', 'partially_paid'] and self.due_at and self.due_at < timezone.now()):
            delta = timezone.now() - self.due_at
            return delta.days
        return 0
    
    def validate_integrity(self):
        """
        Validate invoice integrity using billing validation service
        
        Returns:
            dict: Validation results with 'valid', 'errors', 'warnings', 'details'
        """
        from hospital.services.billing_validation_service import billing_validator
        return billing_validator.validate_invoice_integrity(self)
    
    def validate_before_payment(self, amount, payment_method='cash'):
        """
        Validate payment before processing
        
        Args:
            amount: Payment amount (Decimal or float)
            payment_method: Payment method string
        
        Returns:
            dict: Validation results
        """
        from hospital.services.billing_validation_service import billing_validator
        from decimal import Decimal
        return billing_validator.validate_payment(self, Decimal(str(amount)), payment_method)
    
    def reconcile(self):
        """
        Reconcile invoice - recalculate totals and balance, fix discrepancies
        
        Returns:
            dict: Reconciliation results
        """
        from hospital.services.billing_validation_service import billing_validator
        return billing_validator.reconcile_invoice(self)
    
    def is_valid(self):
        """
        Quick check if invoice is valid
        
        Returns:
            bool: True if invoice passes validation
        """
        validation = self.validate_integrity()
        return validation['valid']


class InvoiceLine(BaseModel):
    """Invoice line items"""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    service_code = models.ForeignKey(ServiceCode, on_delete=models.CASCADE, related_name='invoice_lines')
    prescription = models.ForeignKey(
        'Prescription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_lines',
        help_text="Link to prescription if this line item is for a drug"
    )
    description = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        ordering = ['created']
        # Prevent duplicate lines for same service_code on same invoice (unless prescription is different)
        # Note: We can't use unique_together because prescription is nullable
        # So we handle duplicate prevention in save() method instead
        indexes = [
            models.Index(fields=['invoice', 'service_code', 'is_deleted']),
            models.Index(fields=['prescription', 'is_deleted']),
        ]
    insurance_exclusion_rule = models.ForeignKey(
        'hospital.InsuranceExclusionRule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_lines',
        help_text="Reference to the exclusion rule that matched (if any)"
    )
    insurance_enforcement_action = models.CharField(
        max_length=20,
        blank=True,
        help_text="What the insurer expects us to do (block/patient_pay/warn)"
    )
    insurance_exclusion_reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Friendly explanation for frontdesk/pharmacy users"
    )
    is_insurance_excluded = models.BooleanField(
        default=False,
        help_text="If True, this line will never be sent to insurance claims"
    )
    patient_pay_cash = models.BooleanField(
        default=False,
        help_text="If True, this item requires cash payment from patient (insurance excluded but patient can pay)"
    )
    waived_at = models.DateTimeField(null=True, blank=True, help_text='When this line was waived (e.g. patient from old system)')
    waived_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='waived_invoice_lines',
        help_text='User (cashier) who waived this line'
    )
    waiver_reason = models.CharField(max_length=255, blank=True, help_text='Reason for waiver (e.g. Migrated from old system - already paid)')
    
    class Meta:
        ordering = ['created']
    
    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.description}"
    
    def get_subtotal(self):
        """Subtotal (qty × unit_price) for display when line is waived."""
        from decimal import Decimal
        return Decimal(str(self.quantity)) * Decimal(str(self.unit_price))

    def get_display_pricing(self):
        """
        (unit_price, line_total) for screens and APIs when stored fields are 0 (stale repricing/sync).
        See hospital.utils_invoice_line.invoice_line_display_unit_and_total.
        """
        if not hasattr(self, '_display_pricing_tuple'):
            from hospital.utils_invoice_line import invoice_line_display_unit_and_total
            self._display_pricing_tuple = invoice_line_display_unit_and_total(self)
        return self._display_pricing_tuple

    @property
    def display_unit_price(self):
        return self.get_display_pricing()[0]

    @property
    def display_line_total(self):
        return self.get_display_pricing()[1]

    def save(self, *args, **kwargs):
        """
        Calculate line total before saving and prevent duplicates
        """
        from decimal import Decimal
        from django.db import transaction
        
        self.__dict__.pop('_display_pricing_tuple', None)
        self._evaluate_insurance_exclusions()
        
        subtotal = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))
        tax = Decimal(str(self.tax_amount or 0))
        discount = Decimal(str(self.discount_amount or 0))
        # When waived, ensure discount = subtotal + tax so line_total = 0 (never exceed -> negative total)
        if getattr(self, 'waived_at', None):
            full_waive = subtotal + tax
            if discount != full_waive:
                self.discount_amount = full_waive
                discount = full_waive
        # Cap discount at subtotal + tax to prevent negative line_total (e.g. after qty changed)
        elif discount > subtotal + tax:
            self.discount_amount = subtotal + tax
            discount = subtotal + tax
        self.line_total = subtotal - discount + tax
        
        # Prevent duplicates: Check for existing line with same service_code before saving
        # This is a safety net in case duplicate prevention wasn't done at creation time
        if self.invoice and self.service_code and not self.pk:
            with transaction.atomic():
                # Lock invoice to prevent race conditions
                invoice = Invoice.objects.select_for_update().get(pk=self.invoice.pk)
                
                # Check for existing line with same service_code (for prescriptions, same drug)
                existing_line = InvoiceLine.objects.filter(
                    invoice=invoice,
                    service_code=self.service_code,
                    is_deleted=False
                ).exclude(pk=self.pk if self.pk else None).first()
                
                if existing_line:
                    # Merge into existing line instead of creating duplicate
                    # LAB lines: never add quantity (one result = one bill, final once sent to cashier)
                    is_lab = self.service_code and getattr(self.service_code, 'code', '').startswith('LAB-')
                    if not is_lab:
                        existing_line.quantity += Decimal(str(self.quantity))
                    existing_line.unit_price = self.unit_price
                    existing_line.discount_amount += Decimal(str(self.discount_amount))
                    existing_line.tax_amount += Decimal(str(self.tax_amount))
                    existing_line.line_total = (
                        existing_line.quantity * existing_line.unit_price
                        - existing_line.discount_amount
                        + existing_line.tax_amount
                    )
                    
                    # Update description to reflect total quantity (robust: strip trailing " xN" pattern)
                    def _base_desc(d):
                        if not d:
                            return str(d).strip()
                        s = str(d).strip()
                        cleaned = re.sub(r'\s*x\s*\d+\s*$', '', s).strip()
                        return cleaned or s
                    if existing_line.description:
                        base_desc = _base_desc(existing_line.description)
                        existing_line.description = f"{base_desc} x{int(existing_line.quantity)}"
                    elif self.description:
                        base_desc = _base_desc(self.description)
                        existing_line.description = f"{base_desc} x{int(existing_line.quantity)}"
                    
                    # Keep the most recent prescription
                    if self.prescription:
                        if not existing_line.prescription or (
                            existing_line.prescription and 
                            self.prescription.created > existing_line.prescription.created
                        ):
                            existing_line.prescription = self.prescription
                    
                    existing_line.save()
                    
                    # Recalculate invoice totals
                    invoice.calculate_totals()
                    invoice.save()
                    
                    # Don't save this instance - it's been merged
                    return existing_line
        
        super().save(*args, **kwargs)
        
        # Recalculate invoice totals
        if self.invoice:
            self.invoice.calculate_totals()
            self.invoice.save()

    def _evaluate_insurance_exclusions(self):
        """
        Run insurance exclusion logic before saving the line so we can block or mark items.
        Handles both service codes and drugs (via prescription link).
        """
        self.is_insurance_excluded = False
        self.patient_pay_cash = False
        self.insurance_exclusion_rule = None
        self.insurance_enforcement_action = ''
        self.insurance_exclusion_reason = ''
        
        invoice = getattr(self, 'invoice', None)
        if not invoice or not invoice.payer or invoice.payer.payer_type == 'cash':
            return
        
        patient = invoice.patient
        payer = invoice.payer
        if not patient or not payer:
            return
        
        # Get drug from prescription if available
        drug = None
        if self.prescription and hasattr(self.prescription, 'drug'):
            drug = self.prescription.drug
        
        from .services.insurance_exclusion_service import InsuranceExclusionService
        exclusion_service = InsuranceExclusionService(
            patient=patient,
            payer=payer,
            service_code=self.service_code,
            drug=drug,
        )
        result = exclusion_service.evaluate()
        if not result.rule:
            return
        
        self.insurance_exclusion_rule = result.rule
        self.insurance_enforcement_action = result.enforcement
        self.insurance_exclusion_reason = result.reason
        self.is_insurance_excluded = result.is_excluded
        
        # If enforcement is 'patient_pay', mark for cash payment
        if result.enforcement == 'patient_pay' and result.is_excluded:
            self.patient_pay_cash = True
        
        if result.should_block:
            raise ValidationError(result.reason)


# ==================== NEW FEATURES: APPOINTMENTS ====================

class Appointment(BaseModel):
    """Patient appointments"""
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    provider = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='appointments')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='appointments')
    appointment_date = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=30)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    reason = models.TextField()
    notes = models.TextField(blank=True)
    reminder_sent = models.BooleanField(default=False)
    # Consulting room assignment (optional - can be assigned later)
    consulting_room = models.ForeignKey(
        'ConsultingRoom',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointments',
        help_text="Consulting room assigned for this appointment"
    )
    
    class Meta:
        ordering = ['-appointment_date']
        indexes = [
            models.Index(fields=['provider', 'appointment_date', 'status']),
            models.Index(fields=['appointment_date', 'status']),
        ]
    
    def __str__(self):
        return f"{self.patient.full_name} - {self.appointment_date.strftime('%Y-%m-%d %H:%M')}"
    
    def is_past_due(self):
        """Check if appointment is past due"""
        return self.appointment_date < timezone.now() and self.status in ['scheduled', 'confirmed']


# ==================== NEW FEATURES: MEDICAL RECORDS ====================

class MedicalRecord(BaseModel):
    """Medical records/documents"""
    RECORD_TYPES = [
        ('lab_result', 'Lab Result'),
        ('imaging', 'Imaging Report'),
        ('prescription', 'Prescription'),
        ('discharge_summary', 'Discharge Summary'),
        ('consultation_note', 'Consultation Note'),
        ('surgical_report', 'Surgical Report'),
        ('other', 'Other'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='medical_records')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='medical_records', null=True, blank=True)
    record_type = models.CharField(max_length=20, choices=RECORD_TYPES)
    title = models.CharField(max_length=200)
    document = models.FileField(upload_to='medical_records/', blank=True, null=True)
    content = models.TextField(blank=True)
    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-created']
        # Note: Unique constraint added via migration to handle is_deleted condition
    
    def __str__(self):
        return f"{self.title} - {self.patient.full_name}"
    
    def save(self, *args, **kwargs):
        """Prevent duplicate records"""
        from django.utils import timezone
        from django.db.models import Q
        
        # Check for existing duplicate before saving
        if not self.is_deleted and self.patient_id and self.record_type and self.title:
            existing = MedicalRecord.objects.filter(
                patient_id=self.patient_id,
                encounter_id=self.encounter_id,
                record_type=self.record_type,
                title=self.title,
                is_deleted=False
            ).exclude(id=self.id if self.id else None).first()
            
            if existing:
                # If duplicate exists, update the existing one instead of creating new
                # Update content if new content is provided and existing is empty
                if self.content and not existing.content:
                    existing.content = self.content
                if self.document and not existing.document:
                    existing.document = self.document
                if self.created_by and not existing.created_by:
                    existing.created_by = self.created_by
                existing.save()
                # Set self.pk to existing to prevent creation
                self.pk = existing.pk
                self.id = existing.id
                return
        
        super().save(*args, **kwargs)


# ==================== NEW FEATURES: NOTIFICATIONS ====================

class Notification(BaseModel):
    """System notifications"""
    NOTIFICATION_TYPES = [
        ('appointment_reminder', 'Appointment Reminder'),
        ('lab_result_ready', 'Lab Result Ready'),
        ('imaging_result_ready', 'Imaging Result Ready'),
        ('invoice_overdue', 'Invoice Overdue'),
        ('low_stock', 'Low Stock Alert'),
        ('bed_available', 'Bed Available'),
        ('order_urgent', 'Urgent Order'),
        ('activity', 'Activity / Event'),
        ('other', 'Other'),
    ]
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    related_object_id = models.UUIDField(null=True, blank=True)
    related_object_type = models.CharField(max_length=50, blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.title} - {self.recipient.username}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()


# Import advanced models to ensure they're registered
# This must be at the end to avoid circular imports
try:
    from . import models_advanced  # noqa
except ImportError:
    pass

# Import chat models
try:
    from . import models_chat  # noqa
except ImportError:
    pass

# Import workflow and accounting models
try:
    from . import models_workflow  # noqa
    from . import models_accounting  # noqa
    from . import models_hr  # noqa
except ImportError:
    pass

# Import missing features models
try:
    from . import models_missing_features  # noqa
except ImportError:
    pass

# Import specialist models
try:
    from . import models_specialists  # noqa
except ImportError:
    pass

# Import procurement models
try:
    from . import models_procurement  # noqa
except ImportError:
    pass

# Import pricing models
try:
    from . import models_pricing  # noqa
except ImportError:
    pass

# Import diagnosis models
try:
    from . import models_diagnosis  # noqa
except ImportError:
    pass

# Import blood bank models
try:
    from . import models_blood_bank  # noqa
except ImportError:
    pass

# Import login tracking models
try:
    from . import models_login_tracking  # noqa
except ImportError:
    pass

# Import patient deposit models
try:
    from . import models_patient_deposits  # noqa
except ImportError:
    pass

# Import medical records models
try:
    from . import models_medical_records  # noqa
except ImportError:
    pass

# Import HR activities models
try:
    from . import models_hr_activities  # noqa
except ImportError:
    pass

# Import HOD models
try:
    from . import models_hod_simple  # noqa
except ImportError:
    pass
