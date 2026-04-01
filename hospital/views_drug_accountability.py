"""
Views for Drug Accountability System
Drug returns, inventory history, and complete audit trails
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum, Count, F
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db import ProgrammingError, OperationalError
from decimal import Decimal
from datetime import date, timedelta

from .models import Staff, Patient, Drug, Prescription
from .models_payment_verification import PharmacyDispensing

# ==================== HELPER FUNCTIONS ====================

def is_medical_director(user):
    """Check if user is Medical Director"""
    try:
        staff = Staff.objects.get(user=user, is_deleted=False)
        # Check if specialization contains "Medical Director" or "medical director"
        specialization = (staff.specialization or '').lower()
        return (
            'medical director' in specialization or
            user.is_superuser or
            user.is_staff and staff.profession == 'doctor' and 'director' in specialization
        )
    except Staff.DoesNotExist:
        return user.is_superuser or user.is_staff

def can_approve_drug_returns(user):
    """Check if user can approve drug returns (Admin or Medical Director)"""
    return user.is_superuser or is_medical_director(user)

# Try to import accountability models - handle if migration not run yet
try:
    from .models_procurement import Store, InventoryItem
    from .models_inventory_advanced import InventoryTransaction
    from .models_drug_accountability import DrugReturn, DrugAdministrationInventory
    from .models_payment_verification import PharmacyDispensing
    ACCOUNTABILITY_AVAILABLE = True
except (ImportError, Exception):
    # Models not available yet (migration not run) or any other error
    ACCOUNTABILITY_AVAILABLE = False
    Store = None
    InventoryItem = None
    InventoryTransaction = None
    DrugReturn = None
    DrugAdministrationInventory = None
    PharmacyDispensing = None


# ==================== DRUG RETURNS ====================

@login_required
def drug_returns_list(request):
    """List all drug returns"""
    # Wrap entire function in try-except to catch any database errors
    try:
        if not ACCOUNTABILITY_AVAILABLE:
            messages.warning(request, 'Drug accountability system is not available. Please run migrations first.')
            return redirect('hospital:pharmacy_dashboard')
        
        # Check if DrugReturn model is available before querying
        if DrugReturn is None:
            messages.error(request, 'Drug accountability models not available. Please run migrations: python manage.py migrate hospital 1058_add_drug_accountability_system')
            return redirect('hospital:pharmacy_dashboard')
        
        # Check if table exists before querying (prevents ProgrammingError)
        from django.db import connection
        table_name = DrugReturn._meta.db_table
        with connection.cursor() as cursor:
            if connection.vendor == 'postgresql':
                cursor.execute(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s)",
                    [table_name]
                )
                table_exists = cursor.fetchone()[0]
            else:
                # For other databases, try a simple query
                try:
                    cursor.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
                    table_exists = True
                except Exception:
                    table_exists = False
        
        if not table_exists:
            messages.error(request, 'Database tables not found. Please run migrations: python manage.py migrate hospital 1058_add_drug_accountability_system')
            return redirect('hospital:pharmacy_dashboard')
        
        # Try to query - this will fail if table doesn't exist
        returns = DrugReturn.objects.filter(is_deleted=False).select_related(
            'patient', 'drug', 'requested_by', 'approved_by', 'processed_by', 'store'
        ).order_by('-return_date')
        
        # Filters
        status_filter = request.GET.get('status', '')
        if status_filter:
            returns = returns.filter(status=status_filter)
        
        search_query = request.GET.get('search', '')
        if search_query:
            returns = returns.filter(
                Q(return_number__icontains=search_query) |
                Q(patient__first_name__icontains=search_query) |
                Q(patient__last_name__icontains=search_query) |
                Q(patient__middle_name__icontains=search_query) |
                Q(patient__mrn__icontains=search_query) |
                Q(drug__name__icontains=search_query)
            )
        
        # Pagination
        paginator = Paginator(returns, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Statistics
        stats = {
            'total': returns.count(),
            'pending': returns.filter(status='pending').count(),
            'approved': returns.filter(status='approved').count(),
            'completed': returns.filter(status='completed').count(),
            'rejected': returns.filter(status='rejected').count(),
        }
        
        # Check if user can approve returns
        can_approve = can_approve_drug_returns(request.user)
        
        context = {
            'page_obj': page_obj,
            'returns': page_obj,
            'stats': stats,
            'status_filter': status_filter,
            'search_query': search_query,
            'can_approve': can_approve,
        }
        
        return render(request, 'hospital/drug_accountability/returns_list.html', context)
        
    except (ProgrammingError, OperationalError) as e:
        # Handle case where tables don't exist yet
        messages.error(request, 'Database tables not found. Please run migrations: python manage.py migrate hospital 1058_add_drug_accountability_system')
        return redirect('hospital:pharmacy_dashboard')
    except Exception as e:
        # Catch any other errors
        messages.error(request, f'Error loading drug returns: {str(e)}')
        return redirect('hospital:pharmacy_dashboard')


@login_required
@login_required
def patient_search_api(request):
    """AJAX endpoint to search patients by name or MRN"""
    if request.method != 'GET':
        return JsonResponse({'error': 'GET method required'}, status=405)
    
    search_query = request.GET.get('q', '').strip()
    if not search_query or len(search_query) < 2:
        return JsonResponse({'results': []})
    
    try:
        # Enhanced search: also search by full name combination
        query_parts = search_query.split()
        patient_search = Q(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(middle_name__icontains=search_query) |
            Q(mrn__icontains=search_query) |
            Q(phone_number__icontains=search_query)
        )
        
        # If query has multiple words, search for full name combinations
        if len(query_parts) >= 2:
            first_part = query_parts[0]
            last_parts = ' '.join(query_parts[1:])
            patient_search |= Q(
                Q(first_name__icontains=first_part) &
                Q(last_name__icontains=last_parts)
            )
            patient_search |= Q(
                Q(first_name__icontains=last_parts) &
                Q(last_name__icontains=first_part)
            )
        
        # Search patients
        patients = Patient.objects.filter(
            patient_search,
            is_deleted=False
        ).distinct().order_by('first_name', 'last_name')[:20]
        
        results = []
        for patient in patients:
            try:
                results.append({
                    'id': str(patient.id),
                    'text': f"{patient.full_name} (MRN: {patient.mrn})",
                    'name': patient.full_name,
                    'mrn': patient.mrn,
                    'phone': patient.phone_number or '',
                })
            except Exception as e:
                # Skip patients with errors, continue with others
                continue
        
        return JsonResponse({'results': results})
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Patient search error: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def drug_search_api(request):
    """AJAX endpoint to search drugs by name or code"""
    if request.method != 'GET':
        return JsonResponse({'error': 'GET method required'}, status=405)
    
    search_query = request.GET.get('q', '').strip()
    if not search_query or len(search_query) < 2:
        return JsonResponse({'results': []})
    
    try:
        # Build query - search by name and atc_code (Drug model uses atc_code, not code)
        query = Q(name__icontains=search_query) | Q(atc_code__icontains=search_query)
        
        # Add generic_name to query if field exists
        try:
            query |= Q(generic_name__icontains=search_query)
        except Exception:
            # Field might not exist, skip it
            pass
        
        # Filter drugs
        drugs = Drug.objects.filter(
            query,
            is_deleted=False,
            is_active=True
        ).order_by('name')[:20]
        
        results = []
        for drug in drugs:
            try:
                # Get code - try 'code' first, then 'atc_code'
                drug_code = getattr(drug, 'code', None) or getattr(drug, 'atc_code', 'N/A')
                if drug_code:
                    drug_code = str(drug_code)
                else:
                    drug_code = 'N/A'
                
                results.append({
                    'id': str(drug.id),
                    'text': f"{drug.name} ({drug_code})",
                    'name': drug.name,
                    'code': drug_code,
                })
            except Exception as e:
                # Skip drugs with errors, continue with others
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error processing drug {drug.id}: {str(e)}")
                continue
        
        return JsonResponse({'results': results})
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        error_traceback = traceback.format_exc()
        logger.error(f"Drug search error: {str(e)}\n{error_traceback}", exc_info=True)
        return JsonResponse({'error': str(e), 'details': error_traceback[:500]}, status=500)


@login_required
def drug_return_create(request):
    """Create a new drug return request"""
    if not ACCOUNTABILITY_AVAILABLE:
        messages.warning(request, 'Drug accountability system is not available. Please run migrations first.')
        return redirect('hospital:pharmacy_dashboard')
    
    if request.method == 'POST':
        try:
            staff = Staff.objects.get(user=request.user, is_deleted=False)
            
            prescription_id = request.POST.get('prescription_id')
            dispensing_id = request.POST.get('dispensing_id')
            patient_id = request.POST.get('patient_id', '').strip()
            drug_id = request.POST.get('drug_id', '').strip()
            patient_search = request.POST.get('patient_search', '').strip()
            drug_search = request.POST.get('drug_search', '').strip()
            quantity = int(request.POST.get('quantity', 0))
            return_reason = request.POST.get('return_reason')
            reason_details = request.POST.get('reason_details', '')
            condition = request.POST.get('condition_on_return', 'sealed')
            return_to_inventory = request.POST.get('return_to_inventory') == 'on'
            
            # Use search field if main field is empty
            if not patient_id and patient_search:
                patient_id = patient_search
            if not drug_id and drug_search:
                drug_id = drug_search
            
            if not all([patient_id, drug_id, quantity, return_reason]):
                messages.error(request, 'Please fill in all required fields.')
                return redirect('hospital:drug_return_create')
            
            # Validate and find patient - handle both UUID and search by name/MRN
            patient = None
            try:
                from uuid import UUID
                # Try to parse as UUID first
                UUID(patient_id)
                patient = get_object_or_404(Patient, id=patient_id, is_deleted=False)
            except (ValueError, TypeError):
                # Not a valid UUID, try to search by name or MRN (full_name is @property, not DB field)
                patient = Patient.objects.filter(
                    Q(mrn__icontains=patient_id) |
                    Q(first_name__icontains=patient_id) |
                    Q(last_name__icontains=patient_id) |
                    Q(middle_name__icontains=patient_id),
                    is_deleted=False
                ).first()
                if not patient:
                    messages.error(request, f'Patient "{patient_id}" not found. Please select from the dropdown or enter a valid patient UUID, name, or MRN.')
                    return redirect('hospital:drug_return_create')
            
            # Validate and find drug - handle both UUID and search by name/code
            drug = None
            try:
                from uuid import UUID
                # Try to parse as UUID first
                UUID(drug_id)
                drug = get_object_or_404(Drug, id=drug_id, is_deleted=False)
            except (ValueError, TypeError):
                # Not a valid UUID, try to search by name or code
                drug = Drug.objects.filter(
                    Q(name__icontains=drug_id) | 
                    Q(code__icontains=drug_id),
                    is_deleted=False
                ).first()
                if not drug:
                    messages.error(request, f'Drug "{drug_id}" not found. Please select from the dropdown or enter a valid drug UUID, name, or code.')
                    return redirect('hospital:drug_return_create')
            
            # Get prescription or dispensing record if provided
            prescription = None
            dispensing_record = None
            original_unit_price = drug.unit_price or Decimal('0.00')
            
            if prescription_id:
                prescription = get_object_or_404(Prescription, id=prescription_id, is_deleted=False)
                original_unit_price = drug.unit_price or Decimal('0.00')
            
            if dispensing_id:
                dispensing_record = get_object_or_404(PharmacyDispensing, id=dispensing_id, is_deleted=False)
                original_unit_price = drug.unit_price or Decimal('0.00')
            
            # Create return request
            try:
                drug_return = DrugReturn.objects.create(
                    patient=patient,
                    drug=drug,
                    prescription=prescription,
                    dispensing_record=dispensing_record,
                    quantity_returned=quantity,
                    quantity_original=quantity,  # Can be enhanced
                    return_reason=return_reason,
                    reason_details=reason_details,
                    original_unit_price=original_unit_price,
                    refund_amount=original_unit_price * quantity if return_to_inventory else Decimal('0.00'),
                    return_to_inventory=return_to_inventory,
                    requested_by=staff,
                    condition_on_return=condition,
                    notes=request.POST.get('notes', ''),
                )
                
                messages.success(request, f'Drug return request {drug_return.return_number} created successfully.')
                return redirect('hospital:drug_return_detail', return_id=drug_return.id)
            except (ProgrammingError, OperationalError) as e:
                messages.error(request, 'Database tables not found. Please run migrations: python manage.py migrate hospital 1058_add_drug_accountability_system')
                return redirect('hospital:pharmacy_dashboard')
        
        except Exception as e:
            messages.error(request, f'Error creating return request: {str(e)}')
            return redirect('hospital:drug_returns_list')
    
    # GET request - show form
    # Get recent prescriptions/dispensings for selection
    recent_dispensings = []
    return_reasons = []
    patients = []
    drugs = []
    
    if ACCOUNTABILITY_AVAILABLE:
        try:
            recent_dispensings = PharmacyDispensing.objects.filter(
                is_deleted=False,
                dispensing_status='fully_dispensed'
            ).select_related('prescription__drug', 'patient').order_by('-dispensed_at')[:50]
            return_reasons = DrugReturn.RETURN_REASONS
            
            # Get recent patients and drugs for dropdown
            patients = Patient.objects.filter(is_deleted=False).order_by('-created')[:100]
            drugs = Drug.objects.filter(is_deleted=False, is_active=True).order_by('name')[:200]
        except (ProgrammingError, OperationalError):
            # Tables don't exist yet
            recent_dispensings = []
            return_reasons = []
            patients = []
            drugs = []
    
    context = {
        'recent_dispensings': recent_dispensings,
        'return_reasons': return_reasons,
        'patients': patients,
        'drugs': drugs,
    }
    
    return render(request, 'hospital/drug_accountability/return_create.html', context)


@login_required
def drug_return_detail(request, return_id):
    """View details of a drug return"""
    if not ACCOUNTABILITY_AVAILABLE:
        messages.warning(request, 'Drug accountability system is not available. Please run migrations first.')
        return redirect('hospital:pharmacy_dashboard')
    
    try:
        drug_return = get_object_or_404(DrugReturn, id=return_id, is_deleted=False)
        
        # Get related transactions
        transactions = []
        if drug_return.inventory_transaction:
            transactions = [drug_return.inventory_transaction]
        
        # Check if user can approve (Admin or Medical Director)
        can_approve = can_approve_drug_returns(request.user)
        
        context = {
            'drug_return': drug_return,
            'transactions': transactions,
            'can_approve': can_approve,
            'is_medical_director': is_medical_director(request.user),
        }
        
        return render(request, 'hospital/drug_accountability/return_detail.html', context)
    except (ProgrammingError, OperationalError) as e:
        messages.error(request, 'Database tables not found. Please run migrations: python manage.py migrate hospital 1058_add_drug_accountability_system')
        return redirect('hospital:pharmacy_dashboard')


@login_required
def drug_return_approve(request, return_id):
    """Approve a drug return request - Accessible by Admin and Medical Director"""
    if not ACCOUNTABILITY_AVAILABLE:
        messages.warning(request, 'Drug accountability system is not available. Please run migrations first.')
        return redirect('hospital:pharmacy_dashboard')
    
    # Check authorization - Admin or Medical Director only
    if not can_approve_drug_returns(request.user):
        messages.error(request, 'You do not have permission to approve drug returns. Only Administrators and Medical Directors can approve returns.')
        return redirect('hospital:drug_return_detail', return_id=return_id)
    
    try:
        drug_return = get_object_or_404(DrugReturn, id=return_id, is_deleted=False)
        
        if request.method == 'POST':
            try:
                staff = Staff.objects.get(user=request.user, is_deleted=False)
                notes = request.POST.get('approval_notes', '')
                
                drug_return.approve(staff, notes)
                messages.success(request, f'Return {drug_return.return_number} approved successfully.')
            except Exception as e:
                messages.error(request, f'Error approving return: {str(e)}')
        
        return redirect('hospital:drug_return_detail', return_id=return_id)
    except (ProgrammingError, OperationalError) as e:
        messages.error(request, 'Database tables not found. Please run migrations: python manage.py migrate hospital 1058_add_drug_accountability_system')
        return redirect('hospital:pharmacy_dashboard')


@login_required
def drug_return_bulk_approve(request):
    """Bulk approve all pending drug returns - Accessible by Admin and Medical Director"""
    if not ACCOUNTABILITY_AVAILABLE:
        messages.warning(request, 'Drug accountability system is not available. Please run migrations first.')
        return redirect('hospital:drug_returns_list')
    
    # Check authorization - Admin or Medical Director only
    if not can_approve_drug_returns(request.user):
        messages.error(request, 'You do not have permission to approve drug returns. Only Administrators and Medical Directors can approve returns.')
        return redirect('hospital:drug_returns_list')
    
    if request.method != 'POST':
        messages.error(request, 'Invalid request method. Use POST to approve returns.')
        return redirect('hospital:drug_returns_list')
    
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
        
        # Get all pending returns
        pending_returns = DrugReturn.objects.filter(
            status='pending',
            is_deleted=False
        )
        
        approved_count = 0
        failed_count = 0
        errors = []
        
        for drug_return in pending_returns:
            try:
                notes = f'Bulk approved by {staff.user.get_full_name() or staff.user.username}'
                drug_return.approve(staff, notes)
                approved_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f'Return {drug_return.return_number}: {str(e)}')
        
        if approved_count > 0:
            messages.success(request, f'Successfully approved {approved_count} pending return(s).')
        
        if failed_count > 0:
            messages.warning(request, f'Failed to approve {failed_count} return(s).')
            for error in errors[:5]:  # Show first 5 errors
                messages.error(request, error)
        
        if approved_count == 0 and failed_count == 0:
            messages.info(request, 'No pending returns to approve.')
        
    except Staff.DoesNotExist:
        messages.error(request, 'Staff record not found. Please contact administrator.')
    except (ProgrammingError, OperationalError) as e:
        messages.error(request, 'Database tables not found. Please run migrations: python manage.py migrate hospital 1058_add_drug_accountability_system')
    except Exception as e:
        messages.error(request, f'Error during bulk approval: {str(e)}')
    
    return redirect('hospital:drug_returns_list')


@login_required
def drug_return_reject(request, return_id):
    """Reject a drug return request - Accessible by Admin and Medical Director"""
    if not ACCOUNTABILITY_AVAILABLE:
        messages.warning(request, 'Drug accountability system is not available. Please run migrations first.')
        return redirect('hospital:pharmacy_dashboard')
    
    # Check authorization - Admin or Medical Director only
    if not can_approve_drug_returns(request.user):
        messages.error(request, 'You do not have permission to reject drug returns. Only Administrators and Medical Directors can reject returns.')
        return redirect('hospital:drug_return_detail', return_id=return_id)
    if not ACCOUNTABILITY_AVAILABLE:
        messages.warning(request, 'Drug accountability system is not available. Please run migrations first.')
        return redirect('hospital:pharmacy_dashboard')
    
    try:
        drug_return = get_object_or_404(DrugReturn, id=return_id, is_deleted=False)
        
        if request.method == 'POST':
            try:
                staff = Staff.objects.get(user=request.user, is_deleted=False)
                reason = request.POST.get('rejection_reason', '')
                
                if not reason:
                    messages.error(request, 'Please provide a rejection reason.')
                    return redirect('hospital:drug_return_detail', return_id=return_id)
                
                drug_return.reject(staff, reason)
                messages.success(request, f'Return {drug_return.return_number} rejected.')
            except Exception as e:
                messages.error(request, f'Error rejecting return: {str(e)}')
        
        return redirect('hospital:drug_return_detail', return_id=return_id)
    except (ProgrammingError, OperationalError) as e:
        messages.error(request, 'Database tables not found. Please run migrations: python manage.py migrate hospital 1058_add_drug_accountability_system')
        return redirect('hospital:pharmacy_dashboard')


@login_required
def drug_return_process(request, return_id):
    """Process a drug return - add back to inventory"""
    if not ACCOUNTABILITY_AVAILABLE:
        messages.warning(request, 'Drug accountability system is not available. Please run migrations first.')
        return redirect('hospital:pharmacy_dashboard')
    
    try:
        drug_return = get_object_or_404(DrugReturn, id=return_id, is_deleted=False)
        
        if request.method == 'POST':
            try:
                staff = Staff.objects.get(user=request.user, is_deleted=False)
                
                transaction = drug_return.process_return(staff)
                
                messages.success(
                    request,
                    f'Return {drug_return.return_number} processed successfully. '
                    f'Drug returned to inventory. Transaction: {transaction.transaction_number}'
                )
            except Exception as e:
                messages.error(request, f'Error processing return: {str(e)}')
        
        return redirect('hospital:drug_return_detail', return_id=return_id)
    except (ProgrammingError, OperationalError) as e:
        messages.error(request, 'Database tables not found. Please run migrations: python manage.py migrate hospital 1058_add_drug_accountability_system')
        return redirect('hospital:pharmacy_dashboard')


# ==================== INVENTORY HISTORY ====================

@login_required
def inventory_history(request):
    """Complete inventory transaction history"""
    if not ACCOUNTABILITY_AVAILABLE:
        messages.warning(request, 'Drug accountability system is not available. Please run migrations first.')
        return redirect('hospital:pharmacy_dashboard')
    
    try:
        transactions = InventoryTransaction.objects.filter(is_deleted=False).select_related(
            'inventory_item', 'store', 'performed_by', 'approved_by'
        ).order_by('-transaction_date')
        
        # Filters
        store_filter = request.GET.get('store', '')
        if store_filter:
            transactions = transactions.filter(store_id=store_filter)
        
        transaction_type_filter = request.GET.get('transaction_type', '')
        if transaction_type_filter:
            transactions = transactions.filter(transaction_type=transaction_type_filter)
        
        item_filter = request.GET.get('item', '')
        if item_filter:
            transactions = transactions.filter(inventory_item_id=item_filter)
        
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        
        if date_from:
            transactions = transactions.filter(transaction_date__gte=date_from)
        
        if date_to:
            transactions = transactions.filter(transaction_date__lte=date_to)
        
        search_query = request.GET.get('search', '')
        if search_query:
            transactions = transactions.filter(
                Q(transaction_number__icontains=search_query) |
                Q(reference_number__icontains=search_query) |
                Q(inventory_item__item_name__icontains=search_query) |
                Q(batch_number__icontains=search_query) |
                Q(notes__icontains=search_query)
            )
        
        # Pagination
        paginator = Paginator(transactions, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Statistics
        stats = {
            'total_transactions': transactions.count(),
            'total_receipts': transactions.filter(transaction_type='receipt').count(),
            'total_issues': transactions.filter(transaction_type='issue').count(),
            'total_transfers': transactions.filter(transaction_type__in=['transfer_in', 'transfer_out']).count(),
            'total_returns': transactions.filter(transaction_type='return_from_dept').count(),
        }
        
        # Get stores and items for filters
        stores = Store.objects.filter(is_deleted=False).order_by('name')
        items = InventoryItem.objects.filter(is_deleted=False).order_by('item_name')[:100]
        
        context = {
            'page_obj': page_obj,
            'transactions': page_obj,
            'stats': stats,
            'stores': stores,
            'items': items,
            'transaction_types': InventoryTransaction.TRANSACTION_TYPES,
            'store_filter': store_filter,
            'transaction_type_filter': transaction_type_filter,
            'item_filter': item_filter,
            'date_from': date_from,
            'date_to': date_to,
            'search_query': search_query,
        }
        
        return render(request, 'hospital/drug_accountability/inventory_history.html', context)
    except (ProgrammingError, OperationalError) as e:
        messages.error(request, 'Database tables not found. Please run migrations: python manage.py migrate hospital 1058_add_drug_accountability_system')
        return redirect('hospital:pharmacy_dashboard')


@login_required
def inventory_item_history(request, item_id):
    """History for a specific inventory item"""
    if not ACCOUNTABILITY_AVAILABLE:
        messages.warning(request, 'Drug accountability system is not available. Please run migrations first.')
        return redirect('hospital:pharmacy_dashboard')
    
    try:
        inventory_item = get_object_or_404(InventoryItem, id=item_id, is_deleted=False)
        
        transactions = InventoryTransaction.objects.filter(
            inventory_item=inventory_item,
            is_deleted=False
        ).select_related(
            'store', 'performed_by', 'approved_by'
        ).order_by('-transaction_date')
        
        # Date filters
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        
        if date_from:
            transactions = transactions.filter(transaction_date__gte=date_from)
        
        if date_to:
            transactions = transactions.filter(transaction_date__lte=date_to)
        
        # Pagination
        paginator = Paginator(transactions, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Calculate running balance
        current_balance = inventory_item.quantity_on_hand
        balance_history = []
        
        for txn in reversed(list(transactions)):
            if txn.transaction_type in ['receipt', 'transfer_in', 'return_from_dept', 'found']:
                current_balance -= abs(txn.quantity)
            elif txn.transaction_type in ['issue', 'transfer_out', 'disposal', 'damaged', 'expired', 'theft']:
                current_balance += abs(txn.quantity)
            elif txn.transaction_type == 'adjustment':
                current_balance -= txn.quantity
            
            balance_history.append({
                'transaction': txn,
                'balance_after': current_balance,
            })
        
        balance_history.reverse()
        
        context = {
            'inventory_item': inventory_item,
            'page_obj': page_obj,
            'transactions': page_obj,
            'balance_history': balance_history,
            'date_from': date_from,
            'date_to': date_to,
        }
        
        return render(request, 'hospital/drug_accountability/item_history.html', context)
    except (ProgrammingError, OperationalError) as e:
        messages.error(request, 'Database tables not found. Please run migrations: python manage.py migrate hospital 1058_add_drug_accountability_system')
        return redirect('hospital:pharmacy_dashboard')


@login_required
def drug_administration_history(request):
    """History of drug administrations with inventory tracking"""
    if not ACCOUNTABILITY_AVAILABLE:
        messages.warning(request, 'Drug accountability system is not available. Please run migrations first.')
        return redirect('hospital:pharmacy_dashboard')
    
    try:
        administrations = DrugAdministrationInventory.objects.filter(
            is_deleted=False
        ).select_related(
            'patient', 'drug', 'administered_by', 'inventory_item', 'store', 'inventory_transaction'
        ).order_by('-administered_at')
        
        # Filters
        patient_filter = request.GET.get('patient', '')
        if patient_filter:
            administrations = administrations.filter(patient_id=patient_filter)
        
        drug_filter = request.GET.get('drug', '')
        if drug_filter:
            administrations = administrations.filter(drug_id=drug_filter)
        
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        
        if date_from:
            administrations = administrations.filter(administered_at__gte=date_from)
        
        if date_to:
            administrations = administrations.filter(administered_at__lte=date_to)
        
        # Pagination
        paginator = Paginator(administrations, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Statistics
        stats = {
            'total_administrations': administrations.count(),
            'total_quantity': administrations.aggregate(Sum('quantity_administered'))['quantity_administered__sum'] or 0,
            'total_cost': administrations.aggregate(Sum('total_cost'))['total_cost__sum'] or Decimal('0.00'),
        }
        
        context = {
            'page_obj': page_obj,
            'administrations': page_obj,
            'stats': stats,
            'patient_filter': patient_filter,
            'drug_filter': drug_filter,
            'date_from': date_from,
            'date_to': date_to,
        }
        
        return render(request, 'hospital/drug_accountability/administration_history.html', context)
    except (ProgrammingError, OperationalError) as e:
        messages.error(request, 'Database tables not found. Please run migrations: python manage.py migrate hospital 1058_add_drug_accountability_system')
        return redirect('hospital:pharmacy_dashboard')


@login_required
def inventory_accountability_dashboard(request):
    """Dashboard for inventory accountability"""
    if not ACCOUNTABILITY_AVAILABLE:
        messages.warning(request, 'Drug accountability system is not available. Please run migrations first.')
        return redirect('hospital:pharmacy_dashboard')
    
    try:
        from datetime import datetime, timedelta
        
        # Date ranges
        today = date.today()
        last_7_days = today - timedelta(days=7)
        last_30_days = today - timedelta(days=30)
        
        # Recent transactions
        recent_transactions = InventoryTransaction.objects.filter(
            is_deleted=False
        ).select_related(
            'inventory_item', 'store', 'performed_by'
        ).order_by('-transaction_date')[:20]
        
        # Statistics
        stats = {
            'transactions_today': InventoryTransaction.objects.filter(
                transaction_date__date=today,
                is_deleted=False
            ).count(),
            'transactions_7_days': InventoryTransaction.objects.filter(
                transaction_date__gte=last_7_days,
                is_deleted=False
            ).count(),
            'transactions_30_days': InventoryTransaction.objects.filter(
                transaction_date__gte=last_30_days,
                is_deleted=False
            ).count(),
            'pending_returns': DrugReturn.objects.filter(
                status='pending',
                is_deleted=False
            ).count(),
            'total_items': InventoryItem.objects.filter(is_deleted=False).count(),
            'low_stock_items': InventoryItem.objects.filter(
                is_deleted=False
            ).annotate(
                needs_reorder=Q(quantity_on_hand__lte=F('reorder_level'))
            ).filter(needs_reorder=True).count(),
        }
        
        # Transaction types breakdown
        transaction_types = InventoryTransaction.objects.filter(
            transaction_date__gte=last_30_days,
            is_deleted=False
        ).values('transaction_type').annotate(
            count=Count('id')
        ).order_by('-count')
    except (ProgrammingError, OperationalError) as e:
        messages.error(request, 'Database tables not found. Please run migrations: python manage.py migrate hospital 1058_add_drug_accountability_system')
        return redirect('hospital:pharmacy_dashboard')
    
    context = {
        'stats': stats,
        'recent_transactions': recent_transactions,
        'transaction_types': transaction_types,
    }
    
    return render(request, 'hospital/drug_accountability/dashboard.html', context)

