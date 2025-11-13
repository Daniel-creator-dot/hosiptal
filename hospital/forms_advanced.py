"""
Advanced forms for Hospital Management System
"""
from django import forms
from django.utils import timezone
from .models import Patient, Encounter, Staff, Department, Ward, Appointment
from .models_advanced import Queue, Triage, ProviderSchedule


class QueueForm(forms.ModelForm):
    """Form for creating/editing queue entries"""
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
        fields = ['patient', 'provider', 'department', 'appointment_date', 'duration_minutes', 'reason', 'notes']
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-control form-control-modern'}),
            'provider': forms.Select(attrs={'class': 'form-control form-control-modern'}),
            'department': forms.Select(attrs={'class': 'form-control form-control-modern'}),
            'appointment_date': forms.DateTimeInput(attrs={'class': 'form-control form-control-modern', 'type': 'datetime-local'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control form-control-modern', 'min': 15, 'step': 15}),
            'reason': forms.Textarea(attrs={'class': 'form-control form-control-modern', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-modern', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['patient'].queryset = Patient.objects.filter(
            is_deleted=False
        ).order_by('first_name', 'last_name')
        self.fields['provider'].queryset = Staff.objects.filter(
            is_active=True,
            is_deleted=False
        )
        self.fields['department'].queryset = Department.objects.filter(
            is_active=True,
            is_deleted=False
        )

