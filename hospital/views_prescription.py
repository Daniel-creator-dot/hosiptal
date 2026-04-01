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
from hospital.decorators import role_required
import logging

logger = logging.getLogger(__name__)


@login_required
@role_required('doctor', 'admin', message='Access denied. Only doctors can manage prescriptions.')
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
        order = getattr(prescription, "order", None)
        encounter = getattr(order, "encounter", None) if order else None
        provider = getattr(encounter, "provider", None) if encounter else None
        can_delete = (
            prescription.prescribed_by == staff
            or is_admin
            or (is_doctor and encounter and provider == staff)
        )
        
        if not can_delete:
            messages.error(request, 'You can only delete prescriptions you created or prescriptions for your patients.')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)
            return redirect('hospital:dashboard')
        
        # If already dispensed, do not allow delete (safety)
        dispensing_record = getattr(prescription, "dispensing_record", None)
        try:
            if dispensing_record and getattr(dispensing_record, "is_dispensed", False):
                messages.warning(request, 'This prescription has already been dispensed. Contact pharmacy to cancel.')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Prescription already dispensed'}, status=400)
                return redirect('hospital:dashboard')
        except Exception:
            pass

        # Cascade to pharmacy and invoice: waive invoice lines, cancel dispensing
        from hospital.services.prescription_cascade_service import cascade_prescription_deleted
        cascade_prescription_deleted(prescription, waived_by_user=request.user)

        # Soft delete
        drug_name = prescription.drug.name
        patient_name = "Unknown"
        try:
            order = getattr(prescription, "order", None)
            encounter = getattr(order, "encounter", None) if order else None
            if encounter and getattr(encounter, "patient", None):
                patient_name = encounter.patient.full_name
        except Exception:
            pass
        
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
        order = getattr(prescription, "order", None)
        encounter = getattr(order, "encounter", None) if order else None
        if order and encounter:
            return redirect('hospital:encounter_detail', pk=encounter.id)
        
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

