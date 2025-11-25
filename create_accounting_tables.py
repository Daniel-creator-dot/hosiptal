"""
Create Accounting Tables Directly
"""

import sqlite3
import os

def main():
    print("="*70)
    print("CREATING ACCOUNTING TABLES")
    print("="*70)
    print()
    
    # Connect to database
    db_path = 'db.sqlite3'
    
    if not os.path.exists(db_path):
        print(f"Error: Database file not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Read SQL file
    with open('create_accounting_tables.sql', 'r') as f:
        sql_script = f.read()
    
    # Execute SQL
    try:
        cursor.executescript(sql_script)
        conn.commit()
        print("[OK] All accounting tables created successfully!")
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()
    
    print()
    print("="*70)
    print("TABLES CREATED!")
    print("="*70)
    print()
    print("Next steps:")
    print("1. python setup_accounting_simple.py")
    print("2. python import_legacy_accounting.py")


if __name__ == '__main__':
    main()




















