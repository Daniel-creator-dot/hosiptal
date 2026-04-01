#!/usr/bin/env python
"""
Fix common server deployment errors
Run this script on your server after deployment
"""
import os
import sys
import subprocess
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')

import django
django.setup()

from django.conf import settings
from django.core.management import call_command


def fix_permissions():
    """Fix file permissions for static and media files"""
    print("=" * 60)
    print("Fixing File Permissions")
    print("=" * 60)
    
    directories = [
        settings.STATIC_ROOT,
        settings.MEDIA_ROOT,
        BASE_DIR / 'logs',
        BASE_DIR / 'staticfiles',
    ]
    
    for directory in directories:
        if directory and directory.exists():
            try:
                # Set permissions: 755 for directories
                os.chmod(directory, 0o755)
                print(f"✅ Fixed permissions for: {directory}")
                
                # Recursively fix permissions for files
                for root, dirs, files in os.walk(directory):
                    for d in dirs:
                        os.chmod(os.path.join(root, d), 0o755)
                    for f in files:
                        os.chmod(os.path.join(root, f), 0o644)
                
                print(f"✅ Fixed recursive permissions for: {directory}")
            except Exception as e:
                print(f"⚠️  Warning: Could not fix permissions for {directory}: {e}")


def create_directories():
    """Create necessary directories if they don't exist"""
    print("\n" + "=" * 60)
    print("Creating Required Directories")
    print("=" * 60)
    
    directories = [
        settings.STATIC_ROOT,
        settings.MEDIA_ROOT,
        BASE_DIR / 'logs',
        BASE_DIR / 'staticfiles',
        BASE_DIR / 'media' / 'patient_profiles',
        BASE_DIR / 'media' / 'documents',
        BASE_DIR / 'media' / 'uploads',
    ]
    
    for directory in directories:
        if directory:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                print(f"✅ Created/Verified: {directory}")
            except Exception as e:
                print(f"⚠️  Warning: Could not create {directory}: {e}")


def collect_static_files():
    """Collect static files"""
    print("\n" + "=" * 60)
    print("Collecting Static Files")
    print("=" * 60)
    
    try:
        call_command('collectstatic', '--noinput', '--clear', verbosity=1)
        print("✅ Static files collected successfully")
    except Exception as e:
        print(f"❌ Error collecting static files: {e}")
        return False
    return True


def check_database_connection():
    """Check database connection"""
    print("\n" + "=" * 60)
    print("Checking Database Connection")
    print("=" * 60)
    
    try:
        from django.db import connection
        connection.ensure_connection()
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check DATABASE_URL in .env file")
        print("2. Verify PostgreSQL is running")
        print("3. Check database credentials")
        return False


def check_settings():
    """Check critical settings"""
    print("\n" + "=" * 60)
    print("Checking Settings")
    print("=" * 60)
    
    issues = []
    
    # Check SECRET_KEY
    if settings.SECRET_KEY.startswith('django-insecure-'):
        issues.append("⚠️  SECRET_KEY is using default insecure value")
    
    # Check DEBUG
    if settings.DEBUG:
        print("⚠️  DEBUG is True (should be False in production)")
    else:
        print("✅ DEBUG is False (production mode)")
    
    # Check ALLOWED_HOSTS
    if '*' in settings.ALLOWED_HOSTS and not settings.DEBUG:
        issues.append("⚠️  ALLOWED_HOSTS contains '*' (security risk in production)")
    else:
        print(f"✅ ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
    
    # Check static files
    if not settings.STATIC_ROOT:
        issues.append("❌ STATIC_ROOT is not set")
    else:
        print(f"✅ STATIC_ROOT: {settings.STATIC_ROOT}")
    
    # Check media files
    if not settings.MEDIA_ROOT:
        issues.append("❌ MEDIA_ROOT is not set")
    else:
        print(f"✅ MEDIA_ROOT: {settings.MEDIA_ROOT}")
    
    if issues:
        print("\nIssues found:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("✅ All critical settings are configured")
    
    return len(issues) == 0


def run_migrations():
    """Run database migrations"""
    print("\n" + "=" * 60)
    print("Running Database Migrations")
    print("=" * 60)
    
    try:
        call_command('migrate', '--noinput', verbosity=1)
        print("✅ Migrations completed successfully")
        return True
    except Exception as e:
        print(f"❌ Migration error: {e}")
        return False


def main():
    """Main function"""
    print("\n" + "=" * 60)
    print("SERVER DEPLOYMENT ERROR FIXER")
    print("=" * 60)
    print("\nThis script will fix common server deployment errors:")
    print("  - File permissions")
    print("  - Missing directories")
    print("  - Static files collection")
    print("  - Database connection")
    print("  - Settings validation")
    print("  - Database migrations")
    print()
    
    # Create directories first
    create_directories()
    
    # Fix permissions
    if os.name != 'nt':  # Not Windows
        fix_permissions()
    else:
        print("\n⚠️  Skipping permission fixes (Windows)")
    
    # Check settings
    settings_ok = check_settings()
    
    # Check database
    db_ok = check_database_connection()
    
    if db_ok:
        # Run migrations
        run_migrations()
    
    # Collect static files
    static_ok = collect_static_files()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Settings: {'✅ OK' if settings_ok else '⚠️  Issues found'}")
    print(f"Database: {'✅ OK' if db_ok else '❌ Failed'}")
    print(f"Static Files: {'✅ OK' if static_ok else '❌ Failed'}")
    print(f"Directories: ✅ Created/Verified")
    
    if settings_ok and db_ok and static_ok:
        print("\n🎉 All checks passed! Server should be ready.")
    else:
        print("\n⚠️  Some issues found. Please review the output above.")
    
    print("\n" + "=" * 60)


if __name__ == '__main__':
    main()



