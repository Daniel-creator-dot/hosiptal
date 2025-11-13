"""
Management command to generate comprehensive test data for all models
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta
import random

from hospital.models import (
    Patient, Encounter, Staff, Department, Ward, Bed,
    Prescription, Order, Appointment, VitalSign, Admission,
    Invoice, InvoiceLine, LabTest, LabResult, Drug, PharmacyStock
)
from hospital.models_advanced import (
    ClinicalNote, CarePlan, ProblemList, ProviderSchedule, Queue, Triage,
    TheatreSchedule, MedicationAdministrationRecord, HandoverSheet,
    IncidentLog, MedicalEquipment, ConsumablesInventory,
    DutyRoster, LeaveRequest, ImagingStudy
)


class Command(BaseCommand):
    help = 'Generates comprehensive test data for all HMS models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--patients',
            type=int,
            default=50,
            help='Number of patients to create'
        )
        parser.add_argument(
            '--encounters',
            type=int,
            default=100,
            help='Number of encounters to create'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Starting comprehensive test data generation...'))
        
        num_patients = options['patients']
        num_encounters = options['encounters']
        
        # Get existing data
        departments = list(Department.objects.filter(is_active=True))
        staff_list = list(Staff.objects.all())
        wards = list(Ward.objects.filter(is_active=True))
        beds = list(Bed.objects.filter(is_deleted=False))
        lab_tests = list(LabTest.objects.all())
        drugs = list(Drug.objects.all())
        
        if not departments or not staff_list:
            self.stdout.write(self.style.ERROR('❌ Please run seed_data first to create departments and staff!'))
            return
        
        # Create patients
        self.stdout.write(f'Creating {num_patients} patients...')
        patients = []
        for i in range(num_patients):
            patient = Patient.objects.create(
                first_name=f'TestPatient{i+1}',
                last_name=f'LastName{i+1}',
                date_of_birth=timezone.now().date() - timedelta(days=random.randint(1, 36500)),
                gender=random.choice(['M', 'F', 'O']),
                phone_number=f'+23324{random.randint(1000000, 9999999)}',
                email=f'patient{i+1}@test.com',
            )
            patients.append(patient)
        
        self.stdout.write(self.style.SUCCESS(f'✅ Created {len(patients)} patients'))
        
        # Create encounters
        self.stdout.write(f'Creating {num_encounters} encounters...')
        encounters = []
        encounter_types = ['outpatient', 'inpatient', 'er']
        statuses = ['active', 'completed', 'cancelled']
        
        for i in range(num_encounters):
            patient = random.choice(patients)
            provider = random.choice(staff_list) if staff_list else None
            location = random.choice(wards) if wards else None
            
            encounter = Encounter.objects.create(
                patient=patient,
                encounter_type=random.choice(encounter_types),
                status=random.choice(statuses),
                started_at=timezone.now() - timedelta(days=random.randint(0, 90)),
                ended_at=timezone.now() - timedelta(days=random.randint(0, 89)) if random.choice([True, False]) else None,
                location=location,
                provider=provider,
                chief_complaint=f'Chief complaint {i+1}: Patient presents with symptoms',
                diagnosis=f'Diagnosis code {i+1}',
            )
            encounters.append(encounter)
            
            # Create vital signs for some encounters
            if random.choice([True, False]):
                VitalSign.objects.create(
                    encounter=encounter,
                    systolic_bp=random.randint(100, 140),
                    diastolic_bp=random.randint(60, 90),
                    heart_rate=random.randint(60, 100),
                    temperature=round(random.uniform(36.0, 38.0), 1),
                    respiratory_rate=random.randint(12, 20),
                    recorded_by=provider,
                )
        
        self.stdout.write(self.style.SUCCESS(f'✅ Created {len(encounters)} encounters'))
        
        # Create admissions for some inpatient encounters
        self.stdout.write('Creating admissions...')
        inpatient_encounters = [e for e in encounters if e.encounter_type == 'inpatient']
        admissions_created = 0
        
        for encounter in inpatient_encounters[:len(inpatient_encounters)//2]:
            if beds:
                bed = random.choice([b for b in beds if b.status == 'available'])
                if bed:
                    Admission.objects.create(
                        encounter=encounter,
                        ward=encounter.location,
                        bed=bed,
                        admit_date=encounter.started_at,
                        discharge_date=encounter.ended_at,
                        status='discharged' if encounter.ended_at else 'admitted',
                        admitting_doctor=encounter.provider,
                    )
                    if not encounter.ended_at:
                        bed.occupy()
                    admissions_created += 1
        
        self.stdout.write(self.style.SUCCESS(f'✅ Created {admissions_created} admissions'))
        
        # Create appointments
        self.stdout.write('Creating appointments...')
        appointments_created = 0
        for i in range(min(30, num_patients)):
            Appointment.objects.create(
                patient=random.choice(patients),
                provider=random.choice(staff_list),
                department=random.choice(departments),
                appointment_date=timezone.now() + timedelta(days=random.randint(1, 30)),
                duration_minutes=30,
                status=random.choice(['scheduled', 'confirmed', 'completed', 'no_show']),
                reason=f'Follow-up appointment {i+1}',
            )
            appointments_created += 1
        
        self.stdout.write(self.style.SUCCESS(f'✅ Created {appointments_created} appointments'))
        
        # Create invoices
        self.stdout.write('Creating invoices...')
        invoices_created = 0
        for i, encounter in enumerate(encounters[:len(encounters)//2]):
            invoice = Invoice.objects.create(
                patient=encounter.patient,
                issue_date=encounter.started_at.date() + timedelta(days=1),
                due_date=encounter.started_at.date() + timedelta(days=30),
                status=random.choice(['issued', 'paid', 'overdue']),
            )
            
            # Add invoice lines
            InvoiceLine.objects.create(
                invoice=invoice,
                description=f'Consultation fee for {encounter.get_encounter_type_display()}',
                quantity=1,
                unit_price=Decimal('50.00'),
            )
            invoices_created += 1
        
        self.stdout.write(self.style.SUCCESS(f'✅ Created {invoices_created} invoices'))
        
        # Create clinical notes
        self.stdout.write('Creating clinical notes...')
        notes_created = 0
        for encounter in encounters[:len(encounters)//2]:
            ClinicalNote.objects.create(
                encounter=encounter,
                note_type=random.choice(['soap', 'progress', 'consultation']),
                subjective='Patient reports improvement',
                objective='Physical examination normal',
                assessment='Patient doing well',
                plan='Continue current treatment',
                notes=f'Progress note for encounter {encounter.id}',
                created_by=encounter.provider,
            )
            notes_created += 1
        
        self.stdout.write(self.style.SUCCESS(f'✅ Created {notes_created} clinical notes'))
        
        # Create queues for ER encounters
        self.stdout.write('Creating queue entries...')
        er_encounters = [e for e in encounters if e.encounter_type == 'er']
        queues_created = 0
        for i, encounter in enumerate(er_encounters[:20]):
            Queue.objects.create(
                encounter=encounter,
                department=encounter.provider.department if encounter.provider else None,
                queue_number=i + 1,
                location='clinic',
                priority=random.choice(['routine', 'urgent', 'stat']),
                status=random.choice(['waiting', 'in_progress', 'completed']),
            )
            queues_created += 1
        
        self.stdout.write(self.style.SUCCESS(f'✅ Created {queues_created} queue entries'))
        
        self.stdout.write(self.style.SUCCESS('\n🎉 Test data generation completed!'))
        self.stdout.write(self.style.SUCCESS(f'\nSummary:'))
        self.stdout.write(self.style.SUCCESS(f'   - Patients: {len(patients)}'))
        self.stdout.write(self.style.SUCCESS(f'   - Encounters: {len(encounters)}'))
        self.stdout.write(self.style.SUCCESS(f'   - Admissions: {admissions_created}'))
        self.stdout.write(self.style.SUCCESS(f'   - Appointments: {appointments_created}'))
        self.stdout.write(self.style.SUCCESS(f'   - Invoices: {invoices_created}'))
        self.stdout.write(self.style.SUCCESS(f'   - Clinical Notes: {notes_created}'))
        self.stdout.write(self.style.SUCCESS(f'   - Queue Entries: {queues_created}'))

