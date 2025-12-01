"""
World-Class Database Backup System
Automated PostgreSQL backup with compression and retention
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
import os
import subprocess
import gzip
import shutil
from datetime import timedelta


class Command(BaseCommand):
    help = 'Create a backup of the PostgreSQL database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='backups',
            help='Directory to save backups (default: backups)',
        )
        parser.add_argument(
            '--compress',
            action='store_true',
            help='Compress backup with gzip',
        )
        parser.add_argument(
            '--keep-days',
            type=int,
            default=30,
            help='Keep backups for N days (default: 30)',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up old backups',
        )

    def handle(self, *args, **options):
        output_dir = options['output_dir']
        compress = options['compress']
        keep_days = options['keep_days']
        cleanup = options['cleanup']
        
        self.stdout.write('\n=== Database Backup System ===\n')
        
        # Get database connection info
        db_settings = settings.DATABASES['default']
        db_name = db_settings.get('NAME')
        db_user = db_settings.get('USER')
        db_password = db_settings.get('PASSWORD')
        db_host = db_settings.get('HOST', 'localhost')
        db_port = db_settings.get('PORT', '5432')
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate backup filename
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'{db_name}_{timestamp}.sql'
        backup_path = os.path.join(output_dir, backup_filename)
        
        self.stdout.write(f'Database: {db_name}')
        self.stdout.write(f'Host: {db_host}:{db_port}')
        self.stdout.write(f'Backup file: {backup_path}\n')
        
        # Set PGPASSWORD environment variable
        env = os.environ.copy()
        if db_password:
            env['PGPASSWORD'] = db_password
        
        # Create backup using pg_dump
        try:
            self.stdout.write('Creating backup...')
            pg_dump_cmd = [
                'pg_dump',
                '-h', db_host,
                '-p', str(db_port),
                '-U', db_user,
                '-d', db_name,
                '-F', 'p',  # Plain text format
                '-f', backup_path,
                '--no-owner',
                '--no-acl',
            ]
            
            result = subprocess.run(
                pg_dump_cmd,
                env=env,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                self.stdout.write(self.style.ERROR(f'❌ Backup failed: {result.stderr}'))
                return
            
            # Get file size
            file_size = os.path.getsize(backup_path)
            file_size_mb = file_size / (1024 * 1024)
            
            self.stdout.write(self.style.SUCCESS(f'✅ Backup created: {backup_filename}'))
            self.stdout.write(f'   Size: {file_size_mb:.2f} MB')
            
            # Compress if requested
            if compress:
                self.stdout.write('Compressing backup...')
                compressed_path = f'{backup_path}.gz'
                with open(backup_path, 'rb') as f_in:
                    with gzip.open(compressed_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                os.remove(backup_path)
                compressed_size = os.path.getsize(compressed_path)
                compressed_size_mb = compressed_size / (1024 * 1024)
                compression_ratio = (1 - compressed_size / file_size) * 100
                
                self.stdout.write(self.style.SUCCESS(f'✅ Compressed: {compressed_path}'))
                self.stdout.write(f'   Size: {compressed_size_mb:.2f} MB ({compression_ratio:.1f}% reduction)')
                backup_path = compressed_path
            
            # Cleanup old backups
            if cleanup:
                self.stdout.write(f'\nCleaning up backups older than {keep_days} days...')
                cutoff_date = timezone.now() - timedelta(days=keep_days)
                deleted_count = 0
                
                for filename in os.listdir(output_dir):
                    file_path = os.path.join(output_dir, filename)
                    if os.path.isfile(file_path):
                        file_time = timezone.datetime.fromtimestamp(
                            os.path.getmtime(file_path),
                            tz=timezone.utc
                        )
                        if file_time < cutoff_date:
                            os.remove(file_path)
                            deleted_count += 1
                
                if deleted_count > 0:
                    self.stdout.write(self.style.SUCCESS(f'✅ Deleted {deleted_count} old backup(s)'))
                else:
                    self.stdout.write('   No old backups to delete')
            
            self.stdout.write(self.style.SUCCESS('\n✅ Backup completed successfully!\n'))
            
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('❌ pg_dump not found. Please install PostgreSQL client tools.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Backup failed: {e}'))





