"""Direct patient data import using SQLite"""
import os
import re
import sqlite3

def convert_mysql_to_sqlite(sql_content, skip_drop=False):
    """Convert MySQL SQL syntax to SQLite compatible syntax"""
    
    if skip_drop:
        sql_content = re.sub(r'DROP TABLE .*?;', '', sql_content, flags=re.IGNORECASE)

    # Remove MySQL-specific keywords
    sql_content = re.sub(r'ENGINE\s*=\s*\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'DEFAULT CHARSET\s*=\s*\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'CHARSET\s+\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'COLLATE\s+\w+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'AUTO_INCREMENT\s*=\s*\d+', '', sql_content, flags=re.IGNORECASE)
    sql_content = re.sub(r'COMMENT\s+["\'].*?["\']', '', sql_content, flags=re.IGNORECASE)
    
    # Convert AUTO_INCREMENT - remove it, SQLite handles auto-increment differently
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
    
    sql_content = re.sub(r'\s+UNSIGNED', '', sql_content, flags=re.IGNORECASE)
    sql_content = sql_content.replace('`', '"')
    
    sql_content = re.sub(
        r"DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        "DEFAULT CURRENT_TIMESTAMP",
        sql_content,
        flags=re.IGNORECASE
    )
    
    # Remove KEY definitions (handle both backticks and quotes)
    # Remove UNIQUE KEY first
    sql_content = re.sub(r',\s*UNIQUE\s+KEY\s+[^,)]+\s*\([^)]+\)', '', sql_content, flags=re.IGNORECASE)
    # Remove KEY definitions
    sql_content = re.sub(r',\s*KEY\s+[^,)]+\s*\([^)]+\)', '', sql_content, flags=re.IGNORECASE)
    # Remove PRIMARY KEY constraints at the end
    sql_content = re.sub(r',\s*PRIMARY\s+KEY\s*\([^)]+\)', '', sql_content, flags=re.IGNORECASE)
    
    # Handle ENUM types
    sql_content = re.sub(r'ENUM\s*\([^)]+\)', 'TEXT', sql_content, flags=re.IGNORECASE)
    
    return sql_content

def split_sql_statements(sql_content):
    """Split SQL content into individual statements"""
    sql_content = re.sub(r'--.*?$', '', sql_content, flags=re.MULTILINE)
    sql_content = re.sub(r'/\*.*?\*/', '', sql_content, flags=re.DOTALL)
    
    statements = []
    current = []
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
            current.append(char)
            stmt = ''.join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(char)
    
    if current:
        stmt = ''.join(current).strip()
        if stmt:
            statements.append(stmt)
    
    return statements

# Main execution
base_dir = os.path.dirname(os.path.abspath(__file__))
sql_file = os.path.join(base_dir, 'import', 'legacy', 'patient_data.sql')
db_path = os.path.join(base_dir, 'db.sqlite3')

print("="*70)
print("PATIENT DATA IMPORT")
print("="*70)
print()
print(f"SQL File: {sql_file}")
print(f"Database: {db_path}")
print()

if not os.path.exists(sql_file):
    print(f"ERROR: SQL file not found: {sql_file}")
    exit(1)

if not os.path.exists(db_path):
    print(f"ERROR: Database not found: {db_path}")
    exit(1)

print("Reading SQL file...")
with open(sql_file, 'r', encoding='utf-8', errors='ignore') as f:
    sql_content = f.read()

print("Converting MySQL to SQLite...")
sql_content = convert_mysql_to_sqlite(sql_content, skip_drop=True)

print("Splitting into statements...")
statements = split_sql_statements(sql_content)
print(f"Found {len(statements):,} SQL statements")
print()

print("Connecting to database...")
conn = sqlite3.connect(db_path)
conn.execute("PRAGMA foreign_keys = OFF;")
cursor = conn.cursor()

tables_created = 0
rows_inserted = 0
errors = 0

print("Executing statements...")
print()

for i, statement in enumerate(statements):
    statement = statement.strip()
    if not statement or statement.startswith('--'):
        continue
    
    # Fix CREATE TABLE for SQLite
    if statement.upper().startswith('CREATE TABLE'):
        # Fix id column to be INTEGER PRIMARY KEY (handle bigint(20) NOT NULL AUTO_INCREMENT)
        # First, handle the id column definition
        statement = re.sub(
            r'"id"\s+INTEGER\s+NOT\s+NULL(\s+AUTOINCREMENT)?',
            r'"id" INTEGER PRIMARY KEY',
            statement,
            flags=re.IGNORECASE
        )
        # Remove UNIQUE KEY definitions (handle both backticks and quotes)
        statement = re.sub(r',\s*UNIQUE\s+KEY\s+[^,)]+\s*\([^)]+\)', '', statement, flags=re.IGNORECASE)
        # Remove KEY definitions
        statement = re.sub(r',\s*KEY\s+[^,)]+\s*\([^)]+\)', '', statement, flags=re.IGNORECASE)
        # Remove any remaining PRIMARY KEY constraint at the end
        statement = re.sub(r',\s*PRIMARY\s+KEY\s*\([^)]+\)', '', statement, flags=re.IGNORECASE)
        # Clean up any trailing commas before closing paren
        statement = re.sub(r',\s*\)', ')', statement)
    
    try:
        cursor.execute(statement)
        
        if statement.upper().startswith('CREATE TABLE'):
            tables_created += 1
            print(f"[OK] Created table: patient_data")
        elif statement.upper().startswith('INSERT INTO'):
            rows_inserted += 1
            if rows_inserted % 1000 == 0:
                print(f"  ... {rows_inserted:,} rows inserted")
                
    except sqlite3.Error as e:
        error_msg = str(e).lower()
        if 'already exists' not in error_msg and 'UNIQUE constraint' not in error_msg:
            errors += 1
            if errors <= 5:
                print(f"  [WARNING] {str(e)[:150]}")

conn.commit()
conn.close()

print()
print("="*70)
print("IMPORT COMPLETE")
print("="*70)
print(f"Tables created: {tables_created}")
print(f"Rows inserted: {rows_inserted:,}")
if errors > 5:
    print(f"Warnings: {errors} (first 5 shown)")
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
        print("\nSample patients:")
        for row in cursor.fetchall():
            print(f"  ID: {row[0]}, Name: {row[1]} {row[2]}, DOB: {row[3]}")
except Exception as e:
    print(f"[ERROR] Could not verify: {e}")
finally:
    conn.close()

print()
print("="*70)
