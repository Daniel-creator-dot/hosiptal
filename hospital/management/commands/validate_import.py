"""
Django Management Command to Validate Imported Legacy Data
Checks data integrity and provides statistics
"""

from django.core.management.base import BaseCommand
from django.db import connection
from collections import defaultdict


class Command(BaseCommand):
    help = 'Validate imported legacy database and show statistics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed statistics for each table'
        )
        parser.add_argument(
            '--check-integrity',
            action='store_true',
            help='Perform integrity checks'
        )

    def handle(self, *args, **options):
        detailed = options['detailed']
        check_integrity = options['check_integrity']

        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('LEGACY DATABASE VALIDATION'))
        self.stdout.write(self.style.SUCCESS('='*70))

        # Get all legacy tables
        tables = self.get_legacy_tables()
        
        if not tables:
            self.stdout.write(self.style.WARNING('No legacy tables found'))
            return

        self.stdout.write(f'\nFound {len(tables)} legacy tables\n')

        # Categorize tables
        categorized = self.categorize_tables(tables)
        
        # Show summary by category
        self.show_category_summary(categorized)

        # Show detailed stats if requested
        if detailed:
            self.show_detailed_stats(tables)

        # Check integrity if requested
        if check_integrity:
            self.check_data_integrity(tables)

        # Show overall summary
        self.show_overall_summary(tables)

    def get_legacy_tables(self):
        """Get all legacy (non-Django) tables"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                AND name NOT LIKE 'sqlite_%'
                AND name NOT LIKE 'django_%'
                AND name NOT LIKE 'auth_%'
                ORDER BY name
            """)
            return [row[0] for row in cursor.fetchall()]

    def categorize_tables(self, tables):
        """Categorize tables by prefix/purpose"""
        categories = defaultdict(list)
        
        category_map = {
            'acc_': 'Accounting',
            'admission_': 'Admissions',
            'blood_': 'Blood Bank',
            'form_': 'Clinical Forms',
            'lab_': 'Laboratory',
            'diag_imaging_': 'Imaging',
            'drug_': 'Pharmacy',
            'insurance_': 'Insurance',
            'procedure_': 'Procedures',
            'surgery_': 'Surgery',
            'user': 'Users',
            'employee': 'HR',
            'patient': 'Patients',
        }

        for table in tables:
            categorized = False
            for prefix, category in category_map.items():
                if table.startswith(prefix) or prefix.rstrip('_') in table:
                    categories[category].append(table)
                    categorized = True
                    break
            
            if not categorized:
                categories['Other'].append(table)

        return categories

    def show_category_summary(self, categorized):
        """Show summary by category"""
        self.stdout.write('\n📊 TABLES BY CATEGORY')
        self.stdout.write('-'*70)
        
        for category in sorted(categorized.keys()):
            tables = categorized[category]
            total_rows = 0
            
            with connection.cursor() as cursor:
                for table in tables:
                    try:
                        cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                        count = cursor.fetchone()[0]
                        total_rows += count
                    except:
                        pass

            self.stdout.write(f'\n{category}:')
            self.stdout.write(f'  Tables: {len(tables)}')
            self.stdout.write(f'  Total Rows: {total_rows:,}')
            
            if len(tables) <= 5:
                for table in tables:
                    self.stdout.write(f'    - {table}')
            else:
                for table in tables[:3]:
                    self.stdout.write(f'    - {table}')
                self.stdout.write(f'    ... and {len(tables)-3} more')

    def show_detailed_stats(self, tables):
        """Show detailed statistics for each table"""
        self.stdout.write('\n\n📈 DETAILED TABLE STATISTICS')
        self.stdout.write('-'*70)

        with connection.cursor() as cursor:
            for table in tables:
                try:
                    # Get row count
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                    row_count = cursor.fetchone()[0]

                    # Get column count
                    cursor.execute(f'PRAGMA table_info("{table}")')
                    columns = cursor.fetchall()
                    col_count = len(columns)

                    self.stdout.write(f'\n{table}:')
                    self.stdout.write(f'  Rows: {row_count:,}')
                    self.stdout.write(f'  Columns: {col_count}')

                    if row_count > 0:
                        # Show sample data
                        cursor.execute(f'SELECT * FROM "{table}" LIMIT 1')
                        sample = cursor.fetchone()
                        if sample:
                            self.stdout.write(f'  Sample ID: {sample[0]}')

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'\n{table}: Error - {str(e)}'))

    def check_data_integrity(self, tables):
        """Perform basic integrity checks"""
        self.stdout.write('\n\n🔍 DATA INTEGRITY CHECKS')
        self.stdout.write('-'*70)

        issues = []

        with connection.cursor() as cursor:
            for table in tables:
                try:
                    # Check for empty tables
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                    count = cursor.fetchone()[0]
                    
                    if count == 0:
                        issues.append(f'{table}: Empty table')

                    # Check for NULL in primary key (if has 'id' column)
                    cursor.execute(f'PRAGMA table_info("{table}")')
                    columns = cursor.fetchall()
                    has_id = any(col[1] == 'id' for col in columns)
                    
                    if has_id:
                        cursor.execute(f'SELECT COUNT(*) FROM "{table}" WHERE id IS NULL')
                        null_ids = cursor.fetchone()[0]
                        if null_ids > 0:
                            issues.append(f'{table}: {null_ids} rows with NULL id')

                except Exception as e:
                    issues.append(f'{table}: Check failed - {str(e)}')

        if issues:
            self.stdout.write(self.style.WARNING(f'\nFound {len(issues)} potential issues:\n'))
            for issue in issues[:20]:  # Show first 20
                self.stdout.write(f'  ⚠️  {issue}')
            if len(issues) > 20:
                self.stdout.write(f'  ... and {len(issues)-20} more issues')
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ No integrity issues found'))

    def show_overall_summary(self, tables):
        """Show overall database summary"""
        self.stdout.write('\n\n📋 OVERALL SUMMARY')
        self.stdout.write('='*70)

        total_rows = 0
        total_size_kb = 0

        with connection.cursor() as cursor:
            # Count total rows
            for table in tables:
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                    count = cursor.fetchone()[0]
                    total_rows += count
                except:
                    pass

            # Get database size
            try:
                cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
                total_size_kb = cursor.fetchone()[0] / 1024
            except:
                pass

        self.stdout.write(f'\nTotal Tables:    {len(tables)}')
        self.stdout.write(f'Total Rows:      {total_rows:,}')
        self.stdout.write(f'Database Size:   {total_size_kb:,.2f} KB ({total_size_kb/1024:.2f} MB)')
        
        # Top tables by row count
        self.stdout.write('\n\n🏆 TOP 10 TABLES BY ROW COUNT')
        self.stdout.write('-'*70)
        
        table_counts = []
        with connection.cursor() as cursor:
            for table in tables:
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                    count = cursor.fetchone()[0]
                    table_counts.append((table, count))
                except:
                    pass

        table_counts.sort(key=lambda x: x[1], reverse=True)
        
        for i, (table, count) in enumerate(table_counts[:10], 1):
            self.stdout.write(f'{i:2d}. {table:40s} {count:>10,} rows')

        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('✓ Validation Complete'))
        self.stdout.write('='*70)




















