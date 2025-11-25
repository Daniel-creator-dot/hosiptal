"""
Working Patient Data Import
Proper extraction and conversion
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


def main():
    print("="*70)
    print("PATIENT DATA IMPORT")
    print("="*70)
    print()
    
    sql_file = r'C:\Users\user\Videos\DS\patient_data.sql'
    
    print(f"Reading: {os.path.basename(sql_file)}")
    with open(sql_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Find CREATE TABLE section
    create_start = None
    create_end = None
    
    for i, line in enumerate(lines):
        if 'CREATE TABLE' in line.upper():
            create_start = i
        if create_start is not None and ');' in line and 'ENGINE' in line:
            create_end = i
            break
    
    if create_start is None or create_end is None:
        print("ERROR: Could not find CREATE TABLE statement")
        return
    
    # Extract and convert CREATE TABLE
    create_lines = lines[create_start:create_end+1]
    create_sql = ''.join(create_lines)
    
    # Convert to SQLite
    print("Converting to SQLite...")
    
    # Remove backticks
    create_sql = create_sql.replace('`', '"')
    
    # Find PRIMARY KEY column
    pk_match = re.search(r'PRIMARY KEY\s*\("?(\w+)"?\)', create_sql, re.IGNORECASE)
    pk_column = pk_match.group(1) if pk_match else 'id'
    
    # Fix the PRIMARY KEY column definition
    create_sql = re.sub(
        rf'("{pk_column}"\s+\w+)\s+NOT NULL\s+AUTO_INCREMENT',
        rf'\1 PRIMARY KEY AUTOINCREMENT',
        create_sql,
        flags=re.IGNORECASE
    )
    
    # Remove duplicate PRIMARY KEY definition
    create_sql = re.sub(rf',\s*PRIMARY KEY\s*\("{pk_column}"\)', '', create_sql, flags=re.IGNORECASE)
    
    # Convert types
    create_sql = re.sub(r'bigint\(\d+\)', 'INTEGER', create_sql, flags=re.IGNORECASE)
    create_sql = re.sub(r'int\(\d+\)', 'INTEGER', create_sql, flags=re.IGNORECASE)
    create_sql = re.sub(r'tinyint\(\d+\)', 'INTEGER', create_sql, flags=re.IGNORECASE)
    create_sql = re.sub(r'smallint\(\d+\)', 'INTEGER', create_sql, flags=re.IGNORECASE)
    create_sql = re.sub(r'longtext', 'TEXT', create_sql, flags=re.IGNORECASE)
    create_sql = re.sub(r'mediumtext', 'TEXT', create_sql, flags=re.IGNORECASE)
    create_sql = re.sub(r'tinytext', 'TEXT', create_sql, flags=re.IGNORECASE)
    create_sql = re.sub(r'datetime', 'TEXT', create_sql, flags=re.IGNORECASE)
    create_sql = re.sub(r'timestamp', 'TEXT', create_sql, flags=re.IGNORECASE)
    
    # Remove COMMENT
    create_sql = re.sub(r"COMMENT\s+'[^']*'", '', create_sql, flags=re.IGNORECASE)
    create_sql = re.sub(r'COMMENT\s+"[^"]*"', '', create_sql, flags=re.IGNORECASE)
    
    # Remove UNSIGNED
    create_sql = re.sub(r'\s+unsigned', '', create_sql, flags=re.IGNORECASE)
    
    # Remove KEY definitions
    create_sql = re.sub(r',\s*KEY\s+"[^"]+"\s+\([^)]+\)', '', create_sql, flags=re.IGNORECASE)
    create_sql = re.sub(r',\s*UNIQUE KEY\s+"[^"]+"\s+\([^)]+\)', '', create_sql, flags=re.IGNORECASE)
    
    # Remove ENGINE and CHARSET
    create_sql = re.sub(r'\)\s*ENGINE.*', ')', create_sql, flags=re.IGNORECASE | re.DOTALL)
    
    # Add semicolon
    if not create_sql.strip().endswith(';'):
        create_sql = create_sql.strip() + ';'
    
    # Extract INSERT statements
    insert_start = create_end + 1
    insert_lines = []
    for line in lines[insert_start:]:
        if line.strip().startswith('INSERT INTO'):
            insert_lines.append(line.replace('`', '"'))
    
    print(f"Found: 1 CREATE TABLE + {len(insert_lines)} INSERT statements")
    print()
    
    # Import
    print("Importing to database...")
    
    with connection.cursor() as cursor:
        # Drop if exists
        try:
            cursor.execute('DROP TABLE IF EXISTS patient_data')
            print("[OK] Dropped existing table")
        except:
            pass
        
        # Create table
        try:
            cursor.execute(create_sql)
            print("[OK] Created patient_data table")
        except Exception as e:
            print(f"[ERROR] CREATE TABLE failed: {e}")
            print("\nSQL Preview (first 500 chars):")
            print(create_sql[:500])
            return
        
        # Insert data
        print(f"\nInserting {len(insert_lines):,} patient records...")
        print("(This will take 2-5 minutes for large datasets)")
        print()
        
        inserted = 0
        errors = 0
        
        for i, stmt in enumerate(insert_lines, 1):
            try:
                cursor.execute(stmt.strip())
                inserted += 1
                
                if i % 2000 == 0:
                    print(f"  {i:,}/{len(insert_lines):,} ({i/len(insert_lines)*100:.1f}%) - {inserted:,} inserted")
                    
            except Exception as e:
                errors += 1
                if errors < 3:
                    print(f"  [ERROR] Row {i}: {str(e)[:50]}")
        
        connection.connection.commit()
        
        print()
        print(f"[OK] Import complete!")
        print(f"     Inserted: {inserted:,}")
        print(f"     Errors: {errors}")
    
    # Verify
    print()
    print("="*70)
    print("VERIFICATION")
    print("="*70)
    
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM patient_data')
        count = cursor.fetchone()[0]
        print(f"\nPatient records in database: {count:,}")
        
        if count > 0:
            print("\nSample patients (first 10):")
            print("-"*70)
            cursor.execute('''
                SELECT id, fname, lname, DOB, sex, phone_cell 
                FROM patient_data 
                WHERE fname != '' 
                LIMIT 10
            ''')
            
            for row in cursor.fetchall():
                name = f"{row[1]} {row[2]}"
                print(f"  {row[0]:6d} | {name:25s} | {row[3]:12s} | {row[4]:6s} | {row[5]}")
            
            print()
            print("="*70)
            print("[SUCCESS] PATIENT DATA IMPORTED!")
            print("="*70)
            print()
            print("You can now:")
            print("1. Query: python manage.py dbshell")
            print("          SELECT * FROM patient_data LIMIT 5;")
            print()
            print("2. Count by sex:")
            print("          SELECT sex, COUNT(*) FROM patient_data GROUP BY sex;")
            print()
            print("3. Generate Django model:")
            print("          python manage.py inspectdb patient_data")
        else:
            print("\n[WARNING] Table created but no data inserted")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()




















