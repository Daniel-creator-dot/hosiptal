"""
Clean up patient names - remove numbers, special characters, and normalize
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q, Count
from hospital.models import Patient
from hospital.models_legacy_patients import LegacyPatient
from difflib import SequenceMatcher
import re


class Command(BaseCommand):
    help = 'Clean up patient names and identify duplicates'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            default='django',
            choices=['django', 'legacy', 'both'],
            help='Which patient model to clean'
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually apply the changes (default is dry-run)'
        )
    
    def handle(self, *args, **options):
        model_choice = options['model']
        apply_changes = options['apply']
        
        if not apply_changes:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))
        
        self.stdout.write(self.style.SUCCESS('=== PATIENT NAME CLEANUP ===\n'))
        
        if model_choice in ['django', 'both']:
            self.clean_django_patients(apply_changes)
        
        if model_choice in ['legacy', 'both']:
            self.analyze_legacy_patients()
    
    def clean_django_patients(self, apply_changes):
        """Clean Django patient names"""
        self.stdout.write(self.style.WARNING('--- Cleaning Django Patients ---\n'))
        
        patients = Patient.objects.filter(is_deleted=False)
        cleaned_count = 0
        
        for patient in patients:
            changes = []
            
            # Clean first name
            cleaned_fname = self.clean_name(patient.first_name)
            if cleaned_fname != patient.first_name:
                changes.append(f"First: '{patient.first_name}' -> '{cleaned_fname}'")
                if apply_changes:
                    patient.first_name = cleaned_fname
            
            # Clean last name
            cleaned_lname = self.clean_name(patient.last_name)
            if cleaned_lname != patient.last_name:
                changes.append(f"Last: '{patient.last_name}' -> '{cleaned_lname}'")
                if apply_changes:
                    patient.last_name = cleaned_lname
            
            # Clean middle name
            cleaned_mname = self.clean_name(patient.middle_name)
            if cleaned_mname != patient.middle_name:
                changes.append(f"Middle: '{patient.middle_name}' -> '{cleaned_mname}'")
                if apply_changes:
                    patient.middle_name = cleaned_mname
            
            if changes:
                self.stdout.write(f'  {patient.mrn} - {patient.full_name}:')
                for change in changes:
                    self.stdout.write(f'    - {change}')
                
                if apply_changes:
                    patient.save()
                    cleaned_count += 1
                else:
                    cleaned_count += 1
        
        if cleaned_count > 0:
            if apply_changes:
                self.stdout.write(self.style.SUCCESS(f'\nCleaned {cleaned_count} patient names'))
            else:
                self.stdout.write(self.style.WARNING(f'\nWould clean {cleaned_count} patient names'))
        else:
            self.stdout.write(self.style.SUCCESS('\nAll patient names are already clean!'))
    
    def analyze_legacy_patients(self):
        """Analyze legacy patient name patterns"""
        self.stdout.write(self.style.WARNING('\n--- Analyzing Legacy Patients ---\n'))
        
        # Find patterns of problematic names
        problematic_patterns = {
            'with_numbers': LegacyPatient.objects.filter(
                Q(fname__regex=r'[0-9]') | Q(lname__regex=r'[0-9]')
            ).count(),
            'with_special_chars': LegacyPatient.objects.filter(
                Q(fname__regex=r'[^a-zA-Z\s\-\']') | Q(lname__regex=r'[^a-zA-Z\s\-\']')
            ).count(),
            'all_caps': LegacyPatient.objects.filter(
                fname__regex=r'^[A-Z\s]+$',
                lname__regex=r'^[A-Z\s]+$'
            ).exclude(fname='', lname='').count(),
            'empty_fname': LegacyPatient.objects.filter(fname='').count(),
            'empty_lname': LegacyPatient.objects.filter(lname='').count(),
        }
        
        self.stdout.write('  Name Quality Issues:')
        for issue, count in problematic_patterns.items():
            if count > 0:
                self.stdout.write(f'    - {issue.replace("_", " ").title()}: {count:,} patients')
        
        # Show examples
        self.stdout.write('\n  Examples of problematic names:')
        
        # Names with numbers
        with_numbers = LegacyPatient.objects.filter(
            Q(fname__regex=r'[0-9]') | Q(lname__regex=r'[0-9]')
        )[:10]
        
        if with_numbers.exists():
            self.stdout.write('\n    Names with numbers:')
            for p in with_numbers:
                self.stdout.write(f'      - PID {p.pid}: {p.fname} {p.lname}')
        
        self.stdout.write('\n  Note: Legacy patient table is read-only (managed=False)')
        self.stdout.write('  To clean these, migrate to Django Patient model first')
    
    def clean_name(self, name):
        """Clean a name string"""
        if not name:
            return name
        
        # Remove numbers
        name = re.sub(r'[0-9]+', '', name)
        
        # Remove excessive special characters (keep hyphens, apostrophes, spaces)
        name = re.sub(r'[^a-zA-Z\s\-\'\.]', '', name)
        
        # Remove multiple spaces
        name = re.sub(r'\s+', ' ', name)
        
        # Proper case (capitalize first letter of each word)
        name = ' '.join(word.capitalize() if word.isupper() else word for word in name.split())
        
        # Trim
        name = name.strip()
        
        return name
    
    def similarity_score(self, str1, str2):
        """Calculate similarity between two strings"""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

