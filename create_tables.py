import sqlite3
import uuid

# Connect to database
conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

print("Creating biometric tables...")

# Read and execute SQL
with open('create_biometric_tables.sql', 'r') as f:
    sql_script = f.read()
    cursor.executescript(sql_script)

conn.commit()
print("[OK] All biometric tables created successfully!")

# Verify tables exist
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'hospital_biometric%';")
tables = cursor.fetchall()
print(f"\nCreated tables:")
for table in tables:
    print(f"  - {table[0]}")

conn.close()
print("\n[DONE] Now try accessing the enrollment page again.")

