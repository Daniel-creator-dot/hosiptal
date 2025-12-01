"""
World-Class Database Optimization System
Automated database maintenance and optimization
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    help = 'Optimize database performance (VACUUM, ANALYZE, REINDEX)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--vacuum',
            action='store_true',
            help='Run VACUUM on all tables',
        )
        parser.add_argument(
            '--analyze',
            action='store_true',
            help='Run ANALYZE on all tables',
        )
        parser.add_argument(
            '--reindex',
            action='store_true',
            help='Rebuild all indexes',
        )
        parser.add_argument(
            '--full',
            action='store_true',
            help='Run full optimization (VACUUM FULL, ANALYZE, REINDEX)',
        )
        parser.add_argument(
            '--table',
            type=str,
            help='Optimize specific table only',
        )

    def handle(self, *args, **options):
        vacuum = options['vacuum'] or options['full']
        analyze = options['analyze'] or options['full']
        reindex = options['reindex'] or options['full']
        table = options['table']
        full = options['full']
        
        self.stdout.write('\n=== Database Optimization ===\n')
        
        with connection.cursor() as cursor:
            # Get tables to optimize
            if table:
                tables = [table]
                self.stdout.write(f'Optimizing table: {table}\n')
            else:
                cursor.execute("""
                    SELECT tablename 
                    FROM pg_tables 
                    WHERE schemaname = 'public'
                    ORDER BY tablename
                """)
                tables = [row[0] for row in cursor.fetchall()]
                self.stdout.write(f'Found {len(tables)} tables to optimize\n')
            
            # VACUUM
            if vacuum:
                self.stdout.write('Running VACUUM...')
                for table_name in tables:
                    try:
                        vacuum_type = 'VACUUM FULL' if full else 'VACUUM'
                        cursor.execute(f'{vacuum_type} "{table_name}"')
                        self.stdout.write(self.style.SUCCESS(f'   ✅ {table_name}'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'   ❌ {table_name}: {e}'))
                self.stdout.write('')
            
            # ANALYZE
            if analyze:
                self.stdout.write('Running ANALYZE...')
                for table_name in tables:
                    try:
                        cursor.execute(f'ANALYZE "{table_name}"')
                        self.stdout.write(self.style.SUCCESS(f'   ✅ {table_name}'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'   ❌ {table_name}: {e}'))
                self.stdout.write('')
            
            # REINDEX
            if reindex:
                self.stdout.write('Rebuilding indexes...')
                try:
                    if table:
                        cursor.execute(f'REINDEX TABLE "{table}"')
                        self.stdout.write(self.style.SUCCESS(f'   ✅ Indexes for {table}'))
                    else:
                        cursor.execute('REINDEX DATABASE current_database()')
                        self.stdout.write(self.style.SUCCESS('   ✅ All indexes'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'   ❌ REINDEX failed: {e}'))
                self.stdout.write('')
        
        self.stdout.write(self.style.SUCCESS('✅ Database optimization completed!\n'))





