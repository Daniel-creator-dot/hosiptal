"""
Create Sample Procurement Requests for Testing
This will create test requests so you can see the approval workflow
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_procurement import ProcurementRequest, ProcurementRequestItem, Store, Supplier
from hospital.models import Staff
from django.contrib.auth.models import User
from decimal import Decimal


def create_sample_requests():
    print("="*70)
    print("CREATING SAMPLE PROCUREMENT REQUESTS")
    print("="*70)
    print()
    
    # Get or create a store
    store = Store.objects.first()
    if not store:
        print("[INFO] Creating sample store...")
        store = Store.objects.create(
            name="Main Pharmacy",
            store_type="pharmacy",
            location="Building A, Floor 1"
        )
    
    # Get or create a staff member
    staff = Staff.objects.first()
    user = User.objects.filter(is_superuser=True).first()
    
    # Get or create supplier
    supplier = Supplier.objects.first()
    if not supplier:
        print("[INFO] Creating sample supplier...")
        supplier = Supplier.objects.create(
            name="MedSupply Corp",
            contact_person="John Doe",
            phone="0201234567",
            email="contact@medsupply.com"
        )
    
    # Create 3 sample requests
    requests_data = [
        {
            'priority': 'urgent',
            'justification': 'Critical shortage of Paracetamol in pharmacy. High patient demand.',
            'items': [
                ('Paracetamol 500mg Tablets', 10000, 'tablets', Decimal('0.50')),
                ('Ibuprofen 400mg Tablets', 5000, 'tablets', Decimal('0.75')),
            ]
        },
        {
            'priority': 'high',
            'justification': 'Need surgical gloves for upcoming surgeries scheduled this week.',
            'items': [
                ('Surgical Gloves (Medium)', 500, 'boxes', Decimal('15.00')),
                ('Surgical Gloves (Large)', 500, 'boxes', Decimal('15.00')),
                ('Face Masks (N95)', 1000, 'pieces', Decimal('2.50')),
            ]
        },
        {
            'priority': 'normal',
            'justification': 'Monthly restock of laboratory supplies.',
            'items': [
                ('Blood Collection Tubes', 1000, 'pieces', Decimal('1.20')),
                ('Syringes 5ml', 2000, 'pieces', Decimal('0.80')),
                ('Alcohol Swabs', 5000, 'pieces', Decimal('0.10')),
            ]
        },
    ]
    
    created_count = 0
    
    for idx, req_data in enumerate(requests_data, 1):
        try:
            # Create procurement request
            pr = ProcurementRequest.objects.create(
                requested_by_store=store,
                requested_by=staff,
                priority=req_data['priority'],
                justification=req_data['justification'],
                status='submitted',  # Ready for admin approval
                notes=f"Sample request {idx} for testing",
            )
            
            # Add items
            total = Decimal('0.00')
            for item_name, quantity, unit, unit_price in req_data['items']:
                line_total = quantity * unit_price
                total += line_total
                
                ProcurementRequestItem.objects.create(
                    request=pr,
                    item_name=item_name,
                    quantity=quantity,
                    unit_of_measure=unit,
                    estimated_unit_price=unit_price,
                    line_total=line_total,
                    preferred_supplier=supplier
                )
            
            # Update total
            pr.total_amount = total
            pr.save()
            
            print(f"[OK] Created: {pr.request_number}")
            print(f"     Priority: {req_data['priority'].upper()}")
            print(f"     Items: {len(req_data['items'])}")
            print(f"     Total: ${total:,.2f}")
            print(f"     Status: SUBMITTED (Ready for admin approval)")
            print()
            
            created_count += 1
        
        except Exception as e:
            print(f"[ERROR] Failed to create request {idx}: {e}")
            print()
    
    print("="*70)
    print(f"CREATED: {created_count} sample procurement requests")
    print("="*70)
    print()
    
    if created_count > 0:
        print("NOW YOU CAN:")
        print("  1. Go to: http://127.0.0.1:8000/hms/")
        print("  2. See alert: 'Administrator Approval Needed'")
        print("  3. Click: 'Review Requests Now'")
        print("  4. Approve the requests")
        print("  5. Watch auto-accounting work!")
        print()
        print("THESE REQUESTS ARE READY FOR APPROVAL!")
    
    print()


if __name__ == '__main__':
    try:
        create_sample_requests()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()




















