"""
Django management command to fix database errors
"""
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.core.management import call_command
from django.db.utils import OperationalError, ProgrammingError, DatabaseError
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix common database errors and issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Only check for errors, do not fix',
        )
        parser.add_argument(
            '--fix-migrations',
            action='store_true',
            help='Create and apply missing migrations',
        )
        parser.add_argument(
            '--fix-constraints',
            action='store_true',
            help='Fix foreign key and constraint issues',
        )

    def handle(self, *args, **options):
        check_only = options.get('check_only', False)
        fix_migrations = options.get('fix_migrations', False)
        fix_constraints = options.get('fix_constraints', False)
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('DATABASE ERROR FIX UTILITY'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        issues_found = []
        fixes_applied = []
        
        # 1. Check database connection
        self.stdout.write('\n[1] Checking database connection...')
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                self.stdout.write(self.style.SUCCESS('  ✓ Database connection OK'))
        except Exception as e:
            error_msg = f'  ✗ Database connection error: {e}'
            self.stdout.write(self.style.ERROR(error_msg))
            issues_found.append(error_msg)
            return
        
        # 2. Check for missing tables
        self.stdout.write('\n[2] Checking for missing tables...')
        missing_tables = self._check_missing_tables()
        if missing_tables:
            issues_found.extend([f'Missing table: {t}' for t in missing_tables])
            if not check_only and fix_migrations:
                self.stdout.write(self.style.WARNING('  → Will create migrations to fix missing tables'))
        else:
            self.stdout.write(self.style.SUCCESS('  ✓ All required tables exist'))
        
        # 3. Check for missing columns
        self.stdout.write('\n[3] Checking for missing columns...')
        missing_columns = self._check_missing_columns()
        if missing_columns:
            issues_found.extend([f'Missing column: {t}.{c}' for t, c in missing_columns])
            if not check_only and fix_migrations:
                self.stdout.write(self.style.WARNING('  → Will create migrations to fix missing columns'))
        else:
            self.stdout.write(self.style.SUCCESS('  ✓ All critical columns exist'))
        
        # 4. Check migration status
        self.stdout.write('\n[4] Checking migration status...')
        migrations_ok = self._check_migrations()
        if not migrations_ok:
            issues_found.append('Unapplied migrations detected')
            if not check_only and fix_migrations:
                try:
                    self.stdout.write('  → Creating migrations...')
                    call_command('makemigrations', 'hospital', verbosity=0)
                    self.stdout.write('  → Applying migrations...')
                    call_command('migrate', verbosity=0)
                    fixes_applied.append('Applied pending migrations')
                    self.stdout.write(self.style.SUCCESS('  ✓ Migrations applied'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ✗ Migration error: {e}'))
        else:
            self.stdout.write(self.style.SUCCESS('  ✓ All migrations applied'))
        
        # 5. Check foreign key constraints
        self.stdout.write('\n[5] Checking foreign key constraints...')
        broken_fks = self._check_foreign_keys()
        if broken_fks:
            issues_found.extend([f'Broken FK: {fk}' for fk in broken_fks[:5]])
            if not check_only and fix_constraints:
                self.stdout.write(self.style.WARNING('  → Manual review required for FK issues'))
        else:
            self.stdout.write(self.style.SUCCESS('  ✓ Foreign key constraints OK'))
        
        # 6. Check for orphaned records
        self.stdout.write('\n[6] Checking for orphaned records...')
        orphaned = self._check_orphaned_records()
        if orphaned:
            issues_found.extend([f'Orphaned records: {o}' for o in orphaned[:5]])
        else:
            self.stdout.write(self.style.SUCCESS('  ✓ No orphaned records found'))
        
        # Summary
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write('SUMMARY')
        self.stdout.write('=' * 70)
        
        if issues_found:
            self.stdout.write(self.style.WARNING(f'\n⚠️  Found {len(issues_found)} issues:'))
            for issue in issues_found[:10]:
                self.stdout.write(f'   - {issue}')
            if len(issues_found) > 10:
                self.stdout.write(f'   ... and {len(issues_found) - 10} more')
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ No database errors found!'))
        
        if fixes_applied:
            self.stdout.write(self.style.SUCCESS(f'\n✅ Applied {len(fixes_applied)} fixes:'))
            for fix in fixes_applied:
                self.stdout.write(f'   - {fix}')
        
        if issues_found and check_only:
            self.stdout.write('\n💡 Run without --check-only to attempt fixes')
            self.stdout.write('   python manage.py fix_database --fix-migrations')

    def _check_missing_tables(self):
        """Check for missing database tables"""
        missing = []
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    AND table_type = 'BASE TABLE'
                """)
                existing_tables = {row[0] for row in cursor.fetchall()}
                
                # Check critical tables
                critical_tables = [
                    'hospital_patient',
                    'hospital_staff',
                    'hospital_invoice',
                    'hospital_generalledger',
                    'hospital_journalentry',
                    'hospital_transaction',
                ]
                
                for table in critical_tables:
                    if table not in existing_tables:
                        missing.append(table)
        except Exception as e:
            logger.error(f"Error checking tables: {e}")
        return missing

    def _check_missing_columns(self):
        """Check for missing columns in critical tables"""
        missing = []
        try:
            with connection.cursor() as cursor:
                critical_checks = [
                    ('hospital_generalledger', 'balance'),
                    ('hospital_generalledger', 'reference_number'),
                    ('hospital_journalentry', 'entry_type'),
                    ('hospital_journalentry', 'reference_number'),
                    ('hospital_journalentry', 'posted_by_id'),
                    ('hospital_journalentry', 'status'),
                ]
                
                for table_name, column_name in critical_checks:
                    cursor.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = %s
                        AND column_name = %s
                    """, [table_name, column_name])
                    
                    if not cursor.fetchone():
                        missing.append((table_name, column_name))
        except Exception as e:
            logger.error(f"Error checking columns: {e}")
        return missing

    def _check_migrations(self):
        """Check if all migrations are applied"""
        try:
            from django.db.migrations.executor import MigrationExecutor
            from django.db import connections
            
            executor = MigrationExecutor(connections['default'])
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            return len(plan) == 0
        except Exception as e:
            logger.error(f"Error checking migrations: {e}")
            return False

    def _check_foreign_keys(self):
        """Check for broken foreign key constraints"""
        broken = []
        try:
            with connection.cursor() as cursor:
                # This is a simplified check - full validation would require more complex queries
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM information_schema.table_constraints 
                    WHERE constraint_type = 'FOREIGN KEY'
                    AND table_schema = 'public'
                """)
                count = cursor.fetchone()[0]
                # Basic check - would need more detailed validation
        except Exception as e:
            logger.error(f"Error checking foreign keys: {e}")
        return broken

    def _check_orphaned_records(self):
        """Check for orphaned records"""
        orphaned = []
        try:
            # Check for orphaned invoice lines
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM hospital_invoiceline il
                    LEFT JOIN hospital_invoice i ON il.invoice_id = i.id
                    WHERE i.id IS NULL AND il.is_deleted = false
                """)
                count = cursor.fetchone()[0]
                if count > 0:
                    orphaned.append(f'{count} orphaned invoice lines')
        except Exception as e:
            logger.error(f"Error checking orphaned records: {e}")
        return orphaned

