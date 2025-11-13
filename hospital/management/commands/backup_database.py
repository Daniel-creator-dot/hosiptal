"""
Database backup management command
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import os
import shutil
from datetime import datetime
import json


class Command(BaseCommand):
    help = 'Backup the database and media files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='backups',
            help='Directory to store backups (default: backups/)',
        )

    def handle(self, *args, **options):
        output_dir = options['output_dir']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create backup directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        backup_name = f'backup_{timestamp}'
        backup_path = os.path.join(output_dir, backup_name)
        os.makedirs(backup_path)
        
        self.stdout.write(self.style.SUCCESS(f'\n{"="*70}'))
        self.stdout.write(self.style.SUCCESS('DATABASE BACKUP STARTED'))
        self.stdout.write(self.style.SUCCESS(f'{"="*70}\n'))
        self.stdout.write(f'Backup Directory: {backup_path}\n')
        
        # Get database settings
        db_engine = settings.DATABASES['default']['ENGINE']
        db_name = settings.DATABASES['default']['NAME']
        
        # Backup SQLite database
        if 'sqlite' in db_engine:
            self.stdout.write('Database Type: SQLite')
            
            # Copy database file
            if os.path.exists(db_name):
                db_backup_path = os.path.join(backup_path, 'db.sqlite3')
                shutil.copy2(db_name, db_backup_path)
                db_size = os.path.getsize(db_name) / (1024 * 1024)  # Size in MB
                self.stdout.write(self.style.SUCCESS(f'  Database backed up: {db_size:.2f} MB'))
            else:
                self.stdout.write(self.style.ERROR(f'  Database file not found: {db_name}'))
        
        # Backup media files
        media_root = settings.MEDIA_ROOT
        if os.path.exists(media_root):
            media_backup_path = os.path.join(backup_path, 'media')
            shutil.copytree(media_root, media_backup_path, dirs_exist_ok=True)
            self.stdout.write(self.style.SUCCESS(f'  Media files backed up'))
        
        # Create backup manifest
        manifest = {
            'timestamp': timestamp,
            'datetime': datetime.now().isoformat(),
            'database': {
                'engine': db_engine,
                'name': db_name,
                'size_mb': os.path.getsize(db_name) / (1024 * 1024) if os.path.exists(db_name) else 0
            },
            'django_version': settings.VERSION if hasattr(settings, 'VERSION') else 'Unknown',
            'backup_location': backup_path
        }
        
        manifest_path = os.path.join(backup_path, 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        self.stdout.write(self.style.SUCCESS(f'  Manifest created'))
        
        self.stdout.write(self.style.SUCCESS(f'\n{"="*70}'))
        self.stdout.write(self.style.SUCCESS('BACKUP COMPLETED SUCCESSFULLY!'))
        self.stdout.write(self.style.SUCCESS(f'{"="*70}'))
        self.stdout.write(f'\nBackup Location: {backup_path}')
        self.stdout.write(f'Timestamp: {timestamp}\n')
        
        # List all backups
        self.stdout.write(self.style.WARNING('\nAll Available Backups:'))
        backups = [d for d in os.listdir(output_dir) if d.startswith('backup_')]
        backups.sort(reverse=True)
        
        for i, backup in enumerate(backups[:10], 1):
            backup_full_path = os.path.join(output_dir, backup)
            manifest_file = os.path.join(backup_full_path, 'manifest.json')
            if os.path.exists(manifest_file):
                with open(manifest_file, 'r') as f:
                    m = json.load(f)
                    self.stdout.write(f"  {i}. {backup} - {m.get('datetime', 'Unknown')} - {m['database'].get('size_mb', 0):.2f} MB")
            else:
                self.stdout.write(f"  {i}. {backup}")
        
        self.stdout.write(self.style.SUCCESS(f'\nTo restore this backup, run:'))
        self.stdout.write(f'  python manage.py restore_database --backup={backup_name}\n')




















