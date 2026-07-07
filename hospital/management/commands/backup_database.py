"""
Database Backup Management Command
Automated database backup with scheduling support
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import os
import subprocess
import shutil
import logging
from pathlib import Path

from hospital.backup_retention import (
    BACKUP_EXTENSIONS,
    get_retention_days,
    prune_backup_folders,
    prune_directory,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create a backup of the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='backups/',
            help='Directory to save backup files'
        )
        parser.add_argument(
            '--keep-days',
            type=int,
            default=14,
            help='Number of days to keep backups (default: 14)'
        )

    def handle(self, *args, **options):
        output_dir = options['output_dir']
        keep_days = options['keep_days'] or get_retention_days(default=14)
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Get database configuration
        db_config = settings.DATABASES['default']
        db_engine = db_config.get('ENGINE', '')
        
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        
        try:
            if 'postgresql' in db_engine:
                # PostgreSQL backup
                db_name = db_config.get('NAME')
                db_user = db_config.get('USER')
                db_password = db_config.get('PASSWORD')
                db_host = db_config.get('HOST', 'localhost')
                db_port = db_config.get('PORT', '5432')
                
                backup_file = os.path.join(output_dir, f'hms_backup_{timestamp}.sql')
                
                # Set PGPASSWORD environment variable
                env = os.environ.copy()
                env['PGPASSWORD'] = db_password
                
                # Run pg_dump
                cmd = [
                    'pg_dump',
                    '-h', db_host,
                    '-p', str(db_port),
                    '-U', db_user,
                    '-d', db_name,
                    '-F', 'c',  # Custom format
                    '-f', backup_file
                ]
                
                result = subprocess.run(cmd, env=env, capture_output=True, text=True)
                
                if result.returncode == 0:
                    self.stdout.write(self.style.SUCCESS(f'Backup created successfully: {backup_file}'))
                    logger.info(f'Database backup created: {backup_file}')
                else:
                    self.stdout.write(self.style.ERROR(f'Backup failed: {result.stderr}'))
                    logger.error(f'Database backup failed: {result.stderr}')
                    return
                    
            elif 'mysql' in db_engine:
                # MySQL backup
                db_name = db_config.get('NAME')
                db_user = db_config.get('USER')
                db_password = db_config.get('PASSWORD')
                db_host = db_config.get('HOST', 'localhost')
                db_port = db_config.get('PORT', '3306')
                
                backup_file = os.path.join(output_dir, f'hms_backup_{timestamp}.sql')
                
                cmd = [
                    'mysqldump',
                    f'--host={db_host}',
                    f'--port={db_port}',
                    f'--user={db_user}',
                    f'--password={db_password}',
                    db_name
                ]
                
                with open(backup_file, 'w') as f:
                    result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
                
                if result.returncode == 0:
                    self.stdout.write(self.style.SUCCESS(f'Backup created successfully: {backup_file}'))
                    logger.info(f'Database backup created: {backup_file}')
                else:
                    self.stdout.write(self.style.ERROR(f'Backup failed: {result.stderr}'))
                    logger.error(f'Database backup failed: {result.stderr}')
                    return
            elif 'sqlite' in db_engine:
                # SQLite backup (copy the DB file)
                db_path = db_config.get('NAME')
                if not db_path or not os.path.exists(db_path):
                    raise FileNotFoundError(f"SQLite database file not found at {db_path}")
                
                backup_file = os.path.join(output_dir, f'hms_backup_{timestamp}.sqlite3')
                shutil.copy2(db_path, backup_file)
                self.stdout.write(self.style.SUCCESS(f'Backup created successfully: {backup_file}'))
                logger.info(f'SQLite database backup created: {backup_file}')
            else:
                msg = f'Backup not supported for database engine: {db_engine}'
                self.stdout.write(self.style.WARNING(msg))
                logger.warning(msg)
                return
            
            # Clean up old backups in output dir and import/ retention targets
            self.cleanup_old_backups(output_dir, keep_days)
            from hospital.backup_retention import prune_all_retention_targets

            prune_all_retention_targets(keep_days=keep_days, dry_run=False)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating backup: {e}'))
            logger.error(f'Error creating backup: {e}', exc_info=True)

    def cleanup_old_backups(self, backup_dir, keep_days):
        """Remove backups older than keep_days in the given directory."""
        try:
            if keep_days <= 0:
                return
            backup_path = Path(backup_dir)
            deleted, _ = prune_directory(
                backup_path,
                keep_days=keep_days,
                allowed_extensions=BACKUP_EXTENSIONS,
                dry_run=False,
            )
            folder_deleted, _ = prune_backup_folders(backup_path.parent, keep_days=keep_days, dry_run=False)
            if deleted or folder_deleted:
                self.stdout.write(
                    f'Removed {deleted} old backup file(s) and {folder_deleted} folder(s)'
                )
        except Exception as e:
            logger.warning(f'Error cleaning up old backups: {e}')
