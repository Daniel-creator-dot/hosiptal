#!/usr/bin/env python
"""
Server Deployment Fixes - Pre-deployment checks and fixes
Run this before deploying to server
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def check_and_fix_paths():
    """Check and fix path-related issues"""
    print("=" * 60)
    print("Checking Paths")
    print("=" * 60)
    
    issues = []
    
    # Check if using absolute paths
    if str(BASE_DIR).startswith('/'):
        print(f"✅ Using absolute path: {BASE_DIR}")
    else:
        issues.append(f"⚠️  Using relative path: {BASE_DIR}")
    
    # Check critical directories
    critical_dirs = [
        BASE_DIR / 'staticfiles',
        BASE_DIR / 'media',
        BASE_DIR / 'logs',
    ]
    
    for dir_path in critical_dirs:
        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"✅ Created: {dir_path}")
            except Exception as e:
                issues.append(f"❌ Could not create {dir_path}: {e}")
        else:
            print(f"✅ Exists: {dir_path}")
    
    return issues


def check_environment_variables():
    """Check critical environment variables"""
    print("\n" + "=" * 60)
    print("Checking Environment Variables")
    print("=" * 60)
    
    required_vars = ['DATABASE_URL']
    optional_vars = ['SECRET_KEY', 'DEBUG', 'ALLOWED_HOSTS', 'STATIC_ROOT', 'MEDIA_ROOT']
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
            print(f"❌ Missing required: {var}")
        else:
            print(f"✅ Found: {var}")
    
    for var in optional_vars:
        if os.getenv(var):
            print(f"✅ Found optional: {var}")
        else:
            print(f"ℹ️  Not set (optional): {var}")
    
    return missing


def check_file_permissions():
    """Check file permissions (Unix only)"""
    if os.name == 'nt':
        print("\n" + "=" * 60)
        print("Skipping Permission Check (Windows)")
        print("=" * 60)
        return []
    
    print("\n" + "=" * 60)
    print("Checking File Permissions")
    print("=" * 60)
    
    issues = []
    directories = [
        BASE_DIR / 'staticfiles',
        BASE_DIR / 'media',
    ]
    
    for dir_path in directories:
        if dir_path.exists():
            stat = os.stat(dir_path)
            mode = oct(stat.st_mode)[-3:]
            print(f"✅ {dir_path}: {mode}")
            
            # Check if writable
            if not os.access(dir_path, os.W_OK):
                issues.append(f"⚠️  {dir_path} is not writable")
        else:
            issues.append(f"❌ {dir_path} does not exist")
    
    return issues


def generate_server_checklist():
    """Generate server deployment checklist"""
    print("\n" + "=" * 60)
    print("Server Deployment Checklist")
    print("=" * 60)
    
    checklist = """
Before deploying to server, ensure:

1. ✅ Environment Variables Set:
   - DATABASE_URL (required)
   - SECRET_KEY (required for production)
   - DEBUG=False (for production)
   - ALLOWED_HOSTS (required for production)
   - STATIC_ROOT (optional, defaults to ./staticfiles)
   - MEDIA_ROOT (optional, defaults to ./media)

2. ✅ Directories Created:
   - staticfiles/ (for collected static files)
   - media/ (for user uploads)
   - logs/ (for application logs)

3. ✅ File Permissions:
   - staticfiles/ and media/ must be writable by web server user
   - Run: chmod -R 755 staticfiles media
   - Run: chown -R www-data:www-data staticfiles media (if using www-data)

4. ✅ Database:
   - PostgreSQL is running
   - Database exists
   - User has proper permissions
   - Connection string is correct

5. ✅ Static Files:
   - Run: python manage.py collectstatic --noinput
   - Verify staticfiles/ directory has files

6. ✅ Migrations:
   - Run: python manage.py migrate --noinput
   - All migrations applied

7. ✅ Web Server Configuration:
   - Nginx/Apache configured
   - Static files served correctly
   - Media files served correctly
   - Proxy settings correct

8. ✅ Process Manager:
   - Gunicorn/uWSGI configured
   - Supervisor/systemd service set up
   - Auto-restart on failure

9. ✅ Security:
   - DEBUG=False
   - SECRET_KEY is secure
   - ALLOWED_HOSTS configured
   - SSL/HTTPS configured (for production)

10. ✅ Testing:
    - Test all major features
    - Test static files loading
    - Test media uploads
    - Test database operations
"""
    print(checklist)


def main():
    """Main function"""
    print("\n" + "=" * 60)
    print("SERVER DEPLOYMENT PRE-CHECK")
    print("=" * 60)
    print()
    
    # Check paths
    path_issues = check_and_fix_paths()
    
    # Check environment
    env_issues = check_environment_variables()
    
    # Check permissions
    perm_issues = check_file_permissions()
    
    # Generate checklist
    generate_server_checklist()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_issues = path_issues + env_issues + perm_issues
    
    if all_issues:
        print(f"⚠️  Found {len(all_issues)} issue(s):")
        for issue in all_issues:
            print(f"  {issue}")
    else:
        print("✅ No issues found! Ready for deployment.")
    
    print("\n" + "=" * 60)


if __name__ == '__main__':
    main()



