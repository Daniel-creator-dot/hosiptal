"""
HR Forms
"""
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML, ButtonHolder
from django.contrib.auth.models import User
from .models import Staff, Department
from .models_hr import (
    StaffContract, PayGrade, StaffDocument,
    PerformanceReview, TrainingRecord,
    AllowanceType, DeductionType, TaxBracket, PayrollConfiguration
)
from .models_advanced import LeaveRequest
from .models_hr_activities import RecruitmentPosition, Candidate


class StaffForm(forms.ModelForm):
    """Form for creating/editing staff - Enhanced"""
    username = forms.CharField(required=True)
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    
    class Meta:
        model = Staff
        fields = [
            'employee_id', 'profession', 'department', 
            'date_of_birth', 'gender', 'blood_group', 'marital_status',
            'phone_number', 'personal_email', 'address', 'city',
            'registration_number', 'license_number', 'specialization',
            'emergency_contact_name', 'emergency_contact_relationship', 'emergency_contact_phone',
            'date_of_joining', 'employment_status',
            'bank_name', 'bank_account_number', 'bank_branch',
            'is_active'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'date_of_joining': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set up department queryset
        self.fields['department'].queryset = Department.objects.filter(is_active=True, is_deleted=False)
        self.fields['employee_id'].required = False
        self.fields['employee_id'].help_text = "Leave blank to auto-generate (DEPT-PROF-NUMBER)"
        
        # Configure fields based on whether editing or creating
        if self.instance and self.instance.pk and hasattr(self.instance, 'user'):
            # Editing existing staff - populate user fields
            try:
                self.fields['username'].initial = self.instance.user.username
                self.fields['email'].initial = self.instance.user.email
                self.fields['first_name'].initial = self.instance.user.first_name
                self.fields['last_name'].initial = self.instance.user.last_name
                self.fields['password'].required = False
                self.fields['password'].help_text = "Leave blank to keep current password"
                # Make username readonly only when editing
                self.fields['username'].widget.attrs['readonly'] = True
            except:
                # If user doesn't exist, treat as new
                self.fields['password'].required = True
                self.fields['password'].help_text = "Create a secure password"
        else:
            # Creating new staff - all fields editable
            self.fields['password'].required = True
            self.fields['password'].help_text = "Create a secure password"
            # Ensure username is NOT readonly
            self.fields['username'].widget.attrs.pop('readonly', None)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5 class="mb-3"><i class="bi bi-person-badge"></i> User Account</h5>'),
            Row(
                Column('username', css_class='form-group col-md-6 mb-0'),
                Column('password', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('first_name', css_class='form-group col-md-6 mb-0'),
                Column('last_name', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('email', css_class='form-group col-md-6 mb-0'),
                Column('personal_email', css_class='form-group col-md-6 mb-0'),
            ),
            
            HTML('<h5 class="mt-4 mb-3"><i class="bi bi-building"></i> Employment Details</h5>'),
            Row(
                Column('employee_id', css_class='form-group col-md-4 mb-0'),
                Column('profession', css_class='form-group col-md-4 mb-0'),
                Column('department', css_class='form-group col-md-4 mb-0'),
            ),
            Row(
                Column('specialization', css_class='form-group col-md-6 mb-0'),
                Column('date_of_joining', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('registration_number', css_class='form-group col-md-6 mb-0'),
                Column('license_number', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('employment_status', css_class='form-group col-md-6 mb-0'),
                Column(Field('is_active'), css_class='form-group col-md-6 mb-0'),
            ),
            
            HTML('<h5 class="mt-4 mb-3"><i class="bi bi-person-heart"></i> Personal Information</h5>'),
            Row(
                Column('date_of_birth', css_class='form-group col-md-6 mb-0'),
                Column('gender', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('blood_group', css_class='form-group col-md-6 mb-0'),
                Column('marital_status', css_class='form-group col-md-6 mb-0'),
            ),
            
            HTML('<h5 class="mt-4 mb-3"><i class="bi bi-telephone"></i> Contact Information</h5>'),
            Row(
                Column('phone_number', css_class='form-group col-md-6 mb-0'),
                Column('city', css_class='form-group col-md-6 mb-0'),
            ),
            'address',
            
            HTML('<h5 class="mt-4 mb-3"><i class="bi bi-shield-exclamation"></i> Emergency Contact</h5>'),
            Row(
                Column('emergency_contact_name', css_class='form-group col-md-6 mb-0'),
                Column('emergency_contact_relationship', css_class='form-group col-md-6 mb-0'),
            ),
            'emergency_contact_phone',
            
            HTML('<h5 class="mt-4 mb-3"><i class="bi bi-bank"></i> Banking Information (for Payroll)</h5>'),
            Row(
                Column('bank_name', css_class='form-group col-md-6 mb-0'),
                Column('bank_account_number', css_class='form-group col-md-6 mb-0'),
            ),
            'bank_branch',
            
            Submit('submit', 'Save Staff', css_class='btn btn-primary-modern btn-lg mt-4')
        )
    
    def clean(self):
        """Check for duplicate staff before saving"""
        cleaned_data = super().clean()
        username = cleaned_data.get('username', '').strip()
        email = cleaned_data.get('email', '').strip()
        personal_email = cleaned_data.get('personal_email', '').strip()
        first_name = cleaned_data.get('first_name', '').strip()
        last_name = cleaned_data.get('last_name', '').strip()
        phone_number = cleaned_data.get('phone_number', '').strip()
        employee_id = cleaned_data.get('employee_id', '').strip()
        
        # Get the instance (if editing existing staff)
        instance = self.instance
        staff_id = instance.pk if instance else None
        
        # Normalize phone number for comparison
        def normalize_phone(phone):
            if not phone:
                return ''
            phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            if phone.startswith('0') and len(phone) == 10:
                phone = '233' + phone[1:]
            elif phone.startswith('+'):
                phone = phone[1:]
            return phone
        
        normalized_phone = normalize_phone(phone_number)
        
        # Check for duplicates
        from django.contrib.auth.models import User
        from .models import Staff
        duplicate_checks = []
        
        # Check 1: Username (must be unique)
        if username:
            existing_user = User.objects.filter(username__iexact=username).exclude(
                staff__pk=staff_id if staff_id else None
            ).first()
            if existing_user:
                duplicate_checks.append(
                    f"A user with username '{username}' already exists. "
                    f"Please choose a different username."
                )
        
        # Check 2: Email (must be unique)
        if email:
            existing_user = User.objects.filter(email__iexact=email).exclude(
                staff__pk=staff_id if staff_id else None
            ).first()
            if existing_user:
                duplicate_checks.append(
                    f"A user with email '{email}' already exists. "
                    f"Username: {existing_user.username}"
                )
        
        # Check 3: Personal email (if different from main email)
        if personal_email and personal_email != email:
            existing = Staff.objects.filter(
                personal_email__iexact=personal_email,
                is_deleted=False
            ).exclude(pk=staff_id)
            
            if existing.exists():
                staff = existing.first()
                duplicate_checks.append(
                    f"A staff member with personal email '{personal_email}' already exists. "
                    f"Name: {staff.user.get_full_name()}, Employee ID: {staff.employee_id}"
                )
        
        # Check 4: Employee ID (must be unique)
        if employee_id:
            existing = Staff.objects.filter(
                employee_id=employee_id,
                is_deleted=False
            ).exclude(pk=staff_id)
            
            if existing.exists():
                staff = existing.first()
                duplicate_checks.append(
                    f"A staff member with Employee ID '{employee_id}' already exists. "
                    f"Name: {staff.user.get_full_name()}"
                )
        
        # Check 5: Same name + phone (potential duplicate)
        if first_name and last_name and normalized_phone:
            existing = Staff.objects.filter(
                user__first_name__iexact=first_name,
                user__last_name__iexact=last_name,
                is_deleted=False
            ).exclude(pk=staff_id)
            
            for staff in existing:
                if normalize_phone(staff.phone_number) == normalized_phone:
                    duplicate_checks.append(
                        f"A staff member with the same name ({first_name} {last_name}) and "
                        f"phone number ({phone_number}) already exists. "
                        f"Employee ID: {staff.employee_id}, Username: {staff.user.username}"
                    )
                    break
        
        # Check 6: Same phone number
        if normalized_phone:
            existing = Staff.objects.filter(
                is_deleted=False
            ).exclude(pk=staff_id)
            
            for staff in existing:
                if normalize_phone(staff.phone_number) == normalized_phone:
                    duplicate_checks.append(
                        f"A staff member with phone number '{phone_number}' already exists. "
                        f"Name: {staff.user.get_full_name()}, Employee ID: {staff.employee_id}"
                    )
                    break
        
        # Raise validation error if duplicates found
        if duplicate_checks:
            error_message = "⚠️ Potential duplicate staff member detected:\n\n" + "\n\n".join(duplicate_checks)
            error_message += "\n\nPlease verify this is not a duplicate before proceeding."
            raise forms.ValidationError(error_message)
        
        return cleaned_data
    
    def save(self, commit=True):
        staff = super().save(commit=False)
        
        if staff.pk and hasattr(staff, 'user'):
            # Update existing user
            user = staff.user
            user.email = self.cleaned_data['email']
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            if self.cleaned_data.get('password'):
                user.set_password(self.cleaned_data['password'])
            user.save()
        else:
            # Create new user first
            user = User.objects.create_user(
                username=self.cleaned_data['username'],
                email=self.cleaned_data['email'],
                password=self.cleaned_data['password'],
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
            )
            staff.user = user
            
            # Employee ID will be auto-generated by the model's save() method
            # Don't override it here - let the model handle it
        
        if commit:
            staff.save()  # This triggers the model's save() which generates employee_id
        return staff


class StaffContractForm(forms.ModelForm):
    """Form for staff contracts"""
    class Meta:
        model = StaffContract
        fields = [
            'contract_type', 'pay_grade', 'job_title', 'department',
            'start_date', 'end_date', 'basic_salary', 'allowances', 'benefits'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['pay_grade'].queryset = PayGrade.objects.filter(is_active=True, is_deleted=False)
        self.fields['department'].queryset = Department.objects.filter(is_active=True, is_deleted=False)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('contract_type', css_class='form-group col-md-6 mb-0'),
                Column('pay_grade', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('job_title', css_class='form-group col-md-6 mb-0'),
                Column('department', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('start_date', css_class='form-group col-md-6 mb-0'),
                Column('end_date', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('basic_salary', css_class='form-group col-md-6 mb-0'),
                Column('allowances', css_class='form-group col-md-6 mb-0'),
            ),
            'benefits',
            Submit('submit', 'Save Contract', css_class='btn btn-primary')
        )


class LeaveRequestForm(forms.ModelForm):
    """Form for leave requests"""
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'end_date', 'days_requested', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'days_requested': forms.NumberInput(attrs={'min': 1}),
            'reason': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'leave_type',
            Row(
                Column('start_date', css_class='form-group col-md-4 mb-0'),
                Column('end_date', css_class='form-group col-md-4 mb-0'),
                Column('days_requested', css_class='form-group col-md-4 mb-0'),
            ),
            'reason',
            Submit('submit', 'Submit Leave Request', css_class='btn btn-primary')
        )


class StaffDocumentForm(forms.ModelForm):
    """Form for uploading staff documents"""
    class Meta:
        model = StaffDocument
        fields = ['document_type', 'title', 'description', 'file', 'expiry_date']
        widgets = {
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('document_type', css_class='form-group col-md-6 mb-0'),
                Column('expiry_date', css_class='form-group col-md-6 mb-0'),
            ),
            'title',
            'description',
            'file',
            Submit('submit', 'Upload Document', css_class='btn btn-primary')
        )


class PerformanceReviewForm(forms.ModelForm):
    """Form for performance reviews"""
    class Meta:
        model = PerformanceReview
        fields = [
            'review_period_start', 'review_period_end', 'review_date',
            'overall_rating', 'strengths', 'weaknesses', 'goals', 'comments'
        ]
        widgets = {
            'review_period_start': forms.DateInput(attrs={'type': 'date'}),
            'review_period_end': forms.DateInput(attrs={'type': 'date'}),
            'review_date': forms.DateInput(attrs={'type': 'date'}),
            'strengths': forms.Textarea(attrs={'rows': 4}),
            'weaknesses': forms.Textarea(attrs={'rows': 4}),
            'goals': forms.Textarea(attrs={'rows': 4}),
            'comments': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('review_period_start', css_class='form-group col-md-4 mb-0'),
                Column('review_period_end', css_class='form-group col-md-4 mb-0'),
                Column('review_date', css_class='form-group col-md-4 mb-0'),
            ),
            'overall_rating',
            'strengths',
            'weaknesses',
            'goals',
            'comments',
            Submit('submit', 'Save Review', css_class='btn btn-primary')
        )


class TrainingRecordForm(forms.ModelForm):
    """Form for training records"""
    class Meta:
        model = TrainingRecord
        fields = [
            'training_title', 'training_type', 'provider', 'location',
            'start_date', 'end_date', 'duration_hours', 'cost',
            'certificate_issued', 'certificate_number', 'status', 'notes'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('training_title', css_class='form-group col-md-6 mb-0'),
                Column('training_type', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('provider', css_class='form-group col-md-6 mb-0'),
                Column('location', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('start_date', css_class='form-group col-md-4 mb-0'),
                Column('end_date', css_class='form-group col-md-4 mb-0'),
                Column('duration_hours', css_class='form-group col-md-4 mb-0'),
            ),
            Row(
                Column('cost', css_class='form-group col-md-4 mb-0'),
                Column('certificate_issued', css_class='form-group col-md-4 mb-0'),
                Column('status', css_class='form-group col-md-4 mb-0'),
            ),
            'certificate_number',
            'notes',
            Submit('submit', 'Save Training Record', css_class='btn btn-primary')
        )


# Recruitment & Talent Acquisition Forms
class RecruitmentPositionForm(forms.ModelForm):
    """Create or update recruitment positions."""

    class Meta:
        model = RecruitmentPosition
        fields = [
            'position_title',
            'department',
            'employment_type',
            'number_of_positions',
            'job_description',
            'requirements',
            'qualifications',
            'salary_range_min',
            'salary_range_max',
            'posted_date',
            'closing_date',
            'status',
            'hiring_manager',
            'is_urgent',
        ]
        widgets = {
            'posted_date': forms.DateInput(attrs={'type': 'date'}),
            'closing_date': forms.DateInput(attrs={'type': 'date'}),
            'job_description': forms.Textarea(attrs={'rows': 3}),
            'requirements': forms.Textarea(attrs={'rows': 3}),
            'qualifications': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].queryset = Department.objects.filter(is_deleted=False, is_active=True)
        self.fields['hiring_manager'].queryset = Staff.objects.filter(is_deleted=False, is_active=True).order_by('user__first_name', 'user__last_name')
        self.fields['hiring_manager'].required = False

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column('position_title', css_class='col-md-8'),
                Column('employment_type', css_class='col-md-4'),
            ),
            Row(
                Column('department', css_class='col-md-6'),
                Column('hiring_manager', css_class='col-md-6'),
            ),
            Row(
                Column('number_of_positions', css_class='col-md-4'),
                Column('status', css_class='col-md-4'),
                Column('is_urgent', css_class='col-md-4 mt-4'),
            ),
            'job_description',
            'requirements',
            'qualifications',
            Row(
                Column('salary_range_min', css_class='col-md-6'),
                Column('salary_range_max', css_class='col-md-6'),
            ),
            Row(
                Column('posted_date', css_class='col-md-6'),
                Column('closing_date', css_class='col-md-6'),
            ),
            ButtonHolder(
                Submit('save_position', 'Save Position', css_class='btn btn-primary w-100 mt-2')
            ),
        )

    def clean(self):
        cleaned = super().clean()
        min_salary = cleaned.get('salary_range_min')
        max_salary = cleaned.get('salary_range_max')

        if min_salary and max_salary and min_salary > max_salary:
            self.add_error('salary_range_max', 'Maximum salary must be greater than or equal to minimum salary.')

        return cleaned


class CandidateForm(forms.ModelForm):
    """Capture candidate applications and pipeline updates."""

    class Meta:
        model = Candidate
        fields = [
            'position',
            'first_name',
            'last_name',
            'email',
            'phone',
            'resume',
            'cover_letter',
            'application_date',
            'status',
            'interview_date',
            'interview_notes',
            'interview_score',
            'offer_salary',
            'offer_date',
            'notes',
        ]
        widgets = {
            'application_date': forms.DateInput(attrs={'type': 'date'}),
            'interview_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'offer_date': forms.DateInput(attrs={'type': 'date'}),
            'cover_letter': forms.Textarea(attrs={'rows': 3}),
            'interview_notes': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'interview_score': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': 0.1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['position'].queryset = RecruitmentPosition.objects.filter(is_deleted=False).order_by('-posted_date')

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column('position', css_class='col-md-12'),
            ),
            Row(
                Column('first_name', css_class='col-md-6'),
                Column('last_name', css_class='col-md-6'),
            ),
            Row(
                Column('email', css_class='col-md-6'),
                Column('phone', css_class='col-md-6'),
            ),
            'resume',
            'cover_letter',
            Row(
                Column('application_date', css_class='col-md-6'),
                Column('status', css_class='col-md-6'),
            ),
            Row(
                Column('interview_date', css_class='col-md-6'),
                Column('interview_score', css_class='col-md-6'),
            ),
            'interview_notes',
            Row(
                Column('offer_salary', css_class='col-md-6'),
                Column('offer_date', css_class='col-md-6'),
            ),
            'notes',
            ButtonHolder(
                Submit('save_candidate', 'Save Candidate', css_class='btn btn-primary w-100 mt-2')
            ),
        )


# Payroll Configuration Forms
class AllowanceTypeForm(forms.ModelForm):
    """Form for creating/editing allowance types"""
    class Meta:
        model = AllowanceType
        fields = ['name', 'code', 'description', 'calculation_type', 'default_amount', 
                  'is_taxable', 'is_statutory', 'display_order', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='form-group col-md-6 mb-0'),
                Column('code', css_class='form-group col-md-6 mb-0'),
            ),
            'description',
            Row(
                Column('calculation_type', css_class='form-group col-md-6 mb-0'),
                Column('default_amount', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('is_taxable', css_class='form-group col-md-4 mb-0'),
                Column('is_statutory', css_class='form-group col-md-4 mb-0'),
                Column('display_order', css_class='form-group col-md-4 mb-0'),
            ),
            'is_active',
            Submit('submit', 'Save Allowance Type', css_class='btn btn-primary')
        )


class DeductionTypeForm(forms.ModelForm):
    """Form for creating/editing deduction types"""
    class Meta:
        model = DeductionType
        fields = ['name', 'code', 'description', 'calculation_type', 'default_amount',
                  'min_amount', 'max_amount', 'is_statutory', 'is_loan', 'display_order', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='form-group col-md-6 mb-0'),
                Column('code', css_class='form-group col-md-6 mb-0'),
            ),
            'description',
            Row(
                Column('calculation_type', css_class='form-group col-md-6 mb-0'),
                Column('default_amount', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('min_amount', css_class='form-group col-md-6 mb-0'),
                Column('max_amount', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('is_statutory', css_class='form-group col-md-4 mb-0'),
                Column('is_loan', css_class='form-group col-md-4 mb-0'),
                Column('display_order', css_class='form-group col-md-4 mb-0'),
            ),
            'is_active',
            Submit('submit', 'Save Deduction Type', css_class='btn btn-primary')
        )


class TaxBracketForm(forms.ModelForm):
    """Form for creating/editing tax brackets"""
    class Meta:
        model = TaxBracket
        fields = ['bracket_name', 'min_income', 'max_income', 'tax_rate', 'fixed_amount',
                  'effective_from', 'effective_to', 'is_active']
        widgets = {
            'effective_from': forms.DateInput(attrs={'type': 'date'}),
            'effective_to': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'bracket_name',
            Row(
                Column('min_income', css_class='form-group col-md-6 mb-0'),
                Column('max_income', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('tax_rate', css_class='form-group col-md-6 mb-0'),
                Column('fixed_amount', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('effective_from', css_class='form-group col-md-6 mb-0'),
                Column('effective_to', css_class='form-group col-md-6 mb-0'),
            ),
            'is_active',
            Submit('submit', 'Save Tax Bracket', css_class='btn btn-primary')
        )


class PayrollConfigurationForm(forms.ModelForm):
    """Form for creating/editing payroll configuration"""
    class Meta:
        model = PayrollConfiguration
        fields = ['name', 'tax_calculation_method', 'default_tax_rate', 'tax_free_allowance',
                  'social_security_rate', 'social_security_max_amount',
                  'pension_rate', 'pension_max_amount',
                  'default_payroll_day', 'regular_hours_per_day', 'overtime_multiplier',
                  'currency_symbol', 'currency_code', 'is_active', 'is_default', 'notes']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='form-group col-md-6 mb-0'),
                Column('is_default', css_class='form-group col-md-3 mb-0'),
                Column('is_active', css_class='form-group col-md-3 mb-0'),
            ),
            HTML('<h5>Tax Settings</h5>'),
            Row(
                Column('tax_calculation_method', css_class='form-group col-md-6 mb-0'),
                Column('default_tax_rate', css_class='form-group col-md-3 mb-0'),
                Column('tax_free_allowance', css_class='form-group col-md-3 mb-0'),
            ),
            HTML('<h5>Social Security</h5>'),
            Row(
                Column('social_security_rate', css_class='form-group col-md-6 mb-0'),
                Column('social_security_max_amount', css_class='form-group col-md-6 mb-0'),
            ),
            HTML('<h5>Pension</h5>'),
            Row(
                Column('pension_rate', css_class='form-group col-md-6 mb-0'),
                Column('pension_max_amount', css_class='form-group col-md-6 mb-0'),
            ),
            HTML('<h5>Payroll Period</h5>'),
            'default_payroll_day',
            HTML('<h5>Overtime</h5>'),
            Row(
                Column('regular_hours_per_day', css_class='form-group col-md-6 mb-0'),
                Column('overtime_multiplier', css_class='form-group col-md-6 mb-0'),
            ),
            HTML('<h5>Currency</h5>'),
            Row(
                Column('currency_symbol', css_class='form-group col-md-6 mb-0'),
                Column('currency_code', css_class='form-group col-md-6 mb-0'),
            ),
            'notes',
            Submit('submit', 'Save Configuration', css_class='btn btn-primary')
        )

