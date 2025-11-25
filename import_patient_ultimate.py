"""
Ultimate Patient Data Import
Comprehensive MySQL to SQLite conversion
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


def convert_mysql_to_sqlite(sql_content):
    """Comprehensive MySQL to SQLite conversion"""
    
    # Remove DROP TABLE
    sql_content = re.sub(r'DROP TABLE[^;]*;', '', sql_content, flags=re.IGNORECASE)
    
    # Convert backticks to quotes
    sql_content = sql_content.replace('`', '"')
    
    # Remove COMMENT anywhere (more aggressive)
    sql_content = re.sub(r'COMMENT\s+["\'].*?["\']', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'COMMENT\s+".*?"', '', sql_content, flags=re.IGNORECASE)
    
    # Remove MySQL-specific keywords
    sql_content = re.sub(r'\s+UNSIGNED', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'ENGINE\s*=\s*\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'AUTO_INCREMENT\s*=\s*\d+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'DEFAULT CHARSET\s*=\s*\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'CHARSET\s+\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'COLLATE\s+\w+', '', sql_content, flags=re.IGNORECASE)
    
    # Handle AUTO_INCREMENT - make it AUTOINCREMENT only for PRIMARY KEY
    sql_content = re.sub(
        r'(INTEGER\s+NOT NULL)\s+AUTO_INCREMENT\s+,\s*PRIMARY KEY',
        r'\1 PRIMARY KEY AUTOINCREMENT, ',
        sql_content,
        flags=re.IGNORECASE
    )
    
    # Remove remaining AUTO_INCREMENT
    sql_content = re.sub(r'\s+AUTO_INCREMENT', '', sql_content, flags=re.IGNORECASE)
    
    # Convert data types
    sql_content = re.sub(r'BIGINT\(\d+\)', 'INTEGER', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'INT\(\d+\)', 'INTEGER', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'TINYINT\(\d+\)', 'INTEGER', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'SMALLINT\(\d+\)', 'INTEGER', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'MEDIUMINT\(\d+\)', 'INTEGER', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'FLOAT\(\d+,\d+\)', 'REAL', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'DOUBLE', 'REAL', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'DECIMAL\(\d+,\d+\)', 'REAL', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'LONGTEXT', 'TEXT', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'MEDIUMTEXT', 'TEXT', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'TINYTEXT', 'TEXT', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'DATETIME', 'TEXT', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'TIMESTAMP', 'TEXT', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'\bDATE\b', 'TEXT', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'\bTIME\b', 'TEXT', sql_content, flags=re.IGNORECASE)
    
    # Remove KEY and INDEX definitions
    sql_content = re.sub(r',\s*KEY\s+"[^"]+"\s+\([^)]+\)', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r',\s*UNIQUE KEY\s+"[^"]+"\s+\([^)]+\)', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r',\s*INDEX\s+"[^"]+"\s+\([^)]+\)', '', sql_content, flags=re.IGNORECASE)
    
    # Remove ON UPDATE CURRENT_TIMESTAMP
    sql_content = re.sub(
        r'DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
        'DEFAULT CURRENT_TIMESTAMP',
        sql_content,
        flags=re.IGNORECASE
    )
    
    return sql_content


def main():
    print("="*70)
    print("PATIENT DATA IMPORT - ULTIMATE VERSION")
    print("="*70)
    print()
    
    sql_file = r'C:\Users\user\Videos\DS\patient_data.sql'
    
    if not os.path.exists(sql_file):
        print(f"ERROR: File not found: {sql_file}")
        return
    
    print(f"Reading: {os.path.basename(sql_file)}")
    with open(sql_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    print("Converting MySQL to SQLite...")
    content = convert_mysql_to_sqlite(content)
    
    # Extract CREATE TABLE
    create_match = re.search(r'(CREATE TABLE.*?)\);', content, re.IGNORECASE | re.DOTALL)
    if not create_match:
        print("ERROR: Could not find CREATE TABLE statement")
        return
    
    create_stmt = create_match.group(0)
    
    # Extract INSERT statements
    insert_stmts = re.findall(r'INSERT INTO[^;]+;', content, re.IGNORECASE)
    
    print(f"Statements: 1 CREATE + {len(insert_stmts)} INSERTs")
    print()
    
    # Import
    print("Importing to database...")
    
    with connection.cursor() as cursor:
        # Drop if exists
        try:
            cursor.execute('DROP TABLE IF EXISTS patient_data')
        except:
            pass
        
        # Create table
        try:
            cursor.execute(create_stmt)
            print("[OK] Table created")
        except Exception as e:
            print(f"[ERROR] CREATE failed: {e}")
            print()
            print("SQL Preview:")
            print(create_stmt[:1000])
            return
        
        # Insert data
        inserted = 0
        errors = 0
        
        print(f"Inserting {len(insert_stmts):,} rows (this may take a few minutes)...")
        
        for i, stmt in enumerate(insert_stmts, 1):
            try:
                cursor.execute(stmt)
                inserted += 1
                
                if i % 1000 == 0:
                    print(f"  Progress: {i:,}/{len(insert_stmts):,} ({i/len(insert_stmts)*100:.1f}%)")
                    
            except Exception as e:
                errors += 1
                if errors < 5:
                    print(f"  [ERROR] Row {i}: {str(e)[:60]}")
        
        # Commit
        connection.connection.commit()
        
        print()
        print(f"[OK] Inserted {inserted:,} rows")
        if errors > 0:
            print(f"[WARNING] {errors} rows had errors")
    
    # Verify
    print()
    print("="*70)
    print("VERIFICATION")
    print("="*70)
    
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM patient_data')
        count = cursor.fetchone()[0]
        print(f"\nTotal patients: {count:,}")
        
        if count > 0:
            print("\nSample patient records:")
            print("-"*70)
            cursor.execute('SELECT id, fname, lname, DOB, sex, phone_cell FROM patient_data LIMIT 10')
            for row in cursor.fetchall():
                print(f"ID: {row[0]:6d} | {row[1]:12s} {row[2]:12s} | {row[3]} | {row[4]:6s} | {row[5]}")
            
            print()
            print("="*70)
            print("[SUCCESS] Patient data is now available!")
            print("="*70)
            print()
            print("You can now query patient data:")
            print("  python manage.py dbshell")
            print("  SELECT * FROM patient_data WHERE fname LIKE 'John%';")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()




















