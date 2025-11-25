#!/usr/bin/env python3
"""
Script to create PostgreSQL database if it doesn't exist
Run this from the host machine (not Docker) if you have psycopg2 installed
Or run from Docker: docker-compose exec web python create_postgresql_db.py
"""
import sys
import os

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("ERROR: psycopg2 not installed")
    print("Install with: pip install psycopg2-binary")
    sys.exit(1)

# Database configuration
# Always use host.docker.internal when running from Docker
DB_CONFIG = {
    'host': 'host.docker.internal',
    'port': 5432,
    'user': 'postgres',
    'password': '1993',
    'database': 'postgres'  # Connect to default database first
}

TARGET_DB = 'hms_db'

print("=" * 50)
print("PostgreSQL Database Setup")
print("=" * 50)
print(f"\nConnecting to PostgreSQL...")
print(f"Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
print(f"User: {DB_CONFIG['user']}")
print(f"Target Database: {TARGET_DB}")
print()

try:
    # Connect to PostgreSQL server (using default 'postgres' database)
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    print("✅ Connected to PostgreSQL server")
    
    # Check if database exists
    cursor.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s",
        (TARGET_DB,)
    )
    
    exists = cursor.fetchone()
    
    if exists:
        print(f"✅ Database '{TARGET_DB}' already exists")
    else:
        print(f"Creating database '{TARGET_DB}'...")
        cursor.execute(f'CREATE DATABASE {TARGET_DB} OWNER {DB_CONFIG["user"]}')
        print(f"✅ Database '{TARGET_DB}' created successfully!")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 50)
    print("Database Setup Complete!")
    print("=" * 50)
    print("\nNext step: Run migrations")
    print("docker-compose exec web python manage.py migrate")
    print()
    
except psycopg2.OperationalError as e:
    print(f"❌ ERROR: Could not connect to PostgreSQL")
    print(f"Error: {e}")
    print("\nPlease verify:")
    print("1. PostgreSQL Desktop is running")
    print(f"2. Password is correct: {DB_CONFIG['password']}")
    print(f"3. PostgreSQL is listening on port {DB_CONFIG['port']}")
    print(f"4. User '{DB_CONFIG['user']}' exists and has permissions")
    sys.exit(1)
except Exception as e:
    print(f"❌ ERROR: {e}")
    sys.exit(1)

