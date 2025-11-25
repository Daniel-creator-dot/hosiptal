"""
Check Database Sync Status
Verifies all database records are present, especially client/patient data
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.apps import apps
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Check database sync status and verify all records are present'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed breakdown by model',
        )
        parser.add_argument(
            '--recent-only',
            action='store_true',
            help='Only check records created in the last 7 days',
        )

    def handle(self, *args, **options):
        detailed = options['detailed']
        recent_only = options['recent_only']
        
        self.stdout.write(self.style.SUCCESS('\n=== Database Sync Status Check ===\n'))
        
        # Get all models from hospital app
        hospital_models = []
        for model in apps.get_models():
            if model._meta.app_label == 'hospital':
                hospital_models.append(model)
        
        # Key models to check (especially client/patient related)
        key_models = [
            'Patient',
            'Encounter',
            'Invoice',
            'PaymentReceipt',
            'Appointment',
            'LabTest',
            'LabResult',
            'Prescription',
            'PharmacyStock',
            'Staff',
            'Department',
            'Ward',
            'Bed',
            'Admission',
            'Order',
            'MedicalRecord',
            'VitalSign',
            'QueueEntry',
            'Queue',
            'CorporateAccount',
            'InsuranceCompany',
        ]
        
        # Filter to key models if not detailed
        if not detailed:
            models_to_check = [m for m in hospital_models if m.__name__ in key_models]
        else:
            models_to_check = hospital_models
        
        # Sort by name
        models_to_check.sort(key=lambda x: x.__name__)
        
        total_records = 0
        total_models = 0
        issues = []
        
        self.stdout.write(f"{'Model':<40} {'Records':<15} {'Status':<15}")
        self.stdout.write("-" * 70)
        
        for model in models_to_check:
            try:
                # Check if table exists
                with connection.cursor() as cursor:
                    table_name = model._meta.db_table
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = %s
                        );
                    """, [table_name])
                    table_exists = cursor.fetchone()[0]
                    
                    if not table_exists:
                        self.stdout.write(
                            self.style.WARNING(
                                f"{model.__name__:<40} {'N/A':<15} {'TABLE MISSING':<15}"
                            )
                        )
                        issues.append(f"Table missing: {model.__name__} ({table_name})")
                        continue
                
                # Count records
                # Check if model has is_deleted field
                has_is_deleted = hasattr(model, '_meta') and 'is_deleted' in [f.name for f in model._meta.get_fields()]
                
                if recent_only:
                    # Check records from last 7 days
                    if hasattr(model, 'created'):
                        qs = model.objects.filter(created__gte=timezone.now() - timedelta(days=7))
                        if has_is_deleted:
                            qs = qs.filter(is_deleted=False)
                        count = qs.count()
                    else:
                        qs = model.objects.all()
                        if has_is_deleted:
                            qs = qs.filter(is_deleted=False)
                        count = qs.count()
                else:
                    qs = model.objects.all()
                    if has_is_deleted:
                        qs = qs.filter(is_deleted=False)
                    count = qs.count()
                
                total_records += count
                total_models += 1
                
                # Status indicator
                if count == 0:
                    status = self.style.WARNING("EMPTY")
                    if model.__name__ in key_models:
                        issues.append(f"No records in key model: {model.__name__}")
                else:
                    status = self.style.SUCCESS("OK")
                
                self.stdout.write(f"{model.__name__:<40} {count:<15} {status}")
                
                # Show deleted count if any
                if has_is_deleted:
                    deleted_count = model.objects.filter(is_deleted=True).count()
                    if deleted_count > 0:
                        self.stdout.write(
                            f"  └─ Deleted: {deleted_count}"
                        )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"{model.__name__:<40} {'ERROR':<15} {str(e)[:30]:<15}"
                    )
                )
                issues.append(f"Error checking {model.__name__}: {str(e)}")
                logger.error(f"Error checking model {model.__name__}: {e}", exc_info=True)
        
        # Summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(f"\nTotal Models Checked: {total_models}")
        self.stdout.write(f"Total Records: {total_records:,}")
        
        # Check for pending migrations
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("\nChecking for pending migrations...")
        try:
            from django.core.management import call_command
            from io import StringIO
            output = StringIO()
            call_command('showmigrations', '--list', stdout=output)
            migrations_output = output.getvalue()
            
            pending = [line for line in migrations_output.split('\n') if '[ ]' in line]
            if pending:
                self.stdout.write(self.style.WARNING(f"\n⚠ Found {len(pending)} pending migrations:"))
                for line in pending[:10]:  # Show first 10
                    self.stdout.write(f"  {line.strip()}")
                if len(pending) > 10:
                    self.stdout.write(f"  ... and {len(pending) - 10} more")
                issues.append(f"{len(pending)} pending migrations")
            else:
                self.stdout.write(self.style.SUCCESS("\n✓ All migrations are applied"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\nError checking migrations: {e}"))
            issues.append(f"Error checking migrations: {str(e)}")
        
        # Check database connection
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("\nDatabase Connection Status:")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()[0]
                self.stdout.write(self.style.SUCCESS(f"✓ Connected to: {connection.settings_dict.get('NAME')}"))
                self.stdout.write(f"  PostgreSQL Version: {version.split(',')[0]}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Database connection error: {e}"))
            issues.append(f"Database connection error: {str(e)}")
        
        # Final summary
        self.stdout.write("\n" + "=" * 70)
        if issues:
            self.stdout.write(self.style.WARNING(f"\n⚠ Found {len(issues)} potential issues:"))
            for issue in issues:
                self.stdout.write(f"  • {issue}")
            self.stdout.write("\n" + self.style.WARNING("Please review and address these issues."))
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ Database sync check completed successfully!"))
            self.stdout.write("  All models are accessible and migrations are up to date.")
        
        self.stdout.write("\n")

