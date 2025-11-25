#!/usr/bin/env python
"""
Restore Staff and Patient Data from SQLite Backup
"""
import os
import sys
import django
import sqlite3
from pathlib import Path

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import transaction
from django.contrib.auth import get_user_model
from hospital.models import Staff, Patient, Department, Payer
from decimal import Decimal
from datetime import datetime

User = get_user_model()

# Backup file path
BACKUP_FILE = 'backups/database/db_auto_backup_20251111_215301.sqlite3'

def restore_data():
    """Restore staff and patient data from SQLite backup"""
    print("=" * 70)
    print("RESTORING STAFF AND PATIENT DATA")
    print("=" * 70)
    print()
    
    # Check if backup exists
    if not os.path.exists(BACKUP_FILE):
        print(f"ERROR: Backup file not found: {BACKUP_FILE}")
        return False
    
    print(f"Found backup: {BACKUP_FILE}")
    print()
    
    # Connect to backup database
    try:
        backup_conn = sqlite3.connect(BACKUP_FILE)
        backup_cursor = backup_conn.cursor()
        
        # Check what tables exist
        backup_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in backup_cursor.fetchall()]
        
        print(f"Found {len(tables)} tables in backup")
        print()
        
        # Check for patient tables
        patient_tables = [t for t in tables if 'patient' in t.lower()]
        staff_tables = [t for t in tables if 'staff' in t.lower()]
        user_tables = [t for t in tables if 'user' in t.lower() or 'auth_user' in t.lower()]
        
        print(f"Patient tables: {len(patient_tables)}")
        print(f"Staff tables: {len(staff_tables)}")
        print(f"User tables: {len(user_tables)}")
        print()
        
        restored_patients = 0
        restored_staff = 0
        restored_users = 0
        
        # Restore Users
        if 'auth_user' in tables:
            print("Restoring users...")
            backup_cursor.execute("SELECT * FROM auth_user")
            users_data = backup_cursor.fetchall()
            
            # Get column names
            backup_cursor.execute("PRAGMA table_info(auth_user)")
            columns = [col[1] for col in backup_cursor.fetchall()]
            
            with transaction.atomic():
                for user_row in users_data:
                    user_dict = dict(zip(columns, user_row))
                    username = user_dict.get('username')
                    
                    if not username or username == 'AnonymousUser':
                        continue
                    
                    # Check if user already exists
                    if User.objects.filter(username=username).exists():
                        continue
                    
                    try:
                        user = User.objects.create(
                            username=username,
                            email=user_dict.get('email', ''),
                            first_name=user_dict.get('first_name', ''),
                            last_name=user_dict.get('last_name', ''),
                            is_staff=user_dict.get('is_staff', False),
                            is_superuser=user_dict.get('is_superuser', False),
                            is_active=user_dict.get('is_active', True),
                            date_joined=datetime.fromisoformat(user_dict['date_joined']) if user_dict.get('date_joined') else datetime.now(),
                        )
                        # Note: Password hash cannot be easily transferred, will need reset
                        restored_users += 1
                        print(f"  ✅ Restored user: {username}")
                    except Exception as e:
                        print(f"  ⚠️  Error restoring user {username}: {e}")
            
            print(f"Restored {restored_users} users")
            print()
        
        # Restore Patients
        patient_table = None
        for table in patient_tables:
            if table == 'patient' or table == 'hospital_patient':
                patient_table = table
                break
        
        if patient_table:
            print(f"Restoring patients from {patient_table}...")
            backup_cursor.execute(f"SELECT * FROM {patient_table}")
            patients_data = backup_cursor.fetchall()
            
            # Get column names
            backup_cursor.execute(f"PRAGMA table_info({patient_table})")
            columns = [col[1] for col in backup_cursor.fetchall()]
            
            with transaction.atomic():
                for patient_row in patients_data:
                    patient_dict = dict(zip(columns, patient_row))
                    
                    # Get or create patient
                    mrn = patient_dict.get('mrn') or patient_dict.get('patient_number') or patient_dict.get('id')
                    
                    if not mrn:
                        continue
                    
                    # Check if patient already exists
                    if Patient.objects.filter(mrn=str(mrn)).exists():
                        continue
                    
                    try:
                        # Parse date of birth
                        dob = patient_dict.get('date_of_birth')
                        if dob:
                            if isinstance(dob, str):
                                try:
                                    from dateutil import parser
                                    dob = parser.parse(dob).date()
                                except:
                                    dob = None
                        
                        patient = Patient.objects.create(
                            mrn=str(mrn),
                            first_name=patient_dict.get('first_name', '') or 'Unknown',
                            last_name=patient_dict.get('last_name', '') or 'Unknown',
                            middle_name=patient_dict.get('middle_name', ''),
                            date_of_birth=dob or datetime(2000, 1, 1).date(),
                            gender=patient_dict.get('gender', 'M'),
                            phone_number=patient_dict.get('phone_number', ''),
                            email=patient_dict.get('email', ''),
                            address=patient_dict.get('address', ''),
                            next_of_kin_name=patient_dict.get('emergency_contact_name', '') or patient_dict.get('next_of_kin_name', ''),
                            next_of_kin_phone=patient_dict.get('emergency_contact_phone', '') or patient_dict.get('next_of_kin_phone', ''),
                            blood_type=patient_dict.get('blood_group', '') or patient_dict.get('blood_type', ''),
                        )
                        restored_patients += 1
                        if restored_patients % 100 == 0:
                            print(f"  Restored {restored_patients} patients...")
                    except Exception as e:
                        print(f"  ⚠️  Error restoring patient {mrn}: {e}")
            
            print(f"Restored {restored_patients} patients")
            print()
        
        # Restore Staff
        staff_table = None
        for table in staff_tables:
            if table == 'staff' or table == 'hospital_staff':
                staff_table = table
                break
        
        if staff_table:
            print(f"Restoring staff from {staff_table}...")
            backup_cursor.execute(f"SELECT * FROM {staff_table}")
            staff_data = backup_cursor.fetchall()
            
            # Get column names
            backup_cursor.execute(f"PRAGMA table_info({staff_table})")
            columns = [col[1] for col in backup_cursor.fetchall()]
            
            # Get default department
            default_dept = Department.objects.first()
            if not default_dept:
                print("  ⚠️  No department found. Creating default department...")
                default_dept = Department.objects.create(
                    name='General',
                    code='GEN',
                    description='Default Department'
                )
            
            with transaction.atomic():
                for staff_row in staff_data:
                    staff_dict = dict(zip(columns, staff_row))
                    
                    # Get user if linked
                    user_id = staff_dict.get('user_id')
                    user = None
                    if user_id:
                        try:
                            user = User.objects.get(id=user_id)
                        except User.DoesNotExist:
                            pass
                    
                    # Check if staff already exists
                    employee_id = staff_dict.get('employee_id')
                    if employee_id and Staff.objects.filter(employee_id=employee_id).exists():
                        continue
                    
                    if not user:
                        # Create user for staff if not exists
                        username = staff_dict.get('username') or f"staff_{staff_dict.get('id', 'unknown')}"
                        if User.objects.filter(username=username).exists():
                            user = User.objects.get(username=username)
                        else:
                            user = User.objects.create_user(
                                username=username,
                                email=staff_dict.get('email', ''),
                                first_name=staff_dict.get('first_name', ''),
                                last_name=staff_dict.get('last_name', ''),
                                is_staff=True,
                                is_active=True,
                            )
                    
                    try:
                        staff = Staff.objects.create(
                            user=user,
                            employee_id=employee_id or f"EMP{user.id:06d}",
                            profession=staff_dict.get('profession', 'admin'),
                            department=default_dept,
                            phone_number=staff_dict.get('phone_number', ''),
                            is_active=staff_dict.get('is_active', True) if 'is_active' in staff_dict else True,
                        )
                        restored_staff += 1
                        print(f"  ✅ Restored staff: {user.get_full_name()}")
                    except Exception as e:
                        print(f"  ⚠️  Error restoring staff: {e}")
            
            print(f"Restored {restored_staff} staff")
            print()
        
        backup_conn.close()
        
        print("=" * 70)
        print("✅ RESTORATION COMPLETE!")
        print("=" * 70)
        print()
        print(f"Summary:")
        print(f"  - Users restored: {restored_users}")
        print(f"  - Patients restored: {restored_patients}")
        print(f"  - Staff restored: {restored_staff}")
        print()
        print("Note: User passwords need to be reset.")
        print("Run: RESET_ALL_STAFF_PASSWORDS.bat")
        print()
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    restore_data()

