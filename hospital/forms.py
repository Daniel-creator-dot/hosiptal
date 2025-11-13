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
from crispy_forms.layout import Layout, Row, Column, Submit, Fieldset, HTML


class PatientForm(forms.ModelForm):
    """Patient registration form with world-class insurance integration"""
    # Add insurance company field
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
    
    class Meta:
        model = Patient
        fields = [
            'first_name', 'last_name', 'middle_name',
            'date_of_birth', 'gender', 'blood_type',
            'phone_number', 'email', 'address',
            'next_of_kin_name', 'next_of_kin_phone', 'next_of_kin_relationship',
            'insurance_company', 'insurance_id', 'insurance_member_id', 'primary_insurance',
            'allergies', 'chronic_conditions', 'medications'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 3}),
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
        self.fields['primary_insurance'].queryset = self.fields['primary_insurance'].queryset.filter(is_active=True)
        self.fields['primary_insurance'].required = False
        
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
            Fieldset('🏥 Insurance Information',
                Row(Column('selected_insurance_company', css_class='form-group col-md-6'),
                    Column('selected_insurance_plan', css_class='form-group col-md-6')),
                Row(Column('insurance_id', css_class='form-group col-md-6'),
                    Column('insurance_member_id', css_class='form-group col-md-6')),
                HTML('<small class="text-muted">Or enter manually below:</small>'),
                Row(Column('insurance_company', css_class='form-group col-md-6'),
                    Column('primary_insurance', css_class='form-group col-md-6')),
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
