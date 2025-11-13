#!/usr/bin/env python
"""
Fix Service Types for Existing Payment Receipts
This updates historical receipts so revenue dashboard shows correct breakdown
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import PaymentReceipt
from django.db.models import Q

def fix_service_types():
    """Update service_type for existing receipts based on invoice/encounter data"""
    
    print("=" * 70)
    print("Fixing Service Types for Payment Receipts")
    print("=" * 70)
    print()
    
    # Get receipts with 'other' or empty service_type
    receipts_to_fix = PaymentReceipt.objects.filter(
        Q(service_type='other') | Q(service_type='') | Q(service_type__isnull=True),
        is_deleted=False
    )
    
    total = receipts_to_fix.count()
    print(f"Found {total} receipts to update...")
    print()
    
    updated = 0
    for receipt in receipts_to_fix:
        service_type = 'other'  # Default
        
        try:
            # Try to detect from invoice/encounter
            if receipt.invoice and hasattr(receipt.invoice, 'encounter'):
                encounter = receipt.invoice.encounter
                if encounter:
                    # Check encounter type
                    if encounter.encounter_type == 'er':
                        service_type = 'emergency'
                    elif encounter.encounter_type == 'surgery':
                        service_type = 'procedure'
                    elif encounter.current_activity:
                        # Check current activities
                        activities = encounter.current_activity.lower()
                        if 'lab' in activities:
                            service_type = 'lab'
                        elif 'pharmacy' in activities:
                            service_type = 'pharmacy'
                        elif 'imaging' in activities:
                            service_type = 'imaging'
                        elif 'consult' in activities:
                            service_type = 'consultation'
                    else:
                        # Default to consultation for outpatient
                        if encounter.encounter_type == 'outpatient':
                            service_type = 'consultation'
            
            # Update if changed
            if service_type != receipt.service_type:
                receipt.service_type = service_type
                receipt.save(update_fields=['service_type'])
                updated += 1
                
                if updated % 10 == 0:
                    print(f"  Updated {updated}/{total} receipts...")
                    
        except Exception as e:
            print(f"  Error updating receipt {receipt.receipt_number}: {e}")
            continue
    
    print()
    print("=" * 70)
    print("[SUCCESS] COMPLETE!")
    print(f"   Updated: {updated} receipts")
    print(f"   Unchanged: {total - updated} receipts")
    print("=" * 70)
    print()
    print("Refresh your dashboard to see updated revenue breakdown!")
    print()

if __name__ == '__main__':
    fix_service_types()

