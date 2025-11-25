"""
Create Accounting Migrations
Automatically handles field rename questions
"""

import subprocess
import sys

def run_migrations():
    print("="*70)
    print("CREATING ACCOUNTING SYSTEM MIGRATIONS")
    print("="*70)
    print()
    
    print("Step 1: Creating migrations (answering 'n' to rename questions)...")
    print()
    
    # Prepare input: answer 'n' to all rename questions
    input_data = "n\n" * 10  # Answer 'n' ten times to handle all rename questions
    
    # Run makemigrations with input
    process = subprocess.Popen(
        [sys.executable, 'manage.py', 'makemigrations', 'hospital'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    output, _ = process.communicate(input=input_data)
    print(output)
    
    if process.returncode == 0 or 'Migrations for' in output:
        print()
        print("[OK] Migrations created successfully!")
        
        print()
        print("Step 2: Applying migrations...")
        print()
        
        # Run migrate
        result = subprocess.run(
            [sys.executable, 'manage.py', 'migrate'],
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        if result.returncode == 0:
            print()
            print("[OK] Migrations applied successfully!")
            return True
        else:
            print()
            print("[ERROR] Migration application failed")
            return False
    else:
        print()
        print("[ERROR] Migration creation failed")
        return False


if __name__ == '__main__':
    success = run_migrations()
    
    if success:
        print()
        print("="*70)
        print("✅ MIGRATIONS COMPLETE!")
        print("="*70)
        print()
        print("Next steps:")
        print("1. Run: python setup_accounting_system.py")
        print("2. Run: python import_legacy_accounting.py")
        print("3. Restart server")
        print("4. Visit: http://127.0.0.1:8000/hms/accounting/")
    else:
        print()
        print("="*70)
        print("⚠️ MIGRATION HAD ISSUES")
        print("="*70)
        print()
        print("Try running manually:")
        print("  python manage.py makemigrations hospital")
        print("  (answer 'n' to rename questions)")
        print("  python manage.py migrate")




















