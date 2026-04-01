#!/usr/bin/env python
"""
Database Health Check and Performance Diagnostic Script
Checks for database issues, slow queries, locks, and connection problems
"""
import os
import sys
import django
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import connection, connections
from django.core.management import call_command
from django.db.utils import OperationalError, DatabaseError
import logging

logger = logging.getLogger(__name__)

def check_database_health():
    """Comprehensive database health check"""
    print("=" * 70)
    print("DATABASE HEALTH CHECK & PERFORMANCE DIAGNOSTIC")
    print("=" * 70)
    print()
    
    issues_found = []
    warnings = []
    
    # 1. Check database connection
    print("[1/8] Checking database connection...")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result:
                print("   [OK] Database connection: OK")
            else:
                issues_found.append("Database connection returned no result")
                print("   [ERROR] Database connection: FAILED")
    except OperationalError as e:
        issues_found.append(f"Database connection error: {str(e)}")
        print(f"   [ERROR] Database connection: FAILED - {str(e)}")
    except Exception as e:
        issues_found.append(f"Unexpected database error: {str(e)}")
        print(f"   [ERROR] Database connection: ERROR - {str(e)}")
    print()
    
    # 2. Check for active connections
    print("[2/8] Checking active database connections...")
    try:
        with connection.cursor() as cursor:
            if connection.vendor == 'postgresql':
                cursor.execute("""
                    SELECT count(*) as active_connections 
                    FROM pg_stat_activity 
                    WHERE datname = current_database()
                """)
                result = cursor.fetchone()
                active_conns = result[0] if result else 0
                print(f"   Active connections: {active_conns}")
                
                if active_conns > 50:
                    warnings.append(f"High number of active connections: {active_conns}")
                    print(f"   ⚠️  WARNING: High number of connections ({active_conns})")
                else:
                    print("   [OK] Connection count: OK")
            else:
                print("   ℹ️  Connection count check not available for this database")
    except Exception as e:
        warnings.append(f"Could not check connection count: {str(e)}")
        print(f"   ⚠️  Could not check connection count: {str(e)}")
    print()
    
    # 3. Check for locks
    print("[3/8] Checking for database locks...")
    try:
        with connection.cursor() as cursor:
            if connection.vendor == 'postgresql':
                cursor.execute("""
                    SELECT count(*) as lock_count
                    FROM pg_locks 
                    WHERE NOT granted
                """)
                result = cursor.fetchone()
                lock_count = result[0] if result else 0
                
                if lock_count > 0:
                    issues_found.append(f"Found {lock_count} ungranted locks")
                    print(f"   ❌ Found {lock_count} ungranted locks (BLOCKING)")
                    
                    # Get details of blocking locks
                    cursor.execute("""
                        SELECT 
                            l.locktype,
                            l.database,
                            l.relation::regclass,
                            l.pid,
                            l.mode,
                            l.granted,
                            a.query,
                            a.state
                        FROM pg_locks l
                        JOIN pg_stat_activity a ON l.pid = a.pid
                        WHERE NOT l.granted
                        LIMIT 10
                    """)
                    locks = cursor.fetchall()
                    if locks:
                        print("   Blocking queries:")
                        for lock in locks:
                            print(f"      - PID {lock[3]}: {lock[6][:100]}...")
                else:
                    print("   [OK] No blocking locks found")
            else:
                print("   ℹ️  Lock check not available for this database")
    except Exception as e:
        warnings.append(f"Could not check locks: {str(e)}")
        print(f"   ⚠️  Could not check locks: {str(e)}")
    print()
    
    # 4. Check for long-running queries
    print("[4/8] Checking for long-running queries...")
    try:
        with connection.cursor() as cursor:
            if connection.vendor == 'postgresql':
                cursor.execute("""
                    SELECT 
                        pid,
                        now() - pg_stat_activity.query_start AS duration,
                        query,
                        state
                    FROM pg_stat_activity
                    WHERE (now() - pg_stat_activity.query_start) > interval '30 seconds'
                      AND state != 'idle'
                    ORDER BY duration DESC
                    LIMIT 10
                """)
                long_queries = cursor.fetchall()
                
                if long_queries:
                    issues_found.append(f"Found {len(long_queries)} long-running queries")
                    print(f"   ❌ Found {len(long_queries)} long-running queries (>30s):")
                    for query in long_queries:
                        duration = str(query[1]).split('.')[0]  # Remove microseconds
                        print(f"      - PID {query[0]}: {duration} - {query[2][:80]}...")
                else:
                    print("   [OK] No long-running queries found")
            else:
                print("   ℹ️  Long query check not available for this database")
    except Exception as e:
        warnings.append(f"Could not check long queries: {str(e)}")
        print(f"   ⚠️  Could not check long queries: {str(e)}")
    print()
    
    # 5. Check database size and bloat
    print("[5/8] Checking database size...")
    try:
        with connection.cursor() as cursor:
            if connection.vendor == 'postgresql':
                cursor.execute("""
                    SELECT 
                        pg_size_pretty(pg_database_size(current_database())) as db_size,
                        pg_database_size(current_database()) as db_size_bytes
                """)
                result = cursor.fetchone()
                if result:
                    db_size = result[0]
                    db_size_bytes = result[1]
                    print(f"   Database size: {db_size}")
                    
                    # Check if database is very large (>10GB)
                    if db_size_bytes > 10 * 1024 * 1024 * 1024:  # 10GB
                        warnings.append(f"Large database size: {db_size}")
                        print(f"   ⚠️  WARNING: Large database ({db_size})")
                    else:
                        print("   [OK] Database size: OK")
            else:
                print("   ℹ️  Size check not available for this database")
    except Exception as e:
        warnings.append(f"Could not check database size: {str(e)}")
        print(f"   ⚠️  Could not check database size: {str(e)}")
    print()
    
    # 6. Check table statistics (last vacuum/analyze)
    print("[6/8] Checking table statistics...")
    try:
        with connection.cursor() as cursor:
            if connection.vendor == 'postgresql':
                cursor.execute("""
                    SELECT 
                        schemaname,
                        relname as tablename,
                        last_vacuum,
                        last_autovacuum,
                        last_analyze,
                        last_autoanalyze,
                        n_dead_tup,
                        n_live_tup
                    FROM pg_stat_user_tables
                    WHERE n_dead_tup > 1000
                    ORDER BY n_dead_tup DESC
                    LIMIT 10
                """)
                bloated_tables = cursor.fetchall()
                
                if bloated_tables:
                    warnings.append(f"Found {len(bloated_tables)} tables with dead tuples")
                    print(f"   ⚠️  Found {len(bloated_tables)} tables with many dead tuples:")
                    for table in bloated_tables:
                        print(f"      - {table[1]}: {table[6]} dead tuples, {table[7]} live tuples")
                else:
                    print("   [OK] Table statistics: OK")
            else:
                print("   ℹ️  Statistics check not available for this database")
    except Exception as e:
        warnings.append(f"Could not check table statistics: {str(e)}")
        print(f"   ⚠️  Could not check statistics: {str(e)}")
    print()
    
    # 7. Test query performance
    print("[7/8] Testing query performance...")
    try:
        from hospital.models import Patient, Encounter
        
        # Test simple query
        start_time = time.time()
        count = Patient.objects.filter(is_deleted=False).count()
        simple_query_time = (time.time() - start_time) * 1000  # Convert to ms
        
        if simple_query_time > 1000:  # > 1 second
            issues_found.append(f"Slow simple query: {simple_query_time:.2f}ms")
            print(f"   ❌ Simple query too slow: {simple_query_time:.2f}ms")
        else:
            print(f"   [OK] Simple query performance: {simple_query_time:.2f}ms")
        
        # Test join query
        start_time = time.time()
        encounters = Encounter.objects.filter(is_deleted=False).select_related('patient')[:10]
        list(encounters)  # Force evaluation
        join_query_time = (time.time() - start_time) * 1000
        
        if join_query_time > 2000:  # > 2 seconds
            issues_found.append(f"Slow join query: {join_query_time:.2f}ms")
            print(f"   [ERROR] Join query too slow: {join_query_time:.2f}ms")
        else:
            print(f"   [OK] Join query performance: {join_query_time:.2f}ms")
            
    except Exception as e:
        warnings.append(f"Could not test query performance: {str(e)}")
        print(f"   ⚠️  Could not test query performance: {str(e)}")
    print()
    
    # 8. Check for missing indexes on frequently queried fields
    print("[8/8] Checking for potential missing indexes...")
    try:
        with connection.cursor() as cursor:
            if connection.vendor == 'postgresql':
                # Check for tables with many rows but missing indexes on common filter fields
                cursor.execute("""
                    SELECT 
                        schemaname,
                        relname as tablename,
                        n_live_tup as row_count
                    FROM pg_stat_user_tables
                    WHERE n_live_tup > 10000
                    ORDER BY n_live_tup DESC
                    LIMIT 5
                """)
                large_tables = cursor.fetchall()
                
                if large_tables:
                    print("   Large tables (>10k rows):")
                    for table in large_tables:
                        print(f"      - {table[1]}: {table[2]:,} rows")
                    print("   ℹ️  Consider adding indexes on frequently filtered columns")
                else:
                    print("   [OK] No extremely large tables found")
            else:
                print("   ℹ️  Index check not available for this database")
    except Exception as e:
        warnings.append(f"Could not check indexes: {str(e)}")
        print(f"   ⚠️  Could not check indexes: {str(e)}")
    print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    if issues_found:
        print(f"[CRITICAL] ISSUES FOUND: {len(issues_found)}")
        for issue in issues_found:
            print(f"   - {issue}")
        print()
        print("RECOMMENDED ACTIONS:")
        print("1. Kill long-running queries if blocking")
        print("2. Check for database locks and resolve them")
        print("3. Restart database server if connection issues persist")
        print("4. Run VACUUM ANALYZE to optimize tables")
        print("5. Check server resources (CPU, RAM, disk)")
    else:
        print("[OK] No critical issues found")
    
    if warnings:
        print(f"\n[WARNING] WARNINGS: {len(warnings)}")
        for warning in warnings:
            print(f"   - {warning}")
    
    if not issues_found and not warnings:
        print("[OK] Database health: EXCELLENT")
        print("   All checks passed successfully!")
    
    print()
    return len(issues_found) == 0

if __name__ == '__main__':
    try:
        is_healthy = check_database_health()
        sys.exit(0 if is_healthy else 1)
    except Exception as e:
        print(f"\n[FATAL ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
