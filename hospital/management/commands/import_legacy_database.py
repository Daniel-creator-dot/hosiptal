"""
Django Management Command to Import Legacy Database from SQL Files
This command reads SQL files from a directory and imports them into the Django database
"""

import os
import re
import glob
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import legacy database from SQL files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sql-dir',
            type=str,
            default=r'C:\Users\user\Videos\DS',
            help='Directory containing SQL files'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing'
        )
        parser.add_argument(
            '--skip-drop',
            action='store_true',
            help='Skip DROP TABLE statements'
        )
        parser.add_argument(
            '--tables',
            nargs='+',
            help='Specific tables to import (e.g., blood_donors blood_stock)'
        )

    def handle(self, *args, **options):
        sql_dir = options['sql_dir']
        dry_run = options['dry_run']
        skip_drop = options['skip_drop']
        specific_tables = options.get('tables')

        if not os.path.exists(sql_dir):
            raise CommandError(f'SQL directory does not exist: {sql_dir}')

        self.stdout.write(self.style.SUCCESS(f'Starting database import from: {sql_dir}'))
        self.stdout.write(self.style.WARNING(f'Dry run: {dry_run}'))

        # Get all SQL files
        sql_files = glob.glob(os.path.join(sql_dir, '*.sql'))
        sql_files.sort()

        self.stdout.write(f'Found {len(sql_files)} SQL files')

        # Filter by specific tables if provided
        if specific_tables:
            filtered_files = []
            for table_name in specific_tables:
                matching = [f for f in sql_files if table_name.lower() in os.path.basename(f).lower()]
                filtered_files.extend(matching)
            sql_files = filtered_files
            self.stdout.write(f'Filtered to {len(sql_files)} files matching: {specific_tables}')

        # Statistics
        stats = {
            'total_files': len(sql_files),
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'tables_created': 0,
            'rows_inserted': 0
        }

        # Process each file
        for sql_file in sql_files:
            try:
                filename = os.path.basename(sql_file)
                self.stdout.write(f'\nProcessing: {filename}')
                
                result = self.process_sql_file(sql_file, dry_run, skip_drop)
                
                stats['processed'] += 1
                stats['tables_created'] += result.get('tables_created', 0)
                stats['rows_inserted'] += result.get('rows_inserted', 0)
                
                self.stdout.write(self.style.SUCCESS(
                    f'  [OK] Tables: {result.get("tables_created", 0)}, Rows: {result.get("rows_inserted", 0)}'
                ))
                
            except Exception as e:
                stats['errors'] += 1
                self.stdout.write(self.style.ERROR(f'  [ERROR] {str(e)}'))
                logger.exception(f'Error processing {filename}')

        # Print summary
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('IMPORT SUMMARY'))
        self.stdout.write('='*70)
        self.stdout.write(f'Total files:      {stats["total_files"]}')
        self.stdout.write(f'Processed:        {stats["processed"]}')
        self.stdout.write(f'Errors:           {stats["errors"]}')
        self.stdout.write(f'Tables created:   {stats["tables_created"]}')
        self.stdout.write(f'Rows inserted:    {stats["rows_inserted"]}')
        self.stdout.write('='*70)

        if dry_run:
            self.stdout.write(self.style.WARNING('\nThis was a DRY RUN. No changes were made to the database.'))

    def process_sql_file(self, sql_file, dry_run=False, skip_drop=False):
        """Process a single SQL file"""
        with open(sql_file, 'r', encoding='utf-8', errors='ignore') as f:
            sql_content = f.read()

        # Convert MySQL to database-compatible SQL (SQLite or PostgreSQL)
        sql_content = self.convert_mysql_to_database(sql_content, skip_drop)

        # Split into individual statements
        statements = self.split_sql_statements(sql_content)

        result = {'tables_created': 0, 'rows_inserted': 0}

        if not dry_run:
            total_statements = len(statements)
            self.stdout.write(f'  Executing {total_statements:,} SQL statements...')
            
            with connection.cursor() as cursor:
                for idx, statement in enumerate(statements, 1):
                    statement = statement.strip()
                    if not statement or statement.startswith('--'):
                        continue

                    try:
                        cursor.execute(statement)
                        
                        # Track statistics
                        if statement.upper().startswith('CREATE TABLE'):
                            result['tables_created'] += 1
                            self.stdout.write(f'  ✓ Table created')
                        elif statement.upper().startswith('INSERT INTO'):
                            result['rows_inserted'] += 1
                            # Show progress every 1000 inserts
                            if result['rows_inserted'] % 1000 == 0:
                                self.stdout.write(f'  ✓ Inserted {result["rows_inserted"]:,} rows...')
                            
                    except Exception as e:
                        # Show first few errors, then suppress
                        error_msg = str(e)[:200]
                        if result.get('error_count', 0) < 5:
                            self.stdout.write(self.style.WARNING(f'  ⚠️  Error: {error_msg}'))
                        result['error_count'] = result.get('error_count', 0) + 1
                        logger.debug(f'Statement failed: {error_msg}')
                        
        return result

    def convert_mysql_to_database(self, sql_content, skip_drop=False):
        """Convert MySQL SQL syntax to database-compatible syntax (SQLite or PostgreSQL)"""
        from django.db import connection
        vendor = connection.vendor
        
        if vendor == 'postgresql':
            return self.convert_mysql_to_postgresql(sql_content, skip_drop)
        else:
            return self.convert_mysql_to_sqlite(sql_content, skip_drop)
    
    def convert_mysql_to_sqlite(self, sql_content, skip_drop=False):
        """Convert MySQL SQL syntax to SQLite compatible syntax"""
        
        # Remove DROP TABLE if requested
        if skip_drop:
            sql_content = re.sub(r'DROP TABLE .*?;', '', sql_content, flags=re.IGNORECASE)

        # Remove MySQL-specific keywords
        sql_content = re.sub(r'ENGINE\s*=\s*\w+', '', sql_content, flags=re.IGNORECASE)
        sql_content = re.sub(r'DEFAULT CHARSET\s*=\s*\w+', '', sql_content, flags=re.IGNORECASE)
        sql_content = re.sub(r'CHARSET\s+\w+', '', sql_content, flags=re.IGNORECASE)
        sql_content = re.sub(r'COLLATE\s+\w+', '', sql_content, flags=re.IGNORECASE)
        sql_content = re.sub(r'AUTO_INCREMENT\s*=\s*\d+', '', sql_content, flags=re.IGNORECASE)
        sql_content = re.sub(r'COMMENT\s+["\'].*?["\']', '', sql_content, flags=re.IGNORECASE)
        
        # Convert AUTO_INCREMENT to AUTOINCREMENT
        sql_content = re.sub(r'AUTO_INCREMENT', 'AUTOINCREMENT', sql_content, flags=re.IGNORECASE)
        
        # Convert MySQL types to SQLite types
        type_mappings = {
            r'INT\(\d+\)': 'INTEGER',
            r'BIGINT\(\d+\)': 'INTEGER',
            r'TINYINT\(\d+\)': 'INTEGER',
            r'SMALLINT\(\d+\)': 'INTEGER',
            r'MEDIUMINT\(\d+\)': 'INTEGER',
            r'FLOAT\(\d+,\d+\)': 'REAL',
            r'DOUBLE(\(\d+,\d+\))?': 'REAL',
            r'DECIMAL\(\d+,\d+\)': 'REAL',
            r'TINYTEXT': 'TEXT',
            r'MEDIUMTEXT': 'TEXT',
            r'LONGTEXT': 'TEXT',
            r'TINYBLOB': 'BLOB',
            r'MEDIUMBLOB': 'BLOB',
            r'LONGBLOB': 'BLOB',
            r'DATETIME': 'TEXT',
            r'TIMESTAMP': 'TEXT',
            r'DATE': 'TEXT',
            r'TIME': 'TEXT',
        }
        
        for mysql_type, sqlite_type in type_mappings.items():
            sql_content = re.sub(mysql_type, sqlite_type, sql_content, flags=re.IGNORECASE)
        
        # Remove UNSIGNED
        sql_content = re.sub(r'\s+UNSIGNED', '', sql_content, flags=re.IGNORECASE)
        
        # Convert backticks to double quotes for identifiers
        sql_content = sql_content.replace('`', '"')
        
        # Fix DEFAULT CURRENT_TIMESTAMP
        sql_content = re.sub(
            r"DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
            "DEFAULT CURRENT_TIMESTAMP",
            sql_content,
            flags=re.IGNORECASE
        )
        
        # Remove KEY definitions that SQLite doesn't support the same way
        sql_content = re.sub(r',\s*KEY\s+"[^"]+"\s+\([^)]+\)', '', sql_content, flags=re.IGNORECASE)
        sql_content = re.sub(r',\s*INDEX\s+"[^"]+"\s+\([^)]+\)', '', sql_content, flags=re.IGNORECASE)
        
        # Handle ENUM types (convert to TEXT with CHECK constraint)
        sql_content = re.sub(
            r'ENUM\s*\([^)]+\)',
            'TEXT',
            sql_content,
            flags=re.IGNORECASE
        )
        
        # Remove IF EXISTS/IF NOT EXISTS in some contexts where SQLite might not support
        # But keep them for DROP and CREATE statements
        
        return sql_content

    def convert_mysql_to_postgresql(self, sql_content, skip_drop=False):
        """Convert MySQL SQL syntax to PostgreSQL compatible syntax"""
        
        # Remove DROP TABLE if requested
        if skip_drop:
            sql_content = re.sub(r'DROP TABLE .*?;', '', sql_content, flags=re.IGNORECASE)

        # Remove MySQL-specific keywords
        sql_content = re.sub(r'ENGINE\s*=\s*\w+', '', sql_content, flags=re.IGNORECASE)
        sql_content = re.sub(r'DEFAULT CHARSET\s*=\s*\w+', '', sql_content, flags=re.IGNORECASE)
        sql_content = re.sub(r'CHARSET\s+\w+', '', sql_content, flags=re.IGNORECASE)
        sql_content = re.sub(r'COLLATE\s+\w+', '', sql_content, flags=re.IGNORECASE)
        sql_content = re.sub(r'AUTO_INCREMENT\s*=\s*\d+', '', sql_content, flags=re.IGNORECASE)
        sql_content = re.sub(r'COMMENT\s+["\'].*?["\']', '', sql_content, flags=re.IGNORECASE)
        
        # Convert AUTO_INCREMENT to SERIAL (PostgreSQL)
        # Handle: AUTO_INCREMENT -> SERIAL, but need to handle NOT NULL AUTO_INCREMENT properly
        sql_content = re.sub(
            r'(\w+)\s+(BIGINT|INT|INTEGER)\(?\d*\)?\s+NOT\s+NULL\s+AUTO_INCREMENT',
            r'\1 SERIAL',
            sql_content,
            flags=re.IGNORECASE
        )
        sql_content = re.sub(
            r'(\w+)\s+(BIGINT|INT|INTEGER)\(?\d*\)?\s+AUTO_INCREMENT',
            r'\1 SERIAL',
            sql_content,
            flags=re.IGNORECASE
        )
        sql_content = re.sub(r'AUTO_INCREMENT', 'SERIAL', sql_content, flags=re.IGNORECASE)
        
        # Convert MySQL types to PostgreSQL types
        type_mappings = {
            r'BIGINT\(20\)': 'BIGINT',
            r'INT\(11\)': 'INTEGER',
            r'INT\(\d+\)': 'INTEGER',
            r'TINYINT\(\d+\)': 'SMALLINT',
            r'SMALLINT\(\d+\)': 'SMALLINT',
            r'MEDIUMINT\(\d+\)': 'INTEGER',
            r'FLOAT\(\d+,\d+\)': 'REAL',
            r'DOUBLE(\(\d+,\d+\))?': 'DOUBLE PRECISION',
            r'DECIMAL\(\d+,\d+\)': 'NUMERIC',
            r'TINYTEXT': 'TEXT',
            r'MEDIUMTEXT': 'TEXT',
            r'LONGTEXT': 'TEXT',
            r'TINYBLOB': 'BYTEA',
            r'MEDIUMBLOB': 'BYTEA',
            r'LONGBLOB': 'BYTEA',
            r'DATETIME': 'TIMESTAMP',
            r'TIMESTAMP': 'TIMESTAMP',
            r'DATE': 'DATE',
            r'TIME': 'TIME',
        }
        
        for mysql_type, pg_type in type_mappings.items():
            sql_content = re.sub(mysql_type, pg_type, sql_content, flags=re.IGNORECASE)
        
        # Remove UNSIGNED (PostgreSQL doesn't have unsigned)
        sql_content = re.sub(r'\s+UNSIGNED', '', sql_content, flags=re.IGNORECASE)
        
        # Convert backticks to double quotes for identifiers (PostgreSQL uses double quotes)
        sql_content = sql_content.replace('`', '"')
        
        # Fix DEFAULT CURRENT_TIMESTAMP
        sql_content = re.sub(
            r"DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
            "DEFAULT CURRENT_TIMESTAMP",
            sql_content,
            flags=re.IGNORECASE
        )
        
        # Handle ENUM types (PostgreSQL supports ENUM, but convert to TEXT for simplicity)
        sql_content = re.sub(
            r'ENUM\s*\([^)]+\)',
            'TEXT',
            sql_content,
            flags=re.IGNORECASE
        )
        
        # PostgreSQL uses single quotes for string literals in INSERT statements
        # But we'll handle this in the statement execution
        
        return sql_content

    def split_sql_statements(self, sql_content):
        """Split SQL content into individual statements"""
        # Remove comments
        sql_content = re.sub(r'--.*?$', '', sql_content, flags=re.MULTILINE)
        sql_content = re.sub(r'/\*.*?\*/', '', sql_content, flags=re.DOTALL)
        
        # Split by semicolons (but not within quotes)
        statements = []
        current_statement = []
        in_quotes = False
        quote_char = None
        
        for i, char in enumerate(sql_content):
            if char in ('"', "'") and (i == 0 or sql_content[i-1] != '\\'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
            
            if char == ';' and not in_quotes:
                current_statement.append(char)
                stmt = ''.join(current_statement).strip()
                if stmt:
                    statements.append(stmt)
                current_statement = []
            else:
                current_statement.append(char)
        
        # Add any remaining statement
        stmt = ''.join(current_statement).strip()
        if stmt:
            statements.append(stmt)
        
        return statements

