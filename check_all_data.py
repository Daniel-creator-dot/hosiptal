"""Check all imported data"""
import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

print("="*70)
print("CHECKING ALL IMPORTED DATA")
print("="*70)
print()

# Check patient data
cursor.execute('SELECT COUNT(*) FROM patient_data')
patient_count = cursor.fetchone()[0]
print(f'PATIENT DATA: {patient_count:,} records')

# Sample patients
cursor.execute('SELECT fname, lname, pmc_mrn FROM patient_data LIMIT 5')
print('\nSample patients:')
for row in cursor.fetchall():
    print(f'  - {row[0]} {row[1]} ({row[2]})')

# Check accounting tables
print()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'acc_%' ORDER BY name")
acc_tables = cursor.fetchall()
print(f'ACCOUNTING TABLES: {len(acc_tables)}')
for t in acc_tables:
    cursor.execute(f'SELECT COUNT(*) FROM {t[0]}')
    count = cursor.fetchone()[0]
    print(f'  - {t[0]}: {count:,} records')

# Check accounting setup
print()
print('ACCOUNTING SETUP:')
cursor.execute('SELECT COUNT(*) FROM hospital_fiscalyear')
print(f'  Fiscal Years: {cursor.fetchone()[0]}')
cursor.execute('SELECT COUNT(*) FROM hospital_accountingperiod')
print(f'  Accounting Periods: {cursor.fetchone()[0]}')
cursor.execute('SELECT COUNT(*) FROM hospital_journal')
print(f'  Journals: {cursor.fetchone()[0]}')
cursor.execute('SELECT COUNT(*) FROM hospital_revenuecategory')
print(f'  Revenue Categories: {cursor.fetchone()[0]}')
cursor.execute('SELECT COUNT(*) FROM hospital_expensecategory')
print(f'  Expense Categories: {cursor.fetchone()[0]}')

conn.close()

print()
print("="*70)
print("DATA CHECK COMPLETE!")
print("="*70)
print()
print("To view in browser:")
print("  Patients: http://127.0.0.1:8000/hms/patients/")
print("  Accounting: http://127.0.0.1:8000/hms/accounting/")
print("  Admin: http://127.0.0.1:8000/admin/")




















