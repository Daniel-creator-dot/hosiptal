"""
Forms for Locum Doctor Service Management
"""
from django import forms
from .models_locum_doctors import LocumDoctorService
from .models import Staff, Patient, Encounter, Invoice, InvoiceLine


class LocumDoctorServiceForm(forms.ModelForm):
    """Form for creating/editing locum doctor service records"""
    
    class Meta:
        model = LocumDoctorService
        fields = ['doctor', 'patient', 'encounter', 'service_date', 'service_type', 
                 'service_description', 'service_charge', 'payment_method']
        widgets = {
            'doctor': forms.Select(attrs={'class': 'form-select'}),
            'patient': forms.Select(attrs={'class': 'form-select'}),
            'encounter': forms.Select(attrs={'class': 'form-select'}),
            'service_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'service_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Consultation, Specialist Service'}),
            'service_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'service_charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter doctors to only show doctors/specialists
        self.fields['doctor'].queryset = Staff.objects.filter(
            profession__in=['doctor', 'specialist'],
            is_locum=True,
            is_deleted=False
        ).select_related('user')
        
        # Make encounter optional
        self.fields['encounter'].required = False
        self.fields['encounter'].queryset = Encounter.objects.filter(is_deleted=False)
        
        # Add help text
        self.fields['service_charge'].help_text = 'Total charge for the service. Doctor will receive 50% of this amount.'
        self.fields['payment_method'].help_text = 'Note: Cash payments above ₵2000 will be taxed at 5%'


