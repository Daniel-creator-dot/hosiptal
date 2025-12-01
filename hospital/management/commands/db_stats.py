"""
World-Class Database Statistics and Analytics
Comprehensive database performance metrics and insights
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
import json


class Command(BaseCommand):
    help = 'Display comprehensive database statistics and performance metrics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output as JSON',
        )
        parser.add_argument(
            '--table',
            type=str,
            help='Show stats for specific table',
        )

    def handle(self, *args, **options):
        output_json = options['json']
        table_name = options['table']
        
        stats = {
            'timestamp': timezone.now().isoformat(),
            'database': {},
            'tables': {},
            'performance': {},
            'indexes': {}
        }
        
        with connection.cursor() as cursor:
            # Database Info
            cursor.execute("""
                SELECT 
                    current_database() as db_name,
                    pg_size_pretty(pg_database_size(current_database())) as size,
                    pg_database_size(current_database()) as size_bytes,
                    (SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()) as connections
            """)
            db_info = cursor.fetchone()
            stats['database'] = {
                'name': db_info[0],
                'size': db_info[1],
                'size_bytes': db_info[2],
                'connections': db_info[3]
            }
            
            if not output_json:
                self.stdout.write('\n=== Database Statistics ===\n')
                self.stdout.write(f"Database: {db_info[0]}")
                self.stdout.write(f"Size: {db_info[1]}")
                self.stdout.write(f"Active Connections: {db_info[3]}\n")
            
            # Table Statistics
            if table_name:
                tables = [table_name]
            else:
                cursor.execute("""
                    SELECT tablename 
                    FROM pg_tables 
                    WHERE schemaname = 'public'
                    ORDER BY tablename
                """)
                tables = [row[0] for row in cursor.fetchall()]
            
            if not output_json:
                self.stdout.write('📊 Table Statistics:\n')
            
            for table in tables:
                cursor.execute(f"""
                    SELECT 
                        n_live_tup as rows,
                        n_dead_tup as dead_rows,
                        last_vacuum,
                        last_autovacuum,
                        last_analyze,
                        last_autoanalyze,
                        seq_scan as sequential_scans,
                        seq_tup_read as seq_tuples_read,
                        idx_scan as index_scans,
                        idx_tup_fetch as idx_tuples_fetched
                    FROM pg_stat_user_tables
                    WHERE relname = %s
                """, [table])
                
                result = cursor.fetchone()
                if result:
                    table_stats = {
                        'rows': result[0],
                        'dead_rows': result[1],
                        'last_vacuum': str(result[2]) if result[2] else None,
                        'last_autovacuum': str(result[3]) if result[3] else None,
                        'last_analyze': str(result[4]) if result[4] else None,
                        'last_autoanalyze': str(result[5]) if result[5] else None,
                        'sequential_scans': result[6],
                        'seq_tuples_read': result[7],
                        'index_scans': result[8],
                        'idx_tuples_fetched': result[9]
                    }
                    stats['tables'][table] = table_stats
                    
                    if not output_json:
                        self.stdout.write(f"  {table}:")
                        self.stdout.write(f"    Rows: {result[0]:,}")
                        self.stdout.write(f"    Dead Rows: {result[1]:,}")
                        self.stdout.write(f"    Sequential Scans: {result[6]:,}")
                        self.stdout.write(f"    Index Scans: {result[8]:,}")
                        if result[8] > 0:
                            ratio = (result[8] / (result[6] + result[8])) * 100
                            self.stdout.write(f"    Index Usage: {ratio:.1f}%")
                        self.stdout.write('')
            
            # Performance Metrics
            cursor.execute("""
                SELECT 
                    sum(heap_blks_read) as heap_read,
                    sum(heap_blks_hit) as heap_hit,
                    sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0) as cache_hit_ratio
                FROM pg_statio_user_tables
            """)
            perf = cursor.fetchone()
            if perf and perf[2]:
                stats['performance']['cache_hit_ratio'] = float(perf[2]) * 100
                if not output_json:
                    self.stdout.write(f"Cache Hit Ratio: {float(perf[2]) * 100:.2f}%\n")
            
            # Index Statistics
            cursor.execute("""
                SELECT 
                    schemaname,
                    relname as tablename,
                    indexrelname as indexname,
                    idx_scan as scans,
                    idx_tup_read as tuples_read,
                    idx_tup_fetch as tuples_fetched
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                ORDER BY idx_scan DESC
                LIMIT 20
            """)
            top_indexes = cursor.fetchall()
            stats['indexes']['top_used'] = []
            
            if not output_json:
                self.stdout.write('🔍 Top Indexes by Usage:\n')
            for idx in top_indexes:
                idx_stat = {
                    'table': idx[1],
                    'index': idx[2],
                    'scans': idx[3],
                    'tuples_read': idx[4],
                    'tuples_fetched': idx[5]
                }
                stats['indexes']['top_used'].append(idx_stat)
                if not output_json:
                    self.stdout.write(f"  {idx[1]}.{idx[2]}: {idx[3]:,} scans")
        
        if output_json:
            self.stdout.write(json.dumps(stats, indent=2))
        else:
            self.stdout.write('\n✅ Statistics generated\n')

