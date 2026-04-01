#!/usr/bin/env python
"""
Search for UUID across all database tables
"""
import os
import sys
import django
import uuid

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import connection

REQUEST_ID = "a723dbe4-c2bd-486f-b131-a562d56e8add"

def search_all_tables(request_id):
    """Search for UUID across all tables"""
    try:
        request_uuid = uuid.UUID(request_id)
    except ValueError:
        print(f"❌ Invalid UUID format: {request_id}")
        return
    
    print(f"\n{'='*80}")
    print(f"Searching ALL tables for UUID: {request_id}")
    print(f"{'='*80}\n")
    
    cursor = connection.cursor()
    
    # Get all tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cursor.fetchall()]
    
    found = False
    found_tables = []
    
    for table in tables:
        try:
            # Check if table has an 'id' column
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s AND column_name = 'id'
            """, [table])
            
            if cursor.fetchone():
                # Check if UUID exists in this table
                cursor.execute(f'SELECT COUNT(*) FROM "{table}" WHERE id = %s', [str(request_uuid)])
                count = cursor.fetchone()[0]
                
                if count > 0:
                    found = True
                    found_tables.append(table)
                    print(f"✅ FOUND in: {table} ({count} record(s))")
        except Exception as e:
            # Skip tables that don't have UUID id or have other issues
            pass
    
    print(f"\n{'='*80}")
    if found:
        print(f"✅ UUID found in {len(found_tables)} table(s):")
        for table in found_tables:
            print(f"   - {table}")
    else:
        print(f"❌ UUID not found in any table")
        print(f"\nSearched {len(tables)} tables")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    search_all_tables(REQUEST_ID)








