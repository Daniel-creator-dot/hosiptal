#!/usr/bin/env python
"""
Database connectivity diagnostic script
Run this on your VPS to check database connection issues
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.conf import settings
from django.db import connection
from django.core.management import execute_from_command_line

def check_database():
    """Check database connectivity and configuration"""
    print("=" * 60)
    print("DATABASE DIAGNOSTIC TOOL")
    print("=" * 60)
    print()
    
    # Check database configuration
    print("1. Database Configuration:")
    print("-" * 60)
    db_config = settings.DATABASES['default']
    engine = db_config.get('ENGINE', 'Unknown')
    name = db_config.get('NAME', 'Unknown')
    user = db_config.get('USER', 'Unknown')
    host = db_config.get('HOST', 'localhost')
    port = db_config.get('PORT', 'default')
    
    print(f"   Engine: {engine}")
    print(f"   Database: {name}")
    print(f"   User: {user}")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print()
    
    # Check environment variables
    print("2. Environment Variables:")
    print("-" * 60)
    database_url = os.environ.get('DATABASE_URL', 'Not set')
    print(f"   DATABASE_URL: {database_url[:50]}..." if len(database_url) > 50 else f"   DATABASE_URL: {database_url}")
    print()
    
    # Test database connection
    print("3. Testing Database Connection:")
    print("-" * 60)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            print(f"   ✅ Connection successful!")
            print(f"   Database version: {version[0][:50]}...")
    except Exception as e:
        print(f"   ❌ Connection failed!")
        print(f"   Error: {str(e)}")
        print()
        print("   Common fixes:")
        print("   1. Check if PostgreSQL is running: sudo systemctl status postgresql")
        print("   2. Check database exists: sudo -u postgres psql -l")
        print("   3. Check user permissions: sudo -u postgres psql -c '\\du'")
        print("   4. Check .env file has correct DATABASE_URL")
        return False
    
    print()
    
    # Check if tables exist
    print("4. Checking Database Tables:")
    print("-" * 60)
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            tables = cursor.fetchall()
            print(f"   ✅ Found {len(tables)} tables")
            if len(tables) > 0:
                print(f"   Sample tables: {', '.join([t[0] for t in tables[:5]])}")
            else:
                print("   ⚠️  No tables found - you may need to run migrations")
    except Exception as e:
        print(f"   ❌ Error checking tables: {str(e)}")
    
    print()
    
    # Check auth_user table specifically
    print("5. Checking Authentication Tables:")
    print("-" * 60)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM auth_user;")
            user_count = cursor.fetchone()[0]
            print(f"   ✅ auth_user table exists")
            print(f"   Total users: {user_count}")
            
            if user_count == 0:
                print("   ⚠️  No users found - create superuser with: python manage.py createsuperuser")
    except Exception as e:
        print(f"   ❌ auth_user table not found or error: {str(e)}")
        print("   Run migrations: python manage.py migrate")
    
    print()
    print("=" * 60)
    print("Diagnostic complete!")
    print("=" * 60)
    
    return True

if __name__ == '__main__':
    try:
        check_database()
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
