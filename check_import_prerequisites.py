"""
Pre-Import System Check
Verifies that everything is ready for database import
"""

import os
import sys
import glob
import io
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def check_python_version():
    """Check Python version"""
    print("🔍 Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro} (OK)")
        return True
    else:
        print(f"   ❌ Python {version.major}.{version.minor}.{version.micro} (Need 3.8+)")
        return False


def check_django_installation():
    """Check if Django is installed"""
    print("\n🔍 Checking Django installation...")
    try:
        import django
        print(f"   ✅ Django {django.get_version()} (OK)")
        return True
    except ImportError:
        print("   ❌ Django not installed")
        print("      Install with: pip install django")
        return False


def check_database_exists():
    """Check if database exists"""
    print("\n🔍 Checking database file...")
    if os.path.exists('db.sqlite3'):
        size_mb = os.path.getsize('db.sqlite3') / (1024 * 1024)
        print(f"   ✅ Database exists (Size: {size_mb:.2f} MB)")
        
        # Check for backup
        if os.path.exists('db.sqlite3.backup'):
            print("   ✅ Backup exists")
        else:
            print("   ⚠️  No backup found - will create one during import")
        return True
    else:
        print("   ℹ️  No database file (will create new)")
        return True


def check_sql_directory():
    """Check if SQL files directory exists"""
    print("\n🔍 Checking SQL files directory...")
    sql_dir = r'C:\Users\user\Videos\DS'
    
    if not os.path.exists(sql_dir):
        print(f"   ❌ Directory not found: {sql_dir}")
        print("      Please update the path in import_database.py")
        return False
    
    sql_files = glob.glob(os.path.join(sql_dir, '*.sql'))
    if not sql_files:
        print(f"   ❌ No SQL files found in: {sql_dir}")
        return False
    
    print(f"   ✅ Found {len(sql_files)} SQL files")
    
    # Show some examples
    print("\n   Sample files:")
    for f in sql_files[:5]:
        filename = os.path.basename(f)
        size_kb = os.path.getsize(f) / 1024
        print(f"      - {filename} ({size_kb:.1f} KB)")
    
    if len(sql_files) > 5:
        print(f"      ... and {len(sql_files)-5} more files")
    
    return True


def check_disk_space():
    """Check available disk space"""
    print("\n🔍 Checking disk space...")
    try:
        import shutil
        total, used, free = shutil.disk_usage('.')
        free_gb = free / (1024**3)
        
        if free_gb > 1:
            print(f"   ✅ Available space: {free_gb:.2f} GB")
            return True
        else:
            print(f"   ⚠️  Low disk space: {free_gb:.2f} GB")
            return False
    except:
        print("   ⚠️  Could not check disk space")
        return True


def check_management_commands():
    """Check if management commands exist"""
    print("\n🔍 Checking management commands...")
    commands_dir = 'hospital/management/commands'
    
    required_commands = [
        'import_legacy_database.py',
        'validate_import.py',
        'map_legacy_tables.py'
    ]
    
    all_exist = True
    for cmd in required_commands:
        cmd_path = os.path.join(commands_dir, cmd)
        if os.path.exists(cmd_path):
            print(f"   ✅ {cmd}")
        else:
            print(f"   ❌ {cmd} (missing)")
            all_exist = False
    
    return all_exist


def check_dependencies():
    """Check required Python packages"""
    print("\n🔍 Checking Python dependencies...")
    
    required = [
        'django',
        'django_extensions',
        'simple_history',
    ]
    
    all_installed = True
    for package in required:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} (not installed)")
            all_installed = False
    
    if not all_installed:
        print("\n   Install missing packages with:")
        print("   pip install -r requirements.txt")
    
    return all_installed


def check_permissions():
    """Check file permissions"""
    print("\n🔍 Checking file permissions...")
    
    # Check if we can write to current directory
    try:
        test_file = 'test_write_permission.tmp'
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print("   ✅ Write permissions OK")
        return True
    except:
        print("   ❌ No write permissions in current directory")
        return False


def main():
    print("="*70)
    print("   DATABASE IMPORT - PREREQUISITES CHECK")
    print("="*70)
    
    checks = [
        ("Python Version", check_python_version),
        ("Django Installation", check_django_installation),
        ("Database File", check_database_exists),
        ("SQL Files Directory", check_sql_directory),
        ("Disk Space", check_disk_space),
        ("Management Commands", check_management_commands),
        ("Python Dependencies", check_dependencies),
        ("File Permissions", check_permissions),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"   ❌ Error during check: {str(e)}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*70)
    print("   SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status:12s} {name}")
    
    print("\n" + "="*70)
    print(f"   {passed}/{total} checks passed")
    print("="*70)
    
    if passed == total:
        print("\n✅ All checks passed! You're ready to import.")
        print("\nNext step: Run 'python import_database.py'")
        print("Or double-click: import_database.bat")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("1. Install Python 3.8+: https://www.python.org/downloads/")
        print("2. Install dependencies: pip install -r requirements.txt")
        print("3. Update SQL directory path in import_database.py")
        return 1


if __name__ == '__main__':
    try:
        exit_code = main()
        print("\n")
        input("Press Enter to exit...")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nCheck cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
        sys.exit(1)

