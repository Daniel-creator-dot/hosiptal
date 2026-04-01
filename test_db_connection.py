#!/usr/bin/env python
"""
Test Database Connection Script
Tests connection to local or remote database server
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')

def test_connection():
    """Test database connection and display information"""
    
    print("=" * 70)
    print("TESTING DATABASE CONNECTION")
    print("=" * 70)
    print()
    
    try:
        # Import Django and setup
        import django
        django.setup()
        
        from django.conf import settings
        from django.db import connection
        
        # Get database configuration
        db_config = settings.DATABASES['default']
        
        print("Database Configuration:")
        print("-" * 70)
        print(f"  Engine: {db_config.get('ENGINE', 'Not specified')}")
        print(f"  Name: {db_config.get('NAME', 'Not specified')}")
        print(f"  Host: {db_config.get('HOST', 'localhost')}")
        print(f"  Port: {db_config.get('PORT', 'default')}")
        print(f"  User: {db_config.get('USER', 'Not specified')}")
        print(f"  Connection Max Age: {db_config.get('CONN_MAX_AGE', 0)} seconds")
        print()
        
        # Check SSL settings
        options = db_config.get('OPTIONS', {})
        if 'sslmode' in options:
            print(f"  [SSL] Mode: {options['sslmode']}")
            print()
        
        # Test connection
        print("Testing connection...")
        print("-" * 70)
        
        with connection.cursor() as cursor:
            # Test query
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            
            if result and result[0] == 1:
                print("[SUCCESS] Database connection SUCCESSFUL!")
                print()
                
                # Get database info
                db_engine = db_config.get('ENGINE', '')
                
                if 'postgresql' in db_engine:
                    print("PostgreSQL Information:")
                    print("-" * 70)
                    
                    # PostgreSQL version
                    cursor.execute("SELECT version();")
                    version = cursor.fetchone()[0]
                    print(f"  Version: {version.split(',')[0]}")
                    
                    # Current database
                    cursor.execute("SELECT current_database();")
                    db_name = cursor.fetchone()[0]
                    print(f"  Database: {db_name}")
                    
                    # Connection info
                    cursor.execute("SELECT inet_server_addr(), inet_server_port();")
                    server_info = cursor.fetchone()
                    if server_info[0]:
                        print(f"  Server Address: {server_info[0]}")
                        print(f"  Server Port: {server_info[1]}")
                    
                    # Check if SSL is active (using pg_is_in_recovery as alternative check)
                    # Note: ssl_is_used() doesn't exist in PostgreSQL 15, so we check SSL mode from connection
                    try:
                        # Try to get SSL status from pg_stat_ssl if available
                        cursor.execute("""
                            SELECT EXISTS (
                                SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
                            );
                        """)
                        # For now, just report SSL mode from settings
                        ssl_mode = options.get('sslmode', 'prefer')
                        if ssl_mode and ssl_mode != 'disable':
                            print(f"  [SSL] Mode: {ssl_mode} (configured)")
                        else:
                            print("  [WARNING] SSL: Not configured (Unencrypted)")
                    except Exception:
                        # If check fails, just report SSL mode from settings
                        ssl_mode = options.get('sslmode', 'prefer')
                        if ssl_mode and ssl_mode != 'disable':
                            print(f"  [SSL] Mode: {ssl_mode} (configured)")
                        else:
                            print("  [WARNING] SSL: Not configured (Unencrypted)")
                    
                    # Check number of connections
                    cursor.execute("""
                        SELECT count(*) 
                        FROM pg_stat_activity 
                        WHERE datname = current_database();
                    """)
                    connections = cursor.fetchone()[0]
                    print(f"  Active Connections: {connections}")
                    
                elif 'mysql' in db_engine:
                    print("MySQL Information:")
                    print("-" * 70)
                    
                    # MySQL version
                    cursor.execute("SELECT VERSION();")
                    version = cursor.fetchone()[0]
                    print(f"  Version: {version}")
                    
                    # Current database
                    cursor.execute("SELECT DATABASE();")
                    db_name = cursor.fetchone()[0]
                    print(f"  Database: {db_name}")
                    
                    # Check SSL
                    cursor.execute("SHOW STATUS LIKE 'Ssl_cipher';")
                    ssl_cipher = cursor.fetchone()
                    if ssl_cipher and ssl_cipher[1]:
                        print(f"  [SSL] Active (Cipher: {ssl_cipher[1]})")
                    else:
                        print("  [WARNING] SSL: Not active")
                    
                    # Connection info
                    cursor.execute("SELECT USER(), @@hostname, @@port;")
                    conn_info = cursor.fetchone()
                    print(f"  Connected as: {conn_info[0]}")
                    print(f"  Server: {conn_info[1]}")
                    print(f"  Port: {conn_info[2]}")
                
                elif 'sqlite' in db_engine:
                    print("SQLite Information:")
                    print("-" * 70)
                    
                    # SQLite version
                    cursor.execute("SELECT sqlite_version();")
                    version = cursor.fetchone()[0]
                    print(f"  Version: {version}")
                    
                    # Database file
                    print(f"  Database File: {db_config.get('NAME', 'Unknown')}")
                    print()
                    print("  [WARNING] SQLite is for development only!")
                    print("            Use PostgreSQL or MySQL for production.")
                
                print()
                print("=" * 70)
                print("[SUCCESS] ALL CHECKS PASSED!")
                print("=" * 70)
                print()
                print("Next steps:")
                print("  1. Run migrations: python manage.py migrate")
                print("  2. Create superuser: python manage.py createsuperuser")
                print("  3. Start server: python manage.py runserver")
                print()
                
                return True
                
            else:
                print("[ERROR] Connection test failed!")
                return False
                
    except ImportError as e:
        print("[ERROR] Missing required package")
        print()
        print(f"  Error: {str(e)}")
        print()
        print("Fix:")
        
        if 'psycopg2' in str(e):
            print("  Install PostgreSQL driver:")
            print("    pip install psycopg2-binary")
        elif 'MySQLdb' in str(e) or 'pymysql' in str(e):
            print("  Install MySQL driver:")
            print("    pip install mysqlclient")
        else:
            print(f"  pip install {str(e).split()[-1]}")
        
        print()
        return False
        
    except Exception as e:
        print("[ERROR] CONNECTION FAILED!")
        print()
        print(f"Error: {str(e)}")
        print()
        print("Common Solutions:")
        print("-" * 70)
        print()
        print("1. Check DATABASE_URL in .env file")
        print("   Format: postgresql://user:password@host:port/database")
        print()
        print("2. Verify database server is running")
        print("   ping <database-server-ip>")
        print()
        print("3. Check firewall allows port 5432 (PostgreSQL)")
        print("   telnet <database-server-ip> 5432")
        print()
        print("4. Verify user credentials")
        print("   psql -h <host> -U <user> -d <database>")
        print()
        print("5. Check pg_hba.conf allows your IP")
        print("   (On database server)")
        print()
        print("6. For SSL errors, try:")
        print("   DATABASE_SSL_MODE=disable (testing only)")
        print("   DATABASE_SSL_MODE=require (production)")
        print()
        
        return False

if __name__ == '__main__':
    success = test_connection()
    sys.exit(0 if success else 1)

