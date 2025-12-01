"""
Import patient_data.sql into PostgreSQL
Optimized for Docker PostgreSQL setup
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import connection
from django.core.management import call_command
import re

def convert_mysql_to_postgresql(sql_content):
    """Convert MySQL syntax to PostgreSQL"""
    # Remove MySQL-specific syntax
    sql_content = re.sub(r'`([^`]+)`', r'"\1"', sql_content)  # Backticks to double quotes
    sql_content = re.sub(r'AUTO_INCREMENT', 'SERIAL', sql_content)
    sql_content = re.sub(r'bigint\(20\)', 'BIGINT', sql_content)
    sql_content = re.sub(r'int\(11\)', 'INTEGER', sql_content)
    sql_content = re.sub(r'varchar\((\d+)\)', r'VARCHAR(\1)', sql_content)
    sql_content = re.sub(r'longtext', 'TEXT', sql_content)
    sql_content = re.sub(r'ENGINE=InnoDB.*?;', ';', sql_content, flags=re.DOTALL)
    sql_content = re.sub(r'DEFAULT CHARSET.*?;', ';', sql_content, flags=re.DOTALL)
    
    return sql_content

def import_patient_data():
    """Import patient_data.sql file"""
    print("="*70)
    print("   IMPORTING PATIENT_DATA INTO POSTGRESQL")
    print("="*70)
    print()
    
    sql_file = os.path.join(os.path.dirname(__file__), 'import', 'legacy', 'patient_data.sql')
    
    if not os.path.exists(sql_file):
        print(f"❌ Error: File not found: {sql_file}")
        return False
    
    print(f"📁 SQL File: {sql_file}")
    file_size = os.path.getsize(sql_file) / (1024 * 1024)  # MB
    print(f"📊 File Size: {file_size:.2f} MB")
    print()
    
    # Read SQL file
    print("📖 Reading SQL file...")
    with open(sql_file, 'r', encoding='utf-8', errors='ignore') as f:
        sql_content = f.read()
    
    print(f"✅ Read {len(sql_content):,} characters")
    print()
    
    # Convert MySQL to PostgreSQL
    print("🔄 Converting MySQL syntax to PostgreSQL...")
    sql_content = convert_mysql_to_postgresql(sql_content)
    print("✅ Conversion complete")
    print()
    
    # Split into statements
    print("✂️  Splitting SQL statements...")
    # Remove comments and split by semicolon
    statements = []
    current_statement = ""
    
    for line in sql_content.split('\n'):
        line = line.strip()
        if not line or line.startswith('--'):
            continue
        
        current_statement += line + '\n'
        
        if line.endswith(';'):
            stmt = current_statement.strip()
            if stmt and not stmt.startswith('--'):
                statements.append(stmt)
            current_statement = ""
    
    print(f"✅ Found {len(statements):,} SQL statements")
    print()
    
    # Execute statements
    print("🚀 Executing SQL statements...")
    print("   (This may take several minutes for large files)")
    print()
    
    success_count = 0
    error_count = 0
    
    with connection.cursor() as cursor:
        for i, statement in enumerate(statements, 1):
            try:
                # Skip DROP TABLE if table doesn't exist yet
                if 'DROP TABLE' in statement.upper():
                    table_name = re.search(r'DROP TABLE\s+"?(\w+)"?', statement, re.IGNORECASE)
                    if table_name:
                        table = table_name.group(1)
                        # Check if table exists
                        cursor.execute("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_schema = 'public' 
                                AND table_name = %s
                            )
                        """, [table])
                        if not cursor.fetchone()[0]:
                            continue  # Skip DROP if table doesn't exist
                
                cursor.execute(statement)
                success_count += 1
                
                # Progress indicator
                if i % 100 == 0:
                    print(f"   Processed {i:,} / {len(statements):,} statements...")
                    
            except Exception as e:
                error_count += 1
                if error_count <= 5:  # Show first 5 errors
                    print(f"   ⚠️  Error in statement {i}: {str(e)[:100]}")
                elif error_count == 6:
                    print(f"   ... (suppressing further error messages)")
    
    print()
    print("="*70)
    print("   IMPORT SUMMARY")
    print("="*70)
    print()
    print(f"✅ Successful: {success_count:,} statements")
    print(f"❌ Errors: {error_count:,} statements")
    print()
    
    # Verify import
    print("🔍 Verifying import...")
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM patient_data')
            count = cursor.fetchone()[0]
            print(f"✅ patient_data table now contains: {count:,} records")
            print()
            
            if count > 0:
                # Show sample
                cursor.execute('SELECT fname, lname, DOB, sex FROM patient_data LIMIT 5')
                samples = cursor.fetchall()
                print("   Sample records:")
                for s in samples:
                    print(f"      - {s[0]} {s[1]} (DOB: {s[2]}, Sex: {s[3]})")
                print()
    except Exception as e:
        print(f"   ⚠️  Could not verify: {str(e)}")
        print()
    
    return success_count > 0

if __name__ == '__main__':
    try:
        success = import_patient_data()
        if success:
            print("✅ Import completed successfully!")
            print()
            print("Next steps:")
            print("  1. Run: docker-compose exec web python manage.py check_patient_database")
            print("  2. View patients at: http://127.0.0.1:8000/hms/patients/")
            print("  3. Use 'Source' filter to view legacy patients")
        else:
            print("❌ Import had errors. Check the output above.")
    except KeyboardInterrupt:
        print()
        print("⚠️  Import canceled by user")
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()


