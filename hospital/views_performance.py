"""
Performance Monitoring Views
Query optimization and performance metrics
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.db import connection
from django.utils import timezone
from django.core.cache import cache
import logging
import time
from .utils_roles import get_user_role

logger = logging.getLogger(__name__)


def is_admin(user):
    """Strict admin check (no is_staff fallback)."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return get_user_role(user) == 'admin'


@login_required
@user_passes_test(is_admin)
def performance_dashboard(request):
    """Performance monitoring dashboard"""
    
    # Get database query stats
    db_stats = get_database_stats()
    
    # Get cache stats
    cache_stats = get_cache_stats()
    
    # Get slow queries (if available)
    slow_queries = get_slow_queries()
    
    context = {
        'title': 'Performance Monitoring',
        'db_stats': db_stats,
        'cache_stats': cache_stats,
        'slow_queries': slow_queries,
    }
    
    return render(request, 'hospital/admin/performance_dashboard.html', context)


def get_database_stats():
    """Get database performance statistics"""
    try:
        with connection.cursor() as cursor:
            # Get connection count
            cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
            connection_count = cursor.fetchone()[0]
            
            # Get database size
            cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
            db_size = cursor.fetchone()[0]
            
            # Get table sizes
            cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                LIMIT 10
            """)
            large_tables = cursor.fetchall()
            
            # Get index usage stats
            cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan as index_scans
                FROM pg_stat_user_indexes
                WHERE idx_scan = 0
                ORDER BY schemaname, tablename
                LIMIT 20
            """)
            unused_indexes = cursor.fetchall()
            
            return {
                'connection_count': connection_count,
                'database_size': db_size,
                'large_tables': large_tables,
                'unused_indexes': unused_indexes,
            }
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {
            'error': str(e)
        }


def get_cache_stats():
    """Get cache performance statistics"""
    try:
        # Test cache performance
        test_key = 'perf_test'
        start = time.time()
        cache.set(test_key, 'test', 1)
        set_time = (time.time() - start) * 1000  # milliseconds
        
        start = time.time()
        cache.get(test_key)
        get_time = (time.time() - start) * 1000  # milliseconds
        cache.delete(test_key)
        
        return {
            'set_time_ms': round(set_time, 2),
            'get_time_ms': round(get_time, 2),
            'backend': cache.__class__.__name__ if hasattr(cache, '__class__') else 'Unknown',
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {
            'error': str(e)
        }


def get_slow_queries():
    """Get slow query information (if available)"""
    # This would require pg_stat_statements extension
    # For now, return empty list
    return []


@login_required
@user_passes_test(is_admin)
def performance_api(request):
    """API endpoint for performance metrics"""
    db_stats = get_database_stats()
    cache_stats = get_cache_stats()
    
    return JsonResponse({
        'db_stats': db_stats,
        'cache_stats': cache_stats,
        'timestamp': timezone.now().isoformat(),
    })






