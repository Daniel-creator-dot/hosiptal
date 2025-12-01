"""
Import Patient Data with Progress Monitoring
Runs import in background and shows progress updates
"""
import subprocess
import time
import os
import sys
from datetime import datetime

def check_table_exists():
    """Check if patient_data table exists"""
    try:
        result = subprocess.run(
            ['docker-compose', 'exec', '-T', 'db', 'psql', '-U', 'hms_user', '-d', 'hms_db', 
             '-c', "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'patient_data') as table_exists;"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return 't' in result.stdout.lower() or 'true' in result.stdout.lower()
    except:
        return False

def get_patient_count():
    """Get current patient count"""
    try:
        result = subprocess.run(
            ['docker-compose', 'exec', '-T', 'db', 'psql', '-U', 'hms_user', '-d', 'hms_db', 
             '-c', 'SELECT COUNT(*) as patient_count FROM patient_data;'],
            capture_output=True,
            text=True,
            timeout=10
        )
        # Extract number from output
        for line in result.stdout.split('\n'):
            if line.strip().isdigit():
                return int(line.strip())
        return 0
    except:
        return 0

def get_log_tail(lines=5):
    """Get last N lines from log file"""
    log_file = 'import_log.txt'
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
                return ''.join(all_lines[-lines:])
        except:
            return ''
    return ''

def main():
    print("="*70)
    print("   BACKGROUND PATIENT DATA IMPORT WITH MONITORING")
    print("="*70)
    print()
    print("Starting import in background...")
    print("Log file: import_log.txt")
    print()
    
    # Start import in background
    log_file = open('import_log.txt', 'w', encoding='utf-8')
    process = subprocess.Popen(
        ['docker-compose', 'exec', 'web', 'python', 'manage.py', 'import_legacy_database', 
         '--tables', 'patient_data', '--sql-dir', 'import/legacy', '--skip-drop'],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True
    )
    log_file.close()
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Import process started (PID: {process.pid})")
    print()
    print("Monitoring progress every 30 seconds...")
    print("Press Ctrl+C to stop monitoring (import will continue in background)")
    print()
    
    check_count = 0
    last_count = 0
    
    try:
        while True:
            time.sleep(30)
            check_count += 1
            
            print("="*70)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Status Check #{check_count}")
            print("="*70)
            
            if check_table_exists():
                count = get_patient_count()
                print(f"✅ patient_data table EXISTS!")
                print(f"📊 Current patient count: {count:,}")
                
                if count > 0:
                    if count == last_count:
                        print()
                        print("✅ Import appears to be COMPLETE!")
                        print()
                        print("Verifying final status...")
                        subprocess.run(['docker-compose', 'exec', 'web', 'python', 'manage.py', 'check_patient_database'])
                        print()
                        print("="*70)
                        print("   IMPORT SUCCESSFUL!")
                        print("="*70)
                        print()
                        print("Next steps:")
                        print("  1. View patients at: http://127.0.0.1:8000/hms/patients/")
                        print("  2. Use 'Source' filter and select 'Imported Legacy'")
                        print("  3. Click 'Search' to see all imported patients")
                        print()
                        break
                    else:
                        print(f"📈 Progress: {count - last_count:,} new records since last check")
                        last_count = count
                else:
                    print("⏳ Table exists but no records yet...")
            else:
                print("⏳ Import in progress... (table not created yet)")
                print()
                print("Last 5 lines from log:")
                log_tail = get_log_tail(5)
                if log_tail:
                    print(log_tail)
                else:
                    print("  (No log output yet)")
            
            print()
            print("Next check in 30 seconds...")
            print()
            
    except KeyboardInterrupt:
        print()
        print("⚠️  Monitoring stopped by user")
        print(f"Import process (PID: {process.pid}) is still running in background")
        print("Check import_log.txt for progress")
        print()
        print("To check status manually, run:")
        print("  docker-compose exec web python manage.py check_patient_database")
        print()

if __name__ == '__main__':
    main()


