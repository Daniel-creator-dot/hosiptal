"""
Management command to check doctor availability for visit creation
Diagnoses why doctors might not be showing in the visit creation form
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from hospital.models import Staff, User, Department


class Command(BaseCommand):
    help = 'Check doctor availability and diagnose issues'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== DOCTOR AVAILABILITY DIAGNOSTIC ===\n'))
        
        # 1. Check all doctors
        all_doctors = Staff.objects.filter(profession='doctor')
        self.stdout.write(f"1. Total doctors in database: {all_doctors.count()}")
        
        if all_doctors.count() == 0:
            self.stdout.write(self.style.WARNING('   ⚠️  No doctors found with profession="doctor"'))
            self.stdout.write('   Solution: Create doctor Staff records')
            return
        
        # 2. Check deleted doctors
        deleted_doctors = all_doctors.filter(is_deleted=True)
        self.stdout.write(f"\n2. Deleted doctors: {deleted_doctors.count()}")
        if deleted_doctors.count() > 0:
            self.stdout.write(self.style.WARNING('   ⚠️  Some doctors are marked as deleted:'))
            for doc in deleted_doctors[:5]:
                name = doc.user.get_full_name() if doc.user else 'No user'
                self.stdout.write(f'      - {name} (ID: {doc.id})')
        
        # 3. Check doctors without user accounts
        doctors_without_users = all_doctors.filter(user__isnull=True)
        self.stdout.write(f"\n3. Doctors without User accounts: {doctors_without_users.count()}")
        if doctors_without_users.count() > 0:
            self.stdout.write(self.style.WARNING('   ⚠️  Doctors missing User accounts:'))
            for doc in doctors_without_users[:5]:
                self.stdout.write(f'      - Staff ID: {doc.id}, Employee ID: {doc.employee_id}')
        
        # 4. Check doctors with inactive users
        doctors_with_inactive_users = all_doctors.filter(
            user__isnull=False,
            user__is_active=False
        )
        self.stdout.write(f"\n4. Doctors with inactive User accounts: {doctors_with_inactive_users.count()}")
        if doctors_with_inactive_users.count() > 0:
            self.stdout.write(self.style.WARNING('   ⚠️  Doctors with inactive users:'))
            for doc in doctors_with_inactive_users[:5]:
                name = doc.user.get_full_name() if doc.user else 'No name'
                self.stdout.write(f'      - {name} (User: {doc.user.username}, Active: {doc.user.is_active})')
        
        # 5. Check available doctors (what the view uses)
        available_doctors = Staff.objects.filter(
            profession='doctor',
            is_deleted=False,
            user__isnull=False,
            user__is_active=True
        ).select_related('user', 'department')
        
        self.stdout.write(f"\n5. AVAILABLE DOCTORS (for visit creation): {available_doctors.count()}")
        
        if available_doctors.count() == 0:
            self.stdout.write(self.style.ERROR('\n   ❌ NO DOCTORS AVAILABLE FOR VISIT CREATION'))
            self.stdout.write('\n   Reasons:')
            if deleted_doctors.count() > 0:
                self.stdout.write(f'      - {deleted_doctors.count()} doctors are deleted')
            if doctors_without_users.count() > 0:
                self.stdout.write(f'      - {doctors_without_users.count()} doctors have no User accounts')
            if doctors_with_inactive_users.count() > 0:
                self.stdout.write(f'      - {doctors_with_inactive_users.count()} doctors have inactive User accounts')
        else:
            self.stdout.write(self.style.SUCCESS(f'\n   [OK] {available_doctors.count()} doctors are available\n'))
            self.stdout.write('   Available Doctors:')
            self.stdout.write('   ' + '-' * 80)
            
            for idx, doctor in enumerate(available_doctors.order_by('user__first_name', 'user__last_name'), 1):
                user = doctor.user
                full_name = user.get_full_name() or f"{user.first_name} {user.last_name}".strip()
                department = doctor.department.name if doctor.department else 'No Department'
                specialization = doctor.specialization or 'Not specified'
                is_active = '[Active]' if doctor.is_active else '[Inactive]'
                
                self.stdout.write(f'\n   {idx}. {full_name}')
                self.stdout.write(f'      - Username: {user.username}')
                self.stdout.write(f'      - Email: {user.email or "No email"}')
                self.stdout.write(f'      - Department: {department}')
                self.stdout.write(f'      - Specialization: {specialization}')
                self.stdout.write(f'      - Staff Status: {is_active}')
                self.stdout.write(f'      - Staff ID: {doctor.id}')
                self.stdout.write(f'      - Employee ID: {doctor.employee_id or "Not set"}')
                
                # Check pricing info
                try:
                    from hospital.utils_doctor_pricing import DoctorPricingService
                    pricing_info = DoctorPricingService.get_doctor_pricing_info(doctor)
                    if pricing_info['is_specialist']:
                        self.stdout.write(f'      - Pricing: Specialist (First: GHS {pricing_info["first_visit"]}, Subsequent: GHS {pricing_info["subsequent_visit"]})')
                        self.stdout.write(f'      - Show Price: {"Yes" if pricing_info["show_price"] else "No"}')
                    else:
                        self.stdout.write(f'      - Pricing: General (GHS {pricing_info["first_visit"]})')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'      - Pricing: Error checking - {e}'))
        
        # 6. Summary and recommendations
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('\nSUMMARY & RECOMMENDATIONS:\n')
        
        if available_doctors.count() == 0:
            self.stdout.write(self.style.ERROR('[ERROR] No doctors are available for visit creation.\n'))
            self.stdout.write('To fix this:\n')
            
            if doctors_without_users.count() > 0:
                self.stdout.write('1. Create User accounts for doctors without users')
                self.stdout.write('   Example:')
                self.stdout.write('   ```python')
                self.stdout.write('   from django.contrib.auth.models import User')
                self.stdout.write('   from hospital.models import Staff')
                self.stdout.write('   ')
                self.stdout.write('   doctor = Staff.objects.get(id=XXX)')
                self.stdout.write('   user = User.objects.create_user(')
                self.stdout.write('       username="dr.username",')
                self.stdout.write('       email="doctor@hospital.com",')
                self.stdout.write('       first_name="Doctor",')
                self.stdout.write('       last_name="Name"')
                self.stdout.write('   )')
                self.stdout.write('   doctor.user = user')
                self.stdout.write('   doctor.save()')
                self.stdout.write('   ```\n')
            
            if doctors_with_inactive_users.count() > 0:
                self.stdout.write('2. Activate User accounts:')
                self.stdout.write('   ```python')
                self.stdout.write('   for doctor in Staff.objects.filter(profession="doctor", user__is_active=False):')
                self.stdout.write('       if doctor.user:')
                self.stdout.write('           doctor.user.is_active = True')
                self.stdout.write('           doctor.user.save()')
                self.stdout.write('   ```\n')
            
            if deleted_doctors.count() > 0:
                self.stdout.write('3. Restore deleted doctors (if needed):')
                self.stdout.write('   ```python')
                self.stdout.write('   Staff.objects.filter(profession="doctor", is_deleted=True).update(is_deleted=False)')
                self.stdout.write('   ```\n')
        else:
            self.stdout.write(self.style.SUCCESS(f'[OK] System is ready! {available_doctors.count()} doctors available for visit creation.\n'))
            self.stdout.write('The visit creation form should display these doctors.\n')
        
        self.stdout.write('\n' + '=' * 80 + '\n')
