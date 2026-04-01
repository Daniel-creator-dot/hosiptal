"""
Revenue Stream Monitoring Views
Monitor where revenue is coming from
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.http import JsonResponse
from decimal import Decimal
from datetime import timedelta

from .models import Department
from .models_revenue_streams import RevenueStream, DepartmentRevenue
from .models_accounting_advanced import Revenue


@login_required
def revenue_streams_dashboard(request):
    """
    Main dashboard for revenue stream monitoring
    Shows breakdown by department and service type
    """
    # Date range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if not date_from:
        # Default to current month
        today = timezone.now().date()
        date_from = today.replace(day=1)
    else:
        date_from = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
    
    if not date_to:
        date_to = timezone.now().date()
    else:
        date_to = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
    
    # Get revenue by service type - REAL-TIME from PaymentReceipts
    try:
        from .models_accounting import PaymentReceipt
        
        # Get all payment receipts in date range
        payment_receipts = PaymentReceipt.objects.filter(
            receipt_date__gte=date_from,
            receipt_date__lte=date_to,
            is_deleted=False
        ).values('service_type').annotate(
            total=Sum('amount_paid'),
            count=Count('id')
        ).order_by('-total')
        
        # Convert to list and calculate percentages
        revenue_by_service = list(payment_receipts)
        total_revenue = sum(item['total'] or Decimal('0') for item in revenue_by_service)
        
        # Add readable names and percentages
        service_type_names = {
            'lab': 'Laboratory',
            'pharmacy': 'Pharmacy',
            'imaging': 'Imaging',
            'imaging_study': 'Imaging',
            'consultation': 'Consultation',
            'admission': 'Admission',
            'procedure': 'Surgery',
            'dental': 'Dental',
            'gynecology': 'Gynecology',
            'emergency': 'Emergency',
            'combined': 'Combined Services',
            'other': 'Other'
        }
        
        for item in revenue_by_service:
            if total_revenue > 0:
                item['percentage'] = (item['total'] / total_revenue) * 100
            else:
                item['percentage'] = 0
            
            # Add readable name
            item['service_name'] = service_type_names.get(item['service_type'], item['service_type'].title())
        
        # FALLBACK: If no payment receipts, try Revenue table
        if not revenue_by_service:
            revenue_by_service = Revenue.objects.filter(
                revenue_date__gte=date_from,
                revenue_date__lte=date_to,
                is_deleted=False
            ).values('service_type').annotate(
                total=Sum('amount'),
                count=Count('id')
            ).order_by('-total')
            
            total_revenue = sum(item['total'] or Decimal('0') for item in revenue_by_service)
            for item in revenue_by_service:
                if total_revenue > 0:
                    item['percentage'] = (item['total'] / total_revenue) * 100
                else:
                    item['percentage'] = 0
                item['service_name'] = service_type_names.get(item['service_type'], item['service_type'].title())
        
    except Exception as e:
        import traceback
        print(f"Error getting revenue: {e}")
        print(traceback.format_exc())
        revenue_by_service = []
        total_revenue = Decimal('0.00')
    
    # Get revenue by department
    try:
        revenue_by_dept = Revenue.objects.filter(
            revenue_date__gte=date_from,
            revenue_date__lte=date_to,
            is_deleted=False,
            department__isnull=False
        ).values('department__name').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')
        
        # Calculate percentages
        for item in revenue_by_dept:
            if total_revenue > 0:
                item['percentage'] = (item['total'] / total_revenue) * 100
            else:
                item['percentage'] = 0
    except:
        revenue_by_dept = []
    
    # Get top revenue streams
    try:
        revenue_streams = RevenueStream.objects.filter(is_active=True)
        stream_performance = []
        
        for stream in revenue_streams:
            stream_revenue = Revenue.objects.filter(
                revenue_stream=stream,
                revenue_date__gte=date_from,
                revenue_date__lte=date_to,
                is_deleted=False
            ).aggregate(
                total=Sum('amount'),
                count=Count('id')
            )
            
            stream_performance.append({
                'stream': stream,
                'total': stream_revenue['total'] or Decimal('0.00'),
                'count': stream_revenue['count'] or 0,
                'target': stream.monthly_target,
                'achievement': ((stream_revenue['total'] or Decimal('0.00')) / stream.monthly_target * 100) if stream.monthly_target > 0 else 0
            })
        
        stream_performance.sort(key=lambda x: x['total'], reverse=True)
    except:
        stream_performance = []
    
    # Summary statistics - Get from PaymentReceipts (real-time data)
    try:
        # Consultation revenue
        consultation_revenue = PaymentReceipt.objects.filter(
            Q(service_type='consultation') | Q(service_type='outpatient'),
            receipt_date__gte=date_from,
            receipt_date__lte=date_to,
            is_deleted=False
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        
        # Lab revenue - includes lab, lab_test, lab_result, laboratory
        lab_revenue = PaymentReceipt.objects.filter(
            Q(service_type='lab') | Q(service_type='lab_test') | Q(service_type='lab_result') | Q(service_type='laboratory'),
            receipt_date__gte=date_from,
            receipt_date__lte=date_to,
            is_deleted=False
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        
        # Pharmacy revenue - includes walk-in sales, prescriptions, medication
        pharmacy_revenue = PaymentReceipt.objects.filter(
            Q(service_type='pharmacy') | Q(service_type='pharmacy_prescription') |
            Q(service_type='pharmacy_walkin') | Q(service_type='medication'),
            receipt_date__gte=date_from,
            receipt_date__lte=date_to,
            is_deleted=False
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        
        # Imaging revenue - includes 'imaging', 'imaging_study', 'radiology'
        imaging_revenue = PaymentReceipt.objects.filter(
            Q(service_type='imaging') | Q(service_type='imaging_study') | Q(service_type='radiology'),
            receipt_date__gte=date_from,
            receipt_date__lte=date_to,
            is_deleted=False
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        
        # Dental revenue
        dental_revenue = PaymentReceipt.objects.filter(
            service_type='dental',
            receipt_date__gte=date_from,
            receipt_date__lte=date_to,
            is_deleted=False
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        
        # Gynecology revenue
        gynecology_revenue = PaymentReceipt.objects.filter(
            service_type='gynecology',
            receipt_date__gte=date_from,
            receipt_date__lte=date_to,
            is_deleted=False
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        
        # Surgery revenue - includes 'surgery', 'procedure'
        surgery_revenue = PaymentReceipt.objects.filter(
            Q(service_type='surgery') | Q(service_type='procedure'),
            receipt_date__gte=date_from,
            receipt_date__lte=date_to,
            is_deleted=False
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        
        # Emergency revenue
        emergency_revenue = PaymentReceipt.objects.filter(
            service_type='emergency',
            receipt_date__gte=date_from,
            receipt_date__lte=date_to,
            is_deleted=False
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        
        # AMBULANCE SERVICE REVENUE
        ambulance_revenue = PaymentReceipt.objects.filter(
            service_type='ambulance',
            receipt_date__gte=date_from,
            receipt_date__lte=date_to,
            is_deleted=False
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        
        # Parse combined receipts - split by service type so consultation/lab/imaging show correctly
        combined_receipts = PaymentReceipt.objects.filter(
            service_type='combined',
            receipt_date__gte=date_from,
            receipt_date__lte=date_to,
            is_deleted=False
        ).only('service_details', 'amount_paid')
        for rec in combined_receipts:
            services = (rec.service_details or {}).get('services') or []
            total_services = sum(Decimal(str(s.get('price', 0) or 0)) for s in services)
            if total_services <= 0:
                continue
            for svc in services:
                try:
                    amt = Decimal(str(svc.get('price', 0) or 0))
                except (TypeError, ValueError):
                    continue
                if amt <= 0:
                    continue
                stype = (svc.get('type') or '').lower()
                if stype in ('consultation', 'outpatient', 'gp'):
                    consultation_revenue += amt
                elif stype in ('lab', 'lab_test', 'lab_result', 'laboratory'):
                    lab_revenue += amt
                elif stype in ('pharmacy', 'pharmacy_prescription', 'pharmacy_walkin', 'medication'):
                    pharmacy_revenue += amt
                elif stype in ('imaging', 'imaging_study', 'radiology'):
                    imaging_revenue += amt
                elif stype == 'dental':
                    dental_revenue += amt
                elif stype == 'gynecology':
                    gynecology_revenue += amt
                elif stype in ('surgery', 'procedure'):
                    surgery_revenue += amt
                elif stype == 'emergency':
                    emergency_revenue += amt
                elif stype == 'ambulance':
                    ambulance_revenue += amt
                # bed, admission, invoice, invoice_line, detainment -> stay in other
        
        # Other: remainder (admission, bed, combined total, null, etc.) - ensures total matches sum of cards
        categorized_sum = (
            consultation_revenue + lab_revenue + pharmacy_revenue + imaging_revenue +
            dental_revenue + gynecology_revenue + surgery_revenue + emergency_revenue +
            ambulance_revenue
        )
        total_from_receipts = PaymentReceipt.objects.filter(
            receipt_date__gte=date_from,
            receipt_date__lte=date_to,
            is_deleted=False
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        other_revenue = max(Decimal('0.00'), total_from_receipts - categorized_sum)
    except Exception as e:
        import traceback
        print(f"Error calculating service revenue: {e}")
        print(traceback.format_exc())
        consultation_revenue = lab_revenue = pharmacy_revenue = imaging_revenue = Decimal('0.00')
        dental_revenue = gynecology_revenue = surgery_revenue = emergency_revenue = Decimal('0.00')
        ambulance_revenue = other_revenue = Decimal('0.00')
    
    # Total = sum of all category cards (always matches the cards; admission/bed/combined in Other)
    total_revenue = (
        consultation_revenue + lab_revenue + pharmacy_revenue + imaging_revenue +
        dental_revenue + gynecology_revenue + surgery_revenue + emergency_revenue +
        ambulance_revenue + other_revenue
    )
    
    context = {
        'date_from': date_from,
        'date_to': date_to,
        'total_revenue': total_revenue,
        'revenue_by_service': revenue_by_service,
        'revenue_by_dept': revenue_by_dept,
        'stream_performance': stream_performance,
        # Quick stats - All from PaymentReceipts (Real-time data)
        'consultation_revenue': consultation_revenue,
        'lab_revenue': lab_revenue,
        'pharmacy_revenue': pharmacy_revenue,
        'imaging_revenue': imaging_revenue,
        'dental_revenue': dental_revenue,
        'gynecology_revenue': gynecology_revenue,
        'surgery_revenue': surgery_revenue,
        'emergency_revenue': emergency_revenue,
        'ambulance_revenue': ambulance_revenue,
        'other_revenue': other_revenue,
    }
    
    return render(request, 'hospital/revenue/streams_dashboard.html', context)


@login_required
def revenue_by_department_report(request):
    """
    Detailed report of revenue by department
    """
    # Get date range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if not date_from:
        today = timezone.now().date()
        date_from = today.replace(day=1)
    else:
        date_from = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
    
    if not date_to:
        date_to = timezone.now().date()
    else:
        date_to = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
    
    # Get all departments
    departments = Department.objects.filter(is_deleted=False)
    
    dept_data = []
    total_all = Decimal('0.00')
    
    for dept in departments:
        try:
            dept_revenue = Revenue.objects.filter(
                department=dept,
                revenue_date__gte=date_from,
                revenue_date__lte=date_to,
                is_deleted=False
            ).aggregate(
                total=Sum('amount'),
                count=Count('id')
            )
            
            total = dept_revenue['total'] or Decimal('0.00')
            count = dept_revenue['count'] or 0
            
            if total > 0 or count > 0:
                dept_data.append({
                    'department': dept,
                    'total': total,
                    'count': count,
                    'average': total / count if count > 0 else Decimal('0.00')
                })
                total_all += total
        except:
            pass
    
    # Calculate percentages
    for item in dept_data:
        if total_all > 0:
            item['percentage'] = (item['total'] / total_all) * 100
        else:
            item['percentage'] = 0
    
    # Sort by total
    dept_data.sort(key=lambda x: x['total'], reverse=True)
    
    avg_per_department = (total_all / len(dept_data)) if dept_data else Decimal('0.00')
    
    context = {
        'date_from': date_from,
        'date_to': date_to,
        'dept_data': dept_data,
        'total_revenue': total_all,
        'average_per_department': avg_per_department,
    }
    
    return render(request, 'hospital/revenue/department_report.html', context)


@login_required
def revenue_streams_api(request):
    """
    API endpoint for revenue stream data (for charts)
    """
    days = max(1, int(request.GET.get('days', 30)))
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    service_map = {
        'lab': 'Laboratory',
        'laboratory': 'Laboratory',
        'pharmacy': 'Pharmacy',
        'pharmacy_prescription': 'Pharmacy Prescription',
        'pharmacy_walkin': 'Pharmacy (Walk-in)',
        'medication': 'Medication',
        'imaging': 'Imaging/Radiology',
        'imaging_study': 'Imaging Study',
        'consultation': 'Consultation',
        'outpatient': 'Outpatient',
        'admission': 'Admission',
        'procedure': 'Procedure',
        'surgery': 'Surgery',
        'dental': 'Dental',
        'gynecology': 'Gynecology',
        'emergency': 'Emergency',
        'ambulance': 'Ambulance/EMS',
        'combined': 'Combined Services',
        'other': 'Other',
    }
    
    try:
        from .models_accounting import PaymentReceipt
    except Exception:
        PaymentReceipt = None
    
    service_data = {}
    total_service_amount = Decimal('0.00')
    
    try:
        if PaymentReceipt:
            receipts = PaymentReceipt.objects.filter(
                receipt_date__date__gte=start_date,
                receipt_date__date__lte=end_date,
                is_deleted=False
            ).values('service_type').annotate(
                total=Sum('amount_paid'),
                count=Count('id')
            )
            
            for item in receipts:
                service_type = item['service_type'] or 'other'
                amount = item['total'] or Decimal('0.00')
                total_service_amount += amount
                service_data[service_type] = {
                    'label': service_map.get(service_type, service_type.title()),
                    'total': float(amount),
                    'count': item['count'] or 0,
                }
        
        # Fallback to Revenue table if no PaymentReceipt data
        if not service_data:
            revenue_rows = Revenue.objects.filter(
                revenue_date__gte=start_date,
                revenue_date__lte=end_date,
                is_deleted=False,
                service_type__isnull=False
            ).values('service_type').annotate(
                total=Sum('amount'),
                count=Count('id')
            )
            
            total_service_amount = Decimal('0.00')
            for item in revenue_rows:
                service_type = item['service_type'] or 'other'
                amount = item['total'] or Decimal('0.00')
                total_service_amount += amount
                service_data[service_type] = {
                    'label': service_map.get(service_type, service_type.title()),
                    'total': float(amount),
                    'count': item['count'] or 0,
                }
        
        # Append percentage share
        for key, data in service_data.items():
            amount = Decimal(str(data['total']))
            data['percentage'] = float((amount / total_service_amount * Decimal('100')) if total_service_amount > 0 else 0)
        
        # Department data (Revenue table has department links)
        department_rows = Revenue.objects.filter(
            revenue_date__gte=start_date,
            revenue_date__lte=end_date,
            is_deleted=False,
            department__isnull=False
        ).values('department__name').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        dept_total_amount = Decimal('0.00')
        dept_data = {}
        for item in department_rows:
            dept_name = item['department__name'] or 'Unassigned'
            amount = item['total'] or Decimal('0.00')
            dept_total_amount += amount
            dept_data[dept_name] = {
                'total': float(amount),
                'count': item['count'] or 0,
            }
        
        for key, data in dept_data.items():
            amount = Decimal(str(data['total']))
            data['percentage'] = float((amount / dept_total_amount * Decimal('100')) if dept_total_amount > 0 else 0)
        
        return JsonResponse({
            'success': True,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': days,
            },
            'totals': {
                'service_revenue': float(total_service_amount),
                'department_revenue': float(dept_total_amount),
            },
            'service_revenue': service_data,
            'department_revenue': dept_data,
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


