"""Analyze duplicate patients in the database"""
from django.core.management.base import BaseCommand
from hospital.models import Patient
from django.db.models import Count, Q
from collections import defaultdict


def normalize_phone(phone):
    """Normalize phone number for comparison"""
    if not phone:
        return ''
    phone = str(phone).strip()
    phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if phone.startswith('0') and len(phone) == 10:
        phone = '233' + phone[1:]
    elif phone.startswith('+'):
        phone = phone[1:]
    return phone


class Command(BaseCommand):
    help = 'Analyze duplicate patients in the database'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Analyzing Duplicate Patients ===\n'))
        
        # Get all active patients
        patients = Patient.objects.filter(is_deleted=False).order_by('created')
        
        # Group by normalized phone + name
        phone_name_groups = defaultdict(list)
        email_groups = defaultdict(list)
        national_id_groups = defaultdict(list)
        name_dob_groups = defaultdict(list)
        
        for patient in patients:
            # Group by phone + name
            if patient.phone_number and patient.first_name and patient.last_name:
                key = (normalize_phone(patient.phone_number), 
                       patient.first_name.lower().strip(), 
                       patient.last_name.lower().strip())
                phone_name_groups[key].append(patient)
            
            # Group by email
            if patient.email:
                email_key = patient.email.lower().strip()
                email_groups[email_key].append(patient)
            
            # Group by national_id
            if patient.national_id:
                national_id_groups[patient.national_id.strip()].append(patient)
            
            # Group by name + DOB
            if patient.first_name and patient.last_name and patient.date_of_birth:
                dob_key = (patient.first_name.lower().strip(),
                          patient.last_name.lower().strip(),
                          patient.date_of_birth)
                name_dob_groups[dob_key].append(patient)
        
        # Report phone + name duplicates
        phone_duplicates = {k: v for k, v in phone_name_groups.items() if len(v) > 1}
        self.stdout.write(self.style.WARNING(f'\n📞 Phone + Name Duplicates: {len(phone_duplicates)} groups'))
        for key, group in list(phone_duplicates.items())[:10]:
            self.stdout.write(f'  {key[1]} {key[2]} ({key[0]}): {len(group)} records')
            for p in group:
                self.stdout.write(f'    - {p.mrn}: Created {p.created.date()}')
        
        # Report email duplicates
        email_duplicates = {k: v for k, v in email_groups.items() if len(v) > 1}
        self.stdout.write(self.style.WARNING(f'\n📧 Email Duplicates: {len(email_duplicates)} groups'))
        for email, group in list(email_duplicates.items())[:10]:
            self.stdout.write(f'  {email}: {len(group)} records')
        
        # Report national_id duplicates
        national_id_duplicates = {k: v for k, v in national_id_groups.items() if len(v) > 1}
        self.stdout.write(self.style.WARNING(f'\n🆔 National ID Duplicates: {len(national_id_duplicates)} groups'))
        for nid, group in list(national_id_duplicates.items())[:10]:
            self.stdout.write(f'  {nid}: {len(group)} records')
        
        # Summary
        total_duplicate_groups = len(phone_duplicates) + len(email_duplicates) + len(national_id_duplicates)
        total_duplicate_records = sum(len(v) - 1 for v in phone_duplicates.values()) + \
                                 sum(len(v) - 1 for v in email_duplicates.values()) + \
                                 sum(len(v) - 1 for v in national_id_duplicates.values())
        
        self.stdout.write(self.style.ERROR(f'\n\n📊 SUMMARY:'))
        self.stdout.write(f'  Total duplicate groups: {total_duplicate_groups}')
        self.stdout.write(f'  Total duplicate records to clean: {total_duplicate_records}')
        self.stdout.write(f'  Total active patients: {patients.count()}')

