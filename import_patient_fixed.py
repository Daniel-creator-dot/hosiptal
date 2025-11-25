"""
Fixed Patient Data Import
Proper MySQL to SQLite conversion
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


def convert_create_table(sql):
    """Convert CREATE TABLE statement"""
    # Extract table name
    match = re.search(r'CREATE TABLE\s+`?(\w+)`?', sql, re.IGNORECASE)
    if not match:
        return sql
    
    table_name = match.group(1)
    
    # Remove DROP TABLE
    sql = re.sub(r'DROP TABLE.*?;', '', sql, flags=re.IGNORECASE)
    
    # Remove backticks
    sql = sql.replace('`', '"')
    
    # Fix AUTO_INCREMENT - only use AUTOINCREMENT for INTEGER PRIMARY KEY
    # First, identify the primary key column
    pk_match = re.search(r'PRIMARY KEY\s*\("?(\w+)"?\)', sql, re.IGNORECASE)
    pk_column = pk_match.group(1) if pk_match else None
    
    # Replace AUTO_INCREMENT properly
    if pk_column:
        # For primary key column, use AUTOINCREMENT
        sql = re.sub(
            rf'("?{pk_column}"?\s+\w+\s+NOT NULL)\s+AUTO_INCREMENT',
            r'\1 PRIMARY KEY AUTOINCREMENT',
            sql,
            flags=re.IGNORECASE
        )
    # Remove other AUTO_INCREMENT
    sql = re.sub(r'\s+AUTO_INCREMENT', '', sql, flags=re.IGNORECASE)
    
    # Remove duplicate PRIMARY KEY definition
    if pk_column:
        sql = re.sub(rf',\s*PRIMARY KEY\s*\("{pk_column}"\)', '', sql, flags=re.IGNORECASE)
    
    # Convert types
    sql = re.sub(r'BIGINT\(\d+\)', 'INTEGER', sql, flags=re.IGNORECASE)
    sql = re.sub(r'INT\(\d+\)', 'INTEGER', sql, flags=re.IGNORECASE)
    sql = re.sub(r'TINYINT\(\d+\)', 'INTEGER', sql, flags=re.IGNORECASE)
    sql = re.sub(r'SMALLINT\(\d+\)', 'INTEGER', sql, flags=re.IGNORECASE)
    sql = re.sub(r'MEDIUMINT\(\d+\)', 'INTEGER', sql, flags=re.IGNORECASE)
    sql = re.sub(r'FLOAT\(\d+,\d+\)', 'REAL', sql, flags=re.IGNORECASE)
    sql = re.sub(r'DOUBLE', 'REAL', sql, flags=re.IGNORECASE)
    sql = re.sub(r'DECIMAL\(\d+,\d+\)', 'REAL', sql, flags=re.IGNORECASE)
    sql = re.sub(r'LONGTEXT', 'TEXT', sql, flags=re.IGNORECASE)
    sql = re.sub(r'MEDIUMTEXT', 'TEXT', sql, flags=re.IGNORECASE)
    sql = re.sub(r'TINYTEXT', 'TEXT', sql, flags=re.IGNORECASE)
    sql = re.sub(r'DATETIME', 'TEXT', sql, flags=re.IGNORECASE)
    sql = re.sub(r'TIMESTAMP', 'TEXT', sql, flags=re.IGNORECASE)
    sql = re.sub(r'DATE\s', 'TEXT ', sql, flags=re.IGNORECASE)
    
    # Remove UNSIGNED
    sql = re.sub(r'\s+UNSIGNED', '', sql, flags=re.IGNORECASE)
    
    # Remove KEY definitions
    sql = re.sub(r',\s*KEY\s+"[^"]+"\s+\([^)]+\)', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r',\s*UNIQUE KEY\s+"[^"]+"\s+\([^)]+\)', '', sql, flags=re.IGNORECASE)
    
    # Remove ENGINE, CHARSET, etc
    sql = re.sub(r'ENGINE\s*=\s*InnoDB', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r'DEFAULT CHARSET\s*=\s*\w+', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r'COMMENT\s*=\s*["\'].*?["\']', '', sql, flags=re.IGNORECASE)
    
    # Handle DEFAULT CURRENT_TIMESTAMP ON UPDATE
    sql = re.sub(
        r'DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
        'DEFAULT CURRENT_TIMESTAMP',
        sql,
        flags=re.IGNORECASE
    )
    
    return sql


def main():
    print("="*70)
    print("PATIENT DATA IMPORT - FIXED VERSION")
    print("="*70)
    print()
    
    sql_file = r'C:\Users\user\Videos\DS\patient_data.sql'
    
    print(f"Reading: {sql_file}")
    with open(sql_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    print("Converting SQL...")
    content = convert_create_table(content)
    
    # Split CREATE TABLE and INSERTS
    create_match = re.search(r'(CREATE TABLE.*?)\s*;', content, re.IGNORECASE | re.DOTALL)
    if not create_match:
        print("ERROR: Could not find CREATE TABLE statement")
        return
    
    create_stmt = create_match.group(1) + ';'
    
    # Get INSERT statements
    insert_stmts = re.findall(r'INSERT INTO.*?;', content, re.IGNORECASE)
    
    print(f"Found 1 CREATE TABLE and {len(insert_stmts)} INSERT statements")
    print()
    
    with connection.cursor() as cursor:
        # Try to drop table first
        try:
            cursor.execute('DROP TABLE IF EXISTS patient_data')
            print("Dropped existing table (if any)")
        except:
            pass
        
        # Create table
        print("Creating patient_data table...")
        try:
            cursor.execute(create_stmt)
            print("[OK] Table created successfully")
        except Exception as e:
            print(f"[ERROR] Failed to create table: {e}")
            print()
            print("CREATE statement:")
            print(create_stmt[:500])
            return
        
        # Insert data
        print()
        print(f"Inserting {len(insert_stmts)} rows...")
        
        inserted = 0
        errors = 0
        
        for i, stmt in enumerate(insert_stmts, 1):
            try:
                cursor.execute(stmt)
                inserted += 1
                if i % 500 == 0:
                    print(f"  Progress: {i}/{len(insert_stmts)} ({(i/len(insert_stmts)*100):.1f}%)")
            except Exception as e:
                errors += 1
                if errors < 3:
                    print(f"  [ERROR] Row {i}: {str(e)[:60]}")
        
        print()
        print(f"Inserted: {inserted:,} rows")
        print(f"Errors: {errors}")
    
    # Verify
    print()
    print("="*70)
    print("VERIFICATION")
    print("="*70)
    
    with connection.cursor() as cursor:
        try:
            cursor.execute('SELECT COUNT(*) FROM patient_data')
            count = cursor.fetchone()[0]
            print(f"Total patient records in database: {count:,}")
            
            if count > 0:
                print()
                print("Sample patients:")
                cursor.execute('SELECT id, fname, lname, DOB, sex FROM patient_data LIMIT 10')
                for row in cursor.fetchall():
                    print(f"  ID: {row[0]:5d} | {row[1]:15s} {row[2]:15s} | DOB: {row[3]} | Sex: {row[4]}")
                
                print()
                print("[SUCCESS] Patient data imported successfully!")
            else:
                print("[WARNING] No patient records found")
                
        except Exception as e:
            print(f"[ERROR] {e}")
    
    print()
    print("="*70)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nImport cancelled")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()




















