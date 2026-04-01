"""
Database Performance Optimization Command
Analyzes and fixes database performance issues:
- Missing indexes
- N+1 query problems
- Inefficient queries
- Database statistics
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Optimize database performance by analyzing and fixing issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--analyze-only',
            action='store_true',
            help='Only analyze, do not apply fixes',
        )
        parser.add_argument(
            '--create-indexes',
            action='store_true',
            help='Create missing performance indexes',
        )
        parser.add_argument(
            '--vacuum',
            action='store_true',
            help='Run VACUUM ANALYZE to optimize database',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all optimizations',
        )

    def handle(self, *args, **options):
        db_engine = settings.DATABASES['default']['ENGINE']
        
        if 'postgresql' in db_engine:
            self.handle_postgresql(options)
        else:
            self.stdout.write(self.style.ERROR(f'Database engine {db_engine} not supported for optimization'))

    def handle_postgresql(self, options):
        """PostgreSQL-specific optimizations"""
        self.stdout.write(self.style.SUCCESS('🔍 Analyzing PostgreSQL database performance...'))
        
        with connection.cursor() as cursor:
            # 1. Check for missing indexes on foreign keys
            if options['analyze_only'] or options['all']:
                self.analyze_missing_indexes(cursor)
            
            # 2. Check table statistics
            if options['analyze_only'] or options['all']:
                self.analyze_table_statistics(cursor)
            
            # 3. Check for unused indexes
            if options['analyze_only'] or options['all']:
                self.analyze_unused_indexes(cursor)
            
            # 4. Create missing indexes
            if options['create_indexes'] or options['all']:
                self.create_performance_indexes(cursor)
            
            # 5. Run VACUUM ANALYZE
            if options['vacuum'] or options['all']:
                self.run_vacuum_analyze(cursor)
            
            # 6. Update query planner statistics
            if options['all']:
                self.update_statistics(cursor)

    def analyze_missing_indexes(self, cursor):
        """Find foreign keys without indexes"""
        self.stdout.write('\n📊 Analyzing missing indexes on foreign keys...')
        
        query = """
        SELECT
            tc.table_name,
            kcu.column_name,
            tc.constraint_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        LEFT JOIN pg_indexes AS idx
            ON idx.tablename = tc.table_name
            AND idx.indexdef LIKE '%' || kcu.column_name || '%'
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = 'public'
            AND idx.indexname IS NULL
        ORDER BY tc.table_name, kcu.column_name;
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        if results:
            self.stdout.write(self.style.WARNING(f'Found {len(results)} foreign keys without indexes:'))
            for table, column, constraint in results[:20]:  # Show first 20
                self.stdout.write(f'  - {table}.{column} (constraint: {constraint})')
            if len(results) > 20:
                self.stdout.write(f'  ... and {len(results) - 20} more')
        else:
            self.stdout.write(self.style.SUCCESS('✅ All foreign keys have indexes'))

    def analyze_table_statistics(self, cursor):
        """Check if tables need statistics update"""
        self.stdout.write('\n📊 Analyzing table statistics...')
        
        query = """
        SELECT
            schemaname,
            tablename,
            n_tup_ins + n_tup_upd as modifications,
            last_vacuum,
            last_autovacuum,
            last_analyze,
            last_autoanalyze
        FROM pg_stat_user_tables
        WHERE schemaname = 'public'
        ORDER BY modifications DESC
        LIMIT 10;
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        if results:
            self.stdout.write('Top tables by modifications:')
            for schema, table, mods, last_vac, last_auto_vac, last_an, last_auto_an in results:
                self.stdout.write(f'  - {table}: {mods} modifications')
                if not last_an and not last_auto_an:
                    self.stdout.write(self.style.WARNING(f'    ⚠️  Never analyzed!'))

    def analyze_unused_indexes(self, cursor):
        """Find indexes that are never used"""
        self.stdout.write('\n📊 Analyzing unused indexes...')
        
        query = """
        SELECT
            schemaname,
            tablename,
            indexname,
            idx_scan as index_scans
        FROM pg_stat_user_indexes
        WHERE schemaname = 'public'
            AND idx_scan = 0
            AND indexname NOT LIKE '%_pkey'
        ORDER BY tablename, indexname
        LIMIT 20;
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        if results:
            self.stdout.write(self.style.WARNING(f'Found {len(results)} potentially unused indexes:'))
            for schema, table, index, scans in results:
                self.stdout.write(f'  - {table}.{index} (0 scans)')
        else:
            self.stdout.write(self.style.SUCCESS('✅ No obviously unused indexes found'))

    def create_performance_indexes(self, cursor):
        """Create critical performance indexes"""
        self.stdout.write('\n🔧 Creating performance indexes...')
        
        indexes = [
            # Encounter indexes
            ("CREATE INDEX IF NOT EXISTS idx_encounter_status_deleted ON hospital_encounter(status, is_deleted) WHERE is_deleted = false;", "Encounter status + deleted"),
            ("CREATE INDEX IF NOT EXISTS idx_encounter_patient_status ON hospital_encounter(patient_id, status) WHERE is_deleted = false;", "Encounter patient + status"),
            ("CREATE INDEX IF NOT EXISTS idx_encounter_started_at ON hospital_encounter(started_at DESC) WHERE is_deleted = false;", "Encounter started_at"),
            
            # Invoice indexes
            ("CREATE INDEX IF NOT EXISTS idx_invoice_status_deleted ON hospital_invoice(status, is_deleted) WHERE is_deleted = false;", "Invoice status + deleted"),
            ("CREATE INDEX IF NOT EXISTS idx_invoice_patient ON hospital_invoice(patient_id) WHERE is_deleted = false;", "Invoice patient"),
            ("CREATE INDEX IF NOT EXISTS idx_invoice_created_at ON hospital_invoice(created_at DESC) WHERE is_deleted = false;", "Invoice created_at"),
            
            # Order indexes
            ("CREATE INDEX IF NOT EXISTS idx_order_encounter_type ON hospital_order(encounter_id, order_type) WHERE is_deleted = false;", "Order encounter + type"),
            ("CREATE INDEX IF NOT EXISTS idx_order_status ON hospital_order(status) WHERE is_deleted = false;", "Order status"),
            
            # Prescription indexes
            ("CREATE INDEX IF NOT EXISTS idx_prescription_encounter ON hospital_prescription(encounter_id) WHERE is_deleted = false;", "Prescription encounter"),
            ("CREATE INDEX IF NOT EXISTS idx_prescription_status ON hospital_prescription(status) WHERE is_deleted = false;", "Prescription status"),
            
            # LabResult indexes
            ("CREATE INDEX IF NOT EXISTS idx_labresult_order ON hospital_labresult(order_id) WHERE is_deleted = false;", "LabResult order"),
            ("CREATE INDEX IF NOT EXISTS idx_labresult_verified ON hospital_labresult(verified_by_id) WHERE verified_by_id IS NOT NULL AND is_deleted = false;", "LabResult verified_by"),
            
            # VitalSign indexes
            ("CREATE INDEX IF NOT EXISTS idx_vitalsign_encounter_recorded ON hospital_vitalsign(encounter_id, recorded_at DESC) WHERE is_deleted = false;", "VitalSign encounter + recorded_at"),
            
            # Appointment indexes
            ("CREATE INDEX IF NOT EXISTS idx_appointment_date_status ON hospital_appointment(appointment_date, status) WHERE is_deleted = false;", "Appointment date + status"),
            ("CREATE INDEX IF NOT EXISTS idx_appointment_patient ON hospital_appointment(patient_id) WHERE is_deleted = false;", "Appointment patient"),
            
            # Admission indexes
            ("CREATE INDEX IF NOT EXISTS idx_admission_status ON hospital_admission(status) WHERE is_deleted = false;", "Admission status"),
            ("CREATE INDEX IF NOT EXISTS idx_admission_patient ON hospital_admission(patient_id) WHERE is_deleted = false;", "Admission patient"),
            
            # Staff indexes
            ("CREATE INDEX IF NOT EXISTS idx_staff_user_active ON hospital_staff(user_id, is_active) WHERE is_deleted = false;", "Staff user + active"),
            ("CREATE INDEX IF NOT EXISTS idx_staff_profession ON hospital_staff(profession) WHERE is_deleted = false;", "Staff profession"),
            
            # Payment indexes
            ("CREATE INDEX IF NOT EXISTS idx_payment_invoice ON hospital_payment(invoice_id) WHERE is_deleted = false;", "Payment invoice"),
            ("CREATE INDEX IF NOT EXISTS idx_payment_date ON hospital_payment(payment_date DESC) WHERE is_deleted = false;", "Payment date"),
        ]
        
        created = 0
        errors = 0
        
        for index_sql, description in indexes:
            try:
                cursor.execute(index_sql)
                self.stdout.write(self.style.SUCCESS(f'  ✅ Created: {description}'))
                created += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ❌ Failed: {description} - {str(e)}'))
                errors += 1
        
        self.stdout.write(f'\n📊 Index creation complete: {created} created, {errors} errors')

    def run_vacuum_analyze(self, cursor):
        """Run VACUUM ANALYZE on all tables"""
        self.stdout.write('\n🧹 Running VACUUM ANALYZE...')
        
        try:
            # Get all tables
            cursor.execute("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename LIKE 'hospital_%'
                ORDER BY tablename;
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                try:
                    self.stdout.write(f'  Vacuuming {table}...', ending='')
                    cursor.execute(f'VACUUM ANALYZE {table};')
                    self.stdout.write(self.style.SUCCESS(' ✅'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f' ❌ {str(e)}'))
            
            self.stdout.write(self.style.SUCCESS('\n✅ VACUUM ANALYZE complete'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ VACUUM ANALYZE failed: {str(e)}'))

    def update_statistics(self, cursor):
        """Update query planner statistics"""
        self.stdout.write('\n📊 Updating query planner statistics...')
        
        try:
            cursor.execute('ANALYZE;')
            self.stdout.write(self.style.SUCCESS('✅ Statistics updated'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Statistics update failed: {str(e)}'))
