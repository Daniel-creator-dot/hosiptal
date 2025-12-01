"""
World-Class Database Health Check System
Comprehensive database monitoring and health reporting
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
from datetime import timedelta
import json


class Command(BaseCommand):
    help = 'Comprehensive database health check and performance monitoring'

    def add_arguments(self, parser):
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output results as JSON',
        )
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed information',
        )

    def handle(self, *args, **options):
        output_json = options['json']
        detailed = options['detailed']
        
        health_data = {
            'timestamp': timezone.now().isoformat(),
            'status': 'healthy',
            'checks': {},
            'performance': {},
            'recommendations': []
        }
        
        with connection.cursor() as cursor:
            # 1. Database Connection Check
            self.stdout.write('\n=== Database Health Check ===\n')
            try:
                cursor.execute('SELECT version()')
                db_version = cursor.fetchone()[0]
                health_data['checks']['connection'] = {'status': 'ok', 'version': db_version}
                self.stdout.write(self.style.SUCCESS(f'✅ Database Connection: OK'))
                if detailed:
                    self.stdout.write(f'   Version: {db_version}')
            except Exception as e:
                health_data['checks']['connection'] = {'status': 'error', 'error': str(e)}
                health_data['status'] = 'unhealthy'
                self.stdout.write(self.style.ERROR(f'❌ Database Connection: FAILED - {e}'))
                return
            
            # 2. Database Size
            try:
                cursor.execute("""
                    SELECT 
                        pg_size_pretty(pg_database_size(current_database())) as size,
                        pg_database_size(current_database()) as size_bytes
                """)
                result = cursor.fetchone()
                db_size = result[0]
                db_size_bytes = result[1]
                health_data['performance']['database_size'] = {
                    'formatted': db_size,
                    'bytes': db_size_bytes
                }
                self.stdout.write(self.style.SUCCESS(f'✅ Database Size: {db_size}'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'⚠️  Could not get database size: {e}'))
            
            # 3. Table Count
            try:
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                """)
                table_count = cursor.fetchone()[0]
                health_data['checks']['table_count'] = {'count': table_count, 'status': 'ok'}
                self.stdout.write(self.style.SUCCESS(f'✅ Tables: {table_count}'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'⚠️  Could not count tables: {e}'))
            
            # 4. Connection Status
            try:
                cursor.execute("""
                    SELECT 
                        count(*) as total_connections,
                        count(*) FILTER (WHERE state = 'active') as active_connections,
                        count(*) FILTER (WHERE state = 'idle') as idle_connections,
                        count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                """)
                conn_stats = cursor.fetchone()
                health_data['performance']['connections'] = {
                    'total': conn_stats[0],
                    'active': conn_stats[1],
                    'idle': conn_stats[2],
                    'idle_in_transaction': conn_stats[3]
                }
                self.stdout.write(self.style.SUCCESS(f'✅ Connections: {conn_stats[0]} total ({conn_stats[1]} active, {conn_stats[2]} idle)'))
                
                # Check for connection issues
                if conn_stats[3] > 0:
                    health_data['recommendations'].append('Warning: Idle in transaction connections detected')
                    self.stdout.write(self.style.WARNING(f'⚠️  Idle in transaction: {conn_stats[3]}'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'⚠️  Could not get connection stats: {e}'))
            
            # 5. Index Health
            try:
                cursor.execute("""
                    SELECT 
                        schemaname,
                        relname as tablename,
                        indexrelname as indexname,
                        idx_scan as index_scans,
                        idx_tup_read as tuples_read,
                        idx_tup_fetch as tuples_fetched
                    FROM pg_stat_user_indexes
                    WHERE idx_scan = 0
                    ORDER BY schemaname, relname
                    LIMIT 10
                """)
                unused_indexes = cursor.fetchall()
                if unused_indexes:
                    health_data['recommendations'].append(f'Found {len(unused_indexes)} potentially unused indexes')
                    self.stdout.write(self.style.WARNING(f'⚠️  Unused Indexes: {len(unused_indexes)} (showing first 10)'))
                    if detailed:
                        for idx in unused_indexes[:5]:
                            self.stdout.write(f'   - {idx[1]}.{idx[2]}')
                else:
                    self.stdout.write(self.style.SUCCESS('✅ Index Usage: All indexes are being used'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'⚠️  Could not check index usage: {e}'))
            
            # 6. Table Statistics
            try:
                cursor.execute("""
                    SELECT 
                        schemaname,
                        relname as tablename,
                        n_live_tup as row_count,
                        n_dead_tup as dead_rows,
                        last_vacuum,
                        last_autovacuum,
                        last_analyze,
                        last_autoanalyze
                    FROM pg_stat_user_tables
                    WHERE schemaname = 'public'
                    ORDER BY n_live_tup DESC
                    LIMIT 10
                """)
                table_stats = cursor.fetchall()
                health_data['performance']['top_tables'] = []
                self.stdout.write('\n📊 Top Tables by Row Count:')
                for stat in table_stats:
                    table_name = stat[1]
                    row_count = stat[2]
                    dead_rows = stat[3]
                    health_data['performance']['top_tables'].append({
                        'table': table_name,
                        'rows': row_count,
                        'dead_rows': dead_rows
                    })
                    if detailed:
                        self.stdout.write(f'   {table_name}: {row_count:,} rows ({dead_rows:,} dead)')
                    else:
                        self.stdout.write(f'   {table_name}: {row_count:,} rows')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'⚠️  Could not get table statistics: {e}'))
            
            # 7. Long Running Queries
            try:
                cursor.execute("""
                    SELECT 
                        pid,
                        now() - pg_stat_activity.query_start AS duration,
                        query,
                        state
                    FROM pg_stat_activity
                    WHERE (now() - pg_stat_activity.query_start) > interval '5 seconds'
                    AND state != 'idle'
                    AND datname = current_database()
                    ORDER BY duration DESC
                    LIMIT 5
                """)
                long_queries = cursor.fetchall()
                if long_queries:
                    health_data['recommendations'].append(f'Found {len(long_queries)} long-running queries')
                    self.stdout.write(self.style.WARNING(f'\n⚠️  Long Running Queries: {len(long_queries)}'))
                    for query in long_queries:
                        duration = query[1]
                        query_text = query[2][:100] if len(query[2]) > 100 else query[2]
                        self.stdout.write(f'   Duration: {duration}, Query: {query_text}...')
                else:
                    self.stdout.write(self.style.SUCCESS('\n✅ No Long Running Queries'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'⚠️  Could not check long queries: {e}'))
            
            # 8. Cache Hit Ratio
            try:
                cursor.execute("""
                    SELECT 
                        sum(heap_blks_read) as heap_read,
                        sum(heap_blks_hit) as heap_hit,
                        sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0) as ratio
                    FROM pg_statio_user_tables
                """)
                cache_stats = cursor.fetchone()
                if cache_stats and cache_stats[2]:
                    cache_ratio = float(cache_stats[2]) * 100
                    health_data['performance']['cache_hit_ratio'] = cache_ratio
                    if cache_ratio > 95:
                        self.stdout.write(self.style.SUCCESS(f'\n✅ Cache Hit Ratio: {cache_ratio:.2f}% (Excellent)'))
                    elif cache_ratio > 90:
                        self.stdout.write(self.style.SUCCESS(f'\n✅ Cache Hit Ratio: {cache_ratio:.2f}% (Good)'))
                    else:
                        health_data['recommendations'].append('Cache hit ratio is below 90%, consider increasing shared_buffers')
                        self.stdout.write(self.style.WARNING(f'\n⚠️  Cache Hit Ratio: {cache_ratio:.2f}% (Should be > 90%)'))
                else:
                    self.stdout.write(self.style.WARNING('\n⚠️  Could not calculate cache hit ratio'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'⚠️  Could not check cache: {e}'))
            
            # 9. Database Locks
            try:
                cursor.execute("""
                    SELECT count(*) 
                    FROM pg_locks 
                    WHERE NOT granted
                """)
                waiting_locks = cursor.fetchone()[0]
                if waiting_locks > 0:
                    health_data['recommendations'].append(f'Found {waiting_locks} waiting locks')
                    health_data['status'] = 'degraded'
                    self.stdout.write(self.style.WARNING(f'\n⚠️  Waiting Locks: {waiting_locks}'))
                else:
                    self.stdout.write(self.style.SUCCESS('\n✅ No Waiting Locks'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'⚠️  Could not check locks: {e}'))
        
        # Summary
        self.stdout.write('\n' + '='*50)
        if health_data['status'] == 'healthy':
            self.stdout.write(self.style.SUCCESS('✅ Database Health: EXCELLENT'))
        elif health_data['status'] == 'degraded':
            self.stdout.write(self.style.WARNING('⚠️  Database Health: DEGRADED'))
        else:
            self.stdout.write(self.style.ERROR('❌ Database Health: UNHEALTHY'))
        
        if health_data['recommendations']:
            self.stdout.write('\n📋 Recommendations:')
            for rec in health_data['recommendations']:
                self.stdout.write(f'   - {rec}')
        
        if output_json:
            self.stdout.write('\n' + json.dumps(health_data, indent=2))
        
        self.stdout.write('\n')

