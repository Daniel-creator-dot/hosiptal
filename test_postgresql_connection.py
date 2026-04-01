#!/usr/bin/env python
"""
Test PostgreSQL Connection
Diagnoses database connection issues
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.conf import settings
from django.db import connection
from django.core.exceptions import ImproperlyConfigured

def test_connection():
    """Test PostgreSQL connection and provide diagnostics"""
    
    print("=" * 60)
    print("PostgreSQL Connection Diagnostic")
    print("=" * 60)
    print()
    
    # Check database configuration
    print("1. Checking database configuration...")
    try:
        db_config = settings.DATABASES['default']
        print(f"   [OK] Database engine: {db_config.get('ENGINE', 'Unknown')}")
        print(f"   [OK] Database name: {db_config.get('NAME', 'Unknown')}")
        print(f"   [OK] Database user: {db_config.get('USER', 'Unknown')}")
        print(f"   [OK] Database host: {db_config.get('HOST', 'Unknown')}")
        print(f"   [OK] Database port: {db_config.get('PORT', 'Unknown')}")
        
        # Check if password is set (don't print it)
        password = db_config.get('PASSWORD', '')
        if password:
            print(f"   [OK] Password: {'*' * len(password)} (set)")
        else:
            print(f"   [WARNING] Password: (not set)")
            
    except Exception as e:
        print(f"   [ERROR] Error reading configuration: {e}")
        return False
    
    print()
    
    # Test connection
    print("2. Testing database connection...")
    try:
        connection.ensure_connection()
        print("   [OK] Connection successful!")
        print()
        
        # Get database info
        with connection.cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            print(f"   PostgreSQL version: {version}")
            
            cursor.execute("SELECT current_database(), current_user;")
            db_name, db_user = cursor.fetchone()
            print(f"   Connected to database: {db_name}")
            print(f"   Connected as user: {db_user}")
            
            # Check if tables exist
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            table_count = cursor.fetchone()[0]
            print(f"   Tables in database: {table_count}")
            
        print()
        print("=" * 60)
        print("[SUCCESS] Database connection is working!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"   [ERROR] Connection failed!")
        print()
        print("=" * 60)
        print("ERROR DETAILS")
        print("=" * 60)
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print()
        
        # Provide specific guidance based on error
        error_str = str(e).lower()
        
        if "password authentication failed" in error_str:
            print("DIAGNOSIS: Password authentication failed")
            print()
            print("SOLUTIONS:")
            print("1. Run: FIX_POSTGRESQL_AUTH.bat")
            print("2. Or manually create/update user in pgAdmin:")
            print("   - User: hms_user")
            print("   - Password: hms_password")
            print("3. Or update .env file with correct password")
            
        elif "does not exist" in error_str or "database" in error_str.lower():
            print("DIAGNOSIS: Database or user does not exist")
            print()
            print("SOLUTIONS:")
            print("1. Run: FIX_POSTGRESQL_AUTH.bat")
            print("2. Or create database manually in pgAdmin:")
            print("   - Database name: hms_db")
            print("   - Owner: hms_user")
            
        elif "could not connect" in error_str or "connection refused" in error_str:
            print("DIAGNOSIS: Cannot connect to PostgreSQL server")
            print()
            print("SOLUTIONS:")
            print("1. Check if PostgreSQL service is running:")
            print("   - Open Services: services.msc")
            print("   - Find 'postgresql' service and start it")
            print("2. Verify PostgreSQL is listening on port 5432:")
            print("   - Run: netstat -an | findstr 5432")
            
        elif "role" in error_str and "does not exist" in error_str:
            print("DIAGNOSIS: PostgreSQL user does not exist")
            print()
            print("SOLUTIONS:")
            print("1. Run: FIX_POSTGRESQL_AUTH.bat")
            print("2. Or create user manually in pgAdmin:")
            print("   - Right-click 'Login/Group Roles' → Create")
            print("   - Name: hms_user")
            print("   - Password: hms_password")
            
        else:
            print("DIAGNOSIS: Unknown connection error")
            print()
            print("GENERAL SOLUTIONS:")
            print("1. Verify PostgreSQL is installed and running")
            print("2. Check .env file has correct DATABASE_URL")
            print("3. Run: FIX_POSTGRESQL_AUTH.bat")
            print("4. Check PostgreSQL logs for more details")
        
        print()
        print("=" * 60)
        return False

if __name__ == '__main__':
    success = test_connection()
    sys.exit(0 if success else 1)

