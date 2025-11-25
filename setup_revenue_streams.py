"""
Setup Revenue Streams
Create default revenue streams for monitoring
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Department
from hospital.models_revenue_streams import RevenueStream
from decimal import Decimal


def create_revenue_streams():
    print("="*70)
    print("CREATING REVENUE STREAMS")
    print("="*70)
    print()
    
    # Get departments
    try:
        lab_dept = Department.objects.filter(name__icontains='lab').first()
        pharmacy_dept = Department.objects.filter(name__icontains='pharm').first()
        dental_dept = Department.objects.filter(name__icontains='dent').first()
        gynec_dept = Department.objects.filter(name__icontains='gyn').first()
    except:
        lab_dept = pharmacy_dept = dental_dept = gynec_dept = None
    
    streams_data = [
        {
            'code': 'CONSULT',
            'name': 'Consultation Services',
            'stream_type': 'clinical',
            'department': None,
            'monthly_target': Decimal('50000.00'),
            'annual_target': Decimal('600000.00'),
        },
        {
            'code': 'LAB',
            'name': 'Laboratory Services',
            'stream_type': 'diagnostic',
            'department': lab_dept,
            'monthly_target': Decimal('30000.00'),
            'annual_target': Decimal('360000.00'),
        },
        {
            'code': 'PHARM',
            'name': 'Pharmacy Sales',
            'stream_type': 'pharmacy',
            'department': pharmacy_dept,
            'monthly_target': Decimal('80000.00'),
            'annual_target': Decimal('960000.00'),
        },
        {
            'code': 'IMAGING',
            'name': 'Imaging & Radiology',
            'stream_type': 'diagnostic',
            'department': None,
            'monthly_target': Decimal('25000.00'),
            'annual_target': Decimal('300000.00'),
        },
        {
            'code': 'DENTAL',
            'name': 'Dental Services',
            'stream_type': 'clinical',
            'department': dental_dept,
            'monthly_target': Decimal('15000.00'),
            'annual_target': Decimal('180000.00'),
        },
        {
            'code': 'GYNEC',
            'name': 'Gynecology Services',
            'stream_type': 'clinical',
            'department': gynec_dept,
            'monthly_target': Decimal('20000.00'),
            'annual_target': Decimal('240000.00'),
        },
        {
            'code': 'SURGERY',
            'name': 'Surgical Procedures',
            'stream_type': 'clinical',
            'department': None,
            'monthly_target': Decimal('100000.00'),
            'annual_target': Decimal('1200000.00'),
        },
        {
            'code': 'EMERGENCY',
            'name': 'Emergency Services',
            'stream_type': 'clinical',
            'department': None,
            'monthly_target': Decimal('40000.00'),
            'annual_target': Decimal('480000.00'),
        },
        {
            'code': 'ADMISSION',
            'name': 'Admission Fees',
            'stream_type': 'administrative',
            'department': None,
            'monthly_target': Decimal('20000.00'),
            'annual_target': Decimal('240000.00'),
        },
        {
            'code': 'OUTPATIENT',
            'name': 'Outpatient Services',
            'stream_type': 'clinical',
            'department': None,
            'monthly_target': Decimal('35000.00'),
            'annual_target': Decimal('420000.00'),
        },
    ]
    
    created_count = 0
    
    for stream_data in streams_data:
        stream, created = RevenueStream.objects.get_or_create(
            code=stream_data['code'],
            defaults=stream_data
        )
        
        if created:
            print(f"[OK] Created: {stream.code} - {stream.name}")
            print(f"     Type: {stream.get_stream_type_display()}")
            print(f"     Monthly Target: GHS {stream.monthly_target:,.2f}")
            created_count += 1
        else:
            print(f"[SKIP] {stream.code} already exists")
    
    print()
    print("="*70)
    print(f"CREATED: {created_count} revenue streams")
    print("="*70)
    print()
    
    if created_count > 0:
        print("Revenue streams created for:")
        print("  - Consultation")
        print("  - Laboratory")
        print("  - Pharmacy")
        print("  - Imaging")
        print("  - Dental")
        print("  - Gynecology")
        print("  - Surgery")
        print("  - Emergency")
        print("  - Admission")
        print("  - Outpatient")
        print()
        print("Access Revenue Streams Dashboard:")
        print("  http://127.0.0.1:8000/hms/accounting/revenue-streams/")
    
    print()


if __name__ == '__main__':
    try:
        create_revenue_streams()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()




















