"""
Management command to fix SQLite database locks
Run this if you're experiencing "database is locked" errors
"""
from django.core.management.base import BaseCommand
from django.db import connection
import os
import time


class Command(BaseCommand):
    help = "Fix SQLite database locks by closing connections and enabling WAL mode"

    def handle(self, *args, **options):
        db_path = connection.settings_dict.get('NAME', '')
        
        if not db_path or 'sqlite' not in connection.settings_dict.get('ENGINE', ''):
            self.stdout.write(self.style.WARNING('This command is only for SQLite databases.'))
            return
        
        self.stdout.write('Fixing SQLite database locks...')
        
        # Close all database connections
        connection.close()
        
        # Enable WAL mode if database file exists
        if os.path.exists(db_path):
            try:
                import sqlite3
                conn = sqlite3.connect(db_path, timeout=60)
                cursor = conn.cursor()
                
                # Enable WAL mode for better concurrency
                cursor.execute("PRAGMA journal_mode=WAL;")
                result = cursor.fetchone()
                self.stdout.write(self.style.SUCCESS(f'Journal mode set to: {result[0]}'))
                
                # Set busy timeout
                cursor.execute("PRAGMA busy_timeout=60000;")
                self.stdout.write(self.style.SUCCESS('Busy timeout set to 60 seconds'))
                
                # Set synchronous mode to NORMAL for better performance
                cursor.execute("PRAGMA synchronous=NORMAL;")
                self.stdout.write(self.style.SUCCESS('Synchronous mode set to NORMAL'))
                
                conn.close()
                
                self.stdout.write(self.style.SUCCESS(
                    f'✓ SQLite database at {db_path} has been configured for better concurrency.'
                ))
                self.stdout.write(self.style.SUCCESS(
                    '✓ WAL mode enabled - allows multiple readers and one writer simultaneously.'
                ))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error fixing database: {e}'))
        else:
            self.stdout.write(self.style.WARNING(f'Database file not found: {db_path}'))
        
        self.stdout.write(self.style.SUCCESS('\nDone! Try accessing the application again.'))


