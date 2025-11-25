"""
Management command to set up medical records system
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Set up medical records system tables'

    def handle(self, *args, **options):
        self.stdout.write('Setting up Medical Records System...')
        
        with connection.cursor() as cursor:
            # Create MedicalRecordSummary table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_medicalrecordsummary (
                    id TEXT PRIMARY KEY,
                    created DATETIME NOT NULL,
                    modified DATETIME NOT NULL,
                    is_deleted BOOLEAN NOT NULL DEFAULT 0,
                    patient_id TEXT UNIQUE NOT NULL,
                    record_number TEXT UNIQUE NOT NULL,
                    created_date DATE NOT NULL,
                    last_updated DATETIME NOT NULL,
                    total_visits INTEGER DEFAULT 0,
                    total_admissions INTEGER DEFAULT 0,
                    total_emergency_visits INTEGER DEFAULT 0,
                    total_prescriptions INTEGER DEFAULT 0,
                    total_lab_tests INTEGER DEFAULT 0,
                    total_imaging_studies INTEGER DEFAULT 0,
                    total_procedures INTEGER DEFAULT 0,
                    last_visit_date DATE,
                    last_diagnosis TEXT,
                    current_medications TEXT,
                    chronic_conditions TEXT,
                    allergies TEXT,
                    blood_group TEXT,
                    last_weight_kg DECIMAL(5,2),
                    last_height_cm DECIMAL(5,2),
                    last_bp_systolic INTEGER,
                    last_bp_diastolic INTEGER,
                    family_medical_history TEXT,
                    smoking_status TEXT,
                    alcohol_use TEXT,
                    special_notes TEXT,
                    FOREIGN KEY (patient_id) REFERENCES hospital_patient(id)
                )
            """)
            
            # Create VisitRecord table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_visitrecord (
                    id TEXT PRIMARY KEY,
                    created DATETIME NOT NULL,
                    modified DATETIME NOT NULL,
                    is_deleted BOOLEAN NOT NULL DEFAULT 0,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT UNIQUE NOT NULL,
                    visit_number TEXT UNIQUE NOT NULL,
                    visit_date DATE NOT NULL,
                    visit_time TIME NOT NULL,
                    visit_type TEXT NOT NULL,
                    chief_complaint TEXT NOT NULL,
                    final_diagnosis TEXT NOT NULL,
                    treatment_given TEXT,
                    medications_prescribed TEXT,
                    procedures_performed TEXT,
                    lab_tests_ordered TEXT,
                    imaging_ordered TEXT,
                    clinical_summary TEXT,
                    disposition TEXT,
                    follow_up_required BOOLEAN DEFAULT 0,
                    follow_up_date DATE,
                    follow_up_instructions TEXT,
                    provider_id TEXT,
                    duration_minutes INTEGER,
                    FOREIGN KEY (patient_id) REFERENCES hospital_patient(id),
                    FOREIGN KEY (encounter_id) REFERENCES hospital_encounter(id),
                    FOREIGN KEY (provider_id) REFERENCES hospital_staff(id)
                )
            """)
            
            # Create PatientDocument table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_patientdocument (
                    id TEXT PRIMARY KEY,
                    created DATETIME NOT NULL,
                    modified DATETIME NOT NULL,
                    is_deleted BOOLEAN NOT NULL DEFAULT 0,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT,
                    document_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    file TEXT,
                    document_date DATE NOT NULL,
                    uploaded_by_id TEXT,
                    file_size INTEGER,
                    file_type TEXT,
                    is_confidential BOOLEAN DEFAULT 0,
                    FOREIGN KEY (patient_id) REFERENCES hospital_patient(id),
                    FOREIGN KEY (encounter_id) REFERENCES hospital_encounter(id),
                    FOREIGN KEY (uploaded_by_id) REFERENCES hospital_staff(id)
                )
            """)
            
            # Create MedicalRecordAccess table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_medicalrecordaccess (
                    id TEXT PRIMARY KEY,
                    created DATETIME NOT NULL,
                    modified DATETIME NOT NULL,
                    is_deleted BOOLEAN NOT NULL DEFAULT 0,
                    patient_id TEXT NOT NULL,
                    accessed_by_id TEXT NOT NULL,
                    access_time DATETIME NOT NULL,
                    access_type TEXT NOT NULL,
                    section_accessed TEXT,
                    ip_address TEXT,
                    reason TEXT,
                    FOREIGN KEY (patient_id) REFERENCES hospital_patient(id),
                    FOREIGN KEY (accessed_by_id) REFERENCES hospital_staff(id)
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_medicalrecord_patient 
                ON hospital_medicalrecordsummary(patient_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_visitrecord_patient_date 
                ON hospital_visitrecord(patient_id, visit_date DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_patient 
                ON hospital_patientdocument(patient_id, document_date DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_access_patient_time 
                ON hospital_medicalrecordaccess(patient_id, access_time DESC)
            """)
            
            self.stdout.write(self.style.SUCCESS('[OK] Medical records tables created successfully!'))
            self.stdout.write(self.style.SUCCESS('\n[SUCCESS] Medical Records System is ready!'))
            self.stdout.write(self.style.SUCCESS('Access it at: http://127.0.0.1:8000/hms/medical-records/'))





















