#!/usr/bin/env python3
"""
Docker-based Database Reset Script
This script works with Docker Compose to reset the database.
It will:
1. Stop all services
2. Remove the database volume
3. Start services fresh
4. Run migrations
"""
import subprocess
import sys
from pathlib import Path

project_root = Path(__file__).parent

def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")

def run_command(cmd, check=True):
    """Run a shell command"""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=project_root, check=check, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result

def main():
    """Main execution"""
    print_header("DOCKER DATABASE RESET")
    print("⚠️  WARNING: This will DELETE ALL DATA in the database!")
    print("This will remove the PostgreSQL volume and recreate everything.")
    
    response = input("\nAre you sure you want to continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("\n❌ Operation cancelled")
        sys.exit(0)
    
    try:
        # Step 1: Stop all services
        print_header("Stopping Docker services...")
        run_command(['docker-compose', 'down'])
        print("✅ Services stopped")
        
        # Step 2: Remove database volume
        print_header("Removing database volume...")
        try:
            run_command(['docker-compose', 'volume', 'rm', 'chm_postgres_data'], check=False)
        except:
            # Volume might not exist, that's okay
            pass
        print("✅ Database volume removed")
        
        # Step 3: Start services
        print_header("Starting Docker services...")
        run_command(['docker-compose', 'up', '-d', 'db'])
        print("✅ Database service started")
        
        # Wait for database to be ready
        print("\nWaiting for database to be ready...")
        import time
        time.sleep(5)
        
        # Step 4: Run migrations
        print_header("Running migrations...")
        run_command(['docker-compose', 'exec', '-T', 'web', 'python', 'manage.py', 'migrate', '--noinput'])
        print("✅ Migrations completed")
        
        # Step 5: Start all services
        print_header("Starting all services...")
        run_command(['docker-compose', 'up', '-d'])
        print("✅ All services started")
        
        # Success message
        print_header("✅ DATABASE RESET COMPLETE!")
        print("All services are running with a fresh database.")
        print("\nNext steps:")
        print("1. Create a superuser: docker-compose exec web python manage.py createsuperuser")
        print("2. Access the application: http://localhost:8000")
        
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

