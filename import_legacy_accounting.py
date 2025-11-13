"""
Import Legacy Accounting Data
Import all acc files from DS directory
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from pathlib import Path
from django.core.management import call_command

def main():
    print("="*70)
    print("IMPORTING LEGACY ACCOUNTING DATA")
    print("="*70)
    print()
    
    # Source directory
    source_dir = Path(r'C:\Users\user\Videos\DS')
    
    if not source_dir.exists():
        print(f"Error: Source directory not found: {source_dir}")
        return
    
    # Find all acc_*.sql files
    acc_files = list(source_dir.glob('acc_*.sql'))
    
    if not acc_files:
        print(f"Error: No acc_*.sql files found in {source_dir}")
        return
    
    print(f"Found {len(acc_files)} accounting files to import:")
    print()
    
    for f in sorted(acc_files):
        print(f"  - {f.name}")
    
    print()
    print("="*70)
    print(f"IMPORTING {len(acc_files)} FILES")
    print("="*70)
    print()
    
    # Import each file
    stats = {
        'total': len(acc_files),
        'success': 0,
        'failed': 0,
        'tables': 0,
        'rows': 0,
    }
    
    for sql_file in sorted(acc_files):
        print(f"\nImporting: {sql_file.name}")
        print("-" * 70)
        
        try:
            # Use the existing import command
            call_command(
                'import_legacy_database',
                str(sql_file),
                verbosity=1,
            )
            stats['success'] += 1
            print(f"  [OK] {sql_file.name} imported")
            
        except Exception as e:
            stats['failed'] += 1
            print(f"  [ERROR] {sql_file.name}: {str(e)[:100]}")
    
    # Summary
    print()
    print("="*70)
    print("IMPORT COMPLETE!")
    print("="*70)
    print()
    print(f"Total files:  {stats['total']}")
    print(f"Success:      {stats['success']}")
    print(f"Failed:       {stats['failed']}")
    print()
    
    if stats['success'] > 0:
        print("[OK] Legacy accounting data imported successfully!")
        print()
        print("Next steps:")
        print("1. Restart server: python manage.py runserver")
        print("2. Visit: http://127.0.0.1:8000/hms/accounting/")
        print("3. View financial reports with real data!")
    else:
        print("[WARNING] No files imported successfully")
        print("Check errors above")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

