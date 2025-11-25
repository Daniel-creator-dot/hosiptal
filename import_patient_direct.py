"""
Direct Patient Data Import
Bypasses conversion and imports SQL directly
"""

import os
import sys
import django
import re

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import connection


def convert_sql(sql_content):
    """Convert MySQL to SQLite"""
    # Remove DROP TABLE
    sql_content = re.sub(r'DROP TABLE .*?;', '', sql_content, flags=re.IGNORECASE)
    
    # Remove MySQL-specific stuff
    sql_content = re.sub(r'ENGINE\s*=\s*\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'DEFAULT CHARSET\s*=\s*\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'CHARSET\s+\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'COLLATE\s+\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'AUTO_INCREMENT\s*=\s*\d+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'COMMENT\s+["\'].*?["\']', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'AUTO_INCREMENT', 'AUTOINCREMENT', sql_content, flags=re.IGNORECASE)
    
    # Convert types
    sql_content = re.sub(r'BIGINT\(\d+\)', 'INTEGER', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'INT\(\d+\)', 'INTEGER', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'TINYINT\(\d+\)', 'INTEGER', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'SMALLINT\(\d+\)', 'INTEGER', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'LONGTEXT', 'TEXT', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'MEDIUMTEXT', 'TEXT', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'TINYTEXT', 'TEXT', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'DATETIME', 'TEXT', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'DATE', 'TEXT', sql_content, flags=re.IGNORECASE)
    
    # Remove KEY definitions
    sql_content = re.sub(r',\s*KEY\s+`[^`]+`\s+\([^)]+\)', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r',\s*UNIQUE KEY\s+`[^`]+`\s+\([^)]+\)', '', sql_content, flags=re.IGNORECASE)
    
    # Convert backticks
    sql_content = sql_content.replace('`', '"')
    
    # Handle UNSIGNED
    sql_content = re.sub(r'\s+UNSIGNED', '', sql_content, flags=re.IGNORECASE)
    
    return sql_content


def main():
    print("="*70)
    print("   DIRECT PATIENT DATA IMPORT")
    print("="*70)
    print()
    
    sql_file = r'C:\Users\user\Videos\DS\patient_data.sql'
    
    if not os.path.exists(sql_file):
        print(f"ERROR: File not found: {sql_file}")
        return
    
    print(f"Reading: {sql_file}")
    print()
    
    with open(sql_file, 'r', encoding='utf-8', errors='ignore') as f:
        sql_content = f.read()
    
    print("Converting MySQL to SQLite...")
    sql_content = convert_sql(sql_content)
    
    # Split into statements
    statements = [s.strip() + ';' for s in sql_content.split(';') if s.strip()]
    
    print(f"Found {len(statements)} SQL statements")
    print()
    print("Importing...")
    
    tables_created = 0
    rows_inserted = 0
    errors = 0
    
    with connection.cursor() as cursor:
        for i, stmt in enumerate(statements, 1):
            if not stmt or stmt.startswith('--'):
                continue
            
            try:
                cursor.execute(stmt)
                
                if 'CREATE TABLE' in stmt.upper():
                    tables_created += 1
                    print(f"  [{i}/{len(statements)}] Created table")
                elif 'INSERT INTO' in stmt.upper():
                    rows_inserted += 1
                    if rows_inserted % 100 == 0:
                        print(f"  [{i}/{len(statements)}] Inserted {rows_inserted} rows...")
                        
            except Exception as e:
                errors += 1
                if errors < 5:  # Only show first few errors
                    print(f"  [ERROR] {str(e)[:80]}")
    
    print()
    print("="*70)
    print("IMPORT COMPLETE")
    print("="*70)
    print(f"Tables created: {tables_created}")
    print(f"Rows inserted: {rows_inserted}")
    print(f"Errors: {errors}")
    print()
    
    # Verify
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM patient_data')
            count = cursor.fetchone()[0]
            print(f"Total patient records: {count:,}")
            
            if count > 0:
                cursor.execute('SELECT id, fname, lname, DOB FROM patient_data LIMIT 5')
                print()
                print("Sample patients:")
                for row in cursor.fetchall():
                    print(f"  ID: {row[0]:5d}, Name: {row[1]} {row[2]}, DOB: {row[3]}")
    except Exception as e:
        print(f"Verification error: {e}")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()




















