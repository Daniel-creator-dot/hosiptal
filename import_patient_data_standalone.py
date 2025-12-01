"""
Standalone Patient Data Import Script
Imports patient_data table directly using SQLite (no Django required)
"""

import os
import re
import sqlite3
from pathlib import Path

def convert_mysql_to_sqlite(sql_content, skip_drop=False):
    """Convert MySQL SQL syntax to SQLite compatible syntax"""
    
    # Remove DROP TABLE if requested
    if skip_drop:
        sql_content = re.sub(r'DROP TABLE .*?;', '', sql_content, flags=re.IGNORECASE)

    # Remove MySQL-specific keywords
    sql_content = re.sub(r'ENGINE\s*=\s*\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'DEFAULT CHARSET\s*=\s*\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'CHARSET\s+\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'COLLATE\s+\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'AUTO_INCREMENT\s*=\s*\d+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'COMMENT\s+["\'].*?["\']', '', sql_content, flags=re.IGNORECASE)
    
    # Convert AUTO_INCREMENT - SQLite uses INTEGER PRIMARY KEY for auto-increment
    # We'll handle this differently - remove AUTO_INCREMENT and let SQLite handle it
    sql_content = re.sub(r'\s+AUTO_INCREMENT', '', sql_content, flags=re.IGNORECASE)
    
    # Convert MySQL types to SQLite types
    type_mappings = {
        r'INT\(\d+\)': 'INTEGER',
        r'BIGINT\(\d+\)': 'INTEGER',
        r'TINYINT\(\d+\)': 'INTEGER',
        r'SMALLINT\(\d+\)': 'INTEGER',
        r'MEDIUMINT\(\d+\)': 'INTEGER',
        r'FLOAT\(\d+,\d+\)': 'REAL',
        r'DOUBLE(\(\d+,\d+\))?': 'REAL',
        r'DECIMAL\(\d+,\d+\)': 'REAL',
        r'TINYTEXT': 'TEXT',
        r'MEDIUMTEXT': 'TEXT',
        r'LONGTEXT': 'TEXT',
        r'TINYBLOB': 'BLOB',
        r'MEDIUMBLOB': 'BLOB',
        r'LONGBLOB': 'BLOB',
        r'DATETIME': 'TEXT',
        r'TIMESTAMP': 'TEXT',
        r'DATE': 'TEXT',
        r'TIME': 'TEXT',
    }
    
    for mysql_type, sqlite_type in type_mappings.items():
        sql_content = re.sub(mysql_type, sqlite_type, sql_content, flags=re.IGNORECASE)
    
    # Remove UNSIGNED
    sql_content = re.sub(r'\s+UNSIGNED', '', sql_content, flags=re.IGNORECASE)
    
    # Convert backticks to double quotes for identifiers
    sql_content = sql_content.replace('`', '"')
    
    # Fix DEFAULT CURRENT_TIMESTAMP
    sql_content = re.sub(
        r"DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        "DEFAULT CURRENT_TIMESTAMP",
        sql_content,
        flags=re.IGNORECASE
    )
    
    # Remove KEY definitions that SQLite doesn't support the same way
    sql_content = re.sub(r',\s*KEY\s+"[^"]+"\s+\([^)]+\)', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r',\s*INDEX\s+"[^"]+"\s+\([^)]+\)', '', sql_content, flags=re.IGNORECASE)
    
    # Handle ENUM types (convert to TEXT)
    sql_content = re.sub(
        r'ENUM\s*\([^)]+\)',
        'TEXT',
        sql_content,
        flags=re.IGNORECASE
    )
    
    return sql_content

def split_sql_statements(sql_content):
    """Split SQL content into individual statements"""
    # Remove comments
    sql_content = re.sub(r'--.*?$', '', sql_content, flags=re.MULTILINE)
    sql_content = re.sub(r'/\*.*?\*/', '', sql_content, flags=re.DOTALL)
    
    # Split by semicolons (but not within quotes)
    statements = []
    current_statement = []
    in_quotes = False
    quote_char = None
    
    for i, char in enumerate(sql_content):
        if char in ('"', "'") and (i == 0 or sql_content[i-1] != '\\'):
            if not in_quotes:
                in_quotes = True
                quote_char = char
            elif char == quote_char:
                in_quotes = False
                quote_char = None
        
        if char == ';' and not in_quotes:
            current_statement.append(char)
            stmt = ''.join(current_statement).strip()
            if stmt:
                statements.append(stmt)
            current_statement = []
        else:
            current_statement.append(char)
    
    # Add any remaining statement
    if current_statement:
        stmt = ''.join(current_statement).strip()
        if stmt:
            statements.append(stmt)
    
    return statements

def import_patient_data():
    """Import patient data from SQL file"""
    print("="*70)
    print("   PATIENT DATA IMPORT (Standalone)")
    print("="*70)
    print()
    
    # Get paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sql_dir = os.path.join(base_dir, 'import', 'legacy')
    db_path = os.path.join(base_dir, 'db.sqlite3')
    
    patient_file = os.path.join(sql_dir, 'patient_data.sql')
    
    if not os.path.exists(patient_file):
        print(f"ERROR: Patient SQL file not found: {patient_file}")
        return False
    
    if not os.path.exists(db_path):
        print(f"ERROR: Database file not found: {db_path}")
        return False
    
    print(f"SQL File: {patient_file}")
    print(f"Database: {db_path}")
    print()
    
    print("Starting import...")
    print()
    
    try:
        # Read SQL file
        with open(patient_file, 'r', encoding='utf-8', errors='ignore') as f:
            sql_content = f.read()
        
        # Convert MySQL to SQLite
        sql_content = convert_mysql_to_sqlite(sql_content, skip_drop=True)
        
        # Split into statements
        statements = split_sql_statements(sql_content)
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = OFF;")
        cursor = conn.cursor()
        
        tables_created = 0
        rows_inserted = 0
        errors = 0
        
        for statement in statements:
            statement = statement.strip()
            if not statement or statement.startswith('--'):
                continue
            
            try:
                # Fix CREATE TABLE statements for SQLite
                if statement.upper().startswith('CREATE TABLE'):
                    # Remove PRIMARY KEY from column definition if it's at the end
                    # SQLite needs PRIMARY KEY in column definition, not as separate constraint
                    statement = re.sub(
                        r'(\w+)\s+INTEGER\s+NOT\s+NULL\s+PRIMARY\s+KEY',
                        r'\1 INTEGER PRIMARY KEY',
                        statement,
                        flags=re.IGNORECASE
                    )
                    # Handle BIGINT(20) NOT NULL AUTO_INCREMENT PRIMARY KEY
                    statement = re.sub(
                        r'`id`\s+INTEGER\s+NOT\s+NULL',
                        r'"id" INTEGER PRIMARY KEY',
                        statement,
                        flags=re.IGNORECASE
                    )
                    # Remove any remaining KEY definitions at the end (before closing paren)
                    statement = re.sub(
                        r',\s*PRIMARY\s+KEY\s*\([^)]+\)',
                        '',
                        statement,
                        flags=re.IGNORECASE
                    )
                    # Remove UNIQUE KEY definitions first (they come before KEY)
                    statement = re.sub(
                        r',\s*UNIQUE\s+KEY\s+[^,)]+',
                        '',
                        statement,
                        flags=re.IGNORECASE
                    )
                    # Remove KEY definitions (handle both quoted and unquoted, with parentheses)
                    statement = re.sub(
                        r',\s*KEY\s+[^,)]+',
                        '',
                        statement,
                        flags=re.IGNORECASE
                    )
                    # Remove trailing comma before closing paren
                    statement = re.sub(r',\s*\)', ')', statement)
                    
                    # Debug: print first 500 chars of CREATE TABLE
                    if 'patient_data' in statement.lower():
                        print(f"DEBUG CREATE TABLE (first 500 chars): {statement[:500]}")
                        print(f"DEBUG CREATE TABLE (last 200 chars): {statement[-200:]}")
                
                cursor.execute(statement)
                
                # Track statistics
                if statement.upper().startswith('CREATE TABLE'):
                    tables_created += 1
                    print(f"  [OK] Created table: patient_data")
                elif statement.upper().startswith('INSERT INTO'):
                    rows_inserted += 1
                    if rows_inserted % 1000 == 0:
                        print(f"  ... {rows_inserted:,} rows inserted")
                        
            except sqlite3.Error as e:
                error_msg = str(e).lower()
                # Skip errors for existing tables/duplicates
                if 'already exists' not in error_msg and 'UNIQUE constraint' not in error_msg:
                    errors += 1
                    if errors <= 10:  # Show first 10 errors for debugging
                        print(f"  ⚠ Warning: {str(e)[:150]}")
                        if errors == 10:
                            print(f"  ... (suppressing further warnings)")
        
        conn.commit()
        conn.close()
        
        print()
        print("="*70)
        print("Patient data import complete!")
        print("="*70)
        print()
        print(f"Statistics:")
        print(f"   - Tables created: {tables_created}")
        print(f"   - Rows inserted: {rows_inserted:,}")
        if errors > 5:
            print(f"   - Warnings: {errors} (first 5 shown above)")
        print()
        
        # Verify
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM patient_data')
            count = cursor.fetchone()[0]
            print(f"[OK] Verification: {count:,} patient records in database")
            
            if count > 0:
                cursor.execute('SELECT id, fname, lname, DOB FROM patient_data LIMIT 5')
                print()
                print("Sample patients:")
                for row in cursor.fetchall():
                    print(f"   ID: {row[0]}, Name: {row[1]} {row[2]}, DOB: {row[3]}")
        except Exception as e:
            print(f"⚠ Could not verify: {e}")
        finally:
            conn.close()
        
        print()
        print("Next steps:")
        print("1. Run Django migrations: python manage.py migrate")
        print("2. Import into Patient model: python manage.py import_legacy_patients --sql-dir import\\legacy")
        print()
        
        return True
        
    except Exception as e:
        print(f"ERROR during import: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    try:
        success = import_patient_data()
        if success:
            print("[OK] Import completed successfully!")
        else:
            print("[ERROR] Import failed. Please check the errors above.")
    except KeyboardInterrupt:
        print("\n\nImport cancelled by user.")
    except Exception as e:
        print(f"\n[ERROR] Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()

