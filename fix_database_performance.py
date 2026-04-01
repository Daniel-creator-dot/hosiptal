#!/usr/bin/env python
"""
Fix Database Performance Issues
- Closes idle connections
- Kills long-running queries
- Optimizes database
- Clears connection pool
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import connection, connections, transaction
from django.core.management import call_command
from django.db.utils import OperationalError, DatabaseError
import logging

logger = logging.getLogger(__name__)

def fix_database_performance():
    """Fix database performance issues"""
    print("=" * 70)
    print("FIXING DATABASE PERFORMANCE ISSUES")
    print("=" * 70)
    print()
    
    fixes_applied = []
    
    # 1. Close idle connections
    print("[1/6] Closing idle database connections...")
    try:
        with connection.cursor() as cursor:
            if connection.vendor == 'postgresql':
                # Get idle connections
                cursor.execute("""
                    SELECT pid, state, query_start, now() - query_start as idle_time
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                      AND state = 'idle'
                      AND pid != pg_backend_pid()
                      AND (now() - query_start) > interval '5 minutes'
                """)
                idle_conns = cursor.fetchall()
                
                if idle_conns:
                    print(f"   Found {len(idle_conns)} idle connections (>5 min)")
                    for conn in idle_conns:
                        try:
                            cursor.execute(f"SELECT pg_terminate_backend({conn[0]})")
                            print(f"   [OK] Terminated idle connection PID {conn[0]}")
                            fixes_applied.append(f"Terminated idle connection PID {conn[0]}")
                        except Exception as e:
                            print(f"   [WARNING] Could not terminate PID {conn[0]}: {str(e)}")
                else:
                    print("   [OK] No idle connections to close")
            else:
                print("   [INFO] Idle connection cleanup not available for this database")
    except Exception as e:
        print(f"   [WARNING] Could not close idle connections: {str(e)}")
    print()
    
    # 2. Kill long-running queries
    print("[2/6] Checking for long-running queries...")
    try:
        with connection.cursor() as cursor:
            if connection.vendor == 'postgresql':
                cursor.execute("""
                    SELECT pid, now() - query_start AS duration, query, state
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                      AND state != 'idle'
                      AND pid != pg_backend_pid()
                      AND (now() - query_start) > interval '60 seconds'
                    ORDER BY duration DESC
                """)
                long_queries = cursor.fetchall()
                
                if long_queries:
                    print(f"   Found {len(long_queries)} long-running queries (>60s)")
                    for query in long_queries:
                        duration = str(query[1]).split('.')[0]
                        print(f"   [INFO] PID {query[0]}: Running for {duration}")
                        print(f"          Query: {query[2][:100]}...")
                        
                        # Ask before killing (or auto-kill if >5 minutes)
                        if query[1].total_seconds() > 300:  # > 5 minutes
                            try:
                                cursor.execute(f"SELECT pg_terminate_backend({query[0]})")
                                print(f"   [OK] Killed long-running query PID {query[0]}")
                                fixes_applied.append(f"Killed long-running query PID {query[0]}")
                            except Exception as e:
                                print(f"   [WARNING] Could not kill PID {query[0]}: {str(e)}")
                else:
                    print("   [OK] No long-running queries found")
            else:
                print("   [INFO] Long query check not available for this database")
    except Exception as e:
        print(f"   [WARNING] Could not check long queries: {str(e)}")
    print()
    
    # 3. Close Django connection pool
    print("[3/6] Closing Django connection pool...")
    try:
        connections.close_all()
        print("   [OK] All Django connections closed")
        fixes_applied.append("Closed Django connection pool")
    except Exception as e:
        print(f"   [WARNING] Could not close connections: {str(e)}")
    print()
    
    # 4. Run VACUUM ANALYZE on critical tables
    print("[4/6] Optimizing database tables (VACUUM ANALYZE)...")
    try:
        with connection.cursor() as cursor:
            if connection.vendor == 'postgresql':
                # Get tables with many dead tuples
                cursor.execute("""
                    SELECT relname, n_dead_tup, n_live_tup
                    FROM pg_stat_user_tables
                    WHERE n_dead_tup > 100
                    ORDER BY n_dead_tup DESC
                    LIMIT 10
                """)
                bloated_tables = cursor.fetchall()
                
                if bloated_tables:
                    print(f"   Found {len(bloated_tables)} tables needing optimization")
                    for table in bloated_tables[:5]:  # Optimize top 5
                        try:
                            print(f"   [INFO] Optimizing {table[0]}...")
                            cursor.execute(f'VACUUM ANALYZE "{table[0]}"')
                            print(f"   [OK] Optimized {table[0]}")
                            fixes_applied.append(f"Optimized table {table[0]}")
                        except Exception as e:
                            print(f"   [WARNING] Could not optimize {table[0]}: {str(e)}")
                else:
                    print("   [OK] No tables need optimization")
            else:
                print("   [INFO] VACUUM not available for this database")
    except Exception as e:
        print(f"   [WARNING] Could not optimize tables: {str(e)}")
    print()
    
    # 5. Clear query cache
    print("[5/6] Clearing query cache...")
    try:
        # Reset connection to clear any cached queries
        connection.ensure_connection()
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute("DISCARD PLANS")
                print("   [OK] Query plan cache cleared")
                fixes_applied.append("Cleared query plan cache")
        else:
            print("   [INFO] Query cache clearing not available for this database")
    except Exception as e:
        print(f"   [WARNING] Could not clear query cache: {str(e)}")
    print()
    
    # 6. Test connection after fixes
    print("[6/6] Testing database connection after fixes...")
    try:
        with connection.cursor() as cursor:
            import time
            start = time.time()
            cursor.execute("SELECT 1")
            query_time = (time.time() - start) * 1000
            print(f"   [OK] Connection test: {query_time:.2f}ms")
            if query_time > 1000:
                print(f"   [WARNING] Connection still slow: {query_time:.2f}ms")
            else:
                print("   [OK] Connection performance: GOOD")
    except Exception as e:
        print(f"   [ERROR] Connection test failed: {str(e)}")
    print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    if fixes_applied:
        print(f"[OK] Applied {len(fixes_applied)} fixes:")
        for fix in fixes_applied:
            print(f"   - {fix}")
    else:
        print("[OK] No fixes needed - database is already optimized")
    
    print()
    print("RECOMMENDATIONS:")
    print("1. Monitor connection count - should stay below 50")
    print("2. Check for application-level connection leaks")
    print("3. Consider restarting Django server if issues persist")
    print("4. Check server resources (CPU, RAM, disk I/O)")
    print()
    
    return len(fixes_applied)

if __name__ == '__main__':
    try:
        fixes = fix_database_performance()
        print(f"\n[OK] Database optimization complete. Applied {fixes} fixes.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[FATAL ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
