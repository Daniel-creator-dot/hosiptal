"""
Django Management Command to Find and Merge Duplicate Patients
Identifies patients with similar/duplicate names and allows merging
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.db import transaction
from collections import defaultdict
from difflib import SequenceMatcher
from hospital.models import Patient
from hospital.models_legacy_patients import LegacyPatient


class Command(BaseCommand):
    help = 'Find and optionally merge duplicate patients by name'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            default='both',
            choices=['django', 'legacy', 'both'],
            help='Which patient model to check for duplicates'
        )
        parser.add_argument(
            '--merge',
            action='store_true',
            help='Actually merge duplicates (default is just to show them)'
        )
        parser.add_argument(
            '--threshold',
            type=float,
            default=0.85,
            help='Similarity threshold (0.0-1.0, default 0.85)'
        )
        parser.add_argument(
            '--exact-only',
            action='store_true',
            help='Only show exact name matches (ignore fuzzy matching)'
        )
    
    def handle(self, *args, **options):
        model_choice = options['model']
        merge = options['merge']
        threshold = options['threshold']
        exact_only = options['exact_only']
        
        self.stdout.write(self.style.SUCCESS('=== DUPLICATE PATIENT FINDER ===\n'))
        
        if merge:
            self.stdout.write(self.style.WARNING('MERGE MODE: Duplicates will be merged!\n'))
        else:
            self.stdout.write(self.style.WARNING('REPORT MODE: Just showing duplicates (use --merge to actually merge)\n'))
        
        # Find duplicates in Django patients
        if model_choice in ['django', 'both']:
            self.find_django_duplicates(merge, threshold, exact_only)
        
        # Find duplicates in Legacy patients
        if model_choice in ['legacy', 'both']:
            self.find_legacy_duplicates(merge, threshold, exact_only)
    
    def find_django_duplicates(self, merge=False, threshold=0.85, exact_only=False):
        """Find duplicate Django Patient records"""
        self.stdout.write(self.style.WARNING('\n--- Django Patient Duplicates ---'))
        
        patients = Patient.objects.filter(is_deleted=False).order_by('last_name', 'first_name')
        
        # Find exact duplicates by full name
        duplicates = patients.values('first_name', 'last_name', 'date_of_birth').annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('-count')
        
        total_duplicates = duplicates.count()
        
        if total_duplicates == 0:
            self.stdout.write(self.style.SUCCESS('  No exact duplicate names found in Django patients\n'))
        else:
            self.stdout.write(f'  Found {total_duplicates} sets of exact duplicates:\n')
            
            for dup in duplicates[:50]:  # Show first 50
                fname = dup['first_name']
                lname = dup['last_name']
                dob = dup['date_of_birth']
                count = dup['count']
                
                # Get all patients with this name
                dup_patients = Patient.objects.filter(
                    first_name=fname,
                    last_name=lname,
                    date_of_birth=dob,
                    is_deleted=False
                )
                
                self.stdout.write(f'\n  [{count} duplicates] {fname} {lname} (DOB: {dob}):')
                for p in dup_patients:
                    self.stdout.write(f'    - MRN: {p.mrn}, Phone: {p.phone_number}, Created: {p.created.date()}')
                
                if merge:
                    self.merge_django_patients(list(dup_patients))
        
        # Fuzzy matching if not exact-only
        if not exact_only:
            self.find_fuzzy_duplicates_django(patients, threshold, merge)
    
    def find_legacy_duplicates(self, merge=False, threshold=0.85, exact_only=False):
        """Find duplicate Legacy Patient records"""
        self.stdout.write(self.style.WARNING('\n--- Legacy Patient Duplicates ---'))
        
        # Find exact duplicates by full name
        duplicates = LegacyPatient.objects.values('fname', 'lname', 'DOB').annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('-count')
        
        total_duplicates = duplicates.count()
        
        if total_duplicates == 0:
            self.stdout.write(self.style.SUCCESS('  No exact duplicate names found in Legacy patients\n'))
        else:
            self.stdout.write(f'  Found {total_duplicates} sets of exact duplicates:\n')
            
            # Show first 100
            for dup in duplicates[:100]:
                fname = dup['fname']
                lname = dup['lname']
                dob = dup['DOB']
                count = dup['count']
                
                # Get all patients with this name
                dup_patients = LegacyPatient.objects.filter(
                    fname=fname,
                    lname=lname,
                    DOB=dob
                )
                
                self.stdout.write(f'\n  [{count} duplicates] {fname} {lname} (DOB: {dob}):')
                for p in dup_patients[:10]:  # Limit display to 10 per group
                    self.stdout.write(
                        f'    - PID: {p.pid}, Phone: {p.display_phone}, '
                        f'MRN: {p.mrn_display}'
                    )
                if dup_patients.count() > 10:
                    self.stdout.write(f'    ... and {dup_patients.count() - 10} more')
                
                if merge:
                    self.stdout.write(self.style.WARNING(
                        '    Note: Legacy patient merging not implemented (read-only table)'
                    ))
    
    def find_fuzzy_duplicates_django(self, patients, threshold, merge):
        """Find similar names using fuzzy matching"""
        self.stdout.write(f'\n  Checking for fuzzy matches (threshold={threshold})...')
        
        patient_list = list(patients[:1000])  # Limit for performance
        fuzzy_groups = []
        processed = set()
        
        for i, p1 in enumerate(patient_list):
            if p1.id in processed:
                continue
            
            similar = [p1]
            full_name1 = f"{p1.first_name} {p1.last_name}".lower()
            
            for p2 in patient_list[i+1:]:
                if p2.id in processed:
                    continue
                
                full_name2 = f"{p2.first_name} {p2.last_name}".lower()
                similarity = SequenceMatcher(None, full_name1, full_name2).ratio()
                
                if similarity >= threshold:
                    similar.append(p2)
                    processed.add(p2.id)
            
            if len(similar) > 1:
                fuzzy_groups.append(similar)
                processed.add(p1.id)
        
        if fuzzy_groups:
            self.stdout.write(f'\n  Found {len(fuzzy_groups)} groups of similar names:\n')
            for group in fuzzy_groups[:20]:  # Show first 20
                self.stdout.write(f'\n  Similar patients ({len(group)} matches):')
                for p in group:
                    self.stdout.write(f'    - {p.full_name} (MRN: {p.mrn}, DOB: {p.date_of_birth})')
                
                if merge and len(group) > 1:
                    self.merge_django_patients(group)
        else:
            self.stdout.write('  No fuzzy duplicates found')
    
    def merge_django_patients(self, patients):
        """Merge duplicate Django patients (keep oldest, mark others as deleted)"""
        if len(patients) <= 1:
            return
        
        # Sort by creation date (keep oldest)
        patients_sorted = sorted(patients, key=lambda x: x.created)
        primary = patients_sorted[0]
        duplicates = patients_sorted[1:]
        
        self.stdout.write(f'\n    MERGING into: {primary.full_name} (MRN: {primary.mrn})')
        
        with transaction.atomic():
            for dup in duplicates:
                # Update all related records to point to primary patient
                try:
                    # Encounters
                    if hasattr(dup, 'encounter_set'):
                        dup.encounter_set.update(patient=primary)
                    
                    # Admissions  
                    if hasattr(dup, 'admission_set'):
                        dup.admission_set.update(patient=primary)
                    
                    # Appointments
                    if hasattr(dup, 'appointment_set'):
                        dup.appointment_set.update(patient=primary)
                    
                    # Invoices
                    if hasattr(dup, 'invoice_set'):
                        dup.invoice_set.update(patient=primary)
                    
                    # Insurance claims
                    if hasattr(dup, 'insurance_claims'):
                        dup.insurance_claims.all().update(patient=primary)
                    
                    # Insurance enrollments - be careful not to create duplicates
                    if hasattr(dup, 'insurances'):
                        for insurance in dup.insurances.filter(is_deleted=False):
                            # Check if primary already has this insurance
                            existing = primary.insurances.filter(
                                insurance_company=insurance.insurance_company,
                                is_deleted=False
                            ).first()
                            
                            if not existing:
                                # Move insurance to primary
                                insurance.patient = primary
                                insurance.save()
                            else:
                                # Mark as deleted
                                insurance.is_deleted = True
                                insurance.save()
                    
                    # Mark duplicate as deleted
                    dup.is_deleted = True
                    dup.save()
                    
                    self.stdout.write(f'      Merged: {dup.full_name} (MRN: {dup.mrn}) into primary')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'      Error merging {dup.mrn}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'    Successfully merged {len(duplicates)} duplicate(s)'))

