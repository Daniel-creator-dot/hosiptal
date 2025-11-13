"""
Management command to set up blood bank system
Creates all necessary database tables
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Set up blood bank system tables'

    def handle(self, *args, **options):
        self.stdout.write('Setting up Blood Bank & Transfusion Management System...')
        
        with connection.cursor() as cursor:
            # Create BloodDonor table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_blooddonor (
                    id TEXT PRIMARY KEY,
                    created DATETIME NOT NULL,
                    modified DATETIME NOT NULL,
                    is_deleted BOOLEAN NOT NULL DEFAULT 0,
                    patient_id TEXT,
                    donor_id TEXT UNIQUE NOT NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    date_of_birth DATE NOT NULL,
                    gender TEXT NOT NULL,
                    phone_number TEXT,
                    email TEXT,
                    address TEXT,
                    blood_group TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    is_regular_donor BOOLEAN NOT NULL DEFAULT 0,
                    last_donation_date DATE,
                    total_donations INTEGER NOT NULL DEFAULT 0,
                    is_eligible BOOLEAN NOT NULL DEFAULT 1,
                    ineligibility_reason TEXT,
                    weight_kg DECIMAL(5,2),
                    hemoglobin_level DECIMAL(4,1),
                    notes TEXT,
                    FOREIGN KEY (patient_id) REFERENCES hospital_patient(id)
                )
            """)
            
            # Create BloodDonation table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_blooddonation (
                    id TEXT PRIMARY KEY,
                    created DATETIME NOT NULL,
                    modified DATETIME NOT NULL,
                    is_deleted BOOLEAN NOT NULL DEFAULT 0,
                    donor_id TEXT NOT NULL,
                    donation_date DATETIME NOT NULL,
                    donation_number TEXT UNIQUE NOT NULL,
                    pre_donation_hemoglobin DECIMAL(4,1) NOT NULL,
                    pre_donation_weight DECIMAL(5,2) NOT NULL,
                    pre_donation_bp_systolic INTEGER NOT NULL,
                    pre_donation_bp_diastolic INTEGER NOT NULL,
                    pre_donation_temperature DECIMAL(4,1) NOT NULL,
                    blood_group TEXT NOT NULL,
                    volume_collected_ml INTEGER NOT NULL DEFAULT 450,
                    collected_by_id TEXT,
                    testing_status TEXT NOT NULL DEFAULT 'pending',
                    hiv_tested BOOLEAN NOT NULL DEFAULT 0,
                    hiv_result TEXT,
                    hbv_tested BOOLEAN NOT NULL DEFAULT 0,
                    hbv_result TEXT,
                    hcv_tested BOOLEAN NOT NULL DEFAULT 0,
                    hcv_result TEXT,
                    syphilis_tested BOOLEAN NOT NULL DEFAULT 0,
                    syphilis_result TEXT,
                    malaria_tested BOOLEAN NOT NULL DEFAULT 0,
                    malaria_result TEXT,
                    is_approved BOOLEAN NOT NULL DEFAULT 0,
                    approved_by_id TEXT,
                    approved_at DATETIME,
                    rejection_reason TEXT,
                    notes TEXT,
                    FOREIGN KEY (donor_id) REFERENCES hospital_blooddonor(id),
                    FOREIGN KEY (collected_by_id) REFERENCES hospital_staff(id),
                    FOREIGN KEY (approved_by_id) REFERENCES hospital_staff(id)
                )
            """)
            
            # Create BloodInventory table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_bloodinventory (
                    id TEXT PRIMARY KEY,
                    created DATETIME NOT NULL,
                    modified DATETIME NOT NULL,
                    is_deleted BOOLEAN NOT NULL DEFAULT 0,
                    unit_number TEXT UNIQUE NOT NULL,
                    donation_id TEXT NOT NULL,
                    blood_group TEXT NOT NULL,
                    component_type TEXT NOT NULL DEFAULT 'whole_blood',
                    volume_ml INTEGER NOT NULL,
                    collection_date DATE NOT NULL,
                    expiry_date DATE NOT NULL,
                    storage_location TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'available',
                    temperature_log TEXT,
                    FOREIGN KEY (donation_id) REFERENCES hospital_blooddonation(id)
                )
            """)
            
            # Create TransfusionRequest table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_transfusionrequest (
                    id TEXT PRIMARY KEY,
                    created DATETIME NOT NULL,
                    modified DATETIME NOT NULL,
                    is_deleted BOOLEAN NOT NULL DEFAULT 0,
                    request_number TEXT UNIQUE NOT NULL,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT NOT NULL,
                    requested_by_id TEXT,
                    requested_at DATETIME NOT NULL,
                    patient_blood_group TEXT NOT NULL,
                    component_type TEXT NOT NULL,
                    units_requested INTEGER NOT NULL,
                    indication TEXT NOT NULL,
                    clinical_notes TEXT NOT NULL,
                    pre_transfusion_hb DECIMAL(4,1),
                    pre_transfusion_bp_systolic INTEGER,
                    pre_transfusion_bp_diastolic INTEGER,
                    urgency TEXT NOT NULL DEFAULT 'routine',
                    status TEXT NOT NULL DEFAULT 'pending',
                    processed_by_id TEXT,
                    processed_at DATETIME,
                    crossmatch_completed BOOLEAN NOT NULL DEFAULT 0,
                    crossmatch_compatible BOOLEAN NOT NULL DEFAULT 0,
                    crossmatch_notes TEXT,
                    is_approved BOOLEAN NOT NULL DEFAULT 0,
                    approved_by_id TEXT,
                    approved_at DATETIME,
                    rejection_reason TEXT,
                    FOREIGN KEY (patient_id) REFERENCES hospital_patient(id),
                    FOREIGN KEY (encounter_id) REFERENCES hospital_encounter(id),
                    FOREIGN KEY (requested_by_id) REFERENCES hospital_staff(id),
                    FOREIGN KEY (processed_by_id) REFERENCES hospital_staff(id),
                    FOREIGN KEY (approved_by_id) REFERENCES hospital_staff(id)
                )
            """)
            
            # Create BloodCrossmatch table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_bloodcrossmatch (
                    id TEXT PRIMARY KEY,
                    created DATETIME NOT NULL,
                    modified DATETIME NOT NULL,
                    is_deleted BOOLEAN NOT NULL DEFAULT 0,
                    transfusion_request_id TEXT NOT NULL,
                    blood_unit_id TEXT NOT NULL,
                    tested_by_id TEXT,
                    tested_at DATETIME NOT NULL,
                    major_crossmatch_result TEXT NOT NULL,
                    minor_crossmatch_result TEXT,
                    antibody_screen TEXT,
                    is_compatible BOOLEAN NOT NULL DEFAULT 0,
                    notes TEXT,
                    FOREIGN KEY (transfusion_request_id) REFERENCES hospital_transfusionrequest(id),
                    FOREIGN KEY (blood_unit_id) REFERENCES hospital_bloodinventory(id),
                    FOREIGN KEY (tested_by_id) REFERENCES hospital_staff(id)
                )
            """)
            
            # Create BloodTransfusion table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_bloodtransfusion (
                    id TEXT PRIMARY KEY,
                    created DATETIME NOT NULL,
                    modified DATETIME NOT NULL,
                    is_deleted BOOLEAN NOT NULL DEFAULT 0,
                    transfusion_request_id TEXT NOT NULL,
                    blood_unit_id TEXT NOT NULL,
                    started_at DATETIME NOT NULL,
                    completed_at DATETIME,
                    administered_by_id TEXT,
                    volume_transfused_ml INTEGER NOT NULL,
                    pre_vital_bp_systolic INTEGER NOT NULL,
                    pre_vital_bp_diastolic INTEGER NOT NULL,
                    pre_vital_temperature DECIMAL(4,1) NOT NULL,
                    pre_vital_pulse INTEGER NOT NULL,
                    pre_vital_respiratory_rate INTEGER NOT NULL,
                    post_vital_bp_systolic INTEGER,
                    post_vital_bp_diastolic INTEGER,
                    post_vital_temperature DECIMAL(4,1),
                    post_vital_pulse INTEGER,
                    post_vital_respiratory_rate INTEGER,
                    transfusion_rate TEXT,
                    monitoring_frequency TEXT NOT NULL DEFAULT 'Every 15 minutes',
                    adverse_reaction_occurred BOOLEAN NOT NULL DEFAULT 0,
                    reaction_type TEXT,
                    reaction_severity TEXT,
                    reaction_management TEXT,
                    status TEXT NOT NULL DEFAULT 'in_progress',
                    notes TEXT,
                    FOREIGN KEY (transfusion_request_id) REFERENCES hospital_transfusionrequest(id),
                    FOREIGN KEY (blood_unit_id) REFERENCES hospital_bloodinventory(id),
                    FOREIGN KEY (administered_by_id) REFERENCES hospital_staff(id)
                )
            """)
            
            # Create BloodCompatibilityMatrix table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_bloodcompatibilitymatrix (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient_blood_group TEXT NOT NULL,
                    component_type TEXT NOT NULL,
                    compatible_donor_groups TEXT NOT NULL,
                    UNIQUE(recipient_blood_group, component_type)
                )
            """)
            
            self.stdout.write(self.style.SUCCESS('[OK] Blood bank tables created successfully!'))
            
            # Insert default compatibility matrix
            self.stdout.write('Setting up blood compatibility matrix...')
            
            compatibility_data = [
                ('O-', 'whole_blood', '["O-"]'),
                ('O+', 'whole_blood', '["O-", "O+"]'),
                ('A-', 'whole_blood', '["O-", "A-"]'),
                ('A+', 'whole_blood', '["O-", "O+", "A-", "A+"]'),
                ('B-', 'whole_blood', '["O-", "B-"]'),
                ('B+', 'whole_blood', '["O-", "O+", "B-", "B+"]'),
                ('AB-', 'whole_blood', '["O-", "A-", "B-", "AB-"]'),
                ('AB+', 'whole_blood', '["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]'),
                ('O-', 'packed_rbc', '["O-"]'),
                ('O+', 'packed_rbc', '["O-", "O+"]'),
                ('A-', 'packed_rbc', '["O-", "A-"]'),
                ('A+', 'packed_rbc', '["O-", "O+", "A-", "A+"]'),
                ('B-', 'packed_rbc', '["O-", "B-"]'),
                ('B+', 'packed_rbc', '["O-", "O+", "B-", "B+"]'),
                ('AB-', 'packed_rbc', '["O-", "A-", "B-", "AB-"]'),
                ('AB+', 'packed_rbc', '["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]'),
            ]
            
            # Use ORM for compatibility matrix to avoid SQL parameter issues
            from hospital.models_blood_bank import BloodCompatibilityMatrix
            import json
            
            for recipient, component, compatible_str in compatibility_data:
                compatible_list = json.loads(compatible_str)
                BloodCompatibilityMatrix.objects.get_or_create(
                    recipient_blood_group=recipient,
                    component_type=component,
                    defaults={'compatible_donor_groups': compatible_list}
                )
            
            self.stdout.write(self.style.SUCCESS('[OK] Blood compatibility matrix set up!'))
            self.stdout.write(self.style.SUCCESS('\n[SUCCESS] Blood Bank System is ready to use!'))
            self.stdout.write(self.style.SUCCESS('Access it at: http://127.0.0.1:8000/hms/blood-bank/'))

