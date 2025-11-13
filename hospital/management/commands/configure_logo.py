"""
Management command to configure hospital logo
"""
from django.core.management.base import BaseCommand
from hospital.models_settings import HospitalSettings


class Command(BaseCommand):
    help = 'Configure hospital logo and initial settings'

    def handle(self, *args, **options):
        settings = HospitalSettings.get_settings()
        
        # Set the logo path
        settings.logo = 'hospital_settings/prime_care_medical_center_gh_logo.jpg'
        
        # Set default hospital information
        settings.hospital_name = 'Prime Care Medical Center'
        settings.hospital_tagline = 'Quality Healthcare for All'
        settings.country = 'Ghana'
        
        # Lab department
        settings.lab_department_name = 'Clinical Laboratory'
        settings.lab_accreditation = 'ISO 15189:2012'
        
        # Logo dimensions
        settings.logo_width = 150
        settings.logo_height = 150
        
        settings.save()
        
        self.stdout.write(self.style.SUCCESS('Successfully configured hospital logo!'))
        self.stdout.write(self.style.SUCCESS(f'   Hospital: {settings.hospital_name}'))
        self.stdout.write(self.style.SUCCESS(f'   Logo: {settings.logo}'))
        self.stdout.write(self.style.SUCCESS(''))
        self.stdout.write(self.style.SUCCESS('Logo will now appear on all printed lab reports!'))

