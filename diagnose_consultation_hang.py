#!/usr/bin/env python
"""
Diagnose why consultation page is hanging
Checks for:
- Slow database queries
- Blocking operations
- Missing indexes
- Connection issues
"""
import os
import sys
import django
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import connection
from hospital.models import Encounter, Order, Prescription, LabResult, ImagingStudy
from hospital.models_advanced import ClinicalNote, Diagnosis, ProblemList
import logging

logger = logging.getLogger(__name__)

def diagnose_consultation_hang():
    """Diagnose why consultation page hangs"""
    print("=" * 70)
    print("CONSULTATION PAGE HANG DIAGNOSTIC")
    print("=" * 70)
    print()
    
    issues = []
    
    # Test encounter lookup (what the view does first)
    print("[1/6] Testing encounter lookup...")
    try:
        start = time.time()
        # Simulate the exact query from consultation_view
        encounter = Encounter.objects.select_related(
            'patient', 'provider', 'provider__user', 'provider__department', 'location'
        ).filter(is_deleted=False).first()
        elapsed = (time.time() - start) * 1000
        print(f"   [OK] Encounter lookup: {elapsed:.2f}ms")
        if elapsed > 1000:
            issues.append(f"Slow encounter lookup: {elapsed:.2f}ms")
    except Exception as e:
        issues.append(f"Encounter lookup failed: {str(e)}")
        print(f"   [ERROR] {str(e)}")
    print()
    
    # Test orders query (often slow)
    print("[2/6] Testing orders query...")
    try:
        if encounter:
            start = time.time()
            orders = Order.objects.filter(
                encounter=encounter,
                is_deleted=False
            ).select_related(
                'requested_by', 'requested_by__user'
            ).prefetch_related(
                'imaging_studies', 'lab_results', 'prescriptions'
            ).order_by('-created')[:10]
            list(orders)  # Force evaluation
            elapsed = (time.time() - start) * 1000
            print(f"   [OK] Orders query: {elapsed:.2f}ms")
            if elapsed > 2000:
                issues.append(f"Slow orders query: {elapsed:.2f}ms")
        else:
            print("   [SKIP] No encounter to test")
    except Exception as e:
        issues.append(f"Orders query failed: {str(e)}")
        print(f"   [ERROR] {str(e)}")
    print()
    
    # Test prescriptions query
    print("[3/6] Testing prescriptions query...")
    try:
        if encounter:
            start = time.time()
            prescriptions = Prescription.objects.filter(
                order__encounter=encounter,
                is_deleted=False
            ).select_related(
                'drug', 'prescribed_by', 'prescribed_by__user', 'order'
            ).order_by('-created')[:10]
            list(prescriptions)  # Force evaluation
            elapsed = (time.time() - start) * 1000
            print(f"   [OK] Prescriptions query: {elapsed:.2f}ms")
            if elapsed > 2000:
                issues.append(f"Slow prescriptions query: {elapsed:.2f}ms")
        else:
            print("   [SKIP] No encounter to test")
    except Exception as e:
        issues.append(f"Prescriptions query failed: {str(e)}")
        print(f"   [ERROR] {str(e)}")
    print()
    
    # Test clinical notes query
    print("[4/6] Testing clinical notes query...")
    try:
        if encounter:
            start = time.time()
            notes = ClinicalNote.objects.filter(
                encounter=encounter,
                is_deleted=False
            ).select_related('created_by', 'created_by__user').order_by('-created')[:10]
            list(notes)  # Force evaluation
            elapsed = (time.time() - start) * 1000
            print(f"   [OK] Clinical notes query: {elapsed:.2f}ms")
            if elapsed > 2000:
                issues.append(f"Slow clinical notes query: {elapsed:.2f}ms")
        else:
            print("   [SKIP] No encounter to test")
    except Exception as e:
        issues.append(f"Clinical notes query failed: {str(e)}")
        print(f"   [ERROR] {str(e)}")
    print()
    
    # Check for missing indexes
    print("[5/6] Checking for missing indexes...")
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename IN ('hospital_encounter', 'hospital_order', 'hospital_prescription', 'hospital_clinicalnote')
                ORDER BY tablename, indexname
            """)
            indexes = cursor.fetchall()
            print(f"   [INFO] Found {len(indexes)} indexes on consultation tables")
            
            # Check for critical missing indexes
            index_names = [idx[2] for idx in indexes]
            if 'hospital_encounter_is_deleted_idx' not in index_names:
                issues.append("Missing index on Encounter.is_deleted")
            if 'hospital_order_encounter_id_idx' not in index_names:
                issues.append("Missing index on Order.encounter_id")
    except Exception as e:
        print(f"   [WARNING] Could not check indexes: {str(e)}")
    print()
    
    # Check active queries
    print("[6/6] Checking for blocking queries...")
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    pid,
                    state,
                    now() - query_start as duration,
                    query
                FROM pg_stat_activity
                WHERE datname = current_database()
                  AND state != 'idle'
                  AND pid != pg_backend_pid()
                ORDER BY duration DESC
                LIMIT 5
            """)
            active_queries = cursor.fetchall()
            if active_queries:
                print(f"   [WARNING] Found {len(active_queries)} active queries:")
                for q in active_queries:
                    duration = str(q[2]).split('.')[0]
                    print(f"      - PID {q[0]}: {duration} - {q[3][:80]}...")
            else:
                print("   [OK] No blocking queries found")
    except Exception as e:
        print(f"   [WARNING] Could not check queries: {str(e)}")
    print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    if issues:
        print(f"[CRITICAL] Found {len(issues)} issues:")
        for issue in issues:
            print(f"   - {issue}")
        print()
        print("RECOMMENDATIONS:")
        print("1. Add missing database indexes")
        print("2. Optimize slow queries with select_related/prefetch_related")
        print("3. Consider pagination for large result sets")
        print("4. Check for N+1 query problems")
    else:
        print("[OK] No obvious performance issues found")
        print("   Issue might be in template rendering or JavaScript")
    
    print()
    return len(issues)

if __name__ == '__main__':
    try:
        issues = diagnose_consultation_hang()
        sys.exit(0 if issues == 0 else 1)
    except Exception as e:
        print(f"\n[FATAL ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
