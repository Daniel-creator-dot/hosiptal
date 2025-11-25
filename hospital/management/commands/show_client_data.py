"""
Show Client/Patient Data Summary
Displays all client/patient related data in the database
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from hospital.models import (
    Patient, Encounter, Invoice, Appointment,
    LabTest, LabResult, Prescription, PharmacyStock
)

# Try to import PaymentReceipt from different modules
try:
    from hospital.models_accounting import PaymentReceipt
except ImportError:
    try:
        from hospital.models_payment import PaymentReceipt
    except ImportError:
        PaymentReceipt = None

class Command(BaseCommand):
    help = 'Show client/patient data summary'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== CLIENT/PATIENT DATA SUMMARY ===\n'))
        
        # Patient data
        patients = Patient.objects.filter(is_deleted=False)
        patient_count = patients.count()
        self.stdout.write(f"{'Patients:':<30} {patient_count}")
        
        if patient_count > 0:
            self.stdout.write('\n  Patient Details:')
            for p in patients[:20]:  # Show first 20
                created_str = p.created.strftime('%Y-%m-%d %H:%M') if hasattr(p.created, 'strftime') else str(p.created)
                self.stdout.write(f'    • {p.mrn}: {p.full_name} (Created: {created_str})')
            if patient_count > 20:
                self.stdout.write(f'    ... and {patient_count - 20} more')
        
        # Related data
        self.stdout.write(f"\n{'Encounters:':<30} {Encounter.objects.filter(is_deleted=False).count()}")
        self.stdout.write(f"{'Invoices:':<30} {Invoice.objects.filter(is_deleted=False).count()}")
        if PaymentReceipt:
            self.stdout.write(f"{'Payment Receipts:':<30} {PaymentReceipt.objects.filter(is_deleted=False).count()}")
        else:
            self.stdout.write(f"{'Payment Receipts:':<30} N/A (model not found)")
        self.stdout.write(f"{'Appointments:':<30} {Appointment.objects.filter(is_deleted=False).count()}")
        self.stdout.write(f"{'Lab Tests:':<30} {LabTest.objects.filter(is_deleted=False).count()}")
        self.stdout.write(f"{'Lab Results:':<30} {LabResult.objects.filter(is_deleted=False).count()}")
        self.stdout.write(f"{'Prescriptions:':<30} {Prescription.objects.filter(is_deleted=False).count()}")
        
        # Summary
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(f'\nTotal Client Records: {patient_count}')
        
        if patient_count == 0:
            self.stdout.write(self.style.WARNING('\n⚠ No patient/client data found in database!'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n✓ Found {patient_count} patient(s) in database'))
        
        self.stdout.write('\n')

