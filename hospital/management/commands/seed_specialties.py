"""
Management command to seed common medical specialties
"""
from django.core.management.base import BaseCommand
from hospital.models_specialists import Specialty


class Command(BaseCommand):
    help = 'Seed common medical specialties including Dentist and other specialists'

    def handle(self, *args, **options):
        # Common medical specialties in Ghana
        specialties = [
            # Primary Care & General
            {'name': 'General Practice', 'code': 'GP', 'description': 'General practitioner providing primary healthcare services', 'icon': 'bi-heart-pulse'},
            {'name': 'Family Medicine', 'code': 'FM', 'description': 'Family medicine and primary care', 'icon': 'bi-people'},
            
            # Dental
            {'name': 'Dentistry', 'code': 'DENT', 'description': 'Dental care, oral health, and dental procedures', 'icon': 'bi-tooth'},
            {'name': 'Oral Surgery', 'code': 'ORAL-SURG', 'description': 'Oral and maxillofacial surgery', 'icon': 'bi-scissors'},
            {'name': 'Orthodontics', 'code': 'ORTHO', 'description': 'Orthodontic treatment and braces', 'icon': 'bi-grid'},
            
            # Medical Specialties
            {'name': 'Cardiology', 'code': 'CARD', 'description': 'Heart and cardiovascular diseases', 'icon': 'bi-heart'},
            {'name': 'Ophthalmology', 'code': 'OPHTH', 'description': 'Eye care and vision treatment', 'icon': 'bi-eye'},
            {'name': 'Pediatrics', 'code': 'PEDS', 'description': 'Child healthcare and pediatric medicine', 'icon': 'bi-baby'},
            {'name': 'Obstetrics & Gynecology', 'code': 'OBGYN', 'description': 'Women\'s health, pregnancy, and childbirth', 'icon': 'bi-gender-female'},
            {'name': 'Internal Medicine', 'code': 'INT-MED', 'description': 'Internal medicine and adult diseases', 'icon': 'bi-person'},
            {'name': 'Surgery', 'code': 'SURG', 'description': 'General surgery and surgical procedures', 'icon': 'bi-scissors'},
            {'name': 'Orthopedics', 'code': 'ORTH', 'description': 'Bone, joint, and musculoskeletal disorders', 'icon': 'bi-activity'},
            {'name': 'Dermatology', 'code': 'DERM', 'description': 'Skin, hair, and nail disorders', 'icon': 'bi-heart'},
            {'name': 'Neurology', 'code': 'NEURO', 'description': 'Brain and nervous system disorders', 'icon': 'bi-brain'},
            {'name': 'Psychiatry', 'code': 'PSYCH', 'description': 'Mental health and psychiatric care', 'icon': 'bi-emoji-smile'},
            {'name': 'Urology', 'code': 'URO', 'description': 'Urinary tract and male reproductive system', 'icon': 'bi-person'},
            {'name': 'Ear, Nose & Throat (ENT)', 'code': 'ENT', 'description': 'Ear, nose, and throat disorders', 'icon': 'bi-earbuds'},
            {'name': 'Radiology', 'code': 'RAD', 'description': 'Medical imaging and radiology', 'icon': 'bi-camera'},
            {'name': 'Pathology', 'code': 'PATH', 'description': 'Laboratory medicine and pathology', 'icon': 'bi-microscope'},
            {'name': 'Anesthesiology', 'code': 'ANES', 'description': 'Anesthesia and pain management', 'icon': 'bi-hospital'},
            {'name': 'Emergency Medicine', 'code': 'EM', 'description': 'Emergency and trauma care', 'icon': 'bi-exclamation-triangle'},
            {'name': 'Pulmonology', 'code': 'PULM', 'description': 'Lung and respiratory diseases', 'icon': 'bi-lungs'},
            {'name': 'Gastroenterology', 'code': 'GI', 'description': 'Digestive system disorders', 'icon': 'bi-stomach'},
            {'name': 'Endocrinology', 'code': 'ENDO', 'description': 'Hormone and metabolic disorders', 'icon': 'bi-heart'},
            {'name': 'Nephrology', 'code': 'NEPH', 'description': 'Kidney diseases and dialysis', 'icon': 'bi-heart'},
            {'name': 'Oncology', 'code': 'ONCO', 'description': 'Cancer treatment and oncology', 'icon': 'bi-heart'},
            {'name': 'Rheumatology', 'code': 'RHEUM', 'description': 'Joint and autoimmune diseases', 'icon': 'bi-activity'},
            {'name': 'Hematology', 'code': 'HEM', 'description': 'Blood disorders and hematology', 'icon': 'bi-heart-pulse'},
            {'name': 'Infectious Diseases', 'code': 'ID', 'description': 'Infectious disease treatment', 'icon': 'bi-virus'},
            {'name': 'Geriatrics', 'code': 'GERI', 'description': 'Elderly care and geriatric medicine', 'icon': 'bi-people'},
            {'name': 'Sports Medicine', 'code': 'SPORT', 'description': 'Sports injuries and athletic medicine', 'icon': 'bi-trophy'},
            {'name': 'Allergy & Immunology', 'code': 'ALLERG', 'description': 'Allergies and immune system disorders', 'icon': 'bi-shield'},
            {'name': 'Plastic Surgery', 'code': 'PLAST', 'description': 'Cosmetic and reconstructive surgery', 'icon': 'bi-scissors'},
            {'name': 'Neurosurgery', 'code': 'NEURO-SURG', 'description': 'Brain and spine surgery', 'icon': 'bi-brain'},
            {'name': 'Cardiothoracic Surgery', 'code': 'CT-SURG', 'description': 'Heart and chest surgery', 'icon': 'bi-heart'},
        ]
        
        created_count = 0
        updated_count = 0
        
        for specialty_data in specialties:
            specialty, created = Specialty.objects.update_or_create(
                name=specialty_data['name'],
                defaults={
                    'code': specialty_data['code'],
                    'description': specialty_data['description'],
                    'icon': specialty_data.get('icon', ''),
                    'is_active': True,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created: {specialty.name} ({specialty.code})'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'Updated: {specialty.name} ({specialty.code})'))
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully seeded specialties!\n'
                f'Created: {created_count}\n'
                f'Updated: {updated_count}\n'
                f'Total: {len(specialties)}'
            )
        )





































