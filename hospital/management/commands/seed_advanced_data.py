"""
Management command to seed advanced models with sample data
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta
from hospital.models import (
    Patient, Encounter, Staff, Department, Ward, Bed,
    Prescription, Order, Appointment
)
from hospital.models_advanced import (
    ClinicalNote, CarePlan, ProblemList, ProviderSchedule, Queue, Triage,
    TheatreSchedule, MedicationAdministrationRecord, HandoverSheet,
    IncidentLog, MedicalEquipment, ConsumablesInventory,
    DutyRoster, LeaveRequest
)


class Command(BaseCommand):
    help = 'Seeds advanced models with sample data for testing'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting to seed advanced data...'))
        
        # Get or create sample users/staff
        try:
            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                self.stdout.write(self.style.WARNING('No admin user found. Creating one...'))
                admin_user = User.objects.create_superuser(
                    username='admin',
                    email='admin@example.com',
                    password='admin123'
                )
            
            # Get staff if exists
            staff_list = Staff.objects.all()[:5]
            if not staff_list.exists():
                self.stdout.write(self.style.WARNING('No staff found. Please run seed_data first.'))
                return
            
            # Get patients
            patients = Patient.objects.filter(is_deleted=False)[:10]
            if not patients.exists():
                self.stdout.write(self.style.WARNING('No patients found. Please run seed_data first.'))
                return
            
            # Get encounters
            encounters = Encounter.objects.filter(is_deleted=False)[:10]
            if not encounters.exists():
                self.stdout.write(self.style.WARNING('No encounters found. Please run seed_data first.'))
                return
            
            # Create Clinical Notes
            self.stdout.write('Creating clinical notes...')
            for i, encounter in enumerate(encounters[:5]):
                ClinicalNote.objects.get_or_create(
                    encounter=encounter,
                    note_type='soap',
                    defaults={
                        'subjective': f'Patient presents with chief complaint: {encounter.chief_complaint[:100]}',
                        'objective': f'Vital signs stable. Physical examination unremarkable.',
                        'assessment': 'Diagnosis: {encounter.diagnosis or "Under investigation"}',
                        'plan': 'Continue current treatment plan. Monitor progress.',
                        'notes': f'Detailed progress note for patient {encounter.patient.full_name}',
                        'created_by': staff_list[0] if staff_list.exists() else None,
                    }
                )
            
            # Create Care Plans
            self.stdout.write('Creating care plans...')
            for i, encounter in enumerate(encounters[:3]):
                CarePlan.objects.get_or_create(
                    encounter=encounter,
                    defaults={
                        'plan_type': 'treatment',
                        'goals': 'Patient will achieve symptom relief and functional improvement',
                        'interventions': 'Medication management, physical therapy, follow-up appointments',
                        'status': 'active',
                        'created_by': staff_list[0] if staff_list.exists() else None,
                    }
                )
            
            # Create Queues
            self.stdout.write('Creating queue entries...')
            for i, encounter in enumerate(encounters[:5]):
                if encounter.location:
                    Queue.objects.get_or_create(
                        encounter=encounter,
                        department=encounter.provider.department if encounter.provider else None,
                        defaults={
                            'queue_number': i + 1,
                            'location': 'clinic',
                            'priority': 'routine' if i < 3 else 'urgent',
                            'status': 'waiting' if i < 3 else 'in_progress',
                            'checked_in_at': timezone.now() - timedelta(minutes=30 * i),
                        }
                    )
            
            # Create Triage Records
            self.stdout.write('Creating triage records...')
            for i, encounter in enumerate(encounters[:5]):
                if encounter.encounter_type == 'er':
                    Triage.objects.get_or_create(
                        encounter=encounter,
                        defaults={
                            'triage_level': min(i + 1, 5),
                            'chief_complaint': encounter.chief_complaint,
                            'bp': f'120/{80 + i * 5}',
                            'heart_rate': 70 + i * 5,
                            'temperature': 36.5 + i * 0.1,
                            'pain_score': i + 1,
                            'triage_time': timezone.now() - timedelta(minutes=60 * i),
                            'triaged_by': staff_list[0] if staff_list.exists() else None,
                        }
                    )
            
            # Create Handover Sheets
            self.stdout.write('Creating handover sheets...')
            wards = Ward.objects.filter(is_active=True)[:3]
            for ward in wards:
                if not HandoverSheet.objects.filter(ward=ward, date=timezone.now().date()).exists():
                    HandoverSheet.objects.create(
                        ward=ward,
                        shift_type='morning',
                        date=timezone.now().date(),
                        shift_start=timezone.now().replace(hour=7, minute=0),
                        shift_end=timezone.now().replace(hour=15, minute=0),
                        patients_handed_over=3,
                        new_admissions=1,
                        discharges=1,
                        notes='All patients stable. No critical issues.',
                        status='completed',
                        created_by=staff_list[0] if staff_list.exists() else None,
                    )
            
            # Create Medical Equipment
            self.stdout.write('Creating medical equipment...')
            equipment_items = [
                {'name': 'ECG Machine', 'category': 'Cardiology', 'location': 'Emergency'},
                {'name': 'Ventilator', 'category': 'ICU Equipment', 'location': 'ICU'},
                {'name': 'X-Ray Machine', 'category': 'Imaging', 'location': 'Radiology'},
                {'name': 'Ultrasound', 'category': 'Imaging', 'location': 'Radiology'},
                {'name': 'Defibrillator', 'category': 'Emergency', 'location': 'Emergency'},
            ]
            
            for item in equipment_items:
                MedicalEquipment.objects.get_or_create(
                    equipment_number=f'EQ-{item["name"][:3].upper()}-001',
                    defaults={
                        'name': item['name'],
                        'category': item['category'],
                        'location': item['location'],
                        'status': 'operational',
                        'manufacturer': 'Medical Equipment Co.',
                        'purchase_date': timezone.now().date() - timedelta(days=365),
                        'next_maintenance_due': timezone.now().date() + timedelta(days=30),
                    }
                )
            
            # Create Consumables
            self.stdout.write('Creating consumables inventory...')
            consumables_items = [
                {'name': 'Surgical Gloves', 'category': 'PPE', 'quantity': 500, 'reorder_level': 100},
                {'name': 'Syringes 5ml', 'category': 'Medical Supplies', 'quantity': 200, 'reorder_level': 50},
                {'name': 'IV Cannulas', 'category': 'Medical Supplies', 'quantity': 150, 'reorder_level': 30},
                {'name': 'Gauze Pads', 'category': 'Wound Care', 'quantity': 300, 'reorder_level': 75},
                {'name': 'Medical Masks', 'category': 'PPE', 'quantity': 80, 'reorder_level': 25},
            ]
            
            for item in consumables_items:
                ConsumablesInventory.objects.get_or_create(
                    item_name=item['name'],
                    defaults={
                        'category': item['category'],
                        'quantity_on_hand': item['quantity'],
                        'unit': 'pieces',
                        'reorder_level': item['reorder_level'],
                        'location': 'Main Store',
                    }
                )
            
            # Create Provider Schedules
            self.stdout.write('Creating provider schedules...')
            for staff in staff_list[:3]:
                for day in range(5):  # 5 days
                    ProviderSchedule.objects.get_or_create(
                        provider=staff,
                        date=timezone.now().date() + timedelta(days=day),
                        defaults={
                            'department': staff.department,
                            'start_time': timezone.now().replace(hour=8, minute=0).time(),
                            'end_time': timezone.now().replace(hour=17, minute=0).time(),
                            'is_available': True,
                        }
                    )
            
            self.stdout.write(self.style.SUCCESS('\n✅ Successfully seeded advanced data!'))
            self.stdout.write(self.style.SUCCESS(f'   - {ClinicalNote.objects.count()} Clinical Notes'))
            self.stdout.write(self.style.SUCCESS(f'   - {CarePlan.objects.count()} Care Plans'))
            self.stdout.write(self.style.SUCCESS(f'   - {Queue.objects.count()} Queue Entries'))
            self.stdout.write(self.style.SUCCESS(f'   - {Triage.objects.count()} Triage Records'))
            self.stdout.write(self.style.SUCCESS(f'   - {HandoverSheet.objects.count()} Handover Sheets'))
            self.stdout.write(self.style.SUCCESS(f'   - {MedicalEquipment.objects.count()} Equipment Items'))
            self.stdout.write(self.style.SUCCESS(f'   - {ConsumablesInventory.objects.count()} Consumables'))
            self.stdout.write(self.style.SUCCESS(f'   - {ProviderSchedule.objects.count()} Provider Schedules'))

