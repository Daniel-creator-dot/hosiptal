"""
Comprehensive command to check for ALL types of duplicates in the system
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.db import connection
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Comprehensive check for ALL types of duplicates in the system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('COMPREHENSIVE DUPLICATE CHECK'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))
        
        duplicates_found = False
        
        # 1. Check for duplicate Staff records
        self.stdout.write(self.style.WARNING('[1/8] Checking for duplicate Staff records...'))
        staff_dups = self.check_duplicate_staff()
        if staff_dups:
            duplicates_found = True
        
        # 2. Check for duplicate Users
        self.stdout.write(self.style.WARNING('\n[2/8] Checking for duplicate User accounts...'))
        user_dups = self.check_duplicate_users()
        if user_dups:
            duplicates_found = True
        
        # 3. Check for duplicate Patients
        self.stdout.write(self.style.WARNING('\n[3/8] Checking for duplicate Patient records...'))
        patient_dups = self.check_duplicate_patients()
        if patient_dups:
            duplicates_found = True
        
        # 4. Check for duplicate Employee IDs
        self.stdout.write(self.style.WARNING('\n[4/8] Checking for duplicate Employee IDs...'))
        emp_id_dups = self.check_duplicate_employee_ids()
        if emp_id_dups:
            duplicates_found = True
        
        # 5. Check for duplicate MRNs
        self.stdout.write(self.style.WARNING('\n[5/8] Checking for duplicate MRNs...'))
        mrn_dups = self.check_duplicate_mrns()
        if mrn_dups:
            duplicates_found = True
        
        # 6. Check for duplicate phone numbers (Staff)
        self.stdout.write(self.style.WARNING('\n[6/8] Checking for duplicate Staff phone numbers...'))
        phone_dups = self.check_duplicate_staff_phones()
        if phone_dups:
            duplicates_found = True
        
        # 7. Check for duplicate emails (Users)
        self.stdout.write(self.style.WARNING('\n[7/8] Checking for duplicate User emails...'))
        email_dups = self.check_duplicate_user_emails()
        if email_dups:
            duplicates_found = True
        
        # 8. Check for duplicate patient phones/emails
        self.stdout.write(self.style.WARNING('\n[8/8] Checking for duplicate Patient contact info...'))
        patient_contact_dups = self.check_duplicate_patient_contacts()
        if patient_contact_dups:
            duplicates_found = True
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*70))
        
        if duplicates_found:
            self.stdout.write(self.style.ERROR('\n⚠️  DUPLICATES FOUND! Please review the details above.'))
            self.stdout.write(self.style.WARNING('\n💡 To fix duplicates, run:'))
            self.stdout.write(self.style.WARNING('   python manage.py delete_duplicate_staff_records --force'))
            self.stdout.write(self.style.WARNING('   python manage.py ensure_database_stability --fix-all'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ NO DUPLICATES FOUND! Database is clean.\n'))
        
        self.stdout.write('')
    
    def check_duplicate_staff(self):
        """Check for staff with same user"""
        from hospital.models import Staff
        
        duplicates = Staff.objects.filter(
            is_deleted=False
        ).values('user_id').annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('-count')
        
        if duplicates.exists():
            self.stdout.write(self.style.ERROR(f'   ❌ Found {duplicates.count()} user(s) with multiple staff records:'))
            
            for dup in duplicates[:10]:  # Show first 10
                user_id = dup['user_id']
                count = dup['count']
                
                try:
                    user = User.objects.get(id=user_id)
                    staff_records = Staff.objects.filter(
                        user_id=user_id,
                        is_deleted=False
                    ).order_by('-created')
                    
                    self.stdout.write(self.style.ERROR(f'\n   User: {user.username} ({user.get_full_name() or "No name"})'))
                    self.stdout.write(self.style.ERROR(f'   Has {count} staff record(s):'))
                    
                    for staff in staff_records:
                        self.stdout.write(self.style.ERROR(
                            f'      - Staff ID: {staff.id}, Employee ID: {staff.employee_id}, '
                            f'Created: {staff.created.strftime("%Y-%m-%d %H:%M")}, '
                            f'Active: {staff.is_active}'
                        ))
                except User.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f'   User ID {user_id} (user does not exist)'))
            
            if duplicates.count() > 10:
                self.stdout.write(self.style.WARNING(f'   ... and {duplicates.count() - 10} more'))
            
            return True
        else:
            self.stdout.write(self.style.SUCCESS('   ✅ No duplicate staff records found'))
            return False
    
    def check_duplicate_users(self):
        """Check for duplicate usernames or emails"""
        # Usernames should be unique by default (database constraint)
        # But check for case-insensitive duplicates
        
        duplicate_usernames = User.objects.extra(
            select={'lower_username': 'LOWER(username)'}
        ).values('lower_username').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        duplicate_emails = User.objects.exclude(
            email__isnull=True
        ).exclude(
            email=''
        ).values('email').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        found = False
        
        if duplicate_usernames.exists():
            self.stdout.write(self.style.ERROR(f'   ❌ Found {duplicate_usernames.count()} duplicate username(s) (case-insensitive)'))
            found = True
        
        if duplicate_emails.exists():
            self.stdout.write(self.style.ERROR(f'   ❌ Found {duplicate_emails.count()} duplicate email(s):'))
            for dup in duplicate_emails[:5]:
                email = dup['email']
                count = dup['count']
                users = User.objects.filter(email=email)
                self.stdout.write(self.style.ERROR(f'      Email: {email} - {count} user(s): {", ".join([u.username for u in users])}'))
            found = True
        
        if not found:
            self.stdout.write(self.style.SUCCESS('   ✅ No duplicate users found'))
        
        return found
    
    def check_duplicate_patients(self):
        """Check for duplicate patients by MRN, name+phone, email, national_id"""
        from hospital.models import Patient
        
        # Check duplicate MRNs (should be impossible)
        duplicate_mrns = Patient.objects.filter(
            is_deleted=False
        ).exclude(
            mrn__isnull=True
        ).exclude(
            mrn=''
        ).values('mrn').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        # Check duplicate national_ids
        duplicate_national_ids = Patient.objects.filter(
            is_deleted=False
        ).exclude(
            national_id__isnull=True
        ).exclude(
            national_id=''
        ).values('national_id').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        found = False
        
        if duplicate_mrns.exists():
            self.stdout.write(self.style.ERROR(f'   ❌ Found {duplicate_mrns.count()} duplicate MRN(s) (should be unique!)'))
            for dup in duplicate_mrns[:5]:
                self.stdout.write(self.style.ERROR(f'      MRN: {dup["mrn"]} - {dup["count"]} record(s)'))
            found = True
        
        if duplicate_national_ids.exists():
            self.stdout.write(self.style.ERROR(f'   ❌ Found {duplicate_national_ids.count()} duplicate National ID(s)'))
            for dup in duplicate_national_ids[:5]:
                self.stdout.write(self.style.ERROR(f'      National ID: {dup["national_id"]} - {dup["count"]} record(s)'))
            found = True
        
        if not found:
            self.stdout.write(self.style.SUCCESS('   ✅ No duplicate patient records found'))
        
        return found
    
    def check_duplicate_employee_ids(self):
        """Check for duplicate employee IDs"""
        from hospital.models import Staff
        
        duplicates = Staff.objects.filter(
            is_deleted=False
        ).exclude(
            employee_id__isnull=True
        ).exclude(
            employee_id=''
        ).values('employee_id').annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('-count')
        
        if duplicates.exists():
            self.stdout.write(self.style.ERROR(f'   ❌ Found {duplicates.count()} duplicate Employee ID(s):'))
            for dup in duplicates[:10]:
                emp_id = dup['employee_id']
                count = dup['count']
                staff_records = Staff.objects.filter(
                    employee_id=emp_id,
                    is_deleted=False
                )
                self.stdout.write(self.style.ERROR(f'\n   Employee ID: {emp_id} - {count} record(s):'))
                for staff in staff_records:
                    self.stdout.write(self.style.ERROR(
                        f'      - Staff ID: {staff.id}, User: {staff.user.username if staff.user else "None"}, '
                        f'Created: {staff.created.strftime("%Y-%m-%d")}'
                    ))
            return True
        else:
            self.stdout.write(self.style.SUCCESS('   ✅ No duplicate Employee IDs found'))
            return False
    
    def check_duplicate_mrns(self):
        """Check for duplicate MRNs (should be impossible due to unique constraint)"""
        from hospital.models import Patient
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT mrn, COUNT(*) as count
                FROM hospital_patient
                WHERE is_deleted = false AND mrn != '' AND mrn IS NOT NULL
                GROUP BY mrn
                HAVING COUNT(*) > 1
            """)
            
            duplicate_mrns = cursor.fetchall()
            
            if duplicate_mrns:
                self.stdout.write(self.style.ERROR(f'   ❌ Found {len(duplicate_mrns)} duplicate MRN(s) (CRITICAL!):'))
                for mrn, count in duplicate_mrns[:10]:
                    self.stdout.write(self.style.ERROR(f'      MRN: {mrn} - {count} record(s)'))
                return True
            else:
                self.stdout.write(self.style.SUCCESS('   ✅ No duplicate MRNs found'))
                return False
    
    def check_duplicate_staff_phones(self):
        """Check for duplicate staff phone numbers"""
        from hospital.models import Staff
        
        duplicates = Staff.objects.filter(
            is_deleted=False
        ).exclude(
            phone_number__isnull=True
        ).exclude(
            phone_number=''
        ).values('phone_number').annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('-count')
        
        if duplicates.exists():
            self.stdout.write(self.style.WARNING(f'   ⚠️  Found {duplicates.count()} duplicate phone number(s) (may be legitimate):'))
            for dup in duplicates[:5]:
                phone = dup['phone_number']
                count = dup['count']
                staff_records = Staff.objects.filter(
                    phone_number=phone,
                    is_deleted=False
                ).select_related('user')
                self.stdout.write(self.style.WARNING(f'      Phone: {phone} - {count} staff record(s):'))
                for staff in staff_records:
                    self.stdout.write(self.style.WARNING(
                        f'         - {staff.user.get_full_name() if staff.user else "No user"} '
                        f'({staff.employee_id or "No ID"})'
                    ))
            return True
        else:
            self.stdout.write(self.style.SUCCESS('   ✅ No duplicate staff phone numbers found'))
            return False
    
    def check_duplicate_user_emails(self):
        """Check for duplicate user emails"""
        duplicates = User.objects.exclude(
            email__isnull=True
        ).exclude(
            email=''
        ).values('email').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        if duplicates.exists():
            self.stdout.write(self.style.ERROR(f'   ❌ Found {duplicates.count()} duplicate email(s):'))
            for dup in duplicates[:10]:
                email = dup['email']
                count = dup['count']
                users = User.objects.filter(email=email)
                self.stdout.write(self.style.ERROR(f'      Email: {email} - {count} user(s):'))
                for user in users:
                    self.stdout.write(self.style.ERROR(f'         - {user.username} (ID: {user.id})'))
            return True
        else:
            self.stdout.write(self.style.SUCCESS('   ✅ No duplicate user emails found'))
            return False
    
    def check_duplicate_patient_contacts(self):
        """Check for duplicate patient phone numbers and emails"""
        from hospital.models import Patient
        
        # Check phones
        duplicate_phones = Patient.objects.filter(
            is_deleted=False
        ).exclude(
            phone_number__isnull=True
        ).exclude(
            phone_number=''
        ).values('phone_number').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        # Check emails
        duplicate_emails = Patient.objects.filter(
            is_deleted=False
        ).exclude(
            email__isnull=True
        ).exclude(
            email=''
        ).values('email').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        found = False
        
        if duplicate_phones.exists():
            self.stdout.write(self.style.WARNING(f'   ⚠️  Found {duplicate_phones.count()} duplicate patient phone(s) (may be legitimate):'))
            for dup in duplicate_phones[:5]:
                phone = dup['phone_number']
                count = dup['count']
                patients = Patient.objects.filter(
                    phone_number=phone,
                    is_deleted=False
                )[:3]
                self.stdout.write(self.style.WARNING(f'      Phone: {phone} - {count} patient(s):'))
                for patient in patients:
                    self.stdout.write(self.style.WARNING(f'         - {patient.full_name} (MRN: {patient.mrn})'))
            found = True
        
        if duplicate_emails.exists():
            self.stdout.write(self.style.WARNING(f'   ⚠️  Found {duplicate_emails.count()} duplicate patient email(s) (may be legitimate):'))
            for dup in duplicate_emails[:5]:
                email = dup['email']
                count = dup['count']
                patients = Patient.objects.filter(
                    email=email,
                    is_deleted=False
                )[:3]
                self.stdout.write(self.style.WARNING(f'      Email: {email} - {count} patient(s):'))
                for patient in patients:
                    self.stdout.write(self.style.WARNING(f'         - {patient.full_name} (MRN: {patient.mrn})'))
            found = True
        
        if not found:
            self.stdout.write(self.style.SUCCESS('   ✅ No duplicate patient contact info found'))
        
        return found




