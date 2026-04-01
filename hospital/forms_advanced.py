"""
Advanced forms for Hospital Management System
"""
from django import forms
from django.utils import timezone
from django.contrib.auth.models import User, Group
from .models import Patient, Encounter, Staff, Department, Ward, Appointment
from .models_advanced import Queue, Triage, ProviderSchedule

# Import QueueEntry here to avoid circular imports, but handle gracefully
try:
    from .models_queue import QueueEntry
except ImportError:
    QueueEntry = None


class QueueForm(forms.ModelForm):
    """Form for creating/editing queue entries (Legacy Queue model)"""
    class Meta:
        model = Queue
        fields = ['encounter', 'department', 'location', 'priority']
        widgets = {
            'encounter': forms.Select(attrs={'class': 'form-control form-control-modern'}),
            'department': forms.Select(attrs={'class': 'form-control form-control-modern'}),
            'location': forms.Select(attrs={'class': 'form-control form-control-modern'}),
            'priority': forms.Select(attrs={'class': 'form-control form-control-modern'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter to active encounters only
        self.fields['encounter'].queryset = Encounter.objects.filter(
            status='active',
            is_deleted=False
        )
        self.fields['department'].queryset = Department.objects.filter(
            is_active=True,
            is_deleted=False
        )
        # Add location choices
        LOCATION_CHOICES = [
            ('clinic', 'Clinic'),
            ('ward', 'Ward'),
            ('theatre', 'Theatre'),
            ('er', 'Emergency Room'),
            ('pharmacy', 'Pharmacy'),
            ('lab', 'Laboratory'),
            ('imaging', 'Imaging'),
            ('reception', 'Reception'),
        ]
        self.fields['location'].widget = forms.Select(choices=LOCATION_CHOICES, attrs={'class': 'form-control form-control-modern'})
        self.fields['location'].choices = LOCATION_CHOICES


class QueueEntryForm(forms.ModelForm):
    """Form for creating/editing QueueEntry with doctor and room assignment"""
    assigned_doctor = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Select Doctor (Optional)",
        help_text="Assign patient to specific doctor",
        widget=forms.Select(attrs={'class': 'form-control form-control-modern'})
    )
    consulting_room = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Select Room (Optional)",
        help_text="Assign patient to specific consulting room",
        widget=forms.Select(attrs={'class': 'form-control form-control-modern'})
    )
    
    class Meta:
        # Set model directly if QueueEntry is available, otherwise use None and handle in __init__
        model = QueueEntry if QueueEntry is not None else None
        fields = ['patient', 'encounter', 'department', 'assigned_doctor', 'priority', 'notes']
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-control form-control-modern'}),
            'encounter': forms.Select(attrs={'class': 'form-control form-control-modern'}),
            'department': forms.Select(attrs={'class': 'form-control form-control-modern'}),
            'priority': forms.Select(attrs={'class': 'form-control form-control-modern'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-modern', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        from .models_consulting_rooms import ConsultingRoom
        
        # If QueueEntry wasn't available at class definition, import it now
        if self._meta.model is None:
            try:
                from .models_queue import QueueEntry as QE
                if QE is not None:
                    self._meta.model = QE
                    # Update Meta fields to match the model
                    self._meta.fields = ['patient', 'encounter', 'department', 'assigned_doctor', 'priority', 'notes']
            except ImportError:
                pass
        
        # Ensure model is set before calling super()
        if self._meta.model is None:
            raise ValueError("QueueEntry model is not available. Please ensure models_queue is properly imported.")
        
        # Call super() - this will create fields if model is set
        super().__init__(*args, **kwargs)
        
        # Now configure the querysets for model fields (they should exist after super())
        if 'patient' in self.fields:
            self.fields['patient'].queryset = Patient.objects.filter(is_deleted=False).order_by('first_name', 'last_name')
            self.fields['patient'].required = True
        
        if 'encounter' in self.fields:
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
            self.fields['encounter'].required = False
            self.fields['encounter'].empty_label = "Create New Encounter (Optional)"
        
        if 'department' in self.fields:
            self.fields['department'].queryset = Department.objects.filter(
                is_active=True,
                is_deleted=False
            ).order_by('name')
            self.fields['department'].required = True
        
        if 'priority' in self.fields:
            self.fields['priority'].required = False
        
        # Configure assigned_doctor field
        if 'assigned_doctor' in self.fields:
            try:
                doctor_group = Group.objects.get(name='Doctor')
                self.fields['assigned_doctor'].queryset = User.objects.filter(
                    groups=doctor_group,
                    is_active=True
                ).select_related('staff').order_by('first_name', 'last_name')
            except Group.DoesNotExist:
                self.fields['assigned_doctor'].queryset = User.objects.none()
        
        # Configure consulting_room field (non-model field)
        if 'consulting_room' in self.fields:
            try:
                self.fields['consulting_room'].queryset = ConsultingRoom.objects.filter(
                    is_active=True,
                    is_deleted=False,
                    status='available'
                ).order_by('room_number')
            except Exception:
                self.fields['consulting_room'].queryset = ConsultingRoom.objects.none()
    
    def save(self, commit=True):
        """Save queue entry with room assignment"""
        instance = super().save(commit=False)
        
        # Extract room number from consulting_room if selected
        consulting_room = self.cleaned_data.get('consulting_room')
        if consulting_room:
            instance.room_number = consulting_room.room_number
        
        if commit:
            instance.save()
        return instance


class TriageForm(forms.ModelForm):
    """Form for creating/editing triage records"""
    class Meta:
        model = Triage
        fields = [
            'encounter', 'triage_level', 'chief_complaint',
            'pain_scale', 'notes'
        ]
        widgets = {
            'encounter': forms.Select(attrs={'class': 'form-control form-control-modern'}),
            'triage_level': forms.Select(attrs={'class': 'form-control form-control-modern'}),
            'chief_complaint': forms.Textarea(attrs={'class': 'form-control form-control-modern', 'rows': 3}),
            'pain_scale': forms.NumberInput(attrs={'class': 'form-control form-control-modern', 'min': 0, 'max': 10}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-modern', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter to ER encounters
        self.fields['encounter'].queryset = Encounter.objects.filter(
            encounter_type='er',
            is_deleted=False
        )


class ProviderScheduleForm(forms.ModelForm):
    """Form for creating/editing provider schedules"""
    class Meta:
        model = ProviderSchedule
        fields = ['provider', 'department', 'date', 'start_time', 'end_time', 'is_available', 'notes']
        widgets = {
            'provider': forms.Select(attrs={'class': 'form-control form-control-modern'}),
            'department': forms.Select(attrs={'class': 'form-control form-control-modern'}),
            'date': forms.DateInput(attrs={'class': 'form-control form-control-modern', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control form-control-modern', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control form-control-modern', 'type': 'time'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-modern', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['provider'].queryset = Staff.objects.filter(
            is_active=True,
            is_deleted=False
        )
        self.fields['department'].queryset = Department.objects.filter(
            is_active=True,
            is_deleted=False
        )


class AppointmentForm(forms.ModelForm):
    """Form for creating/editing appointments"""
    class Meta:
        model = Appointment
        fields = ['patient', 'provider', 'department', 'appointment_date', 'duration_minutes', 'reason', 'notes', 'consulting_room']
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-control form-control-modern'}),
            'provider': forms.Select(attrs={'class': 'form-control form-control-modern'}),
            'department': forms.Select(attrs={'class': 'form-control form-control-modern'}),
            'appointment_date': forms.DateTimeInput(attrs={'class': 'form-control form-control-modern', 'type': 'datetime-local'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control form-control-modern', 'min': 15, 'step': 15}),
            'reason': forms.Textarea(attrs={'class': 'form-control form-control-modern', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-modern', 'rows': 2}),
            'consulting_room': forms.Select(attrs={'class': 'form-control form-control-modern'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Patient, Staff, Department
        
        self.fields['patient'].queryset = Patient.objects.filter(
            is_deleted=False
        ).order_by('first_name', 'last_name')
        
        # Filter to only doctors
        self.fields['provider'].queryset = Staff.objects.filter(
            profession='doctor',
            is_active=True,
            is_deleted=False
        ).order_by('user__first_name', 'user__last_name')
        
        # Filter departments to show only medical specialties (Eye, Dental, Gynae, etc.)
        # Exclude administrative departments (Accounts, HR, IT, etc.)
        from django.db.models import Q
        
        # Administrative departments to exclude
        admin_departments = [
            'Accounts', 'Administration', 'HR', 'IT Support', 'Finance',
            'Cashier', 'Front Office', 'BD', 'Marketing & Business Development',
            'Sanitation', 'Nurses'  # Nurses is a profession, not a specialty
        ]
        
        # Medical specialty keywords to include
        medical_keywords = [
            'Eye', 'Ophthalmology', 'Dental', 'Dentistry', 'Gynae', 'Gynecology',
            'Obstetrics', 'Cardiology', 'Pediatrics', 'Surgery', 'Orthopedic',
            'Dermatology', 'Neurology', 'Psychiatry', 'Urology', 'ENT',
            'Ear Nose Throat', 'Radiology', 'Pathology', 'Emergency',
            'Pulmonology', 'Gastroenterology', 'Endocrinology', 'Nephrology',
            'Oncology', 'Rheumatology', 'Hematology', 'Anesthesiology',
            'Internal Medicine', 'Family Medicine', 'General Practice',
            'Medicine', 'Maternity', 'General Medicine'
        ]
        
        # Build query to include medical specialties and exclude administrative
        self.fields['department'].queryset = Department.objects.filter(
            is_active=True,
            is_deleted=False
        ).exclude(
            name__in=admin_departments
        ).filter(
            Q(name__in=medical_keywords) |
            Q(name__icontains='Medicine') |
            Q(name__icontains='Surgery') |
            Q(name__icontains='Gynecology') |
            Q(name__icontains='Gynae') |
            Q(name__icontains='Eye') |
            Q(name__icontains='Ophthalmology') |
            Q(name__icontains='Dental') |
            Q(name__icontains='Dentistry') |
            Q(name__icontains='Cardiology') |
            Q(name__icontains='Pediatrics') |
            Q(name__icontains='Orthopedic') |
            Q(name__icontains='Dermatology') |
            Q(name__icontains='Neurology') |
            Q(name__icontains='Psychiatry') |
            Q(name__icontains='Urology') |
            Q(name__icontains='ENT') |
            Q(name__icontains='Radiology') |
            Q(name__icontains='Pathology') |
            Q(name__icontains='Emergency') |
            Q(name__icontains='Pulmonology') |
            Q(name__icontains='Gastroenterology') |
            Q(name__icontains='Endocrinology') |
            Q(name__icontains='Nephrology') |
            Q(name__icontains='Oncology') |
            Q(name__icontains='Rheumatology') |
            Q(name__icontains='Hematology') |
            Q(name__icontains='Anesthesiology') |
            Q(name__icontains='Maternity')
        ).distinct().order_by('name')
        
        # Consulting room is optional
        try:
            from .models_consulting_rooms import ConsultingRoom
            self.fields['consulting_room'].queryset = ConsultingRoom.objects.filter(
                is_active=True,
                is_deleted=False
            ).order_by('room_number')
            self.fields['consulting_room'].required = False
            self.fields['consulting_room'].empty_label = "Select room (optional)"
        except ImportError:
            # If consulting rooms model not available yet, hide the field
            if 'consulting_room' in self.fields:
                del self.fields['consulting_room']

