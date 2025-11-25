"""
Database restore management command
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import os
import shutil
from datetime import datetime
import json


class Command(BaseCommand):
    help = 'Restore database from backup'

    def add_arguments(self, parser):
        parser.add_argument(
            '--backup',
            type=str,
            required=True,
            help='Backup directory name (e.g., backup_20251103_120000)',
        )
        parser.add_argument(
            '--source-dir',
            type=str,
            default='backups',
            help='Directory where backups are stored (default: backups/)',
        )

    def handle(self, *args, **options):
        backup_name = options['backup']
        source_dir = options['source_dir']
        backup_path = os.path.join(source_dir, backup_name)
        
        if not os.path.exists(backup_path):
            self.stdout.write(self.style.ERROR(f'\nBackup not found: {backup_path}'))
            self.stdout.write('Available backups:')
            if os.path.exists(source_dir):
                backups = [d for d in os.listdir(source_dir) if d.startswith('backup_')]
                for backup in sorted(backups, reverse=True)[:10]:
                    self.stdout.write(f'  - {backup}')
            return
        
        self.stdout.write(self.style.WARNING(f'\n{"="*70}'))
        self.stdout.write(self.style.WARNING('DATABASE RESTORE'))
        self.stdout.write(self.style.WARNING(f'{"="*70}\n'))
        
        # Read manifest
        manifest_path = os.path.join(backup_path, 'manifest.json')
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            self.stdout.write(f'Backup Date: {manifest.get("datetime", "Unknown")}')
            self.stdout.write(f'Database Size: {manifest["database"].get("size_mb", 0):.2f} MB\n')
        
        # Confirm restore
        confirm = input('This will OVERWRITE your current database. Are you sure? (yes/no): ')
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.WARNING('Restore cancelled.'))
            return
        
        # Get database settings
        db_engine = settings.DATABASES['default']['ENGINE']
        db_name = settings.DATABASES['default']['NAME']
        
        # Restore SQLite database
        if 'sqlite' in db_engine:
            db_backup_path = os.path.join(backup_path, 'db.sqlite3')
            
            if not os.path.exists(db_backup_path):
                self.stdout.write(self.style.ERROR(f'Database backup file not found: {db_backup_path}'))
                return
            
            # Create backup of current database before restore
            if os.path.exists(db_name):
                current_backup = f'{db_name}.before_restore_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
                shutil.copy2(db_name, current_backup)
                self.stdout.write(self.style.WARNING(f'Current database backed up to: {current_backup}'))
            
            # Restore database
            shutil.copy2(db_backup_path, db_name)
            self.stdout.write(self.style.SUCCESS('Database restored successfully!'))
        
        # Restore media files
        media_backup_path = os.path.join(backup_path, 'media')
        if os.path.exists(media_backup_path):
            media_root = settings.MEDIA_ROOT
            
            # Backup current media
            if os.path.exists(media_root):
                media_current_backup = f'{media_root}_before_restore_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
                shutil.copytree(media_root, media_current_backup, dirs_exist_ok=True)
                self.stdout.write(self.style.WARNING(f'Current media backed up to: {media_current_backup}'))
            
            # Restore media
            shutil.copytree(media_backup_path, media_root, dirs_exist_ok=True)
            self.stdout.write(self.style.SUCCESS('Media files restored successfully!'))
        
        self.stdout.write(self.style.SUCCESS(f'\n{"="*70}'))
        self.stdout.write(self.style.SUCCESS('RESTORE COMPLETED SUCCESSFULLY!'))
        self.stdout.write(self.style.SUCCESS(f'{"="*70}\n'))
        self.stdout.write('Please restart the Django server for changes to take effect.\n')
































