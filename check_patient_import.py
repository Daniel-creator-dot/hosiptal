"""Check if patient data was imported successfully"""
import sqlite3
import os

db_path = 'db.sqlite3'

if not os.path.exists(db_path):
    print(f"ERROR: Database file not found: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if patient_data table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='patient_data'")
result = cursor.fetchone()

if result:
    print(f"[OK] Table 'patient_data' exists")
    
    # Count records
    cursor.execute('SELECT COUNT(*) FROM patient_data')
    count = cursor.fetchone()[0]
    print(f"[OK] Patient records in patient_data table: {count:,}")
    
    # Show sample records
    if count > 0:
        cursor.execute('SELECT id, fname, lname, DOB, sex FROM patient_data LIMIT 5')
        print("\nSample patients:")
        for row in cursor.fetchall():
            print(f"  ID: {row[0]}, Name: {row[1]} {row[2]}, DOB: {row[3]}, Sex: {row[4]}")
else:
    print("[ERROR] Table 'patient_data' does not exist")
    print("The import may have failed or not completed yet.")

# Check Patient model records
try:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='hospital_patient'")
    result = cursor.fetchone()
    if result:
        cursor.execute('SELECT COUNT(*) FROM hospital_patient')
        count = cursor.fetchone()[0]
        print(f"\n[OK] Patient model records: {count:,}")
except Exception as e:
    print(f"\nNote: Could not check Patient model: {e}")

conn.close()


