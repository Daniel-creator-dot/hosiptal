"""
Verify database integrity and show statistics
"""
from django.core.management.base import BaseCommand
from django.db import connection
from hospital.models import Staff, Patient, Department
from hospital.models_advanced import LeaveRequest, Attendance
from hospital.models_hr import (
    PayrollPeriod, Payroll, LeaveBalance, PerformanceReview,
    TrainingRecord, StaffContract
)
from hospital.models_accounting import Transaction, Invoice


class Command(BaseCommand):
    help = 'Verify database integrity and show statistics'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('DATABASE INTEGRITY CHECK'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))
        
        # Database file info
        from django.conf import settings
        db_name = settings.DATABASES['default']['NAME']
        import os
        if os.path.exists(db_name):
            db_size = os.path.getsize(db_name) / (1024 * 1024)
            self.stdout.write(f'Database File: {db_name}')
            self.stdout.write(f'Database Size: {db_size:.2f} MB\n')
        
        # Check critical tables
        self.stdout.write(self.style.WARNING('CORE DATA:'))
        
        models_to_check = [
            ('Staff', Staff),
            ('Patients', Patient),
            ('Departments', Department),
            ('Leave Requests', LeaveRequest),
            ('Staff Contracts', StaffContract),
            ('Leave Balances', LeaveBalance),
            ('Attendance Records', Attendance),
            ('Performance Reviews', PerformanceReview),
            ('Training Records', TrainingRecord),
            ('Payroll Periods', PayrollPeriod),
            ('Payroll Records', Payroll),
            ('Invoices', Invoice),
            ('Transactions', Transaction),
        ]
        
        total_records = 0
        for name, model in models_to_check:
            try:
                count = model.objects.count()
                active_count = model.objects.filter(is_deleted=False).count() if hasattr(model.objects.first(), 'is_deleted') else count
                total_records += count
                self.stdout.write(f'  {name:<25s}: {count:>6d} total, {active_count:>6d} active')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  {name:<25s}: ERROR - {str(e)}'))
        
        self.stdout.write(f'\nTotal Records: {total_records:,}')
        
        # Database connection info
        self.stdout.write(self.style.WARNING('\n\nDATABASE CONNECTION:'))
        with connection.cursor() as cursor:
            cursor.execute("SELECT sqlite_version();")
            version = cursor.fetchone()
            self.stdout.write(f'  SQLite Version: {version[0]}')
        
        # Check for missing migrations
        self.stdout.write(self.style.WARNING('\n\nMIGRATIONS:'))
        from django.core.management import call_command
        from io import StringIO
        
        try:
            out = StringIO()
            call_command('showmigrations', '--list', stdout=out)
            migrations_output = out.getvalue()
            
            unapplied = [line for line in migrations_output.split('\n') if '[ ]' in line]
            if unapplied:
                self.stdout.write(self.style.ERROR(f'  UNAPPLIED MIGRATIONS FOUND: {len(unapplied)}'))
                for migration in unapplied[:5]:
                    self.stdout.write(f'    {migration}')
                self.stdout.write(self.style.WARNING('\n  Run: python manage.py migrate'))
            else:
                self.stdout.write(self.style.SUCCESS('  All migrations applied'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  Could not check migrations: {str(e)}'))
        
        # Data integrity checks
        self.stdout.write(self.style.WARNING('\n\nDATA INTEGRITY CHECKS:'))
        
        # Check for staff without users
        staff_without_user = 0
        try:
            for staff in Staff.objects.all():
                if not hasattr(staff, 'user') or not staff.user:
                    staff_without_user += 1
            
            if staff_without_user > 0:
                self.stdout.write(self.style.ERROR(f'  Staff without User: {staff_without_user}'))
            else:
                self.stdout.write(self.style.SUCCESS('  All staff have users'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  Staff check error: {str(e)}'))
        
        # Check for leave requests without staff
        orphaned_leaves = LeaveRequest.objects.filter(staff__isnull=True).count()
        if orphaned_leaves > 0:
            self.stdout.write(self.style.ERROR(f'  Orphaned Leave Requests: {orphaned_leaves}'))
        else:
            self.stdout.write(self.style.SUCCESS('  All leave requests have staff'))
        
        # Recommendations
        self.stdout.write(self.style.SUCCESS('\n\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('RECOMMENDATIONS:'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write('\n1. Run backups regularly:')
        self.stdout.write('   python manage.py backup_database')
        self.stdout.write('\n2. Keep migrations up to date:')
        self.stdout.write('   python manage.py makemigrations')
        self.stdout.write('   python manage.py migrate')
        self.stdout.write('\n3. Verify database periodically:')
        self.stdout.write('   python manage.py verify_database')
        self.stdout.write('\n4. Store backups in multiple locations')
        self.stdout.write('   - Local: backups/ folder')
        self.stdout.write('   - External: USB drive, cloud storage\n')
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('CHECK COMPLETE'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))
































