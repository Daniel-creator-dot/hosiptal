"""
Fix Procurement Request Amounts
Calculate total_amount from items for all requests
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_procurement import ProcurementRequest, ProcurementRequestItem
from decimal import Decimal


def fix_all_amounts():
    print("="*70)
    print("FIXING PROCUREMENT REQUEST AMOUNTS")
    print("="*70)
    print()
    
    # Get all procurement requests
    all_requests = ProcurementRequest.objects.filter(is_deleted=False)
    
    print(f"Found {all_requests.count()} procurement requests")
    print()
    
    fixed_count = 0
    
    for pr in all_requests:
        # Calculate total from items
        items = pr.items.all()
        total = Decimal('0.00')
        
        for item in items:
            # Ensure line_total is calculated
            if not item.line_total or item.line_total == 0:
                item.line_total = item.quantity * item.estimated_unit_price
                item.save()
            
            total += item.line_total
        
        # Update procurement request total
        if pr.estimated_total != total or not pr.estimated_total:
            pr.estimated_total = total
            pr.save()
            
            print(f"[OK] {pr.request_number}: GHS {total:,.2f} ({items.count()} items)")
            fixed_count += 1
        else:
            print(f"[SKIP] {pr.request_number}: Already correct (GHS {total:,.2f})")
    
    print()
    print("="*70)
    print(f"FIXED: {fixed_count} procurement requests")
    print("="*70)
    print()
    
    # Show current totals
    print("CURRENT PROCUREMENT REQUESTS:")
    print()
    for pr in ProcurementRequest.objects.filter(is_deleted=False).order_by('-created')[:10]:
        status_display = pr.get_status_display() if hasattr(pr, 'get_status_display') else pr.status
        print(f"  {pr.request_number}: GHS {pr.estimated_total:,.2f} - {status_display}")
    
    print()
    print("REFRESH BROWSER TO SEE AMOUNTS!")
    print()


if __name__ == '__main__':
    try:
        fix_all_amounts()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

