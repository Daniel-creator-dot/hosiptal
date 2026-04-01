"""
Database Stability and Integrity Management Command
Checks and fixes database inconsistencies, orphaned records, and integrity issues
"""
from django.core.management.base import BaseCommand
from django.db import transaction, connection
from django.db.models import Q, Count
from django.utils import timezone
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ensure database stability by checking and fixing inconsistencies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Only check for issues without fixing them',
        )
        parser.add_argument(
            '--fix-orphans',
            action='store_true',
            help='Fix orphaned records',
        )
        parser.add_argument(
            '--fix-constraints',
            action='store_true',
            help='Fix broken foreign key constraints',
        )
        parser.add_argument(
            '--fix-all',
            action='store_true',
            help='Fix all detected issues',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('DATABASE STABILITY CHECK'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))
        
        issues_found = []
        issues_fixed = []
        
        # Check for orphaned records
        self.stdout.write(self.style.WARNING('Checking for orphaned records...'))
        orphaned = self.check_orphaned_records()
        issues_found.extend(orphaned)
        
        # Check foreign key integrity
        self.stdout.write(self.style.WARNING('Checking foreign key integrity...'))
        broken_fks = self.check_foreign_key_integrity()
        issues_found.extend(broken_fks)
        
        # Check for missing indexes
        self.stdout.write(self.style.WARNING('Checking for missing indexes...'))
        missing_indexes = self.check_missing_indexes()
        issues_found.extend(missing_indexes)
        
        # Check for duplicate records
        self.stdout.write(self.style.WARNING('Checking for duplicates...'))
        duplicates = self.check_duplicates()
        issues_found.extend(duplicates)
        
        # Check for null constraint violations
        self.stdout.write(self.style.WARNING('Checking for null constraint violations...'))
        null_violations = self.check_null_constraints()
        issues_found.extend(null_violations)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*70))
        
        if issues_found:
            self.stdout.write(self.style.ERROR(f'\n⚠️  Found {len(issues_found)} issue(s):\n'))
            for issue in issues_found:
                self.stdout.write(f'  - {issue}')
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ No issues found! Database is stable.\n'))
        
        # Fix issues if requested
        if not options['check_only'] and (options['fix_all'] or options['fix_orphans'] or options['fix_constraints']):
            self.stdout.write(self.style.WARNING('\n' + '='*70))
            self.stdout.write(self.style.WARNING('FIXING ISSUES'))
            self.stdout.write(self.style.WARNING('='*70 + '\n'))
            
            if options['fix_all'] or options['fix_orphans']:
                fixed = self.fix_orphaned_records()
                issues_fixed.extend(fixed)
            
            if options['fix_all'] or options['fix_constraints']:
                fixed = self.fix_foreign_key_constraints()
                issues_fixed.extend(fixed)
            
            if issues_fixed:
                self.stdout.write(self.style.SUCCESS(f'\n✅ Fixed {len(issues_fixed)} issue(s)\n'))
            else:
                self.stdout.write(self.style.SUCCESS('\n✅ No fixes needed\n'))
        elif not options['check_only']:
            self.stdout.write(self.style.WARNING('\n💡 Use --fix-all to automatically fix issues'))
            self.stdout.write(self.style.WARNING('   Or use --fix-orphans or --fix-constraints for specific fixes\n'))

    def check_orphaned_records(self):
        """Check for orphaned records across all models"""
        issues = []
        
        try:
            from hospital.models import (
                Encounter, Patient, Invoice, InvoiceLine,
                LabResult, Order, Prescription, Admission,
                Vitals, Appointment
            )
            
            # Check orphaned encounters
            orphaned_encounters = Encounter.objects.filter(
                patient__isnull=False
            ).exclude(
                patient__in=Patient.objects.filter(is_deleted=False)
            ).count()
            
            if orphaned_encounters > 0:
                issues.append(f'{orphaned_encounters} orphaned encounter(s) (patient deleted)')
            
            # Check orphaned invoice lines
            orphaned_invoice_lines = InvoiceLine.objects.filter(
                invoice__isnull=False
            ).exclude(
                invoice__in=Invoice.objects.filter(is_deleted=False)
            ).count()
            
            if orphaned_invoice_lines > 0:
                issues.append(f'{orphaned_invoice_lines} orphaned invoice line(s)')
            
            # Check orphaned lab results
            orphaned_lab_results = LabResult.objects.filter(
                order__isnull=False
            ).exclude(
                order__in=Order.objects.filter(is_deleted=False)
            ).count()
            
            if orphaned_lab_results > 0:
                issues.append(f'{orphaned_lab_results} orphaned lab result(s)')
            
            # Check orphaned prescriptions
            orphaned_prescriptions = Prescription.objects.filter(
                order__isnull=False
            ).exclude(
                order__in=Order.objects.filter(is_deleted=False)
            ).count()
            
            if orphaned_prescriptions > 0:
                issues.append(f'{orphaned_prescriptions} orphaned prescription(s)')
            
            # Check orphaned vitals
            orphaned_vitals = Vitals.objects.filter(
                encounter__isnull=False
            ).exclude(
                encounter__in=Encounter.objects.filter(is_deleted=False)
            ).count()
            
            if orphaned_vitals > 0:
                issues.append(f'{orphaned_vitals} orphaned vital record(s)')
            
            # Check orphaned appointments
            orphaned_appointments = Appointment.objects.filter(
                patient__isnull=False
            ).exclude(
                patient__in=Patient.objects.filter(is_deleted=False)
            ).count()
            
            if orphaned_appointments > 0:
                issues.append(f'{orphaned_appointments} orphaned appointment(s)')
            
            if not issues:
                self.stdout.write(self.style.SUCCESS('  ✅ No orphaned records found'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ❌ Error checking orphaned records: {e}'))
            logger.exception("Error checking orphaned records")
        
        return issues

    def check_foreign_key_integrity(self):
        """Check for broken foreign key relationships"""
        issues = []
        
        try:
            from hospital.models import Staff
            from django.contrib.auth.models import User
            
            # Check staff without users
            staff_without_user = Staff.objects.filter(
                user__isnull=True
            ).exclude(is_deleted=True).count()
            
            if staff_without_user > 0:
                issues.append(f'{staff_without_user} staff record(s) without user account')
            
            # Check users without staff (not necessarily an issue, but worth noting)
            if hasattr(self, '_verbose') and self._verbose:
                users_without_staff = User.objects.exclude(
                    staff__isnull=False
                ).filter(is_staff=True).count()
                
                if users_without_staff > 0:
                    self.stdout.write(self.style.WARNING(f'  ℹ️  {users_without_staff} staff user(s) without staff record'))
            
            if not issues:
                self.stdout.write(self.style.SUCCESS('  ✅ Foreign key integrity OK'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ❌ Error checking foreign keys: {e}'))
            logger.exception("Error checking foreign key integrity")
        
        return issues

    def check_missing_indexes(self):
        """Check for missing database indexes on critical fields"""
        issues = []
        
        try:
            with connection.cursor() as cursor:
                # Check if Patient table has required indexes
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM pg_indexes
                    WHERE tablename = 'hospital_patient'
                    AND indexname LIKE '%phone%'
                """)
                
                phone_index_count = cursor.fetchone()[0]
                
                if phone_index_count == 0:
                    issues.append('Missing index on hospital_patient.phone_number')
                
                if not issues:
                    self.stdout.write(self.style.SUCCESS('  ✅ Critical indexes present'))
            
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  Could not check indexes: {e}'))
        
        return issues

    def check_duplicates(self):
        """Check for duplicate records"""
        issues = []
        
        try:
            from hospital.models import Patient
            
            # Check for duplicate MRNs (should be impossible due to unique constraint)
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT mrn, COUNT(*) as count
                    FROM hospital_patient
                    WHERE is_deleted = false AND mrn != ''
                    GROUP BY mrn
                    HAVING COUNT(*) > 1
                """)
                
                duplicate_mrns = cursor.fetchall()
                
                if duplicate_mrns:
                    issues.append(f'{len(duplicate_mrns)} duplicate MRN(s) found (should be unique)')
            
            if not issues:
                self.stdout.write(self.style.SUCCESS('  ✅ No duplicates found'))
            
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  Could not check duplicates: {e}'))
        
        return issues

    def check_null_constraints(self):
        """Check for null values in required fields"""
        issues = []
        
        try:
            from hospital.models import Patient
            
            # Check for patients with empty MRN
            empty_mrn = Patient.objects.filter(
                Q(mrn='') | Q(mrn__isnull=True),
                is_deleted=False
            ).count()
            
            if empty_mrn > 0:
                issues.append(f'{empty_mrn} patient(s) with empty MRN')
            
            # Check for patients with empty names
            empty_names = Patient.objects.filter(
                (Q(first_name='') | Q(first_name__isnull=True)) |
                (Q(last_name='') | Q(last_name__isnull=True)),
                is_deleted=False
            ).count()
            
            if empty_names > 0:
                issues.append(f'{empty_names} patient(s) with empty name(s)')
            
            if not issues:
                self.stdout.write(self.style.SUCCESS('  ✅ No null constraint violations'))
            
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  Could not check null constraints: {e}'))
        
        return issues

    @transaction.atomic
    def fix_orphaned_records(self):
        """Fix orphaned records by soft-deleting them"""
        fixed = []
        
        try:
            from hospital.models import (
                InvoiceLine, LabResult, Prescription,
                Vitals, Appointment
            )
            
            # Fix orphaned invoice lines
            orphaned_lines = InvoiceLine.objects.filter(
                invoice__isnull=False
            ).exclude(
                invoice__in=Invoice.objects.filter(is_deleted=False)
            )
            
            count = orphaned_lines.count()
            if count > 0:
                orphaned_lines.update(is_deleted=True)
                fixed.append(f'Soft-deleted {count} orphaned invoice line(s)')
                self.stdout.write(self.style.SUCCESS(f'  ✅ Fixed {count} orphaned invoice line(s)'))
            
            # Fix orphaned vitals (soft delete)
            orphaned_vitals = Vitals.objects.filter(
                encounter__isnull=False
            ).exclude(
                encounter__in=Encounter.objects.filter(is_deleted=False)
            )
            
            count = orphaned_vitals.count()
            if count > 0:
                orphaned_vitals.update(is_deleted=True)
                fixed.append(f'Soft-deleted {count} orphaned vital record(s)')
                self.stdout.write(self.style.SUCCESS(f'  ✅ Fixed {count} orphaned vital record(s)'))
            
            if not fixed:
                self.stdout.write(self.style.SUCCESS('  ✅ No orphaned records to fix'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ❌ Error fixing orphaned records: {e}'))
            logger.exception("Error fixing orphaned records")
        
        return fixed

    @transaction.atomic
    def fix_foreign_key_constraints(self):
        """Fix broken foreign key constraints"""
        fixed = []
        
        try:
            from hospital.models import Staff
            
            # Fix staff without users by creating placeholder or marking deleted
            staff_without_user = Staff.objects.filter(
                user__isnull=True
            ).exclude(is_deleted=True)
            
            count = staff_without_user.count()
            if count > 0:
                # Mark as deleted instead of creating fake users
                staff_without_user.update(is_deleted=True)
                fixed.append(f'Marked {count} staff record(s) without users as deleted')
                self.stdout.write(self.style.SUCCESS(f'  ✅ Fixed {count} staff record(s) without users'))
            
            if not fixed:
                self.stdout.write(self.style.SUCCESS('  ✅ No foreign key issues to fix'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ❌ Error fixing foreign keys: {e}'))
            logger.exception("Error fixing foreign key constraints")
        
        return fixed




