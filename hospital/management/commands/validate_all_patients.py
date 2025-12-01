"""
Django management command to validate all patient records comprehensively
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from hospital.models import Patient
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Comprehensive validation of all patient records'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('COMPREHENSIVE PATIENT DATABASE VALIDATION'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')
        
        all_patients = Patient.objects.filter(is_deleted=False)
        total_count = all_patients.count()
        
        self.stdout.write(f'Total patients: {total_count}')
        self.stdout.write('')
        
        # Check 1: Missing IDs
        no_id = Patient.objects.filter(is_deleted=False, id__isnull=True).count()
        self.stdout.write(f'✅ Patients with missing ID: {no_id}')
        
        # Check 2: Missing MRN
        no_mrn = Patient.objects.filter(Q(mrn__isnull=True) | Q(mrn=''), is_deleted=False).count()
        self.stdout.write(f'✅ Patients with missing MRN: {no_mrn}')
        
        # Check 3: Empty names
        empty_first = Patient.objects.filter(Q(first_name__isnull=True) | Q(first_name=''), is_deleted=False).count()
        empty_last = Patient.objects.filter(Q(last_name__isnull=True) | Q(last_name=''), is_deleted=False).count()
        self.stdout.write(f'✅ Patients with empty first name: {empty_first}')
        self.stdout.write(f'✅ Patients with empty last name: {empty_last}')
        
        # Check 4: Invalid DOB
        from django.utils import timezone
        today = timezone.now().date()
        future_dob = Patient.objects.filter(is_deleted=False, date_of_birth__gt=today).count()
        self.stdout.write(f'✅ Patients with future DOB: {future_dob}')
        
        # Check 5: Duplicate MRNs
        duplicate_mrns = Patient.objects.filter(is_deleted=False).values('mrn').annotate(
            count=Count('mrn')
        ).filter(count__gt=1)
        dup_mrn_count = duplicate_mrns.count()
        self.stdout.write(f'✅ Duplicate MRNs: {dup_mrn_count}')
        if dup_mrn_count > 0:
            for dup in duplicate_mrns[:5]:
                patients = Patient.objects.filter(mrn=dup['mrn'], is_deleted=False)
                self.stdout.write(f'   - MRN {dup["mrn"]} appears {dup["count"]} times')
                for p in patients:
                    self.stdout.write(f'     * {p.full_name} (ID: {p.id})')
        
        # Check 6: Duplicate National IDs
        duplicate_nids = Patient.objects.filter(
            is_deleted=False
        ).exclude(
            Q(national_id__isnull=True) | Q(national_id='')
        ).values('national_id').annotate(
            count=Count('national_id')
        ).filter(count__gt=1)
        dup_nid_count = duplicate_nids.count()
        self.stdout.write(f'✅ Duplicate National IDs: {dup_nid_count}')
        
        # Check 7: Phone validation
        invalid_phones = []
        for p in Patient.objects.filter(is_deleted=False):
            if p.phone_number:
                try:
                    p.clean_fields()
                except Exception as e:
                    if 'phone_number' in str(e):
                        invalid_phones.append(p)
        self.stdout.write(f'✅ Patients with invalid phone format: {len(invalid_phones)}')
        
        # Check 8: Age validation
        old_patients = []
        for p in Patient.objects.filter(is_deleted=False):
            if p.date_of_birth:
                age = (today - p.date_of_birth).days / 365.25
                if age > 150:
                    old_patients.append(p)
        self.stdout.write(f'✅ Patients with age >150: {len(old_patients)}')
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('VALIDATION SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        total_issues = (no_id + no_mrn + empty_first + empty_last + future_dob + 
                       dup_mrn_count + dup_nid_count + len(invalid_phones) + len(old_patients))
        
        if total_issues == 0:
            self.stdout.write(self.style.SUCCESS('✅ ALL PATIENTS ARE VALID!'))
            self.stdout.write(self.style.SUCCESS('No issues found in patient database.'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠️  Found {total_issues} issues'))
            self.stdout.write(self.style.WARNING('Run: python manage.py fix_all_patients --fix-all'))
        
        self.stdout.write('')

