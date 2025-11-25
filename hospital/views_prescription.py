"""
Prescription Management Views
Handles prescription deletion and management for doctors
"""
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from hospital.models import Prescription, Staff
from hospital.utils_roles import get_user_role
import logging

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["POST", "DELETE"])
def delete_prescription(request, prescription_id):
    """
    Delete a prescription (soft delete)
    Only allows doctors to delete prescriptions they created
    """
    try:
        # Get prescription
        prescription = get_object_or_404(
            Prescription,
            id=prescription_id,
            is_deleted=False
        )
        
        # Get user's staff record
        try:
            staff = Staff.objects.get(user=request.user, is_deleted=False)
        except Staff.DoesNotExist:
            messages.error(request, 'You must be a staff member to delete prescriptions.')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)
            return redirect('hospital:dashboard')
        
        # Check if user is a doctor or has permission
        user_role = get_user_role(request.user)
        is_doctor = user_role == 'doctor'
        is_admin = user_role == 'admin'
        
        # Check if user created this prescription or is admin
        can_delete = (
            prescription.prescribed_by == staff or
            is_admin or
            (is_doctor and prescription.order.encounter.provider == staff)
        )
        
        if not can_delete:
            messages.error(request, 'You can only delete prescriptions you created or prescriptions for your patients.')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)
            return redirect('hospital:dashboard')
        
        # Check if prescription has been dispensed (optional - you may want to prevent deletion if already dispensed)
        # This is a safety check - you can remove it if you want to allow deletion even after dispensing
        if hasattr(prescription, 'dispensing_record') and prescription.dispensing_record:
            messages.warning(request, 'This prescription has already been dispensed. Contact pharmacy to cancel.')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Prescription already dispensed'}, status=400)
            return redirect('hospital:dashboard')
        
        # Soft delete
        drug_name = prescription.drug.name
        patient_name = prescription.order.encounter.patient.full_name if prescription.order.encounter else "Unknown"
        
        prescription.is_deleted = True
        prescription.save(update_fields=['is_deleted', 'modified'])
        
        logger.info(f"Prescription {prescription_id} deleted by {request.user.username} for patient {patient_name}")
        
        messages.success(request, f'Prescription for {drug_name} deleted successfully.')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Prescription for {drug_name} deleted successfully.'
            })
        
        # Redirect back to referring page or encounter
        next_url = request.GET.get('next') or request.POST.get('next')
        if next_url:
            return redirect(next_url)
        
        # Default redirect to encounter if available
        if prescription.order and prescription.order.encounter:
            return redirect('hospital:encounter_detail', pk=prescription.order.encounter.id)
        
        return redirect('hospital:dashboard')
        
    except Prescription.DoesNotExist:
        messages.error(request, 'Prescription not found.')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Prescription not found'}, status=404)
        return redirect('hospital:dashboard')
    except Exception as e:
        logger.error(f"Error deleting prescription {prescription_id}: {e}", exc_info=True)
        messages.error(request, f'Error deleting prescription: {str(e)}')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
        return redirect('hospital:dashboard')

