"""
Management command to create medical specialty departments
"""
from django.core.management.base import BaseCommand
from hospital.models import Department


class Command(BaseCommand):
    help = 'Create medical specialty departments (Eye, Dental, Gynae, etc.)'

    def handle(self, *args, **options):
        # Medical specialty departments to create
        specialties = [
            {'name': 'Eye', 'code': 'EYE', 'description': 'Ophthalmology and Eye Care'},
            {'name': 'Ophthalmology', 'code': 'OPHTH', 'description': 'Eye care and vision treatment'},
            {'name': 'Dental', 'code': 'DENT', 'description': 'Dental care and oral health'},
            {'name': 'Dentistry', 'code': 'DENTISTRY', 'description': 'Dental services'},
            {'name': 'Gynae', 'code': 'GYNAE', 'description': 'Gynecology services'},
            {'name': 'Gynecology', 'code': 'GYN', 'description': 'Women\'s health and gynecology'},
            {'name': 'Obstetrics & Gynecology', 'code': 'OBGYN', 'description': 'Women\'s health, pregnancy, and childbirth'},
            {'name': 'Cardiology', 'code': 'CARD', 'description': 'Heart and cardiovascular diseases'},
            {'name': 'Pediatrics', 'code': 'PEDS', 'description': 'Child healthcare'},
            {'name': 'Surgery', 'code': 'SURG', 'description': 'General surgery'},
            {'name': 'Orthopedics', 'code': 'ORTH', 'description': 'Bone and joint disorders'},
            {'name': 'Dermatology', 'code': 'DERM', 'description': 'Skin diseases'},
            {'name': 'Neurology', 'code': 'NEURO', 'description': 'Brain and nervous system'},
            {'name': 'Psychiatry', 'code': 'PSYCH', 'description': 'Mental health'},
            {'name': 'Urology', 'code': 'URO', 'description': 'Urinary tract and male reproductive'},
            {'name': 'ENT', 'code': 'ENT', 'description': 'Ear, Nose & Throat'},
            {'name': 'Emergency Medicine', 'code': 'EM', 'description': 'Emergency and trauma care'},
            {'name': 'Internal Medicine', 'code': 'INT-MED', 'description': 'Internal medicine'},
        ]
        
        created_count = 0
        existing_count = 0
        
        for spec in specialties:
            dept, created = Department.objects.get_or_create(
                name=spec['name'],
                defaults={
                    'code': spec['code'],
                    'description': spec['description'],
                    'is_active': True,
                    'is_deleted': False,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✅ Created: {dept.name} ({dept.code})'))
            else:
                existing_count += 1
                # Update if needed
                if not dept.is_active or dept.is_deleted:
                    dept.is_active = True
                    dept.is_deleted = False
                    dept.save()
                    self.stdout.write(self.style.WARNING(f'🔄 Updated: {dept.name}'))
                else:
                    self.stdout.write(self.style.WARNING(f'⏭️  Already exists: {dept.name}'))
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Specialty departments setup complete!\n'
                f'   Created: {created_count}\n'
                f'   Existing: {existing_count}\n'
                f'   Total: {len(specialties)}'
            )
        )
