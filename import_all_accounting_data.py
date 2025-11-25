"""
Import All Legacy Accounting Data
Uses Django management command with correct arguments
"""

import subprocess
import sys
from pathlib import Path

def main():
    print("="*70)
    print("IMPORTING ALL LEGACY ACCOUNTING DATA")
    print("="*70)
    print()
    
    # List of accounting table names to import
    acc_tables = [
        'accounts',
        'beneficiaries',
        'bills',
        'chart_accounts',
        'currencies',
        'general_journal_entries',
        'inventories',
        'invoice_items',
        'invoice_payments',
        'invoice_taxes',
        'invoices',
        'master',
        'my_company',
        'revenues',
        'taxes',
    ]
    
    print(f"Importing {len(acc_tables)} accounting tables...")
    print()
    
    # Import all using the management command
    result = subprocess.run(
        [
            sys.executable,
            'manage.py',
            'import_legacy_database',
            '--sql-dir', r'C:\Users\user\Videos\DS',
            '--tables'
        ] + [f'acc_{table}' for table in acc_tables],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    
    print()
    print("="*70)
    print("ACCOUNTING DATA IMPORT COMPLETE!")
    print("="*70)
    print()
    print("Next steps:")
    print("1. Restart server")
    print("2. Visit: http://127.0.0.1:8000/hms/accounting/")
    print("3. See real financial data in reports!")


if __name__ == '__main__':
    main()




















