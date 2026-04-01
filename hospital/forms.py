"""
Forms for Hospital Management System.
"""
from django import forms
from django.contrib.auth.models import User
from .models import (
    Patient, Encounter, Admission, Invoice, InvoiceLine,
    VitalSign, Order, Prescription, Bed, Ward, Department, Staff
)
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, Fieldset, HTML, Div


class PatientForm(forms.ModelForm):
    """Patient registration form with world-class insurance integration"""
    # Payer type selection
    payer_type = forms.ChoiceField(
        choices=[
            ('', 'Select Payment Type...'),
            ('insurance', 'Insurance'),
            ('corporate', 'Corporate'),
            ('cash', 'Cash'),
        ],
        required=False,
        label="Payment Type",
        widget=forms.Select(attrs={
            'class': 'form-select', 
            'id': 'id_payer_type'
        }),
        help_text="Select how the patient will pay for services"
    )
    
    # Insurance fields
    selected_insurance_company = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label="Insurance Company",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_selected_insurance_company'}),
        help_text="Select the patient's insurance company"
    )
    selected_insurance_plan = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label="Insurance Plan",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_selected_insurance_plan'}),
        help_text="Select the insurance plan"
    )
    
    # Corporate fields - using Payer model with payer_type='corporate'
    selected_corporate_company = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label="Corporate Company",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_selected_corporate_company'}),
        help_text="Select the corporate company (Payer or corporate account)",
    )
    employee_id = forms.CharField(
        required=False,
        max_length=50,
        label="Employee ID",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'id': 'id_employee_id',
            'placeholder': 'Employee ID (if corporate)'
        }),
        help_text="Employee ID number (for corporate patients)"
    )
    
    # Cash fields
    receiving_point = forms.CharField(
        required=False,
        max_length=200,
        label="Receiving Point",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'id': 'id_receiving_point',
            'placeholder': 'Cash collection point/location'
        }),
        help_text="Location where cash payments will be received (e.g., Main Cashier, Pharmacy Cashier)"
    )
    
    class Meta:
        model = Patient
        fields = [
            'first_name', 'last_name', 'middle_name',
            'date_of_birth', 'gender', 'blood_type',
            'phone_number', 'email', 'address',
            'national_id',
            'next_of_kin_name', 'next_of_kin_phone', 'next_of_kin_relationship',
            'insurance_company', 'insurance_id', 'insurance_member_id',
            'allergies', 'chronic_conditions', 'medications'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'national_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'National ID (optional)'}),
            'insurance_company': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter insurance company name (or select above)'}),
            'insurance_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Insurance ID/Policy Number'}),
            'insurance_member_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Member ID'}),
            'allergies': forms.Textarea(attrs={'rows': 2}),
            'chronic_conditions': forms.Textarea(attrs={'rows': 2}),
            'medications': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        # CRITICAL: Disable auto-save on patient registration form to prevent duplicate submissions
        self.helper.attrs = {'data-no-autosave': ''}

        # Make sure fields match model defaults (not required if model has defaults)
        self.fields['address'].required = False  # Model has default=''
        self.fields['next_of_kin_name'].required = False  # Model has default=''
        self.fields['next_of_kin_relationship'].required = False  # Model has default=''
        
        # Load insurance companies
        try:
            from .models_insurance_companies import InsuranceCompany, InsurancePlan
            self.fields['selected_insurance_company'].queryset = InsuranceCompany.objects.filter(
                is_active=True,
                status='active',
                is_deleted=False
            ).order_by('name')
            self.fields['selected_insurance_plan'].queryset = InsurancePlan.objects.filter(
                is_active=True,
                is_deleted=False
            ).order_by('plan_name')
        except:
            # Models not migrated yet
            self.fields['selected_insurance_company'].queryset = self.fields['selected_insurance_company'].queryset.none()
            self.fields['selected_insurance_plan'].queryset = self.fields['selected_insurance_plan'].queryset.none()
        
        # Load corporate companies from Payer model (corporate payers)
        try:
            from .models import Payer
            corporate_payers = Payer.objects.filter(
                payer_type='corporate',
                is_active=True,
                is_deleted=False
            ).order_by('name')
            
            if corporate_payers.exists():
                self.fields['selected_corporate_company'].queryset = corporate_payers
            else:
                # Fallback to CorporateAccount if no corporate payers exist
                from .models_enterprise_billing import CorporateAccount
                self.fields['selected_corporate_company'].queryset = CorporateAccount.objects.filter(
                    is_active=True,
                    is_deleted=False
                ).order_by('company_name')
        except Exception as e:
            # If CorporateAccount doesn't exist or error, use Payer
            try:
                from .models import Payer
                self.fields['selected_corporate_company'].queryset = Payer.objects.filter(
                    payer_type='corporate',
                    is_active=True,
                    is_deleted=False
                ).order_by('name')
            except:
                self.fields['selected_corporate_company'].queryset = self.fields['selected_corporate_company'].queryset.none()

        # Editing: pre-fill payment type and selectors from patient.primary_insurance (drives billing)
        if self.instance and self.instance.pk:
            try:
                self.instance.refresh_from_db(fields=['primary_insurance'])
            except Exception:
                pass
            payer = getattr(self.instance, 'primary_insurance', None)
            if payer and not payer.is_deleted:
                pt = (payer.payer_type or '').strip().lower()
                if pt == 'cash':
                    self.fields['payer_type'].initial = 'cash'
                elif pt == 'corporate':
                    self.fields['payer_type'].initial = 'corporate'
                    corp_qs = self.fields['selected_corporate_company'].queryset
                    corp_model = corp_qs.model
                    try:
                        from .models import Payer as PayerModel
                        from .models_enterprise_billing import CorporateAccount

                        if corp_model is PayerModel and corp_qs.filter(pk=payer.pk).exists():
                            self.fields['selected_corporate_company'].initial = payer.pk
                        elif corp_model is CorporateAccount:
                            ca = CorporateAccount.objects.filter(
                                company_name__iexact=payer.name,
                                is_deleted=False,
                            ).first()
                            if ca and corp_qs.filter(pk=ca.pk).exists():
                                self.fields['selected_corporate_company'].initial = ca.pk
                    except Exception:
                        pass
                elif pt in ('private', 'nhis', 'insurance'):
                    self.fields['payer_type'].initial = 'insurance'
                    try:
                        from .models_insurance_companies import InsuranceCompany, PatientInsurance

                        ic = InsuranceCompany.objects.filter(
                            name__iexact=payer.name,
                            is_deleted=False,
                        ).first()
                        if ic:
                            self.fields['selected_insurance_company'].initial = ic.pk
                        enr = (
                            PatientInsurance.objects.filter(
                                patient=self.instance,
                                is_primary=True,
                                is_deleted=False,
                            )
                            .select_related('insurance_plan')
                            .first()
                        )
                        if enr:
                            if enr.insurance_plan_id:
                                self.fields['selected_insurance_plan'].initial = enr.insurance_plan_id
                    except Exception:
                        pass
                else:
                    self.fields['payer_type'].initial = 'cash'
            else:
                self.fields['payer_type'].initial = 'cash'

        submit_label = 'Save Patient' if (self.instance and self.instance.pk) else 'Register Patient'

        self.helper.layout = Layout(
            Fieldset('Personal Information',
                Row(Column('first_name', css_class='form-group col-md-4'),
                    Column('middle_name', css_class='form-group col-md-4'),
                    Column('last_name', css_class='form-group col-md-4')),
                Row(Column('date_of_birth', css_class='form-group col-md-4'),
                    Column('gender', css_class='form-group col-md-4'),
                    Column('blood_type', css_class='form-group col-md-4')),
            ),
            Fieldset('Contact Information',
                Row(Column('phone_number', css_class='form-group col-md-6'),
                    Column('email', css_class='form-group col-md-6')),
                'address',
            ),
            Fieldset('💳 Payment Type & Billing Information',
                HTML('<div class="alert alert-info mb-3"><i class="bi bi-info-circle"></i> <strong>How Billing Works:</strong> Select "Payment Type" below. This will set the patient\'s default payer and all bills will go to this payer.</div>'),
                'payer_type',
                Div(
                    Row(Column('selected_insurance_company', css_class='form-group col-md-6'),
                        Column('selected_insurance_plan', css_class='form-group col-md-6')),
                    Row(Column('insurance_id', css_class='form-group col-md-6'),
                        Column('insurance_member_id', css_class='form-group col-md-6')),
                    HTML('<small class="text-muted d-block mb-2">Or enter manually below:</small>'),
                    Row(Column('insurance_company', css_class='form-group col-md-12')),
                    HTML('<div class="alert alert-warning mt-2 mb-0"><small><i class="bi bi-exclamation-triangle"></i> <strong>Note:</strong> When you select an insurance company above, the patient\'s default payer will be automatically set to that insurance. All bills will go to this insurance company.</small></div>'),
                    css_id='insurance_fields',
                    css_class='mt-3',
                    style='display:none;'
                ),
                Div(
                    Row(Column('selected_corporate_company', css_class='form-group col-md-6'),
                        Column('employee_id', css_class='form-group col-md-6')),
                    css_id='corporate_fields',
                    css_class='mt-3',
                    style='display:none;'
                ),
                Div(
                    'receiving_point',
                    css_id='cash_fields',
                    css_class='mt-3',
                    style='display:none;'
                ),
            ),
            Fieldset('Emergency Contact',
                Row(Column('next_of_kin_name', css_class='form-group col-md-4'),
                    Column('next_of_kin_phone', css_class='form-group col-md-4'),
                    Column('next_of_kin_relationship', css_class='form-group col-md-4')),
            ),
            Fieldset('Medical Information',
                'allergies', 'chronic_conditions', 'medications'
            ),
            Submit('submit', submit_label, css_class='btn btn-primary btn-lg')
        )
    
    def clean(self):
        """Check for duplicate patients before saving"""
        cleaned_data = super().clean()
        
        # Ensure cleaned_data is a dict
        if not cleaned_data:
            return cleaned_data
        
        # Check if user wants to proceed with duplicate (for family members)
        # This is passed from the view via form data or POST data
        proceed_with_duplicate = False
        if hasattr(self, 'data') and self.data:
            # Django QueryDict returns list, so check both string and list
            proceed_val = self.data.get('proceed_with_duplicate')
            if proceed_val:
                if isinstance(proceed_val, list):
                    proceed_with_duplicate = proceed_val[0] == 'true' if proceed_val else False
                else:
                    proceed_with_duplicate = str(proceed_val).lower() == 'true'
        
        # Log for debugging
        if proceed_with_duplicate:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("User proceeding with potential duplicate - bypassing form validation")
        
        first_name = (cleaned_data.get('first_name') or '').strip()
        last_name = (cleaned_data.get('last_name') or '').strip()
        date_of_birth = cleaned_data.get('date_of_birth')
        phone_number = (cleaned_data.get('phone_number') or '').strip()
        email = (cleaned_data.get('email') or '').strip()
        
        # Get the instance (if editing existing patient)
        instance = self.instance
        patient_id = instance.pk if instance else None
        
        # Normalize phone number for comparison (remove spaces, dashes, etc.)
        def normalize_phone(phone):
            if not phone:
                return ''
            # Remove common separators
            phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            # Normalize Ghana numbers: 0241234567, +233241234567, 233241234567 -> 233241234567
            if phone.startswith('0') and len(phone) == 10:
                phone = '233' + phone[1:]
            elif phone.startswith('+'):
                phone = phone[1:]
            return phone
        
        normalized_phone = normalize_phone(phone_number)
        
        # Check for duplicates
        # CRITICAL: Use self._meta.model instead of importing Patient locally
        # Local imports cause variable shadowing issues in views that use this form
        PatientModel = self._meta.model  # Get Patient model from form's Meta class
        from django.db.models import Q
        
        duplicate_checks = []
        
        # Check 1: Same name + DOB + Phone (strongest match - only block this)
        # RELAXED: Only block if name + DOB + phone match (strong duplicate)
        # Phone-only or name-only matches are allowed (family members can share phones/names)
        if first_name and last_name and normalized_phone and date_of_birth and date_of_birth != '2000-01-01':
            # Strong match: name + DOB + phone - this is likely a duplicate
            existing = PatientModel.objects.filter(
                first_name__iexact=first_name,
                last_name__iexact=last_name,
                date_of_birth=date_of_birth,
                is_deleted=False
            ).exclude(pk=patient_id)
            
            # Check phone number matches (normalized)
            for patient in existing:
                if normalize_phone(patient.phone_number) == normalized_phone:
                    # Strong duplicate: name + DOB + phone match
                    duplicate_checks.append(
                        f"⚠️ A patient with the same name ({first_name} {last_name}), "
                        f"date of birth ({date_of_birth}), and phone number ({phone_number}) already exists. "
                        f"MRN: {patient.mrn}. If this is a different person (e.g., family member), you can proceed."
                    )
                    break
        
        # Check 2: Same email (if provided) - BLOCK this as email should be unique
        if email:
            existing = PatientModel.objects.filter(
                email__iexact=email,
                is_deleted=False
            ).exclude(pk=patient_id)
            
            if existing.exists():
                patient = existing.first()
                duplicate_checks.append(
                    f"A patient with the same email ({email}) already exists. "
                    f"Name: {patient.full_name}, MRN: {patient.mrn}"
                )
        
        # RELAXED: Removed Check 3 (name + DOB without phone) - too weak, allows family members
        # RELAXED: Removed Check 4 (phone-only) - too weak, allows family members sharing phones
        # Only strong duplicates (name + DOB + phone) and email duplicates are blocked
        
        # Check 5: Same national_id (if provided)
        national_id = cleaned_data.get('national_id') or ''
        national_id = national_id.strip() if national_id else ''
        if national_id:
            existing = PatientModel.objects.filter(
                national_id=national_id,
                is_deleted=False
            ).exclude(pk=patient_id)
            
            if existing.exists():
                patient = existing.first()
                duplicate_checks.append(
                    f"A patient with the same National ID ({national_id}) already exists. "
                    f"Name: {patient.full_name}, MRN: {patient.mrn}"
                )
        
        # Raise validation error if duplicates found (but allow user to proceed if they confirm)
        if duplicate_checks and not proceed_with_duplicate:
            # Format error message for better display
            error_messages = []
            for check in duplicate_checks:
                error_messages.append(check)
            
            # Create a single error message with note about family members
            error_message = "⚠️ Potential duplicate patient detected:\n\n" + "\n\n".join(error_messages)
            error_message += "\n\n💡 Note: This could be a family member or different person sharing the same contact information."
            error_message += "\n\nPlease verify this is not a duplicate before proceeding, or proceed if this is a different person."
            
            # Raise as non-field error so it displays prominently at top of form
            # The view will handle showing a confirmation option
            raise forms.ValidationError(error_message)
        elif duplicate_checks and proceed_with_duplicate:
            # User confirmed they want to proceed - log it but don't block
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"User proceeding with potential duplicate - bypassing form validation")

        # If Payment Type stayed on "Select..." but insurance/corporate fields were filled, infer payer_type
        # (otherwise apply_patient_payer_from_form skips and everything stays cash / null)
        pt = (cleaned_data.get('payer_type') or '').strip()
        if not pt:
            if cleaned_data.get('selected_insurance_company'):
                cleaned_data['payer_type'] = 'insurance'
            elif cleaned_data.get('selected_corporate_company'):
                cleaned_data['payer_type'] = 'corporate'
        
        return cleaned_data


class EncounterForm(forms.ModelForm):
    """Encounter form"""
    class Meta:
        model = Encounter
        fields = [
            'patient', 'encounter_type', 'status',
            'location', 'provider', 'chief_complaint', 'diagnosis', 'notes'
        ]
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-select'}),
            'encounter_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.Select(attrs={'class': 'form-select'}),
            'provider': forms.Select(attrs={'class': 'form-select'}),
            'chief_complaint': forms.Textarea(attrs={'rows': 3}),
            'diagnosis': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['patient'].queryset = Patient.objects.filter(is_deleted=False)
        self.fields['location'].queryset = Ward.objects.filter(is_active=True, is_deleted=False)
        self.fields['provider'].queryset = Staff.objects.filter(is_active=True, is_deleted=False)
        self.helper = FormHelper()
        self.helper.add_input(Submit('submit', 'Save Encounter', css_class='btn btn-primary'))
    
    def clean(self):
        """Prevent duplicate encounters at form level"""
        cleaned_data = super().clean()
        
        # Only check for duplicates if this is a new encounter (no instance.pk)
        if not self.instance.pk:
            patient = cleaned_data.get('patient')
            encounter_type = cleaned_data.get('encounter_type')
            chief_complaint = cleaned_data.get('chief_complaint', '')
            
            if patient and encounter_type:
                from django.utils import timezone
                from datetime import timedelta
                
                # Check for very recent duplicate encounter (within 5 minutes)
                five_minutes_ago = timezone.now() - timedelta(minutes=5)
                existing = Encounter.objects.filter(
                    patient=patient,
                    encounter_type=encounter_type,
                    chief_complaint=chief_complaint,
                    status='active',
                    started_at__gte=five_minutes_ago,
                    is_deleted=False
                ).order_by('-created').first()
                
                if existing:
                    from django.core.exceptions import ValidationError
                    raise ValidationError(
                        f'A similar active encounter already exists for {patient.full_name} '
                        f'created at {existing.created.strftime("%Y-%m-%d %H:%M")}. '
                        f'Please use the existing encounter or wait a few minutes before creating a new one.'
                    )
        
        return cleaned_data


class AdmissionForm(forms.ModelForm):
    """Admission form"""
    class Meta:
        model = Admission
        fields = [
            'encounter', 'ward', 'bed', 'admitting_doctor',
            'diagnosis_icd10', 'notes'
        ]
        widgets = {
            'encounter': forms.Select(attrs={'class': 'form-select'}),
            'ward': forms.Select(attrs={'class': 'form-select'}),
            'bed': forms.Select(attrs={'class': 'form-select'}),
            'admitting_doctor': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get distinct encounters - prefer most recent per patient per day
        # Use DISTINCT ON approach since UUID fields don't support MAX()
        from django.db import connection
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT ON (patient_id, started_at::date) id
                FROM hospital_encounter
                WHERE is_deleted = false AND status = 'active'
                ORDER BY patient_id, started_at::date, id DESC
            """)
            latest_ids = [row[0] for row in cursor.fetchall()]
        
        self.fields['encounter'].queryset = Encounter.objects.filter(
            id__in=latest_ids
        ).select_related('patient').order_by('-started_at', '-id')
        self.fields['ward'].queryset = Ward.objects.filter(is_active=True, is_deleted=False)
        self.fields['bed'].queryset = Bed.objects.filter(
            status='available',
            is_active=True,
            is_deleted=False
        )
        self.fields['admitting_doctor'].queryset = Staff.objects.filter(
            profession='doctor',
            is_active=True,
            is_deleted=False
        )
        self.helper = FormHelper()
        self.helper.add_input(Submit('submit', 'Admit Patient', css_class='btn btn-primary'))


class InvoiceForm(forms.ModelForm):
    """Invoice form"""
    class Meta:
        model = Invoice
        fields = [
            'patient', 'encounter', 'payer', 'status',
            'issued_at', 'due_at'
        ]
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-select'}),
            'encounter': forms.Select(attrs={'class': 'form-select'}),
            'payer': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'issued_at': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'due_at': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['patient'].queryset = Patient.objects.filter(is_deleted=False)
        self.fields['encounter'].queryset = Encounter.objects.filter(is_deleted=False)
        self.helper = FormHelper()
        self.helper.add_input(Submit('submit', 'Save Invoice', css_class='btn btn-primary'))


class VitalSignForm(forms.ModelForm):
    """Vital signs form"""
    class Meta:
        model = VitalSign
        fields = [
            'encounter', 'systolic_bp', 'diastolic_bp', 'pulse',
            'temperature', 'spo2', 'weight', 'height',
            'respiratory_rate', 'notes'
        ]
        widgets = {
            'encounter': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class ReferralForm(forms.ModelForm):
    """Form for creating a referral to a specialist"""
    class Meta:
        from .models_specialists import Referral, Specialty, SpecialistProfile
        model = Referral
        fields = [
            'specialty', 'specialist', 'reason', 'clinical_summary', 'priority'
        ]
        widgets = {
            'specialty': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'specialist': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'reason': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Reason for referral...'}),
            'clinical_summary': forms.Textarea(attrs={'rows': 5, 'class': 'form-control', 'placeholder': 'Clinical summary, relevant findings, test results...'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        from .models_specialists import Specialty, SpecialistProfile
        super().__init__(*args, **kwargs)
        self.fields['specialty'].queryset = Specialty.objects.filter(is_active=True, is_deleted=False)
        self.fields['specialist'].queryset = SpecialistProfile.objects.filter(is_active=True, is_deleted=False)
        
        # Update specialist queryset when specialty is selected (handled via JavaScript in template)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset('Referral Information',
                Row(Column('specialty', css_class='form-group col-md-6'),
                    Column('specialist', css_class='form-group col-md-6')),
                Row(Column('priority', css_class='form-group col-md-4')),
                'reason',
                'clinical_summary',
            ),
            Submit('submit', 'Create Referral', css_class='btn btn-primary')
        )


class ReferralResponseForm(forms.ModelForm):
    """Form for specialist to respond to a referral"""
    class Meta:
        from .models_specialists import Referral
        model = Referral
        fields = ['specialist_notes', 'appointment_date']
        widgets = {
            'specialist_notes': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'appointment_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['appointment_date'].required = False
        self.helper = FormHelper()
        self.helper.add_input(Submit('accept', 'Accept Referral', css_class='btn btn-success'))
        self.helper.add_input(Submit('decline', 'Decline Referral', css_class='btn btn-danger'))


class TabularLabReportForm(forms.Form):
    """Tabular lab report form for structured test entry (FBC, LFT, RFT, etc.)"""
    
    # Common fields
    test_type = forms.ChoiceField(
        choices=[
            ('single', 'Single Value / Other'),
            ('fbc', 'Full Blood Count'),
            ('lft', 'Liver Function Tests'),
            ('rft', 'Renal Function Tests'),
            ('lipid', 'Lipid Profile'),
            ('tft', 'Thyroid Function Tests'),
            ('glucose', 'Blood Glucose'),
            ('electrolytes', 'Electrolytes'),
            ('urine', 'Urine Routine Examination'),
            ('stool', 'Stool Routine Examination'),
            ('malaria', 'Malaria (RDT/Microscopy)'),
            ('blood_group', 'Blood Group & Rhesus'),
            ('sickle', 'Sickle Cell'),
            ('coagulation', 'Coagulation Panel'),
            ('serology', 'Serology (HIV/VDRL/etc)'),
            ('semen', 'Semen Analysis'),
            ('afb', 'AFB / Sputum'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    # Single-value tests (e.g. Prolactin, hormones, other analytes)
    result_value = forms.CharField(required=False, max_length=64)
    result_unit = forms.CharField(required=False, max_length=32)
    
    status = forms.ChoiceField(
        choices=[
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    qualitative_result = forms.CharField(
        required=False,
        widget=forms.Select(
            choices=[
                ('', '-- Not Applicable --'),
                ('Negative', 'Negative'),
                ('Positive', 'Positive'),
                ('Reactive', 'Reactive'),
                ('Non-Reactive', 'Non-Reactive'),
                ('Normal', 'Normal'),
                ('Abnormal', 'Abnormal'),
            ],
            attrs={'class': 'form-select'}
        )
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control'})
    )
    
    # FBC fields (Evans Lab format: WBC, Lymph#, Mid#, Gran#, Lymph%, Mid%, Gran%, PLT, MPV, PDW, PCT)
    wbc = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    lymph_count = forms.DecimalField(required=False, max_digits=6, decimal_places=2, label='Lymph#')
    mid_count = forms.DecimalField(required=False, max_digits=6, decimal_places=2, label='Mid#')
    gran_count = forms.DecimalField(required=False, max_digits=6, decimal_places=2, label='Gran#')
    lymph_perc = forms.DecimalField(required=False, max_digits=6, decimal_places=2, label='Lymph%')
    mid_perc = forms.DecimalField(required=False, max_digits=6, decimal_places=2, label='Mid%')
    gran_perc = forms.DecimalField(required=False, max_digits=6, decimal_places=2, label='Gran%')
    plt = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    mpv = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    pdw = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    pct = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    # Classic FBC (for compatibility)
    rbc = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    hgb = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    hct = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    mcv = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    mch = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    mchc = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    rdw_cv = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    rdw_sd = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    neut_perc = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    mono_perc = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    eos_perc = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    baso_perc = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    
    # LFT fields
    total_bili = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    direct_bili = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    indirect_bili = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    alt = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    ast = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    alp = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    ggt = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    total_protein = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    albumin = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    globulin = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    ag_ratio = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    
    # RFT fields
    urea = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    bun = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    creatinine = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    egfr = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    uric_acid = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    
    # Electrolytes (shared with RFT)
    sodium = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    potassium = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    chloride = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    bicarbonate = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    calcium = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    magnesium = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    phosphorus = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    
    # Lipid Profile fields
    total_chol = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    triglycerides = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    hdl = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    ldl = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    vldl = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    chol_hdl_ratio = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    ldl_hdl_ratio = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    non_hdl = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    
    # TFT fields
    tsh = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    free_t4 = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    total_t4 = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    free_t3 = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    total_t3 = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    
    # Glucose fields
    fbs = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    rbs = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    hba1c = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    ppbs = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    
    # Urine Routine (CHEMISTRY + MICROSCOPY) - industry standard per CLSI/IFCC
    urine_appearance = forms.CharField(required=False, max_length=64)
    urine_colour = forms.CharField(required=False, max_length=64)
    urine_ph = forms.DecimalField(required=False, max_digits=4, decimal_places=1)
    urine_sgravity = forms.DecimalField(required=False, max_digits=5, decimal_places=3)
    urine_protein = forms.CharField(required=False, max_length=64)
    urine_glucose = forms.CharField(required=False, max_length=64)
    urine_ketones = forms.CharField(required=False, max_length=64)
    urine_blood = forms.CharField(required=False, max_length=64)
    urine_nitrite = forms.CharField(required=False, max_length=64)
    urine_bilirubin = forms.CharField(required=False, max_length=64)
    urine_urobilinogen = forms.CharField(required=False, max_length=64)
    urine_leucocyte = forms.CharField(required=False, max_length=64)
    urine_pus_cells = forms.CharField(required=False, max_length=32)
    urine_epithelial_cells = forms.CharField(required=False, max_length=32)
    urine_rbc = forms.CharField(required=False, max_length=32)
    urine_cast = forms.CharField(required=False, max_length=64)
    urine_crystals = forms.CharField(required=False, max_length=64)
    urine_ova_cyst = forms.CharField(required=False, max_length=64)
    urine_t_vaginalis = forms.CharField(required=False, max_length=64)
    urine_bacteria = forms.CharField(required=False, max_length=64)
    urine_yeast = forms.CharField(required=False, max_length=64)
    
    # Stool Routine Examination
    stool_consistency = forms.CharField(required=False, max_length=64)
    stool_colour = forms.CharField(required=False, max_length=64)
    stool_mucus = forms.CharField(required=False, max_length=64)
    stool_blood = forms.CharField(required=False, max_length=64)
    stool_pus = forms.CharField(required=False, max_length=64)
    stool_ova = forms.CharField(required=False, max_length=64)
    stool_parasites = forms.CharField(required=False, max_length=64)
    stool_cysts = forms.CharField(required=False, max_length=64)
    stool_undigested_food = forms.CharField(required=False, max_length=64)
    stool_fat_globules = forms.CharField(required=False, max_length=64)
    stool_rbc = forms.CharField(required=False, max_length=64)
    stool_wbc = forms.CharField(required=False, max_length=64)
    
    # Malaria (WHO standard)
    malaria_result = forms.CharField(required=False, max_length=64)
    malaria_species = forms.CharField(required=False, max_length=64)
    malaria_count = forms.CharField(required=False, max_length=32)
    malaria_parasitemia = forms.CharField(required=False, max_length=32)
    malaria_stage = forms.CharField(required=False, max_length=64)
    
    # Blood Group & Rhesus (ISBT)
    bg_group = forms.CharField(required=False, max_length=16)
    bg_rhesus = forms.CharField(required=False, max_length=16)
    
    # Sickle Cell
    sickle_solubility = forms.CharField(required=False, max_length=64)
    sickle_electrophoresis = forms.CharField(required=False, max_length=64)
    
    # Coagulation
    coag_pt = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    coag_inr = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    coag_aptt = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    coag_fibrinogen = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    
    # Serology
    serology_result = forms.CharField(required=False, max_length=64)
    serology_titer = forms.CharField(required=False, max_length=32)
    
    # Semen Analysis (WHO)
    semen_volume = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    semen_liquefaction = forms.CharField(required=False, max_length=64)
    semen_ph = forms.DecimalField(required=False, max_digits=4, decimal_places=1)
    semen_count = forms.DecimalField(required=False, max_digits=10, decimal_places=0)
    semen_motility = forms.CharField(required=False, max_length=64)
    semen_morphology = forms.CharField(required=False, max_length=64)
    semen_wbc = forms.CharField(required=False, max_length=64)
    semen_vitality = forms.CharField(required=False, max_length=64)
    
    # AFB / Sputum
    afb_result = forms.CharField(required=False, max_length=64)
    afb_grade = forms.CharField(required=False, max_length=32)
    afb_organism = forms.CharField(required=False, max_length=64)
    
    def get_details_dict(self):
        """Extract all non-empty field values as a dictionary for JSON storage"""
        details = {}
        for field_name, field_value in self.cleaned_data.items():
            if field_name not in ['test_type', 'status', 'qualitative_result', 'notes']:
                if field_value is not None and field_value != '':
                    details[field_name] = str(field_value)
        return details
