"""
Show upcoming birthdays with names
"""
from django.core.management.base import BaseCommand
from hospital.models import Staff, Patient
from datetime import date, timedelta


class Command(BaseCommand):
    help = 'Show upcoming staff and patient birthdays with names'

    def handle(self, *args, **options):
        today = date.today()
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('    UPCOMING BIRTHDAYS - NEXT 30 DAYS'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))
        
        # Get staff birthdays
        staff_birthdays = []
        for i in range(1, 31):
            check_date = today + timedelta(days=i)
            staff_list = Staff.objects.filter(
                date_of_birth__month=check_date.month,
                date_of_birth__day=check_date.day,
                is_active=True,
                is_deleted=False
            ).select_related('user', 'department')
            
            for staff in staff_list:
                this_year_bday = date(today.year, staff.date_of_birth.month, staff.date_of_birth.day)
                if this_year_bday < today:
                    this_year_bday = date(today.year + 1, staff.date_of_birth.month, staff.date_of_birth.day)
                days_until = (this_year_bday - today).days
                staff_birthdays.append((days_until, staff))
        
        # Get patient birthdays
        patient_birthdays = []
        for i in range(1, 31):
            check_date = today + timedelta(days=i)
            patient_list = Patient.objects.filter(
                date_of_birth__month=check_date.month,
                date_of_birth__day=check_date.day,
                is_deleted=False
            )
            
            for patient in patient_list:
                this_year_bday = date(today.year, patient.date_of_birth.month, patient.date_of_birth.day)
                if this_year_bday < today:
                    this_year_bday = date(today.year + 1, patient.date_of_birth.month, patient.date_of_birth.day)
                days_until = (this_year_bday - today).days
                patient_birthdays.append((days_until, patient))
        
        # Display Staff Birthdays
        self.stdout.write(self.style.WARNING('STAFF BIRTHDAYS:\n'))
        if staff_birthdays:
            staff_birthdays.sort(key=lambda x: x[0])
            for days, staff in staff_birthdays:
                dept = staff.department.name if staff.department else "No Department"
                phone = getattr(staff, 'phone_number', None) or "No phone"
                bday_str = staff.date_of_birth.strftime("%B %d, %Y")
                age = today.year - staff.date_of_birth.year
                
                self.stdout.write(f'  {days:2d} days | {staff.user.get_full_name():<30s}')
                self.stdout.write(f'           Birthday: {bday_str} (Age: {age})')
                self.stdout.write(f'           Department: {dept}')
                self.stdout.write(f'           Phone: {phone}')
                self.stdout.write('')
        else:
            self.stdout.write('  No staff birthdays in next 30 days\n')
        
        # Display Patient Birthdays
        self.stdout.write(self.style.WARNING('PATIENT BIRTHDAYS:\n'))
        if patient_birthdays:
            patient_birthdays.sort(key=lambda x: x[0])
            for days, patient in patient_birthdays:
                phone = patient.phone_number or "No phone"
                bday_str = patient.date_of_birth.strftime("%B %d, %Y")
                age = today.year - patient.date_of_birth.year
                
                self.stdout.write(f'  {days:2d} days | {patient.full_name:<30s}')
                self.stdout.write(f'           Birthday: {bday_str} (Age: {age})')
                self.stdout.write(f'           MRN: {patient.mrn}')
                self.stdout.write(f'           Phone: {phone}')
                self.stdout.write('')
        else:
            self.stdout.write('  No patient birthdays in next 30 days\n')
        
        # Summary
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS(f'TOTAL: {len(staff_birthdays)} Staff + {len(patient_birthdays)} Patients = {len(staff_birthdays) + len(patient_birthdays)} Upcoming Birthdays'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

