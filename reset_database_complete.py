#!/usr/bin/env python3
"""
Complete Database Reset Script
This script will:
1. Drop all existing PostgreSQL databases (hms_db and related)
2. Create a fresh PostgreSQL database
3. Run all Django migrations
4. Verify the setup
5. Optionally create a superuser

WARNING: This will DELETE ALL DATA in the database!
"""
import sys
import os
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    from psycopg2 import sql
except ImportError:
    print("❌ ERROR: psycopg2 not installed")
    print("Install with: pip install psycopg2-binary")
    sys.exit(1)

# Database configuration
# These can be overridden via environment variables
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
    'database': 'postgres'  # Connect to default database first
}

TARGET_DB = os.getenv('TARGET_DB', 'hms_db')
TARGET_USER = os.getenv('TARGET_USER', 'hms_user')
TARGET_PASSWORD = os.getenv('TARGET_PASSWORD', 'hms_password')

def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")

def print_step(step_num, text):
    """Print a step number and text"""
    print(f"\n[Step {step_num}] {text}")
    print("-" * 70)

def connect_to_postgres():
    """Connect to PostgreSQL server"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ ERROR: Could not connect to PostgreSQL")
        print(f"Error: {e}")
        print("\nPlease verify:")
        print(f"1. PostgreSQL is running")
        print(f"2. Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        print(f"3. User: {DB_CONFIG['user']}")
        print(f"4. Password is correct")
        sys.exit(1)

def drop_all_databases(conn):
    """Drop all HMS-related databases"""
    print_step(1, "Dropping existing databases...")
    
    cursor = conn.cursor()
    
    # Get list of all databases
    cursor.execute("""
        SELECT datname FROM pg_database 
        WHERE datistemplate = false 
        AND datname NOT IN ('postgres', 'template0', 'template1')
        AND (datname LIKE 'hms%' OR datname = %s)
        ORDER BY datname;
    """, (TARGET_DB,))
    
    databases = [row[0] for row in cursor.fetchall()]
    
    if not databases:
        print("✅ No existing databases to drop")
        return
    
    print(f"Found {len(databases)} database(s) to drop:")
    for db in databases:
        print(f"  - {db}")
    
    # Drop each database
    for db_name in databases:
        try:
            # Terminate all connections to the database first
            print(f"\n  Terminating connections to '{db_name}'...")
            cursor.execute("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid();
            """, (db_name,))
            
            # Drop the database
            print(f"  Dropping database '{db_name}'...")
            cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(db_name)
            ))
            print(f"  ✅ Dropped '{db_name}'")
        except Exception as e:
            print(f"  ⚠️  Warning: Could not drop '{db_name}': {e}")
    
    cursor.close()
    print("\n✅ All databases dropped successfully")

def create_database_and_user(conn):
    """Create the target database and user"""
    print_step(2, "Creating database and user...")
    
    cursor = conn.cursor()
    
    # Create user if it doesn't exist
    try:
        print(f"  Creating user '{TARGET_USER}'...")
        cursor.execute(sql.SQL("CREATE USER {} WITH PASSWORD %s CREATEDB").format(
            sql.Identifier(TARGET_USER)
        ), (TARGET_PASSWORD,))
        print(f"  ✅ User '{TARGET_USER}' created")
    except psycopg2.errors.DuplicateObject:
        print(f"  ℹ️  User '{TARGET_USER}' already exists, updating password...")
        try:
            cursor.execute(sql.SQL("ALTER USER {} WITH PASSWORD %s CREATEDB").format(
                sql.Identifier(TARGET_USER)
            ), (TARGET_PASSWORD,))
            print(f"  ✅ Password updated for '{TARGET_USER}'")
        except Exception as e:
            print(f"  ⚠️  Could not update password (may need manual update): {e}")
    
    # Create database
    try:
        print(f"\n  Creating database '{TARGET_DB}'...")
        cursor.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
            sql.Identifier(TARGET_DB),
            sql.Identifier(TARGET_USER)
        ))
        print(f"  ✅ Database '{TARGET_DB}' created")
    except psycopg2.errors.DuplicateDatabase:
        print(f"  ⚠️  Database '{TARGET_DB}' already exists (should have been dropped)")
    
    # Grant privileges
    print(f"\n  Granting privileges...")
    cursor.execute(sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
        sql.Identifier(TARGET_DB),
        sql.Identifier(TARGET_USER)
    ))
    print(f"  ✅ Privileges granted")
    
    cursor.close()
    print("\n✅ Database and user setup complete")

def run_migrations():
    """Run Django migrations"""
    print_step(3, "Running Django migrations...")
    
    # Set environment variable for database URL
    db_url = f"postgresql://{TARGET_USER}:{TARGET_PASSWORD}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{TARGET_DB}"
    os.environ['DATABASE_URL'] = db_url
    
    try:
        # Run migrations
        print("  Running: python manage.py migrate")
        result = subprocess.run(
            ['python', 'manage.py', 'migrate', '--noinput'],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        if result.stderr:
            print("Warnings:", result.stderr)
        print("  ✅ Migrations completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"  ❌ ERROR: Migrations failed")
        print(f"  Error: {e}")
        print(f"  Output: {e.stdout}")
        print(f"  Error output: {e.stderr}")
        sys.exit(1)

def verify_setup():
    """Verify the database setup"""
    print_step(4, "Verifying database setup...")
    
    db_url = f"postgresql://{TARGET_USER}:{TARGET_PASSWORD}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{TARGET_DB}"
    
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """)
        table_count = cursor.fetchone()[0]
        
        print(f"  ✅ Database connection successful")
        print(f"  ✅ Found {table_count} table(s) in database")
        
        # Check Django migrations
        cursor.execute("""
            SELECT COUNT(*) 
            FROM django_migrations;
        """)
        migration_count = cursor.fetchone()[0]
        print(f"  ✅ Found {migration_count} migration(s) applied")
        
        cursor.close()
        conn.close()
        
        print("\n✅ Database verification complete")
    except Exception as e:
        print(f"  ❌ ERROR: Verification failed: {e}")
        sys.exit(1)

def update_env_file():
    """Update .env file with PostgreSQL configuration"""
    print_step(5, "Updating .env file...")
    
    env_file = project_root / '.env'
    env_example = project_root / 'compose.env'
    
    # Read existing .env or use compose.env as template
    if env_file.exists():
        with open(env_file, 'r') as f:
            content = f.read()
    elif env_example.exists():
        with open(env_example, 'r') as f:
            content = f.read()
    else:
        content = ""
    
    # Update DATABASE_URL
    db_url = f"postgresql://{TARGET_USER}:{TARGET_PASSWORD}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{TARGET_DB}"
    
    lines = content.split('\n')
    updated = False
    new_lines = []
    
    for line in lines:
        if line.startswith('DATABASE_URL='):
            new_lines.append(f'DATABASE_URL={db_url}')
            updated = True
        else:
            new_lines.append(line)
    
    if not updated:
        # Add DATABASE_URL if it doesn't exist
        new_lines.append(f'DATABASE_URL={db_url}')
    
    # Write back to .env
    with open(env_file, 'w') as f:
        f.write('\n'.join(new_lines))
    
    print(f"  ✅ Updated .env file with PostgreSQL configuration")
    print(f"  Database URL: {db_url}")

def main():
    """Main execution"""
    print_header("COMPLETE DATABASE RESET")
    print("⚠️  WARNING: This will DELETE ALL DATA in the database!")
    print(f"Target Database: {TARGET_DB}")
    print(f"Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    
    # Check for --yes flag for non-interactive mode
    auto_confirm = '--yes' in sys.argv or '-y' in sys.argv
    
    if not auto_confirm:
        response = input("\nAre you sure you want to continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("\n❌ Operation cancelled")
            sys.exit(0)
    else:
        print("\n⚠️  Auto-confirming (--yes flag detected)")
    
    try:
        # Step 1: Connect to PostgreSQL
        print_header("Connecting to PostgreSQL...")
        conn = connect_to_postgres()
        print("✅ Connected to PostgreSQL server")
        
        # Step 2: Drop all databases
        drop_all_databases(conn)
        
        # Step 3: Create database and user
        create_database_and_user(conn)
        
        # Close connection
        conn.close()
        
        # Step 4: Run migrations
        run_migrations()
        
        # Step 5: Verify setup
        verify_setup()
        
        # Step 6: Update .env file
        update_env_file()
        
        # Success message
        print_header("✅ DATABASE RESET COMPLETE!")
        print(f"Database: {TARGET_DB}")
        print(f"User: {TARGET_USER}")
        print(f"Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        print("\nNext steps:")
        print("1. Create a superuser: python manage.py createsuperuser")
        print("2. Start the server: python manage.py runserver")
        print("3. Or use Docker: docker-compose up -d")
        
    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

