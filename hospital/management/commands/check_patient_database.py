"""
Check Patient Database - Verify all patient data sources
"""
from django.core.management.base import BaseCommand
from django.db import connection
from hospital.models import Patient
from django.db.models import Q


class Command(BaseCommand):
    help = 'Check patient database and verify all patient data sources'

    def handle(self, *args, **options):
        self.stdout.write("="*70)
        self.stdout.write("   PATIENT DATABASE VERIFICATION")
        self.stdout.write("="*70)
        self.stdout.write("")
        
        # Check database tables
        self.check_database_tables()
        
        # Check Django Patient model
        django_count = self.check_django_patients()
        
        # Check LegacyPatient model
        legacy_count = self.check_legacy_patients()
        
        # Check patient_data table
        patient_data_count = self.check_patient_data_table()
        
        # Summary
        self.stdout.write("")
        self.stdout.write("="*70)
        self.stdout.write("   SUMMARY")
        self.stdout.write("="*70)
        self.stdout.write("")
        self.stdout.write(f"📊 Django Patient Model:     {django_count:,} patients")
        self.stdout.write(f"📊 LegacyPatient Model:      {legacy_count:,} patients")
        self.stdout.write(f"📊 patient_data Table:      {patient_data_count:,} patients")
        self.stdout.write("")
        self.stdout.write(f"📊 TOTAL:                    {django_count + legacy_count + patient_data_count:,} patient records")
        self.stdout.write("")
        
        if django_count == 0 and legacy_count == 0 and patient_data_count == 0:
            self.stdout.write(self.style.WARNING("⚠️  WARNING: No patients found in any database!"))
            self.stdout.write("")
            self.stdout.write("To add patients:")
            self.stdout.write("  1. Go to: http://127.0.0.1:8000/hms/patients/new/")
            self.stdout.write("  2. Or use Django admin: http://127.0.0.1:8000/admin/hospital/patient/")
            self.stdout.write("")
        elif django_count == 0:
            self.stdout.write(self.style.SUCCESS("💡 TIP: No new patients found. Legacy patients are available."))
            self.stdout.write("   Use the 'Source' filter on the patient list page to view legacy patients.")
            self.stdout.write("")
        else:
            self.stdout.write(self.style.SUCCESS("✅ Patient database is populated!"))

    def check_database_tables(self):
        """Check what patient-related tables exist"""
        self.stdout.write("="*70)
        self.stdout.write("   PATIENT DATABASE TABLES CHECK")
        self.stdout.write("="*70)
        self.stdout.write("")
        
        with connection.cursor() as cursor:
            vendor = connection.vendor
            self.stdout.write(f"Database: {vendor}")
            self.stdout.write("")
            
            if vendor == 'postgresql':
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name LIKE '%patient%'
                    ORDER BY table_name
                """)
            else:
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' 
                    AND name LIKE '%patient%'
                    ORDER BY name
                """)
            
            tables = [row[0] for row in cursor.fetchall()]
            
            if not tables:
                self.stdout.write(self.style.WARNING("❌ No patient tables found!"))
                return []
            
            self.stdout.write(self.style.SUCCESS(f"✅ Found {len(tables)} patient-related tables:"))
            self.stdout.write("")
            
            for table in tables:
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                    count = cursor.fetchone()[0]
                    self.stdout.write(f"📊 {table}: {count:,} rows")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"   ⚠️  Error checking {table}: {str(e)}"))
            
            return tables

    def check_django_patients(self):
        """Check Django Patient model"""
        self.stdout.write("")
        self.stdout.write("="*70)
        self.stdout.write("   DJANGO PATIENT MODEL (hospital.models.Patient)")
        self.stdout.write("="*70)
        self.stdout.write("")
        
        try:
            total = Patient.objects.filter(is_deleted=False).count()
            self.stdout.write(self.style.SUCCESS(f"✅ Total Patients (not deleted): {total:,}"))
            
            with_phone = Patient.objects.filter(
                is_deleted=False
            ).exclude(
                Q(phone_number__isnull=True) | Q(phone_number='')
            ).count()
            self.stdout.write(f"   📱 With phone numbers: {with_phone:,}")
            
            recent = Patient.objects.filter(is_deleted=False).order_by('-created')[:5]
            if recent:
                self.stdout.write("")
                self.stdout.write("   Recent Patients:")
                for p in recent:
                    self.stdout.write(f"      - {p.full_name} ({p.mrn}) - Created: {p.created.date()}")
            else:
                self.stdout.write("")
                self.stdout.write(self.style.WARNING("   ⚠️  No patients found in database"))
            
            return total
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {str(e)}"))
            return 0

    def check_legacy_patients(self):
        """Check LegacyPatient model"""
        self.stdout.write("")
        self.stdout.write("="*70)
        self.stdout.write("   LEGACY PATIENT MODEL (hospital.models_legacy_patients.LegacyPatient)")
        self.stdout.write("="*70)
        self.stdout.write("")
        
        try:
            from hospital.models_legacy_patients import LegacyPatient
            
            total = LegacyPatient.objects.count()
            self.stdout.write(self.style.SUCCESS(f"✅ Total Legacy Patients: {total:,}"))
            
            if total > 0:
                sample = LegacyPatient.objects.all()[:5]
                self.stdout.write("")
                self.stdout.write("   Sample Legacy Patients:")
                for p in sample:
                    self.stdout.write(f"      - {p.full_name} (PID: {p.pid}, MRN: {p.mrn_display})")
            else:
                self.stdout.write("")
                self.stdout.write(self.style.WARNING("   ⚠️  No legacy patients found"))
            
            return total
            
        except ImportError:
            self.stdout.write(self.style.WARNING("   ⚠️  LegacyPatient model not found"))
            return 0
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠️  Error: {str(e)}"))
            try:
                with connection.cursor() as cursor:
                    vendor = connection.vendor
                    if vendor == 'postgresql':
                        cursor.execute("SELECT COUNT(*) FROM hospital_legacypatient")
                    else:
                        cursor.execute("SELECT COUNT(*) FROM hospital_legacypatient")
                    count = cursor.fetchone()[0]
                    self.stdout.write(f"   📊 Direct table check: {count:,} rows in hospital_legacypatient")
                    return count
            except:
                return 0

    def check_patient_data_table(self):
        """Check patient_data table (legacy SQL table)"""
        self.stdout.write("")
        self.stdout.write("="*70)
        self.stdout.write("   LEGACY PATIENT_DATA TABLE (Direct SQL)")
        self.stdout.write("="*70)
        self.stdout.write("")
        
        try:
            with connection.cursor() as cursor:
                vendor = connection.vendor
                if vendor == 'postgresql':
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = 'patient_data'
                        )
                    """)
                    exists = cursor.fetchone()[0]
                    
                    if exists:
                        cursor.execute("SELECT COUNT(*) FROM patient_data")
                        count = cursor.fetchone()[0]
                        self.stdout.write(self.style.SUCCESS(f"✅ patient_data table exists: {count:,} rows"))
                        
                        if count > 0:
                            cursor.execute("SELECT fname, lname, DOB, sex FROM patient_data LIMIT 5")
                            samples = cursor.fetchall()
                            self.stdout.write("")
                            self.stdout.write("   Sample Records:")
                            for s in samples:
                                self.stdout.write(f"      - {s[0]} {s[1]} (DOB: {s[2]}, Sex: {s[3]})")
                    else:
                        self.stdout.write(self.style.WARNING("   ⚠️  patient_data table does not exist"))
                        return 0
                else:
                    cursor.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name='patient_data'
                    """)
                    if cursor.fetchone():
                        cursor.execute("SELECT COUNT(*) FROM patient_data")
                        count = cursor.fetchone()[0]
                        self.stdout.write(self.style.SUCCESS(f"✅ patient_data table exists: {count:,} rows"))
                        
                        if count > 0:
                            cursor.execute("SELECT fname, lname, DOB, sex FROM patient_data LIMIT 5")
                            samples = cursor.fetchall()
                            self.stdout.write("")
                            self.stdout.write("   Sample Records:")
                            for s in samples:
                                self.stdout.write(f"      - {s[0]} {s[1]} (DOB: {s[2]}, Sex: {s[3]})")
                    else:
                        self.stdout.write(self.style.WARNING("   ⚠️  patient_data table does not exist"))
                        return 0
                
                return count if 'count' in locals() else 0
                
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠️  Error checking patient_data: {str(e)}"))
            return 0


