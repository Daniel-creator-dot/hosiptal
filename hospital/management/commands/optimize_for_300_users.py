"""
Management command to optimize database for 300+ concurrent users
Creates performance indexes and optimizes database settings
"""
from django.core.management.base import BaseCommand
from django.db import connection
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Optimize database for 300+ concurrent users - creates indexes and optimizes settings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-indexes',
            action='store_true',
            help='Skip creating indexes (if already created)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Optimizing database for 300+ concurrent users...'))
        
        skip_indexes = options.get('skip_indexes', False)
        
        with connection.cursor() as cursor:
            # Check database type
            db_vendor = connection.vendor
            
            if db_vendor == 'postgresql':
                self.optimize_postgresql(cursor, skip_indexes)
            elif db_vendor == 'sqlite':
                self.optimize_sqlite(cursor, skip_indexes)
            else:
                self.stdout.write(self.style.WARNING(f'Database vendor {db_vendor} not specifically optimized'))
        
        self.stdout.write(self.style.SUCCESS('✅ Database optimization complete!'))

    def optimize_postgresql(self, cursor, skip_indexes):
        """Optimize PostgreSQL database"""
        self.stdout.write('Optimizing PostgreSQL database...')
        
        if not skip_indexes:
            # Create performance indexes
            indexes = [
                # Patient indexes
                ("CREATE INDEX IF NOT EXISTS idx_patient_active ON hospital_patient(is_deleted, is_active) WHERE is_deleted = false;",
                 "DROP INDEX IF EXISTS idx_patient_active;"),
                
                # Encounter indexes
                ("CREATE INDEX IF NOT EXISTS idx_encounter_active_status ON hospital_encounter(is_deleted, status) WHERE is_deleted = false;",
                 "DROP INDEX IF EXISTS idx_encounter_active_status;"),
                ("CREATE INDEX IF NOT EXISTS idx_encounter_patient_active ON hospital_encounter(patient_id, is_deleted, status) WHERE is_deleted = false;",
                 "DROP INDEX IF EXISTS idx_encounter_patient_active;"),
                
                # Inventory indexes
                ("CREATE INDEX IF NOT EXISTS idx_inventory_active_store ON hospital_inventoryitem(is_deleted, is_active, store_id) WHERE is_deleted = false AND is_active = true;",
                 "DROP INDEX IF EXISTS idx_inventory_active_store;"),
                ("CREATE INDEX IF NOT EXISTS idx_inventory_drug ON hospital_inventoryitem(drug_id, is_deleted) WHERE drug_id IS NOT NULL AND is_deleted = false;",
                 "DROP INDEX IF EXISTS idx_inventory_drug;"),
                
                # Drug indexes
                ("CREATE INDEX IF NOT EXISTS idx_drug_active_category ON hospital_drug(is_deleted, is_active, category) WHERE is_deleted = false AND is_active = true;",
                 "DROP INDEX IF EXISTS idx_drug_active_category;"),
                
                # Order indexes
                ("CREATE INDEX IF NOT EXISTS idx_order_encounter_status ON hospital_order(encounter_id, status, is_deleted) WHERE is_deleted = false;",
                 "DROP INDEX IF EXISTS idx_order_encounter_status;"),
                
                # Prescription indexes
                ("CREATE INDEX IF NOT EXISTS idx_prescription_order_active ON hospital_prescription(order_id, is_deleted) WHERE is_deleted = false;",
                 "DROP INDEX IF EXISTS idx_prescription_order_active;"),
                
                # Lab result indexes
                ("CREATE INDEX IF NOT EXISTS idx_labresult_status_active ON hospital_labresult(status, is_deleted) WHERE is_deleted = false;",
                 "DROP INDEX IF EXISTS idx_labresult_status_active;"),
                
                # Appointment indexes
                ("CREATE INDEX IF NOT EXISTS idx_appointment_date_status ON hospital_appointment(appointment_date, status, is_deleted) WHERE is_deleted = false;",
                 "DROP INDEX IF EXISTS idx_appointment_date_status;"),
            ]
            
            for create_sql, drop_sql in indexes:
                try:
                    cursor.execute(create_sql)
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Created index'))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  ⚠ Index creation warning: {e}'))
        
        # Analyze tables for better query planning
        try:
            cursor.execute("ANALYZE;")
            self.stdout.write(self.style.SUCCESS('  ✓ Analyzed tables'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠ ANALYZE warning: {e}'))

    def optimize_sqlite(self, cursor, skip_indexes):
        """Optimize SQLite database"""
        self.stdout.write('Optimizing SQLite database...')
        
        # SQLite optimizations
        optimizations = [
            ("PRAGMA journal_mode=WAL;", "WAL mode"),
            ("PRAGMA cache_size=-131072;", "128MB cache"),
            ("PRAGMA synchronous=NORMAL;", "Normal sync mode"),
            ("PRAGMA temp_store=MEMORY;", "Memory temp storage"),
            ("PRAGMA page_size=8192;", "8KB page size"),
        ]
        
        for sql, description in optimizations:
            try:
                cursor.execute(sql)
                self.stdout.write(self.style.SUCCESS(f'  ✓ {description}'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  ⚠ {description} warning: {e}'))
        
        if not skip_indexes:
            # Create performance indexes for SQLite
            indexes = [
                # Patient indexes
                ("CREATE INDEX IF NOT EXISTS idx_patient_active ON hospital_patient(is_deleted, is_active);",
                 "DROP INDEX IF EXISTS idx_patient_active;"),
                
                # Encounter indexes
                ("CREATE INDEX IF NOT EXISTS idx_encounter_active_status ON hospital_encounter(is_deleted, status);",
                 "DROP INDEX IF EXISTS idx_encounter_active_status;"),
                ("CREATE INDEX IF NOT EXISTS idx_encounter_patient_active ON hospital_encounter(patient_id, is_deleted, status);",
                 "DROP INDEX IF EXISTS idx_encounter_patient_active;"),
                
                # Inventory indexes
                ("CREATE INDEX IF NOT EXISTS idx_inventory_active_store ON hospital_inventoryitem(is_deleted, is_active, store_id);",
                 "DROP INDEX IF EXISTS idx_inventory_active_store;"),
                ("CREATE INDEX IF NOT EXISTS idx_inventory_drug ON hospital_inventoryitem(drug_id, is_deleted);",
                 "DROP INDEX IF EXISTS idx_inventory_drug;"),
                
                # Drug indexes
                ("CREATE INDEX IF NOT EXISTS idx_drug_active_category ON hospital_drug(is_deleted, is_active, category);",
                 "DROP INDEX IF EXISTS idx_drug_active_category;"),
                
                # Order indexes
                ("CREATE INDEX IF NOT EXISTS idx_order_encounter_status ON hospital_order(encounter_id, status, is_deleted);",
                 "DROP INDEX IF EXISTS idx_order_encounter_status;"),
                
                # Prescription indexes
                ("CREATE INDEX IF NOT EXISTS idx_prescription_order_active ON hospital_prescription(order_id, is_deleted);",
                 "DROP INDEX IF EXISTS idx_prescription_order_active;"),
                
                # Lab result indexes
                ("CREATE INDEX IF NOT EXISTS idx_labresult_status_active ON hospital_labresult(status, is_deleted);",
                 "DROP INDEX IF EXISTS idx_labresult_status_active;"),
                
                # Appointment indexes
                ("CREATE INDEX IF NOT EXISTS idx_appointment_date_status ON hospital_appointment(appointment_date, status, is_deleted);",
                 "DROP INDEX IF EXISTS idx_appointment_date_status;"),
            ]
            
            for create_sql, drop_sql in indexes:
                try:
                    cursor.execute(create_sql)
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Created index'))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  ⚠ Index creation warning: {e}'))
        
        # VACUUM and ANALYZE for SQLite
        try:
            cursor.execute("VACUUM;")
            self.stdout.write(self.style.SUCCESS('  ✓ VACUUM completed'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠ VACUUM warning: {e}'))
        
        try:
            cursor.execute("ANALYZE;")
            self.stdout.write(self.style.SUCCESS('  ✓ ANALYZE completed'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠ ANALYZE warning: {e}'))
