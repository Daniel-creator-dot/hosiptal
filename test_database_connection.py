#!/usr/bin/env python3
"""
Test Database Connection Script
Quick script to verify PostgreSQL database connection and configuration
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("❌ ERROR: psycopg2 not installed")
    print("Install with: pip install psycopg2-binary")
    sys.exit(1)

# Try to get database URL from environment or .env file
try:
    from decouple import config
    DATABASE_URL = config('DATABASE_URL', default='')
except:
    DATABASE_URL = os.getenv('DATABASE_URL', '')

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL not found")
    print("Please set DATABASE_URL in your .env file or environment")
    print("Example: DATABASE_URL=postgresql://user:password@localhost:5432/dbname")
    sys.exit(1)

print("=" * 70)
print("DATABASE CONNECTION TEST")
print("=" * 70)
print(f"\nDatabase URL: {DATABASE_URL.split('@')[0]}@***/***")
print()

try:
    # Parse database URL
    if DATABASE_URL.startswith('postgresql://'):
        # Extract connection details
        url_parts = DATABASE_URL.replace('postgresql://', '').split('@')
        if len(url_parts) == 2:
            user_pass = url_parts[0].split(':')
            host_db = url_parts[1].split('/')
            host_port = host_db[0].split(':')
            
            db_config = {
                'user': user_pass[0],
                'password': user_pass[1] if len(user_pass) > 1 else '',
                'host': host_port[0],
                'port': int(host_port[1]) if len(host_port) > 1 else 5432,
                'database': host_db[1] if len(host_db) > 1 else ''
            }
        else:
            raise ValueError("Invalid DATABASE_URL format")
    else:
        raise ValueError("Only PostgreSQL URLs are supported")
    
    print(f"Connecting to: {db_config['host']}:{db_config['port']}")
    print(f"Database: {db_config['database']}")
    print(f"User: {db_config['user']}")
    print()
    
    # Test connection
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    
    print("✅ Connection successful!")
    print()
    
    # Get PostgreSQL version
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]
    print(f"PostgreSQL Version: {version.split(',')[0]}")
    print()
    
    # Get database size
    cursor.execute("""
        SELECT pg_size_pretty(pg_database_size(%s));
    """, (db_config['database'],))
    size = cursor.fetchone()[0]
    print(f"Database Size: {size}")
    print()
    
    # Count tables
    cursor.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = 'public';
    """)
    table_count = cursor.fetchone()[0]
    print(f"Tables: {table_count}")
    
    # Count Django migrations
    try:
        cursor.execute("SELECT COUNT(*) FROM django_migrations;")
        migration_count = cursor.fetchone()[0]
        print(f"Django Migrations: {migration_count}")
    except:
        print("Django Migrations: Not found (migrations not run yet)")
    
    print()
    print("=" * 70)
    print("✅ DATABASE CONNECTION TEST PASSED")
    print("=" * 70)
    
    cursor.close()
    conn.close()
    
except psycopg2.OperationalError as e:
    print(f"❌ Connection failed!")
    print(f"Error: {e}")
    print()
    print("Troubleshooting:")
    print("1. Verify PostgreSQL is running")
    print("2. Check host, port, user, and password")
    print("3. Verify database exists")
    print("4. Check firewall settings")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

