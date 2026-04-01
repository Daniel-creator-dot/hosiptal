"""
Radiology-specific views for outstanding radiology role
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse

from .models import Order, Patient

# Import ImagingStudy safely
try:
    from .models_advanced import ImagingStudy, ImagingImage
    ImagingStudy_available = True
except ImportError:
    ImagingStudy = None
    ImagingImage = None
    ImagingStudy_available = False


@login_required
def radiologist_pending_orders(request):
    """View pending imaging orders"""
    from .models import Staff
    from .utils_roles import get_user_role
    from django.db import connection
    from django.utils import timezone
    from .models_advanced import ImagingStudy
    
    # Check if user is radiologist
    user_role = get_user_role(request.user)
    if user_role != 'radiologist' and not request.user.is_superuser:
        from django.contrib import messages
        messages.error(request, 'Access denied. Radiologist access required.')
        return redirect('hospital:dashboard')
    
    staff = Staff.objects.filter(user=request.user, is_deleted=False).first()
    if not staff:
        return render(request, 'hospital/error.html', {'error': 'Staff profile not found'}, status=403)
    
    # CRITICAL: Deduplicate orders - keep only most recent per patient per order type per day
    try:
        with connection.cursor() as cursor:
            sql_query = """
                SELECT DISTINCT ON (p.id, o.order_type, DATE(COALESCE(o.requested_at, o.created))) o.id::text
                FROM hospital_order o
                INNER JOIN hospital_encounter e ON e.id = o.encounter_id
                INNER JOIN hospital_patient p ON p.id = e.patient_id
                WHERE o.order_type = 'imaging'
                  AND o.status = 'pending'
                  AND o.is_deleted = false
                  AND e.is_deleted = false
                  AND e.patient_id IS NOT NULL
                ORDER BY p.id, o.order_type, DATE(COALESCE(o.requested_at, o.created)), o.created DESC, o.id DESC
                LIMIT 100
            """
            cursor.execute(sql_query)
            latest_order_ids = [row[0] for row in cursor.fetchall()]
        
        if not latest_order_ids:
            pending_orders_qs = Order.objects.none()
        else:
            pending_orders_qs = Order.objects.filter(
                pk__in=latest_order_ids
            ).select_related('encounter__patient', 'requested_by', 'requested_by__user')
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error deduplicating orders: {str(e)}")
        # Fallback: original query without deduplication
        pending_orders_qs = Order.objects.filter(
            order_type='imaging',
            status='pending',
            is_deleted=False,
            encounter__isnull=False,
            encounter__patient__isnull=False
        ).select_related('encounter__patient', 'requested_by', 'requested_by__user')
    
    # Fix invalid orders: update requested_at for orders missing it
    now = timezone.now()
    orders_to_fix = []
    for order in pending_orders_qs:
        needs_fix = False
        
        # Fix missing requested_at
        if not order.requested_at:
            order.requested_at = order.created
            needs_fix = True
        
        if needs_fix:
            orders_to_fix.append(order)
    
    # Bulk update fixed orders
    if orders_to_fix:
        Order.objects.bulk_update(orders_to_fix, ['requested_at'], batch_size=50)
    
    # Add description property to each order (generated from imaging studies)
    for order in pending_orders_qs:
        imaging_studies = ImagingStudy.objects.filter(
            order=order,
            is_deleted=False
        )
        
        if imaging_studies.exists():
            study_names = []
            for study in imaging_studies:
                if study.study_type:
                    study_names.append(study.study_type)
                elif study.body_part:
                    study_names.append(f"{study.get_modality_display()} - {study.body_part}")
                else:
                    study_names.append(study.get_modality_display())
            
            order.description = ', '.join(study_names[:3])  # Limit to 3 studies
            if imaging_studies.count() > 3:
                order.description += f" (+{imaging_studies.count() - 3} more)"
        else:
            # No imaging studies - use default
            order.description = 'Imaging Study'
    
    # Sort by priority
    priority_order = {'stat': 0, 'urgent': 1, 'routine': 2}
    pending_orders = sorted(
        list(pending_orders_qs),
        key=lambda x: (priority_order.get(x.priority or 'routine', 2), x.requested_at or x.created),
        reverse=False
    )
    
    context = {
        'staff': staff,
        'pending_orders': pending_orders,
        'page_title': 'Pending Imaging Orders',
    }
    
    return render(request, 'hospital/radiology/pending_orders.html', context)


@login_required
def radiologist_my_studies(request):
    """View studies assigned to current radiologist"""
    from .models import Staff
    from .utils_roles import get_user_role
    from django.shortcuts import redirect
    
    # Check if user is radiologist
    user_role = get_user_role(request.user)
    if user_role != 'radiologist' and not request.user.is_superuser:
        from django.contrib import messages
        messages.error(request, 'Access denied. Radiologist access required.')
        return redirect('hospital:dashboard')
    
    staff = Staff.objects.filter(user=request.user, is_deleted=False).first()
    if not staff:
        return render(request, 'hospital/error.html', {'error': 'Staff profile not found'}, status=403)
    
    my_studies = []
    if ImagingStudy_available:
        try:
            # Show studies assigned to this radiologist OR unassigned studies that need reports
            # This allows radiologists to see and claim unassigned studies
            all_studies = ImagingStudy.objects.filter(
                is_deleted=False
            ).filter(
                Q(assigned_radiologist=staff) |
                (
                    Q(assigned_radiologist__isnull=True) &
                    (
                        Q(status__in=['awaiting_report', 'reporting', 'completed', 'in_progress']) |
                        Q(images__isnull=False)
                    )
                )
            ).select_related(
                'order', 'order__encounter__patient', 
                'technician', 'report_dictated_by', 'report_verified_by', 'assigned_radiologist'
            ).prefetch_related('images').distinct().order_by('-performed_at', '-created')
            
            # Limit to recent studies (last 30 days) to avoid showing too many
            from datetime import timedelta
            thirty_days_ago = timezone.now() - timedelta(days=30)
            all_studies = all_studies.filter(
                Q(performed_at__gte=thirty_days_ago) |
                Q(created__gte=thirty_days_ago) |
                Q(assigned_radiologist=staff)  # Always show assigned studies regardless of date
            )
            
            # DEDUPLICATION: Remove duplicates - keep only the best study per patient+modality+study_type
            # Also check for duplicates within same encounter
            seen_studies_by_key = {}  # patient + modality + study_type
            seen_studies_by_encounter = {}  # patient + encounter + modality (for same-day duplicates)
            
            status_priority = {
                'verified': 10, 'reported': 9, 'completed': 8, 'awaiting_report': 7,
                'reporting': 6, 'in_progress': 5, 'quality_check': 4, 'arrived': 3,
                'scheduled': 2, 'cancelled': 1
            }
            
            for study in all_studies:
                # Primary key: patient + modality + study_type
                key = (study.patient_id, study.modality, study.study_type or '')
                
                # Encounter-based key for same-day duplicates
                encounter_key = None
                if study.encounter_id:
                    encounter_key = (study.patient_id, study.encounter_id, study.modality)
                
                should_keep = True
                existing = None
                
                # Check primary key first
                if key in seen_studies_by_key:
                    existing = seen_studies_by_key[key]
                    existing_time = existing.performed_at or existing.created
                    current_time = study.performed_at or study.created
                    
                    # If current is newer or has higher status, replace
                    if current_time > existing_time:
                        seen_studies_by_key[key] = study
                        should_keep = True
                    elif current_time == existing_time:
                        current_priority = status_priority.get(study.status, 0)
                        existing_priority = status_priority.get(existing.status, 0)
                        if current_priority > existing_priority:
                            seen_studies_by_key[key] = study
                            should_keep = True
                        else:
                            should_keep = False
                    else:
                        should_keep = False
                else:
                    seen_studies_by_key[key] = study
                
                # Also check encounter-based duplicates (same patient, same encounter, same modality within 1 hour)
                if encounter_key and should_keep:
                    if encounter_key in seen_studies_by_encounter:
                        existing_enc = seen_studies_by_encounter[encounter_key]
                        time_diff = abs((study.created - existing_enc.created).total_seconds() / 3600)
                        
                        # If created within 1 hour, likely duplicate - keep the better one
                        if time_diff < 1:
                            existing_time = existing_enc.performed_at or existing_enc.created
                            current_time = study.performed_at or study.created
                            
                            if current_time > existing_time:
                                seen_studies_by_encounter[encounter_key] = study
                                # Remove the old one from primary key if it's there
                                old_key = (existing_enc.patient_id, existing_enc.modality, existing_enc.study_type or '')
                                if old_key in seen_studies_by_key and seen_studies_by_key[old_key].id == existing_enc.id:
                                    seen_studies_by_key[old_key] = study
                            else:
                                should_keep = False
                        else:
                            seen_studies_by_encounter[encounter_key] = study
                    else:
                        seen_studies_by_encounter[encounter_key] = study
                
                # If we're not keeping this one, it's already handled above
                if not should_keep and existing:
                    # Already replaced in seen_studies_by_key, continue
                    continue
            
            # Convert back to list and re-sort
            my_studies = list(seen_studies_by_key.values())
            my_studies.sort(key=lambda x: (x.performed_at or x.created), reverse=True)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error fetching my studies: {str(e)}', exc_info=True)
    
    context = {
        'staff': staff,
        'my_studies': my_studies,
        'page_title': 'My Studies',
    }
    
    return render(request, 'hospital/radiology/my_studies.html', context)


@login_required
def radiologist_report_queue(request):
    """View studies awaiting reports"""
    from .models import Staff
    from .utils_roles import get_user_role
    from django.shortcuts import redirect
    
    # Check if user is radiologist
    user_role = get_user_role(request.user)
    if user_role != 'radiologist' and not request.user.is_superuser:
        from django.contrib import messages
        messages.error(request, 'Access denied. Radiologist access required.')
        return redirect('hospital:dashboard')
    
    staff = Staff.objects.filter(user=request.user, is_deleted=False).first()
    if not staff:
        return render(request, 'hospital/error.html', {'error': 'Staff profile not found'}, status=403)
    
    awaiting_report = []
    if ImagingStudy_available:
        try:
            # Get studies that need reports - either explicitly marked as awaiting_report/reporting
            # OR completed/in_progress studies that don't have any report content yet
            all_awaiting = ImagingStudy.objects.filter(
                is_deleted=False
            ).filter(
                Q(status__in=['awaiting_report', 'reporting']) |
                (
                    Q(status__in=['completed', 'in_progress']) &
                    (
                        (Q(report_text='') | Q(report_text__isnull=True)) &
                        (Q(findings='') | Q(findings__isnull=True)) &
                        (Q(impression='') | Q(impression__isnull=True))
                    )
                )
            ).select_related(
                'order', 'order__encounter__patient', 
                'technician', 'assigned_radiologist'
            ).order_by('-performed_at', '-created')
            
            # DEDUPLICATION: Remove duplicates - keep only the most recent study per patient+modality+study_type
            seen_studies = {}
            for study in all_awaiting:
                # Create unique key: patient + modality + study_type
                key = (study.patient_id, study.modality, study.study_type or '')
                
                # If we haven't seen this combination, or this one is newer, keep it
                if key not in seen_studies:
                    seen_studies[key] = study
                else:
                    # Compare timestamps - keep the newer one
                    existing = seen_studies[key]
                    if study.performed_at and existing.performed_at:
                        if study.performed_at > existing.performed_at:
                            seen_studies[key] = study
                    elif study.created > existing.created:
                        seen_studies[key] = study
            
            # Convert back to list
            awaiting_report = list(seen_studies.values())
            # Re-sort by performed_at or created
            awaiting_report.sort(key=lambda x: x.performed_at or x.created, reverse=True)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error fetching awaiting reports: {str(e)}', exc_info=True)
    
    context = {
        'staff': staff,
        'awaiting_report': awaiting_report,
        'page_title': 'Report Queue',
    }
    
    return render(request, 'hospital/radiology/report_queue.html', context)


@login_required
def radiologist_completed_studies(request):
    """View completed studies"""
    from .models import Staff
    from .utils_roles import get_user_role
    from django.shortcuts import redirect
    
    # Check if user is radiologist
    user_role = get_user_role(request.user)
    if user_role != 'radiologist' and not request.user.is_superuser:
        from django.contrib import messages
        messages.error(request, 'Access denied. Radiologist access required.')
        return redirect('hospital:dashboard')
    
    staff = Staff.objects.filter(user=request.user, is_deleted=False).first()
    if not staff:
        return render(request, 'hospital/error.html', {'error': 'Staff profile not found'}, status=403)
    
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    completed_studies = []
    if ImagingStudy_available:
        try:
            completed_studies = ImagingStudy.objects.filter(
                status__in=['reported', 'verified'],
                is_deleted=False
            ).select_related(
                'order', 'order__encounter__patient', 
                'technician', 'report_dictated_by', 'report_verified_by'
            ).order_by('-performed_at', '-created')[:100]
        except Exception:
            pass
    
    # Statistics
    stats = {
        'total': len(completed_studies),
        'today': len([s for s in completed_studies if s.performed_at and s.performed_at.date() == today]) if ImagingStudy_available else 0,
        'this_week': len([s for s in completed_studies if s.performed_at and s.performed_at.date() >= week_ago]) if ImagingStudy_available else 0,
        'this_month': len([s for s in completed_studies if s.performed_at and s.performed_at.date() >= month_ago]) if ImagingStudy_available else 0,
    }
    
    context = {
        'staff': staff,
        'completed_studies': completed_studies,
        'stats': stats,
        'page_title': 'Completed Studies',
    }
    
    return render(request, 'hospital/radiology/completed_studies.html', context)

