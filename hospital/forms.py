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
    
    # Corporate fields
    selected_corporate_company = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label="Corporate Company",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_selected_corporate_company'}),
        help_text="Select the corporate company"
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
            'insurance_company', 'insurance_id', 'insurance_member_id', 'primary_insurance',
            'allergies', 'chronic_conditions', 'medications'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'national_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'National ID (optional)'}),
            'insurance_company': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter insurance company name (or select above)'}),
            'insurance_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Insurance ID/Policy Number'}),
            'insurance_member_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Member ID'}),
            'primary_insurance': forms.Select(attrs={'class': 'form-select'}),
            'allergies': forms.Textarea(attrs={'rows': 2}),
            'chronic_conditions': forms.Textarea(attrs={'rows': 2}),
            'medications': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        # CRITICAL: Disable auto-save on patient registration form to prevent duplicate submissions
        self.helper.attrs = {'data-no-autosave': ''}
        self.fields['primary_insurance'].queryset = self.fields['primary_insurance'].queryset.filter(is_active=True)
        self.fields['primary_insurance'].required = False
        
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
        
        # Load corporate companies
        try:
            from .models_enterprise_billing import CorporateAccount
            self.fields['selected_corporate_company'].queryset = CorporateAccount.objects.filter(
                is_active=True,
                is_deleted=False,
                credit_status='active'
            ).order_by('company_name')
        except:
            self.fields['selected_corporate_company'].queryset = self.fields['selected_corporate_company'].queryset.none()
        
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
                'payer_type',
                Div(
                    Row(Column('selected_insurance_company', css_class='form-group col-md-6'),
                        Column('selected_insurance_plan', css_class='form-group col-md-6')),
                    Row(Column('insurance_id', css_class='form-group col-md-6'),
                        Column('insurance_member_id', css_class='form-group col-md-6')),
                    HTML('<small class="text-muted d-block mb-2">Or enter manually below:</small>'),
                    Row(Column('insurance_company', css_class='form-group col-md-6'),
                        Column('primary_insurance', css_class='form-group col-md-6')),
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
            Submit('submit', 'Register Patient', css_class='btn btn-primary btn-lg')
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
        from .models import Patient
        from django.db.models import Q
        
        duplicate_checks = []
        
        # Check 1: Same name + DOB + Phone (strongest match)
        # Also check name + phone even without DOB (more aggressive)
        if first_name and last_name and normalized_phone:
            if date_of_birth:
                existing = Patient.objects.filter(
                    first_name__iexact=first_name,
                    last_name__iexact=last_name,
                    date_of_birth=date_of_birth,
                    is_deleted=False
                ).exclude(pk=patient_id)
            else:
                # If no DOB, check by name + phone only
                existing = Patient.objects.filter(
                    first_name__iexact=first_name,
                    last_name__iexact=last_name,
                    is_deleted=False
                ).exclude(pk=patient_id)
            
            # Check phone number matches (normalized)
            for patient in existing:
                if normalize_phone(patient.phone_number) == normalized_phone:
                    if date_of_birth:
                        duplicate_checks.append(
                            f"A patient with the same name ({first_name} {last_name}), "
                            f"date of birth ({date_of_birth}), and phone number ({phone_number}) already exists. "
                            f"MRN: {patient.mrn}"
                        )
                    else:
                        duplicate_checks.append(
                            f"A patient with the same name ({first_name} {last_name}) "
                            f"and phone number ({phone_number}) already exists. "
                            f"MRN: {patient.mrn}"
                        )
                    break
        
        # Check 2: Same email (if provided)
        if email:
            existing = Patient.objects.filter(
                email__iexact=email,
                is_deleted=False
            ).exclude(pk=patient_id)
            
            if existing.exists():
                patient = existing.first()
                duplicate_checks.append(
                    f"A patient with the same email ({email}) already exists. "
                    f"Name: {patient.full_name}, MRN: {patient.mrn}"
                )
        
        # Check 3: Same name + DOB (weaker match, but still important)
        if first_name and last_name and date_of_birth and not normalized_phone:
            existing = Patient.objects.filter(
                first_name__iexact=first_name,
                last_name__iexact=last_name,
                date_of_birth=date_of_birth,
                is_deleted=False
            ).exclude(pk=patient_id)
            
            if existing.exists():
                patient = existing.first()
                duplicate_checks.append(
                    f"A patient with the same name ({first_name} {last_name}) and "
                    f"date of birth ({date_of_birth}) already exists. "
                    f"MRN: {patient.mrn}, Phone: {patient.phone_number or 'N/A'}"
                )
        
        # Check 4: Same phone number (if provided)
        if normalized_phone:
            existing = Patient.objects.filter(
                is_deleted=False
            ).exclude(pk=patient_id)
            
            for patient in existing:
                if normalize_phone(patient.phone_number) == normalized_phone:
                    duplicate_checks.append(
                        f"A patient with the same phone number ({phone_number}) already exists. "
                        f"Name: {patient.full_name}, MRN: {patient.mrn}"
                    )
                    break
        
        # Check 5: Same national_id (if provided)
        national_id = cleaned_data.get('national_id') or ''
        national_id = national_id.strip() if national_id else ''
        if national_id:
            existing = Patient.objects.filter(
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
        self.fields['encounter'].queryset = Encounter.objects.filter(
            status='active',
            is_deleted=False
        )
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
            ('fbc', 'Full Blood Count'),
            ('lft', 'Liver Function Tests'),
            ('rft', 'Renal Function Tests'),
            ('lipid', 'Lipid Profile'),
            ('tft', 'Thyroid Function Tests'),
            ('glucose', 'Blood Glucose'),
            ('electrolytes', 'Electrolytes'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
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
    
    # FBC fields
    wbc = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    rbc = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    hgb = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    hct = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    mcv = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    mch = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    mchc = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    rdw = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    plt = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    neut_perc = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
    lymph_perc = forms.DecimalField(required=False, max_digits=6, decimal_places=2)
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
    
    def get_details_dict(self):
        """Extract all non-empty field values as a dictionary for JSON storage"""
        details = {}
        for field_name, field_value in self.cleaned_data.items():
            if field_name not in ['test_type', 'status', 'qualitative_result', 'notes']:
                if field_value is not None and field_value != '':
                    details[field_name] = str(field_value)
        return details
