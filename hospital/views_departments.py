"""
Department-specific dashboard views for Pharmacy, Laboratory, and Imaging
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg, F
from django.db.models.functions import TruncDay
from django.db.utils import OperationalError
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from django.urls import reverse
from .models import (
    Order, LabTest, LabResult, Drug, PharmacyStock, Prescription,
    Encounter, Patient, Staff, Department
)
from .models_advanced import ImagingStudy, ImagingImage
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
from .services.auto_billing_service import AutoBillingService
from .models_payment_verification import PharmacyDispensing
from .models_accounting import PaymentReceipt
from .models_pharmacy_walkin import WalkInPharmacySale


@login_required
def pharmacy_dashboard(request):
    """World-Class Pharmacy Dashboard - Direct patient service with accounting integration"""
    # Get pending medication orders - prioritize by priority level
    priority_order = {'stat': 0, 'urgent': 1, 'routine': 2}
    pending_orders_qs = Order.objects.filter(
        order_type='medication',
        status='pending',
        is_deleted=False
    ).select_related('encounter__patient', 'requested_by').defer('encounter__current_activity')
    
    # Sort by priority, then by creation time
    pending_orders = sorted(
        pending_orders_qs[:50],
        key=lambda x: (priority_order.get(x.priority, 2), x.requested_at),
        reverse=False
    )[:20]
    
    # Get today's prescriptions (dispensed)
    today = timezone.now().date()
    today_prescriptions = list(Prescription.objects.filter(
        created__date=today,
        is_deleted=False
    ).select_related('order__encounter__patient', 'drug', 'prescribed_by').defer('order__encounter__current_activity')[:20])
    
    # Stock alerts (low stock and expiring soon)
    expiring_soon = date.today() + timedelta(days=30)
    low_stock = list(PharmacyStock.objects.filter(
        quantity_on_hand__lte=F('reorder_level'),
        is_deleted=False
    ).select_related('drug')[:10])
    
    expiring_stock = list(PharmacyStock.objects.filter(
        expiry_date__lte=expiring_soon,
        quantity_on_hand__gt=0,
        is_deleted=False
    ).select_related('drug').order_by('expiry_date')[:10])
    
    # Pharmacy statistics
    total_drugs = Drug.objects.filter(is_active=True, is_deleted=False).count()
    total_prescriptions = Prescription.objects.filter(is_deleted=False).count()
    pending_prescriptions = Prescription.objects.filter(
        order__status='pending',
        is_deleted=False
    ).count()
    
    # Total stock value
    stock_value = PharmacyStock.objects.filter(
        is_deleted=False
    ).aggregate(
        total_value=Sum(F('quantity_on_hand') * F('unit_cost'))
    )['total_value'] or Decimal('0')
    
    # Real-time pharmacy revenue + accountability
    pharmacy_receipt_types = ['pharmacy', 'pharmacy_prescription', 'pharmacy_walkin', 'medication']
    today = timezone.now().date()
    month_start = today.replace(day=1)
    seven_day_window = today - timedelta(days=6)
    recent_window = timezone.now() - timedelta(days=2)
    
    my_receipts_today_qs = PaymentReceipt.objects.filter(
        service_type__in=pharmacy_receipt_types,
        receipt_date__date=today,
        is_deleted=False,
        received_by=request.user
    ).select_related('patient').order_by('-receipt_date')
    
    my_sales_total = my_receipts_today_qs.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    my_sales_count = my_receipts_today_qs.count()
    my_sales_avg_ticket = (my_sales_total / my_sales_count) if my_sales_count else Decimal('0.00')
    
    pharmacy_receipts_today_qs = PaymentReceipt.objects.filter(
        service_type__in=pharmacy_receipt_types,
        receipt_date__date=today,
        is_deleted=False
    )
    pharmacy_revenue_today = pharmacy_receipts_today_qs.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    pharmacy_receipt_count_today = pharmacy_receipts_today_qs.count()
    
    pharmacy_revenue_month = PaymentReceipt.objects.filter(
        service_type__in=pharmacy_receipt_types,
        receipt_date__date__gte=month_start,
        receipt_date__date__lte=today,
        is_deleted=False
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    
    my_sales_share_percentage = 0
    if pharmacy_revenue_today and pharmacy_revenue_today > 0:
        try:
            share = (my_sales_total / pharmacy_revenue_today) * 100
            my_sales_share_percentage = float(round(share, 2))
        except Exception:
            my_sales_share_percentage = 0
    
    pharmacy_daily_trend_qs = PaymentReceipt.objects.filter(
        service_type__in=pharmacy_receipt_types,
        receipt_date__date__gte=seven_day_window,
        receipt_date__date__lte=today,
        is_deleted=False
    ).annotate(day=TruncDay('receipt_date')).values('day').annotate(
        total=Sum('amount_paid'),
        count=Count('id')
    ).order_by('-day')[:7]
    pharmacy_daily_trend = [
        {
            'date': entry['day'].date() if entry['day'] else today,
            'total': entry['total'] or Decimal('0.00'),
            'count': entry['count']
        }
        for entry in reversed(list(pharmacy_daily_trend_qs))
    ]
    
    top_staff_raw = PaymentReceipt.objects.filter(
        service_type__in=pharmacy_receipt_types,
        receipt_date__date=today,
        is_deleted=False,
        received_by__isnull=False
    ).values(
        'received_by__first_name',
        'received_by__last_name',
        'received_by__username'
    ).annotate(
        total=Sum('amount_paid'),
        count=Count('id')
    ).order_by('-total')[:5]
    pharmacy_top_staff = []
    for entry in top_staff_raw:
        first = entry.get('received_by__first_name') or ''
        last = entry.get('received_by__last_name') or ''
        name = f"{first} {last}".strip()
        if not name:
            name = entry.get('received_by__username') or 'Unassigned'
        pharmacy_top_staff.append({
            'name': name,
            'total': entry['total'] or Decimal('0.00'),
            'count': entry['count']
        })
    
    pharmacy_recent_sales = list(
        PaymentReceipt.objects.filter(
            service_type__in=pharmacy_receipt_types,
            receipt_date__gte=recent_window,
            is_deleted=False
        ).select_related('patient', 'received_by').order_by('-receipt_date')[:20]
    )
    
    # Walk-in pharmacy sales (OTC) visibility
    try:
        walkin_sales_today_qs = WalkInPharmacySale.objects.filter(
            sale_date__date=today,
            is_deleted=False
        ).select_related('served_by__user').order_by('-sale_date')
        
        my_walkin_sales_qs = walkin_sales_today_qs.filter(
            served_by__user=request.user,
            payment_status='paid'
        )
        
        my_walkin_sales_total = my_walkin_sales_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        my_walkin_sales_count = my_walkin_sales_qs.count()
        
        walkin_sales_total_today = walkin_sales_today_qs.filter(payment_status='paid').aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        walkin_sales_count_today = walkin_sales_today_qs.count()
        
        walkin_sales_recent = list(
            walkin_sales_today_qs[:10]
        )
    except OperationalError:
        my_walkin_sales_total = Decimal('0.00')
        my_walkin_sales_count = 0
        walkin_sales_total_today = Decimal('0.00')
        walkin_sales_count_today = 0
        walkin_sales_recent = []
    
    combined_total_revenue = (pharmacy_revenue_today or Decimal('0.00')) + (walkin_sales_total_today or Decimal('0.00'))
    my_total_sales = (my_sales_total or Decimal('0.00')) + (my_walkin_sales_total or Decimal('0.00'))
    my_total_transactions = (my_sales_count or 0) + (my_walkin_sales_count or 0)
    my_combined_avg_ticket = (my_total_sales / my_total_transactions) if my_total_transactions else Decimal('0.00')
    my_combined_share = 0
    if combined_total_revenue and combined_total_revenue > 0:
        try:
            my_combined_share = float(round((my_total_sales / combined_total_revenue) * 100, 2))
        except Exception:
            my_combined_share = 0
    
    context = {
        'pending_orders': pending_orders,
        'today_prescriptions': today_prescriptions,
        'low_stock': low_stock,
        'expiring_stock': expiring_stock,
        'total_drugs': total_drugs,
        'total_prescriptions': total_prescriptions,
        'pending_prescriptions': pending_prescriptions,
        'stock_value': stock_value,
        'now': timezone.now(),
        'my_sales_total': my_sales_total,
        'my_sales_count': my_sales_count,
        'my_sales_avg_ticket': my_sales_avg_ticket,
        'my_sales_share_percentage': my_sales_share_percentage,
        'my_recent_pharmacy_receipts': list(my_receipts_today_qs[:8]),
        'my_total_sales': my_total_sales,
        'my_total_transactions': my_total_transactions,
        'my_combined_avg_ticket': my_combined_avg_ticket,
        'my_combined_share_percentage': my_combined_share,
        'pharmacy_revenue_today': pharmacy_revenue_today,
        'pharmacy_receipt_count_today': pharmacy_receipt_count_today,
        'pharmacy_revenue_month': pharmacy_revenue_month,
        'pharmacy_daily_trend': pharmacy_daily_trend,
        'pharmacy_top_staff': pharmacy_top_staff,
        'pharmacy_recent_sales': pharmacy_recent_sales,
        'my_walkin_sales_total': my_walkin_sales_total,
        'my_walkin_sales_count': my_walkin_sales_count,
        'walkin_sales_total_today': walkin_sales_total_today,
        'walkin_sales_count_today': walkin_sales_count_today,
        'walkin_sales_recent': walkin_sales_recent,
    }
    return render(request, 'hospital/pharmacy_dashboard_worldclass.html', context)


@login_required
def laboratory_dashboard(request):
    """Laboratory dashboard with test orders and results"""
    # Get pending lab orders - prioritize by priority level
    priority_order = {'stat': 0, 'urgent': 1, 'routine': 2}
    pending_orders_qs = Order.objects.filter(
        order_type='lab',
        status='pending',
        is_deleted=False
    ).exclude(
        lab_results__status__in=['in_progress', 'completed', 'cancelled']
    ).select_related(
        'encounter__patient',
        'requested_by'
    ).distinct()
    
    # Sort by priority, then by creation time
    pending_orders = sorted(
        pending_orders_qs[:50],
        key=lambda x: (priority_order.get(x.priority, 2), x.requested_at),
        reverse=False
    )[:20]
    
    # Get in-progress results
    in_progress_results = list(LabResult.objects.filter(
        status='in_progress',
        is_deleted=False
    ).select_related('test', 'order__encounter__patient', 'verified_by').order_by('-created')[:20])
    
    # Get completed results today
    today = timezone.now().date()
    today_results = list(LabResult.objects.filter(
        status='completed',
        verified_at__date=today,
        is_deleted=False
    ).select_related('test', 'order__encounter__patient').order_by('-verified_at')[:20])
    
    # Get pending results (no verification yet)
    pending_results = list(LabResult.objects.filter(
        status='pending',
        is_deleted=False
    ).select_related('test', 'order__encounter__patient').order_by('-created')[:20])
    
    # Lab statistics
    total_tests = LabTest.objects.filter(is_active=True, is_deleted=False).count()
    total_results = LabResult.objects.filter(is_deleted=False).count()
    pending_tests = Order.objects.filter(
        order_type='lab',
        status='pending',
        is_deleted=False
    ).count()
    
    # Abnormal results count
    abnormal_results = LabResult.objects.filter(
        is_abnormal=True,
        is_deleted=False
    ).count()
    
    # Average turnaround time (for completed results)
    completed_results = LabResult.objects.filter(
        status='completed',
        verified_at__isnull=False,
        created__isnull=False,
        is_deleted=False
    )
    
    avg_tat_hours = 0
    if completed_results.exists():
        tat_times = []
        for result in completed_results[:100]:  # Sample recent ones
            if result.order and result.order.created and result.verified_at:
                tat = (result.verified_at - result.order.created).total_seconds() / 3600
                tat_times.append(tat)
        if tat_times:
            avg_tat_hours = round(sum(tat_times) / len(tat_times), 1)
    
    context = {
        'pending_orders': pending_orders,
        'in_progress_results': in_progress_results,
        'today_results': today_results,
        'pending_results': pending_results,
        'total_tests': total_tests,
        'total_results': total_results,
        'pending_tests': pending_tests,
        'abnormal_results': abnormal_results,
        'avg_tat_hours': avg_tat_hours,
    }
    return render(request, 'hospital/laboratory_dashboard.html', context)


@login_required
def imaging_dashboard(request):
    """World-Class Imaging/X-ray dashboard - NO REDIRECTIONS!"""
    # Get pending imaging orders - prioritize by priority level
    priority_order = {'stat': 0, 'urgent': 1, 'routine': 2}
    pending_orders_qs = Order.objects.filter(
        order_type='imaging',
        status='pending',
        is_deleted=False
    ).select_related('encounter__patient', 'requested_by').defer('encounter__current_activity')
    
    # Sort by priority, then by creation time
    pending_orders = sorted(
        pending_orders_qs[:50],
        key=lambda x: (priority_order.get(x.priority, 2), x.requested_at),
        reverse=False
    )[:20]
    
    # Get in-progress imaging orders
    in_progress_orders = list(Order.objects.filter(
        order_type='imaging',
        status='in_progress',
        is_deleted=False
    ).select_related('encounter__patient', 'requested_by').defer('encounter__current_activity').order_by('-created')[:20])
    
    # Get completed imaging orders today
    today = timezone.now().date()
    today_imaging_orders = Order.objects.filter(
        order_type='imaging',
        status='completed',
        modified__date=today,
        is_deleted=False
    ).select_related('encounter__patient').defer('encounter__current_activity').order_by('-modified')[:20]
    
    # Get imaging studies for these orders
    today_imaging = []
    for order in today_imaging_orders:
        imaging_studies = order.imaging_studies.all()
        if imaging_studies.exists():
            # Add the imaging study to the order object for template access
            order.imaging_study = imaging_studies.first()
            today_imaging.append(order)
        else:
            # Also add orders without studies so they can be created
            today_imaging.append(order)
    
    # Get imaging reports from MedicalRecords
    from .models import MedicalRecord
    recent_reports = list(MedicalRecord.objects.filter(
        record_type='imaging',
        is_deleted=False
    ).select_related('patient').order_by('-created')[:20])
    
    # Imaging statistics
    total_pending = Order.objects.filter(
        order_type='imaging',
        status='pending',
        is_deleted=False
    ).count()
    
    total_in_progress = Order.objects.filter(
        order_type='imaging',
        status='in_progress',
        is_deleted=False
    ).count()
    
    total_completed_today = Order.objects.filter(
        order_type='imaging',
        status='completed',
        modified__date=today,
        is_deleted=False
    ).count()
    
    total_reports = MedicalRecord.objects.filter(
        record_type='imaging',
        is_deleted=False
    ).count()
    
    context = {
        'pending_orders': pending_orders,
        'in_progress_orders': in_progress_orders,
        'today_imaging': today_imaging,
        'recent_reports': recent_reports,
        'total_pending': total_pending,
        'total_in_progress': total_in_progress,
        'total_completed_today': total_completed_today,
        'total_reports': total_reports,
    }
    return render(request, 'hospital/imaging_dashboard_worldclass.html', context)


@login_required
def imaging_study_detail(request, study_id):
    """View and manage imaging study with images"""
    study = get_object_or_404(ImagingStudy, pk=study_id, is_deleted=False)
    
    # Get all images for this study
    images = study.images.filter(is_deleted=False).order_by('sequence_number', 'uploaded_at')
    
    # Get current staff
    current_staff = None
    try:
        current_staff = request.user.staff
    except:
        pass
    
    # Handle image upload
    if request.method == 'POST' and 'upload_image' in request.POST:
        try:
            image_file = request.FILES.get('image')
            description = request.POST.get('description', '')
            
            if not image_file:
                messages.error(request, 'Please select an image file to upload.')
            else:
                # Get next sequence number
                last_image = study.images.filter(is_deleted=False).order_by('-sequence_number').first()
                next_sequence = (last_image.sequence_number + 1) if last_image else 1
                
                # Create image
                imaging_image = ImagingImage.objects.create(
                    imaging_study=study,
                    image=image_file,
                    description=description,
                    sequence_number=next_sequence,
                    uploaded_by=current_staff
                )
                
                # Mark study as completed if not already
                if study.status != 'completed':
                    study.status = 'completed'
                    study.performed_at = timezone.now()
                    study.save()
                    
                    # Also mark the order as completed
                    if study.order and study.order.status != 'completed':
                        study.order.status = 'completed'
                        study.order.save()
                
                messages.success(request, f'Image uploaded successfully as image #{next_sequence}. Study marked as complete.')
                return redirect('hospital:imaging_study_detail', study_id=study.id)
        except Exception as e:
            messages.error(request, f'Error uploading image: {str(e)}')
    
    # Handle image deletion
    if request.method == 'POST' and 'delete_image' in request.POST:
        try:
            image_id = request.POST.get('image_id')
            image = get_object_or_404(ImagingImage, pk=image_id, imaging_study=study, is_deleted=False)
            image.is_deleted = True
            image.save()
            messages.success(request, 'Image deleted successfully.')
            return redirect('hospital:imaging_study_detail', study_id=study.id)
        except Exception as e:
            messages.error(request, f'Error deleting image: {str(e)}')
    
    context = {
        'study': study,
        'images': images,
        'patient': study.patient,
        'encounter': study.encounter,
    }
    return render(request, 'hospital/imaging_study_detail.html', context)


@login_required
@require_http_methods(["POST"])
def upload_imaging_image(request, study_id):
    """AJAX endpoint for uploading imaging images"""
    study = get_object_or_404(ImagingStudy, pk=study_id, is_deleted=False)
    
    current_staff = None
    try:
        current_staff = request.user.staff
    except:
        pass
    
    # Check if user has permission to upload images (staff only)
    if not current_staff:
        return JsonResponse({'success': False, 'error': 'Access denied. Staff profile required.'}, status=403)
    
    try:
        image_file = request.FILES.get('image')
        description = request.POST.get('description', '')
        
        if not image_file:
            return JsonResponse({'success': False, 'error': 'No image file provided'}, status=400)
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/dicom', 'application/dicom']
        if image_file.content_type not in allowed_types:
            return JsonResponse({'success': False, 'error': 'Invalid file type. Please upload JPG, PNG, or DICOM images.'}, status=400)
        
        # Validate file size (max 10MB)
        if image_file.size > 10 * 1024 * 1024:
            return JsonResponse({'success': False, 'error': 'File too large. Maximum size is 10MB.'}, status=400)
        
        # Get next sequence number
        last_image = study.images.filter(is_deleted=False).order_by('-sequence_number').first()
        next_sequence = (last_image.sequence_number + 1) if last_image else 1
        
        # Create image
        imaging_image = ImagingImage.objects.create(
            imaging_study=study,
            image=image_file,
            description=description,
            sequence_number=next_sequence,
            uploaded_by=current_staff
        )
        
        # Mark study as completed if not already
        if study.status != 'completed':
            study.status = 'completed'
            study.performed_at = timezone.now()
            study.save()
            
            # Also mark the order as completed
            if study.order and study.order.status != 'completed':
                study.order.status = 'completed'
                study.order.save()
        
        return JsonResponse({
            'success': True,
            'image_id': str(imaging_image.id),
            'image_url': imaging_image.image.url,
            'description': imaging_image.description,
            'sequence_number': imaging_image.sequence_number,
            'status': 'completed'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def edit_imaging_report(request, study_id):
    """Edit imaging study report"""
    study = get_object_or_404(ImagingStudy, pk=study_id, is_deleted=False)
    
    # Check if user has permission to edit reports (radiologists, doctors, admin)
    current_staff = None
    try:
        current_staff = request.user.staff
    except:
        pass
    
    if not current_staff:
        messages.error(request, 'Access denied. Staff profile required.')
        return redirect('hospital:imaging_study_detail', study_id=study_id)
    
    # Check if user can edit reports
    can_edit = (
        current_staff.profession in ['radiologist', 'doctor', 'admin'] or
        current_staff.user.is_staff
    )
    
    if not can_edit:
        messages.error(request, 'Access denied. Insufficient permissions to edit reports.')
        return redirect('hospital:imaging_study_detail', study_id=study_id)
    
    if request.method == 'POST':
        try:
            # Update report fields
            study.report_text = request.POST.get('report_text', '')
            study.findings = request.POST.get('findings', '')
            study.impression = request.POST.get('impression', '')
            
            # Set dictated by if not already set
            if not study.report_dictated_by:
                study.report_dictated_by = current_staff
            
            study.save()
            
            messages.success(request, 'Report updated successfully.')
            return redirect('hospital:imaging_study_detail', study_id=study_id)
            
        except Exception as e:
            messages.error(request, f'Error updating report: {str(e)}')
    
    context = {
        'study': study,
        'patient': study.patient,
        'encounter': study.encounter,
    }
    return render(request, 'hospital/edit_imaging_report.html', context)


@login_required
def verify_imaging_report(request, study_id):
    """Verify imaging study report"""
    study = get_object_or_404(ImagingStudy, pk=study_id, is_deleted=False)
    
    # Check if user has permission to verify reports (radiologists, admin)
    current_staff = None
    try:
        current_staff = request.user.staff
    except:
        pass
    
    if not current_staff:
        messages.error(request, 'Access denied. Staff profile required.')
        return redirect('hospital:imaging_study_detail', study_id=study_id)
    
    # Check if user can verify reports
    can_verify = (
        current_staff.profession in ['radiologist', 'admin'] or
        current_staff.user.is_staff
    )
    
    if not can_verify:
        messages.error(request, 'Access denied. Insufficient permissions to verify reports.')
        return redirect('hospital:imaging_study_detail', study_id=study_id)
    
    if request.method == 'POST':
        try:
            study.report_verified_by = current_staff
            study.report_verified_at = timezone.now()
            study.save()
            
            messages.success(request, 'Report verified successfully.')
            return redirect('hospital:imaging_study_detail', study_id=study_id)
            
        except Exception as e:
            messages.error(request, f'Error verifying report: {str(e)}')
    
    return redirect('hospital:imaging_study_detail', study_id=study_id)


@login_required
def pharmacy_stock_list(request):
    """Pharmacy stock/inventory management - shows only pharmacy/pharmaceutical items
    Pharmacy can VIEW but only Admin/Procurement can EDIT"""
    from .models_procurement import InventoryCategory, Store, InventoryItem
    from .views_procurement import can_edit_inventory, is_pharmacy_staff, is_procurement_staff
    
    # Check permissions
    can_edit = can_edit_inventory(request.user)
    is_pharmacy = is_pharmacy_staff(request.user)
    
    query = request.GET.get('q', '')
    filter_type = request.GET.get('filter', 'all')
    
    # Get pharmacy category
    pharmacy_category = InventoryCategory.objects.filter(is_for_pharmacy=True, is_active=True).first()
    
    # Get pharmacy stock (from PharmacyStock model)
    stock_list = PharmacyStock.objects.filter(is_deleted=False).select_related('drug')
    
    # Get pharmacy inventory items (from InventoryItem with pharmacy category)
    # Show items with pharmacy category, regardless of store (but prefer pharmacy stores)
    pharmacy_store = Store.objects.filter(store_type='pharmacy').first()
    inventory_items = InventoryItem.objects.none()
    
    if pharmacy_category:
        # Show all items with pharmacy category (items marked as pharmacy/pharmaceutical)
        inventory_items = InventoryItem.objects.filter(
            category=pharmacy_category,
            is_deleted=False
        ).select_related('drug', 'category', 'store').order_by('store__name', 'item_name')
    else:
        inventory_items = InventoryItem.objects.none()
    
    # Apply filters
    if query:
        stock_list = stock_list.filter(
            Q(drug__name__icontains=query) |
            Q(drug__generic_name__icontains=query) |
            Q(batch_number__icontains=query)
        )
        if inventory_items.exists():
            inventory_items = inventory_items.filter(
                Q(item_name__icontains=query) |
                Q(item_code__icontains=query) |
                Q(description__icontains=query)
            )
    
    if filter_type == 'low_stock':
        stock_list = stock_list.filter(quantity_on_hand__lte=F('reorder_level'))
        if inventory_items.exists():
            inventory_items = inventory_items.filter(quantity_on_hand__lte=F('reorder_level'))
    elif filter_type == 'expiring':
        expiring_soon = date.today() + timedelta(days=30)
        stock_list = stock_list.filter(expiry_date__lte=expiring_soon)
    
    expiry_threshold = date.today() + timedelta(days=30)
    
    # Convert querysets to lists for template - evaluate here
    stock_list_evaluated = list(stock_list.order_by('drug__name')[:100])
    inventory_items_evaluated = list(inventory_items) if inventory_items.exists() else []
    
    context = {
        'stock_list': stock_list_evaluated,
        'inventory_items': inventory_items_evaluated,
        'inventory_count': len(inventory_items_evaluated),
        'query': query,
        'filter_type': filter_type,
        'expiry_threshold': expiry_threshold.isoformat(),
        'pharmacy_category': pharmacy_category,
        'can_edit': can_edit,
        'is_pharmacy': is_pharmacy,
        'pharmacy_store': pharmacy_store,
    }
    return render(request, 'hospital/pharmacy_stock_list.html', context)


@login_required
def lab_results_list(request):
    """List all lab results"""
    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '')
    
    results = LabResult.objects.filter(is_deleted=False).select_related(
        'test', 'order__encounter__patient', 'verified_by'
    )
    
    if status_filter:
        results = results.filter(status=status_filter)
    
    if query:
        results = results.filter(
            Q(test__name__icontains=query) |
            Q(order__encounter__patient__first_name__icontains=query) |
            Q(order__encounter__patient__last_name__icontains=query)
        )
    
    # Get results list (limited to 100)
    results_list = list(results.order_by('-created')[:100])
    
    # Calculate statistics
    completed_count = sum(1 for r in results_list if r.status == 'completed')
    abnormal_count = sum(1 for r in results_list if r.is_abnormal)
    
    context = {
        'results': results_list,
        'status_filter': status_filter,
        'query': query,
        'completed_count': completed_count,
        'abnormal_count': abnormal_count,
    }
    return render(request, 'hospital/lab_results_list.html', context)


@login_required
def edit_lab_result(request, result_id):
    """Structured edit form for lab results (supports FBC table and qualitative terms)"""
    result = get_object_or_404(LabResult, pk=result_id, is_deleted=False)

    # Determine template mode based on test code/name
    test_code = (result.test.code or '').upper()
    test_name = (result.test.name or '').lower()

    is_fbc = test_code in ['FBC', 'CBC'] or 'full blood count' in test_name or 'complete blood count' in test_name

    if request.method == 'POST':
        # Common fields
        notes = request.POST.get('notes', '').strip()
        qualitative = request.POST.get('qualitative_result', '').strip()

        # Build details for FBC or general components
        details = {}
        if is_fbc:
            # Numeric parameters
            fields = [
                'wbc', 'rbc', 'hgb', 'hct', 'mcv', 'mch', 'mchc', 'plt',
                'neut_perc', 'lymph_perc', 'mono_perc', 'eos_perc', 'baso_perc'
            ]
            for f in fields:
                val = request.POST.get(f, '').strip()
                if val != '':
                    details[f] = val
        else:
            # Generic component/value pairs (optional future use)
            for i in range(1, 11):
                key = request.POST.get(f'comp_{i}_name', '').strip()
                val = request.POST.get(f'comp_{i}_value', '').strip()
                if key and val:
                    details[key] = val

        # Save onto result
        result.details = details or None
        result.qualitative_result = qualitative
        result.notes = notes
        # Keep status if already completed else move to in_progress when editing
        if result.status == 'pending':
            result.status = 'in_progress'
        result.save()

        messages.success(request, 'Lab result details saved.')
        return redirect('hospital:laboratory_dashboard')

    # Pre-fill context
    context = {
        'result': result,
        'is_fbc': is_fbc,
        'details': result.details or {},
        'qualitative_result': result.qualitative_result or '',
        # Standard qualitative options commonly used in labs
        'qualitative_options': ['Reactive', 'Non-reactive', 'Positive', 'Negative', 'Equivocal', 'Indeterminate']
    }
    return render(request, 'hospital/lab_result_edit.html', context)


# ==================== REAL-TIME AJAX ENDPOINTS ====================

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def update_order_status(request, order_id):
    """AJAX endpoint to update order status"""
    order = get_object_or_404(Order, pk=order_id, is_deleted=False)
    action = request.POST.get('action', '')
    current_staff = None
    
    try:
        current_staff = request.user.staff
    except:
        pass
    
    if action == 'start':
        # Mark as in-progress
        order.status = 'in_progress'
        order.save(update_fields=['status', 'modified'])
        return JsonResponse({
            'success': True,
            'message': 'Order marked as in progress',
            'new_status': 'in_progress',
            'status_display': order.get_status_display()
        })
    
    elif action == 'complete':
        # Mark as completed
        order.status = 'completed'
        order.save(update_fields=['status', 'modified'])
        return JsonResponse({
            'success': True,
            'message': 'Order completed',
            'new_status': 'completed',
            'status_display': order.get_status_display()
        })
    
    elif action == 'cancel':
        # Cancel order
        order.status = 'cancelled'
        order.save(update_fields=['status', 'modified'])
        return JsonResponse({
            'success': True,
            'message': 'Order cancelled',
            'new_status': 'cancelled',
            'status_display': order.get_status_display()
        })
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Invalid action'
        }, status=400)


@login_required
@require_http_methods(["POST"])
def update_lab_result_status(request, result_id):
    """AJAX endpoint to update lab result status"""
    result = get_object_or_404(LabResult, pk=result_id, is_deleted=False)
    action = request.POST.get('action', '')
    value = request.POST.get('value', '')
    notes = request.POST.get('notes', '')
    
    current_staff = None
    try:
        current_staff = request.user.staff
    except:
        pass
    
    order = result.order if hasattr(result, 'order') else None
    
    if action == 'start':
        # Mark lab result as in-progress
        result.status = 'in_progress'
        result.save(update_fields=['status', 'modified'])

        # Move the parent order out of "pending" so it disappears from Pending Lab Orders
        if order and order.status != 'in_progress':
            order.status = 'in_progress'
            order.save(update_fields=['status', 'modified'])

        return JsonResponse({
            'success': True,
            'message': 'Test started',
            'new_status': 'in_progress'
        })
    
    elif action == 'complete':
        # Mark lab result as completed + verified
        result.status = 'completed'
        if value:
            result.value = value
        if notes:
            result.notes = notes
        if current_staff:
            result.verified_by = current_staff
            result.verified_at = timezone.now()
        result.save()

        # Also mark the parent order as completed so it no longer shows with a Start button
        if order and order.status != 'completed':
            order.status = 'completed'
            order.save(update_fields=['status', 'modified'])

        return JsonResponse({
            'success': True,
            'message': 'Test completed',
            'new_status': 'completed'
        })
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Invalid action'
        }, status=400)


@login_required
def dashboard_stats(request):
    """AJAX endpoint to get real-time dashboard statistics"""
    dashboard_type = request.GET.get('type', 'pharmacy')
    stats = {}
    
    if dashboard_type == 'pharmacy':
        stats = {
            'pending_orders': Order.objects.filter(
                order_type='medication',
                status='pending',
                is_deleted=False
            ).count(),
            'pending_prescriptions': Prescription.objects.filter(
                order__status='pending',
                is_deleted=False
            ).count(),
            'low_stock': PharmacyStock.objects.filter(
                quantity_on_hand__lte=F('reorder_level'),
                is_deleted=False
            ).count(),
        }
    
    elif dashboard_type == 'laboratory':
        stats = {
            'pending_orders': Order.objects.filter(
                order_type='lab',
                status='pending',
                is_deleted=False
            ).count(),
            'in_progress_results': LabResult.objects.filter(
                status='in_progress',
                is_deleted=False
            ).count(),
            'pending_results': LabResult.objects.filter(
                status='pending',
                is_deleted=False
            ).count(),
        }
    
    elif dashboard_type == 'imaging':
        stats = {
            'pending_orders': Order.objects.filter(
                order_type='imaging',
                status='pending',
                is_deleted=False
            ).count(),
            'in_progress_orders': Order.objects.filter(
                order_type='imaging',
                status='in_progress',
                is_deleted=False
            ).count(),
        }
    
    return JsonResponse({
        'success': True,
        'stats': stats,
        'timestamp': timezone.now().isoformat()
    })


@login_required
@require_http_methods(["POST"])
def upload_multiple_imaging_images(request):
    """Upload multiple imaging images via AJAX - World-Class Upload"""
    try:
        order_id = request.POST.get('order_id')
        description = request.POST.get('description', '')
        
        if not order_id:
            return JsonResponse({'success': False, 'error': 'Order ID required'})
        
        order = get_object_or_404(Order, pk=order_id, is_deleted=False)
        
        # Get or create imaging study for this order
        study = order.imaging_studies.filter(is_deleted=False).first()
        if not study:
            # Create new imaging study
            study = ImagingStudy.objects.create(
                order=order,
                patient=order.encounter.patient,
                encounter=order.encounter,
                modality='xray',  # Default, can be customized
                body_part='Unknown',  # Can be updated later
                status='in_progress',
                scheduled_at=timezone.now(),
                priority=order.priority
            )
        
        # Get current staff
        current_staff = None
        try:
            current_staff = request.user.staff
        except:
            pass
        
        # Upload multiple images
        images = request.FILES.getlist('images')
        if not images:
            return JsonResponse({'success': False, 'error': 'No images uploaded'})
        
        uploaded_count = 0
        last_image = study.images.filter(is_deleted=False).order_by('-sequence_number').first()
        next_sequence = (last_image.sequence_number + 1) if last_image else 1
        
        for image_file in images:
            ImagingImage.objects.create(
                imaging_study=study,
                image=image_file,
                description=description or f'Image {next_sequence}',
                sequence_number=next_sequence,
                uploaded_by=current_staff
            )
            next_sequence += 1
            uploaded_count += 1
        
        # Update order status to completed
        if order.status != 'completed':
            order.status = 'completed'
            order.save()
        
        # Mark imaging study as completed and set performed_at
        if study.status != 'completed':
            study.status = 'completed'
            study.performed_at = timezone.now()
            study.save()
        
        # Create medical record for the imaging study
        from .models import MedicalRecord
        record_exists = MedicalRecord.objects.filter(
            patient=study.patient,
            record_type='imaging',
            is_deleted=False,
            content__contains=f'Study ID: {study.id}'
        ).exists()
        
        if not record_exists:
            MedicalRecord.objects.create(
                patient=study.patient,
                encounter=study.encounter,
                record_type='imaging',
                title=f'{study.get_modality_display()} - {study.body_part}',
                content=f'''Imaging Study Completed

Study Type: {study.get_modality_display()}
Body Part: {study.body_part}
Images: {uploaded_count} image(s) uploaded
Study ID: {study.id}
Status: Completed
Performed: {timezone.now().strftime('%Y-%m-%d %H:%M')}

{study.clinical_indication if getattr(study, 'clinical_indication', '') else 'Clinical indication not specified'}

Report pending radiologist review.
''',
                created_by=current_staff
            )
        
        return JsonResponse({
            'success': True,
            'count': uploaded_count,
            'study_id': str(study.id),
            'message': f'Successfully uploaded {uploaded_count} image(s). Study marked as complete.'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def create_imaging_study(request):
    """Create imaging study for an order via AJAX"""
    try:
        order_id = request.POST.get('order_id')
        
        if not order_id:
            return JsonResponse({'success': False, 'error': 'Order ID required'})
        
        order = get_object_or_404(Order, pk=order_id, is_deleted=False)
        
        # Check if study already exists
        existing_study = order.imaging_studies.filter(is_deleted=False).first()
        if existing_study:
            return JsonResponse({
                'success': True,
                'study_id': str(existing_study.id),
                'message': 'Study already exists'
            })
        
        # Create new imaging study
        study = ImagingStudy.objects.create(
            order=order,
            patient=order.encounter.patient,
            encounter=order.encounter,
            modality='xray',  # Default
            body_part='Unknown',
            status='scheduled',
            scheduled_at=timezone.now(),
            priority=order.priority
        )
        
        return JsonResponse({
            'success': True,
            'study_id': str(study.id),
            'message': 'Imaging study created successfully'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_pharmacy_order_prescriptions(request, order_id):
    """API endpoint to get prescriptions for a medication order"""
    try:
        order = get_object_or_404(Order, pk=order_id, order_type='medication', is_deleted=False)
        
        # Get all prescriptions for this order
        prescriptions = order.prescriptions.filter(is_deleted=False).select_related('drug')
        
        prescriptions_data = []
        for rx in prescriptions:
            drug_price = getattr(rx.drug, 'unit_price', Decimal('0.00'))
            
            # Check stock availability
            stock_available = PharmacyStock.objects.filter(
                drug=rx.drug,
                is_deleted=False,
                quantity_on_hand__gt=0
            ).aggregate(total=Sum('quantity_on_hand'))['total'] or 0
            
            prescriptions_data.append({
                'id': str(rx.id),
                'drug_name': rx.drug.name,
                'drug_strength': rx.drug.strength,
                'drug_form': rx.drug.form,
                'dose': rx.dose,
                'frequency': rx.frequency,
                'duration': rx.duration,
                'quantity': rx.quantity,
                'drug_price': float(drug_price),
                'total_price': float(drug_price * rx.quantity),
                'instructions': rx.instructions,
                'stock_available': int(stock_available),
            })
        
        patient = order.encounter.patient
        
        return JsonResponse({
            'success': True,
            'prescriptions': prescriptions_data,
            'patient': {
                'id': str(patient.id),
                'full_name': patient.full_name,
                'mrn': patient.mrn,
                'age': patient.age,
                'phone_number': patient.phone_number or '',
                'gender': patient.get_gender_display(),
            },
            'order': {
                'id': str(order.id),
                'priority': order.priority,
                'requested_by': order.requested_by.user.get_full_name() if order.requested_by else '',
                'requested_at': order.requested_at.strftime('%Y-%m-%d %H:%M'),
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def check_pharmacy_order_payment_status(request, order_id):
    """Check if payment has been made for pharmacy order"""
    try:
        order = get_object_or_404(Order, pk=order_id, order_type='medication', is_deleted=False)
        
        # Get all prescriptions for this order
        prescriptions = order.prescriptions.filter(is_deleted=False)
        
        if not prescriptions.exists():
            return JsonResponse({'success': False, 'error': 'No prescriptions found'})
        
        # Check if any prescription has been paid
        from .models_accounting import PaymentReceipt
        
        payment_verified = False
        for prescription in prescriptions:
            patient = prescription.order.encounter.patient
            
            # Check for payment receipt
            receipt_exists = PaymentReceipt.objects.filter(
                is_deleted=False,
                patient=patient,
                service_type='pharmacy_prescription',
                receipt_date__gte=prescription.created.date()
            ).exists()
            
            if receipt_exists:
                payment_verified = True
                break
        
        return JsonResponse({
            'success': True,
            'payment_verified': payment_verified,
            'prescriptions_count': prescriptions.count()
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def send_pharmacy_order_to_cashier(request, order_id):
    """Ensure pharmacy order is queued for cashier without redirecting pharmacist."""
    try:
        order = get_object_or_404(Order, pk=order_id, order_type='medication', is_deleted=False)
        prescriptions = order.prescriptions.filter(is_deleted=False)
        
        if not prescriptions.exists():
            return JsonResponse({'success': False, 'error': 'No prescriptions found for this order'}, status=400)
        
        patient = order.encounter.patient if order.encounter else None
        if not patient:
            return JsonResponse({'success': False, 'error': 'Patient information missing for this order'}, status=400)
        
        total_amount = Decimal('0.00')
        created_records = 0
        already_pending = 0
        already_paid = 0
        warnings = []
        
        for prescription in prescriptions:
            unit_price = getattr(prescription.drug, 'unit_price', Decimal('0.00')) or Decimal('0.00')
            quantity = Decimal(str(prescription.quantity or 0))
            total_amount += (unit_price * quantity)
            
            dispensing_record = PharmacyDispensing.objects.filter(
                prescription=prescription,
                is_deleted=False
            ).first()
            
            if dispensing_record:
                if dispensing_record.payment_receipt:
                    already_paid += 1
                    continue
                
                if dispensing_record.dispensing_status != 'pending_payment':
                    dispensing_record.dispensing_status = 'pending_payment'
                    dispensing_record.save(update_fields=['dispensing_status'])
                already_pending += 1
                continue
            
            billing_result = AutoBillingService.create_pharmacy_bill(prescription)
            if billing_result.get('success'):
                created_records += 1
            else:
                warnings.append(billing_result.get('message') or 'Unable to auto-create bill.')
        
        if created_records == 0 and already_pending == 0 and already_paid == len(prescriptions):
            return JsonResponse({
                'success': False,
                'error': 'All prescriptions for this order are already paid. Proceed to dispensing.'
            }, status=400)
        
        cashier_url = reverse('hospital:cashier_patient_bills')
        if patient.mrn:
            cashier_url = f"{cashier_url}?search={patient.mrn}"
        
        response_data = {
            'success': True,
            'created': created_records,
            'already_pending': already_pending,
            'already_paid': already_paid,
            'amount': str(total_amount),
            'patient_name': patient.full_name,
            'patient_mrn': patient.mrn,
            'cashier_url': cashier_url,
        }
        
        if warnings:
            response_data['warnings'] = warnings
        
        return JsonResponse(response_data)
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def dispense_pharmacy_order(request, order_id):
    """Dispense medications for an order - with payment verification"""
    try:
        order = get_object_or_404(Order, pk=order_id, order_type='medication', is_deleted=False)
        
        # Get all prescriptions
        prescriptions = order.prescriptions.filter(is_deleted=False)
        
        if not prescriptions.exists():
            return JsonResponse({'success': False, 'error': 'No prescriptions found'}, status=400)
        
        # PAYMENT VERIFICATION: Check if payment has been made
        from .models_payment_verification import PharmacyDispensing
        from .services.unified_receipt_service import UnifiedReceiptService
        
        # Check if patient has paid for this order
        receipt_service = UnifiedReceiptService()
        patient = order.encounter.patient if order.encounter else None
        
        if not patient:
            return JsonResponse({
                'success': False, 
                'error': 'Patient not found for this order'
            }, status=400)
        
        # Check if there's a receipt for these prescriptions
        has_payment = False
        payment_receipt = None
        
        # Check each prescription for payment
        for prescription in prescriptions:
            # Check if there's a PharmacyDispensing record with payment
            existing_dispensing = PharmacyDispensing.objects.filter(
                prescription=prescription,
                is_deleted=False
            ).first()
            
            if existing_dispensing and existing_dispensing.payment_receipt:
                has_payment = True
                payment_receipt = existing_dispensing.payment_receipt
                break
        
        # If no payment found, check if there's a receipt for this encounter
        if not has_payment:
            from .models import Receipt
            payment_receipts = Receipt.objects.filter(
                patient=patient,
                is_deleted=False,
                is_cancelled=False
            ).filter(
                Q(encounter=order.encounter) if order.encounter else Q(id__isnull=False)
            ).order_by('-created')
            
            if payment_receipts.exists():
                payment_receipt = payment_receipts.first()
                has_payment = True
        
        # ENFORCE PAYMENT: Don't allow dispensing without payment
        if not has_payment:
            return JsonResponse({
                'success': False,
                'error': 'Payment required before dispensing',
                'message': 'Patient must pay at cashier before medications can be dispensed.',
                'payment_required': True
            }, status=403)
        
        # Get current staff
        current_staff = None
        try:
            current_staff = request.user.staff
        except:
            pass
        
        # Create dispensing records for each prescription
        dispensed_count = 0
        for prescription in prescriptions:
            # Check if already dispensed
            existing = PharmacyDispensing.objects.filter(
                prescription=prescription,
                is_deleted=False
            ).first()
            
            if not existing:
                # Create dispensing record with payment info
                PharmacyDispensing.objects.create(
                    prescription=prescription,
                    patient=patient,
                    dispensed_by=current_staff,
                    dispensed_at=timezone.now(),
                    quantity_dispensed=prescription.quantity,
                    payment_receipt=payment_receipt,
                    payment_verified_at=timezone.now(),
                    dispensing_status='dispensed',
                    notes='Dispensed from pharmacy dashboard'
                )
                dispensed_count += 1
            elif existing and not existing.quantity_dispensed:
                # Update existing record
                existing.dispensed_by = current_staff
                existing.dispensed_at = timezone.now()
                existing.quantity_dispensed = prescription.quantity
                existing.payment_receipt = payment_receipt
                existing.payment_verified_at = timezone.now()
                existing.dispensing_status = 'dispensed'
                existing.save()
                dispensed_count += 1
        
        # Update order status
        order.status = 'completed'
        order.save()
        
        return JsonResponse({
            'success': True,
            'dispensed_count': dispensed_count,
            'message': f'{dispensed_count} prescription(s) dispensed successfully',
            'receipt_number': payment_receipt.receipt_number if payment_receipt else None
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error processing dispensing: {error_details}")
        return JsonResponse({
            'success': False, 
            'error': 'Error processing dispensing',
            'details': str(e)
        }, status=500)


@login_required
def get_imaging_study_images(request, study_id):
    """Get all images for an imaging study via AJAX"""
    try:
        study = get_object_or_404(ImagingStudy, pk=study_id, is_deleted=False)
        
        images = study.images.filter(is_deleted=False).order_by('sequence_number', 'uploaded_at')
        
        images_data = []
        for img in images:
            images_data.append({
                'id': str(img.id),
                'url': img.image.url,
                'description': img.description,
                'sequence_number': img.sequence_number,
                'uploaded_at': img.uploaded_at.strftime('%Y-%m-%d %H:%M'),
                'uploaded_by': img.uploaded_by.user.get_full_name() if img.uploaded_by else 'Unknown'
            })
        
        return JsonResponse({
            'success': True,
            'images': images_data,
            'study': {
                'id': str(study.id),
                'modality': study.modality,
                'body_part': study.body_part,
                'status': study.status,
                'report_text': study.report_text or '',
                'findings': study.findings or '',
                'impression': study.impression or ''
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
