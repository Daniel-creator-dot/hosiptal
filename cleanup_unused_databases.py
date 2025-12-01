"""
Script to clean up unused SQLite database files and ensure only PostgreSQL is used.
This script will:
1. Find all SQLite database files
2. Move them to backups/archived_databases/ folder
3. Report what was moved
"""
import os
import shutil
from pathlib import Path
from datetime import datetime

def cleanup_sqlite_databases():
    """Find and archive all SQLite database files"""
    base_dir = Path('.')
    backup_dir = base_dir / 'backups' / 'archived_databases'
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all SQLite files
    sqlite_files = []
    for root, dirs, files in os.walk('.'):
        # Skip virtual environments and common ignore directories
        skip_dirs = ['venv', 'env', '.git', '__pycache__', 'node_modules', 'backups']
        if any(skip in root for skip in skip_dirs):
            continue
        
        for file in files:
            if file.endswith('.sqlite3') or (file.endswith('.db') and 'sqlite' in file.lower()):
                full_path = Path(root) / file
                sqlite_files.append(full_path)
    
    if not sqlite_files:
        print("✅ No SQLite database files found. System is already using PostgreSQL only.")
        return
    
    print("=" * 70)
    print("CLEANING UP UNUSED SQLITE DATABASES")
    print("=" * 70)
    print(f"\nFound {len(sqlite_files)} SQLite database file(s):\n")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    moved_count = 0
    
    for db_file in sqlite_files:
        try:
            # Get file size
            size_mb = db_file.stat().st_size / (1024 * 1024)
            print(f"  📁 {db_file} ({size_mb:.2f} MB)")
            
            # Create backup path
            backup_path = backup_dir / f"{db_file.name}_{timestamp}"
            
            # Move file to backup directory
            shutil.move(str(db_file), str(backup_path))
            moved_count += 1
            print(f"     ✅ Moved to: {backup_path}")
            
        except Exception as e:
            print(f"     ❌ Error moving {db_file}: {e}")
    
    print("\n" + "=" * 70)
    print(f"✅ Successfully archived {moved_count} SQLite database file(s)")
    print(f"📦 Backup location: {backup_dir}")
    print("\n⚠️  IMPORTANT: Ensure your .env file has:")
    print("   DATABASE_URL=postgresql://user:password@localhost:5432/hms_db")
    print("=" * 70)

if __name__ == '__main__':
    cleanup_sqlite_databases()

