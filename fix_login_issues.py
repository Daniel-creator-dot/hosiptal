#!/usr/bin/env python
"""
Login Issues Diagnostic and Fix Script
Run this on your VPS to diagnose and fix login problems
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth.models import User
from django.db import connection
from django.conf import settings
from django.contrib.auth import authenticate

def check_database_connection():
    """Check if database is accessible"""
    print("=" * 60)
    print("LOGIN DIAGNOSTIC TOOL")
    print("=" * 60)
    print()
    
    print("1. Database Connection:")
    print("-" * 60)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            print("   ✅ Database connection successful")
    except Exception as e:
        print(f"   ❌ Database connection failed: {str(e)}")
        return False
    print()
    return True

def check_auth_tables():
    """Check if authentication tables exist"""
    print("2. Authentication Tables:")
    print("-" * 60)
    try:
        with connection.cursor() as cursor:
            # Check auth_user table
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'auth_user'
                );
            """)
            exists = cursor.fetchone()[0]
            if exists:
                print("   ✅ auth_user table exists")
                
                # Count users
                cursor.execute("SELECT COUNT(*) FROM auth_user;")
                count = cursor.fetchone()[0]
                print(f"   Total users: {count}")
                
                if count == 0:
                    print("   ⚠️  No users found - you need to create a superuser")
                    return False
                
                # List users
                cursor.execute("SELECT id, username, email, is_active, is_staff, is_superuser FROM auth_user LIMIT 10;")
                users = cursor.fetchall()
                print("   Users:")
                for user in users:
                    status = "✅" if user[3] else "❌"
                    print(f"      {status} {user[1]} (ID: {user[0]}, Active: {user[3]}, Staff: {user[4]}, Superuser: {user[5]})")
            else:
                print("   ❌ auth_user table does not exist")
                print("   Run: python manage.py migrate")
                return False
    except Exception as e:
        print(f"   ❌ Error checking auth tables: {str(e)}")
        return False
    print()
    return True

def check_user_passwords():
    """Check if users have valid passwords"""
    print("3. User Password Check:")
    print("-" * 60)
    try:
        users = User.objects.all()[:5]
        if not users.exists():
            print("   ⚠️  No users to check")
            return False
        
        print("   Checking user passwords...")
        for user in users:
            # Check if password is set (not empty hash)
            if user.password and len(user.password) > 10:
                print(f"   ✅ {user.username}: Password is set")
            else:
                print(f"   ❌ {user.username}: Password is not set or invalid")
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return False
    print()
    return True

def test_authentication():
    """Test authentication with existing users"""
    print("4. Authentication Test:")
    print("-" * 60)
    try:
        users = User.objects.filter(is_active=True)[:3]
        if not users.exists():
            print("   ⚠️  No active users to test")
            return False
        
        print("   Testing authentication (will fail - this is expected):")
        for user in users:
            # Try with wrong password to test auth system
            auth_user = authenticate(username=user.username, password='wrong_password')
            if auth_user is None:
                print(f"   ✅ {user.username}: Authentication system working (wrong password correctly rejected)")
            else:
                print(f"   ⚠️  {user.username}: Unexpected authentication result")
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return False
    print()
    return True

def check_settings():
    """Check login-related settings"""
    print("5. Login Settings:")
    print("-" * 60)
    try:
        login_url = getattr(settings, 'LOGIN_URL', 'Not set')
        login_redirect = getattr(settings, 'LOGIN_REDIRECT_URL', 'Not set')
        logout_redirect = getattr(settings, 'LOGOUT_REDIRECT_URL', 'Not set')
        
        print(f"   LOGIN_URL: {login_url}")
        print(f"   LOGIN_REDIRECT_URL: {login_redirect}")
        print(f"   LOGOUT_REDIRECT_URL: {logout_redirect}")
        
        # Check session settings
        session_engine = getattr(settings, 'SESSION_ENGINE', 'Not set')
        print(f"   SESSION_ENGINE: {session_engine}")
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    print()
    return True

def check_middleware():
    """Check authentication middleware"""
    print("6. Middleware Check:")
    print("-" * 60)
    try:
        middleware = getattr(settings, 'MIDDLEWARE', [])
        required = [
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
        ]
        
        for req in required:
            if req in middleware:
                print(f"   ✅ {req.split('.')[-1]}")
            else:
                print(f"   ❌ Missing: {req.split('.')[-1]}")
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    print()
    return True

def create_test_user():
    """Offer to create a test user"""
    print("7. Create Test User:")
    print("-" * 60)
    try:
        # Check if we have any users
        user_count = User.objects.count()
        if user_count == 0:
            print("   ⚠️  No users found!")
            print("   Run: python manage.py createsuperuser")
            print()
            return False
        else:
            print(f"   ✅ {user_count} user(s) exist")
            print("   If you can't login, try resetting password:")
            print("   python manage.py shell")
            print("   >>> from django.contrib.auth.models import User")
            print("   >>> u = User.objects.get(username='your_username')")
            print("   >>> u.set_password('new_password')")
            print("   >>> u.save()")
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    print()
    return True

def main():
    """Run all diagnostics"""
    if not check_database_connection():
        print("❌ Database connection failed. Fix database first!")
        return False
    
    if not check_auth_tables():
        print("❌ Authentication tables missing. Run migrations!")
        return False
    
    check_user_passwords()
    test_authentication()
    check_settings()
    check_middleware()
    create_test_user()
    
    print("=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)
    print()
    print("Common fixes:")
    print("1. Create superuser: python manage.py createsuperuser")
    print("2. Reset password: python manage.py changepassword <username>")
    print("3. Check .env file has correct DATABASE_URL")
    print("4. Check PostgreSQL is running: sudo systemctl status postgresql")
    print("5. Check Gunicorn logs: sudo journalctl -u gunicorn-chm.service -f")
    print()
    
    return True

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)







