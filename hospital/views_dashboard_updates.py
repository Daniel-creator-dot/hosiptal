"""
Dashboard Live Updates API
Returns real-time updates for pending labs, imaging, and orders
"""
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q
from hospital.models import Order, LabResult
try:
    from hospital.models_advanced import ImagingStudy as AdvancedImagingStudy
except ImportError:
    AdvancedImagingStudy = None
import logging

logger = logging.getLogger(__name__)


@login_required
def dashboard_updates_view(request):
    """
    API endpoint to check for completed labs, imaging, and orders
    Returns JSON with completed item IDs and updated counts
    """
    try:
        # Get doctor's staff record
        from hospital.models import Staff
        try:
            staff = Staff.objects.get(user=request.user, is_deleted=False)
        except Staff.DoesNotExist:
            staff = None
        
        if not staff:
            return JsonResponse({
                'completed_labs': [],
                'completed_orders': [],
                'completed_imaging': [],
                'counts': {}
            })
        
        # Get last check time from request (optional)
        last_check = request.GET.get('last_check')
        
        # Find completed lab results
        # Strategy: Get orders that WOULD appear on dashboard (have pending results),
        # then check which ones no longer have any pending/in_progress results
        completed_labs = []
        
        # Get lab orders that match dashboard criteria (same as dashboard view)
        # These are orders that currently have pending/in_progress results
        dashboard_lab_orders = Order.objects.filter(
            Q(encounter__provider=staff) | Q(requested_by=staff),
            order_type='lab',
            is_deleted=False,
        ).filter(
            lab_results__status__in=['pending', 'in_progress'],
            lab_results__is_deleted=False
        ).select_related('encounter__patient').distinct()[:20]  # Limit to reasonable number
        
        # For each order that appears on dashboard, check if it still has pending results
        for order in dashboard_lab_orders:
            # Check if this order still has any pending or in_progress lab results
            has_pending_results = LabResult.objects.filter(
                order=order,
                status__in=['pending', 'in_progress'],
                is_deleted=False
            ).exists()
            
            # If no pending results exist, the order is completed
            if not has_pending_results:
                completed_labs.append(str(order.id))  # Convert to string for JavaScript
        
        # Find completed orders (non-lab, high priority)
        # Get orders that match dashboard criteria (pending/in_progress, urgent/stat)
        # and check which ones are now completed
        completed_orders = []
        
        # Get high priority orders that match dashboard query
        dashboard_orders = Order.objects.filter(
            encounter__provider=staff,
            status__in=['pending', 'in_progress'],
            priority__in=['urgent', 'stat'],
            is_deleted=False
        )[:20]  # Limit to reasonable number
        
        # Check which ones are now completed/served
        for order in dashboard_orders:
            # Re-fetch to get current status
            current_order = Order.objects.filter(id=order.id).first()
            if current_order and current_order.status in ['completed', 'served']:
                completed_orders.append(str(current_order.id))  # Convert to string for JavaScript
        
        # Find completed imaging studies
        completed_imaging = []
        if AdvancedImagingStudy:
            try:
                # Check for recently completed imaging studies
                recent_time = timezone.now() - timezone.timedelta(hours=1)
                completed_imaging_objs = AdvancedImagingStudy.objects.filter(
                    order__encounter__provider=staff,
                    status__in=['completed', 'reported'],
                    is_deleted=False,
                    modified__gte=recent_time
                )
                completed_imaging = list(completed_imaging_objs.values_list('id', flat=True))
            except Exception as e:
                logger.warning(f"Error checking imaging studies: {e}")
        
        # Get current counts
        from hospital.models import Encounter, Appointment
        today = timezone.now().date()
        
        active_patients = Encounter.objects.filter(
            provider=staff,
            is_deleted=False,
            status='active'
        ).count()
        
        appointments_count = Appointment.objects.filter(
            provider=staff,
            appointment_date__date=today,
            is_deleted=False
        ).count()
        
        pending_labs_count = Order.objects.filter(
            Q(encounter__provider=staff) | Q(requested_by=staff),
            order_type='lab',
            is_deleted=False,
        ).filter(
            lab_results__status__in=['pending', 'in_progress']
        ).distinct().count()
        
        # Log for debugging
        if completed_labs or completed_orders or completed_imaging:
            logger.info(f"Dashboard updates for {staff.user.username}: {len(completed_labs)} labs, {len(completed_orders)} orders, {len(completed_imaging)} imaging")
        
        return JsonResponse({
            'completed_labs': completed_labs,
            'completed_orders': completed_orders,
            'completed_imaging': completed_imaging,
            'counts': {
                'active_patients': active_patients,
                'appointments_count': appointments_count,
                'pending_labs': pending_labs_count,
            },
            'timestamp': timezone.now().isoformat(),
            'debug': {
                'checked_lab_orders': len(dashboard_lab_orders) if 'dashboard_lab_orders' in locals() else 0,
                'checked_orders': len(dashboard_orders) if 'dashboard_orders' in locals() else 0,
            }
        })
        
    except Exception as e:
        logger.error(f"Dashboard updates error: {e}", exc_info=True)
        return JsonResponse({
            'error': str(e),
            'completed_labs': [],
            'completed_orders': [],
            'completed_imaging': [],
            'counts': {}
        }, status=500)

