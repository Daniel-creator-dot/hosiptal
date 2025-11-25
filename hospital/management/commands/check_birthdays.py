"""
Check upcoming birthdays
"""
from django.core.management.base import BaseCommand
from hospital.models import Staff
from datetime import date, timedelta


class Command(BaseCommand):
    help = 'Check upcoming staff birthdays'

    def handle(self, *args, **options):
        today = date.today()
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Birthday Check for {today} ===\n'))
        
        # Total staff
        total_staff = Staff.objects.filter(is_deleted=False, is_active=True).count()
        staff_with_dob = Staff.objects.filter(
            is_deleted=False, 
            is_active=True, 
            date_of_birth__isnull=False
        ).count()
        
        self.stdout.write(f'Total active staff: {total_staff}')
        self.stdout.write(f'Staff with birthdays set: {staff_with_dob}')
        self.stdout.write(f'Staff without birthdays: {total_staff - staff_with_dob}\n')
        
        # Check next 30 days
        upcoming_staff = []
        for i in range(1, 31):
            check_date = today + timedelta(days=i)
            staff_birthdays = Staff.objects.filter(
                date_of_birth__month=check_date.month,
                date_of_birth__day=check_date.day,
                is_active=True,
                is_deleted=False
            ).select_related('user', 'department')
            
            for staff in staff_birthdays:
                this_year_bday = date(today.year, staff.date_of_birth.month, staff.date_of_birth.day)
                if this_year_bday < today:
                    this_year_bday = date(today.year + 1, staff.date_of_birth.month, staff.date_of_birth.day)
                days_until = (this_year_bday - today).days
                upcoming_staff.append((days_until, staff))
        
        self.stdout.write(self.style.WARNING(f'\nUpcoming birthdays in next 30 days: {len(upcoming_staff)}\n'))
        
        if upcoming_staff:
            upcoming_staff.sort(key=lambda x: x[0])
            for days, staff in upcoming_staff[:15]:
                dept_name = staff.department.name if staff.department else "No Department"
                phone = staff.phone_number if hasattr(staff, 'phone_number') and staff.phone_number else "No phone"
                self.stdout.write(
                    f'  {days:2d} days: {staff.user.get_full_name():<30s} | {dept_name:<20s} | DOB: {staff.date_of_birth.strftime("%b %d, %Y")} | {phone}'
                )
        else:
            self.stdout.write('  No birthdays found in next 30 days')
        
        self.stdout.write(self.style.SUCCESS('\n=== Done ===\n'))
































