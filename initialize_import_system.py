"""
Initialize Database Import System
Creates necessary directories and files
"""

import os
import sys
import io

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def create_directory(path):
    """Create directory if it doesn't exist"""
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"✅ Created: {path}")
        return True
    else:
        print(f"ℹ️  Exists: {path}")
        return False


def create_init_file(path):
    """Create __init__.py if it doesn't exist"""
    init_file = os.path.join(path, '__init__.py')
    if not os.path.exists(init_file):
        with open(init_file, 'w') as f:
            f.write('# Auto-generated __init__.py\n')
        print(f"✅ Created: {init_file}")
        return True
    else:
        print(f"ℹ️  Exists: {init_file}")
        return False


def main():
    print("="*70)
    print("   INITIALIZING DATABASE IMPORT SYSTEM")
    print("="*70)
    print()

    # Define required directories
    directories = [
        'hospital/management',
        'hospital/management/commands',
    ]

    # Create directories
    print("📁 Creating directories...")
    for directory in directories:
        create_directory(directory)
        create_init_file(directory)

    print()

    # Check if management commands exist
    print("🔍 Checking management commands...")
    commands_dir = 'hospital/management/commands'
    
    commands = [
        'import_legacy_database.py',
        'validate_import.py',
        'map_legacy_tables.py',
    ]

    all_exist = True
    for cmd in commands:
        cmd_path = os.path.join(commands_dir, cmd)
        if os.path.exists(cmd_path):
            print(f"   ✅ {cmd}")
        else:
            print(f"   ❌ {cmd} - Not found!")
            all_exist = False

    print()

    # Check main scripts
    print("🔍 Checking main scripts...")
    scripts = [
        'import_database.py',
        'import_database.bat',
        'check_import_prerequisites.py',
    ]

    for script in scripts:
        if os.path.exists(script):
            print(f"   ✅ {script}")
        else:
            print(f"   ❌ {script} - Not found!")
            all_exist = False

    print()

    # Check documentation
    print("📚 Checking documentation...")
    docs = [
        'DATABASE_IMPORT_README.md',
        'DATABASE_IMPORT_GUIDE.md',
        'QUICK_START_DATABASE_IMPORT.md',
    ]

    for doc in docs:
        if os.path.exists(doc):
            print(f"   ✅ {doc}")
        else:
            print(f"   ⚠️  {doc} - Not found")

    print()
    print("="*70)

    if all_exist:
        print("✅ System initialization complete!")
        print()
        print("Next steps:")
        print("1. Run: python check_import_prerequisites.py")
        print("2. Run: python import_database.py")
        print()
        return 0
    else:
        print("⚠️  Some files are missing. Please check the output above.")
        print()
        print("The import system files should have been created.")
        print("If any are missing, they may need to be recreated.")
        print()
        return 1


if __name__ == '__main__':
    try:
        exit_code = main()
        input("\nPress Enter to exit...")
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)

