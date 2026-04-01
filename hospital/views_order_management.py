"""
Enhanced Order Management with proper separation of Lab, Imaging, and Medication orders
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse

from .models import Order, LabTest, LabResult, Drug, Prescription, Encounter, Staff
from .models_lab_management import LabReagent
from .models_advanced import ImagingStudy
from .decorators import role_required


@login_required
@role_required('doctor', 'admin', message='Access denied. Only doctors can create orders.')
def create_order(request, encounter_id):
    """Create order with proper type separation"""
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    doctor = request.user.staff_profile if hasattr(request.user, 'staff_profile') else None
    
    if not doctor:
        messages.error(request, 'Staff profile not found.')
        return redirect('hospital:encounter_detail', pk=encounter_id)
    
    if request.method == 'POST':
        order_type = request.POST.get('order_type')
        priority = request.POST.get('priority', 'routine')
        notes = request.POST.get('notes', '')
        
        try:
            if order_type == 'lab':
                # Create LAB order
                test_ids = request.POST.getlist('test_ids')
                if not test_ids:
                    messages.error(request, 'Please select at least one lab test.')
                    return redirect('hospital:create_order', encounter_id=encounter_id)
                
                # Create lab order
                lab_order = Order.objects.create(
                    encounter=encounter,
                    order_type='lab',  # Explicitly set to 'lab'
                    status='pending',
                    priority=priority,
                    notes=notes,
                    requested_by=doctor
                )
                
                # Create lab results for each test
                tests = LabTest.objects.filter(pk__in=test_ids, is_active=True)
                for test in tests:
                    # Check for duplicate before creating
                    existing_result = LabResult.objects.filter(
                        order=lab_order,
                        test=test,
                        is_deleted=False
                    ).first()
                    
                    if not existing_result:
                        LabResult.objects.create(
                            order=lab_order,
                            test=test,
                            status='pending'
                        )
                    
                    # Check reagent availability for this test
                    required_reagents = test.required_reagents.filter(is_deleted=False)
                    unavailable_reagents = [r for r in required_reagents if r.is_low_stock or r.is_expired]
                    if unavailable_reagents:
                        messages.warning(
                            request, 
                            f'Test {test.name} requires reagents that are low stock or expired: {", ".join([r.name for r in unavailable_reagents])}'
                        )
                
                messages.success(request, f'Lab order created with {tests.count()} test(s).')
                return redirect('hospital:encounter_detail', pk=encounter_id)
            
            elif order_type == 'imaging':
                # Create IMAGING order
                imaging_type = request.POST.get('imaging_type', 'X-ray')
                body_part = request.POST.get('body_part', '')
                
                imaging_order = Order.objects.create(
                    encounter=encounter,
                    order_type='imaging',  # Explicitly set to 'imaging'
                    status='pending',
                    priority=priority,
                    notes=notes,
                    requested_by=doctor
                )
                
                # Check for duplicate imaging study before creating
                existing_study = ImagingStudy.objects.filter(
                    order=imaging_order,
                    modality=imaging_type,
                    body_part=body_part,
                    is_deleted=False
                ).first()
                
                if not existing_study:
                    # Create imaging study
                    ImagingStudy.objects.create(
                        order=imaging_order,
                        modality=imaging_type,
                        body_part=body_part,
                        status='pending',
                        requested_by=doctor
                    )
                else:
                    messages.info(request, 'Imaging study already exists for this order.')
                
                messages.success(request, 'Imaging order created successfully.')
                return redirect('hospital:encounter_detail', pk=encounter_id)
            
            elif order_type == 'medication':
                # Create MEDICATION order (prescription)
                drug_ids = request.POST.getlist('drug_ids')
                if not drug_ids:
                    messages.error(request, 'Please select at least one medication.')
                    return redirect('hospital:create_order', encounter_id=encounter_id)
                
                # Create medication order
                med_order = Order.objects.create(
                    encounter=encounter,
                    order_type='medication',  # Explicitly set to 'medication'
                    status='pending',
                    priority=priority,
                    notes=notes,
                    requested_by=doctor
                )
                
                # Create prescriptions for each drug
                drugs = Drug.objects.filter(pk__in=drug_ids, is_deleted=False)
                for drug in drugs:
                    quantity = int(request.POST.get(f'quantity_{drug.pk}', 1))
                    dosage = request.POST.get(f'dosage_{drug.pk}', '')
                    frequency = request.POST.get(f'frequency_{drug.pk}', '')
                    duration = request.POST.get(f'duration_{drug.pk}', '')
                    
                    Prescription.objects.create(
                        order=med_order,
                        drug=drug,
                        quantity=quantity,
                        dosage_instructions=dosage,
                        frequency=frequency,
                        duration_days=int(duration) if duration else None,
                        prescribed_by=doctor
                    )
                
                messages.success(request, f'Medication order created with {drugs.count()} prescription(s).')
                return redirect('hospital:encounter_detail', pk=encounter_id)
            
            else:
                messages.error(request, 'Invalid order type.')
                
        except Exception as e:
            messages.error(request, f'Error creating order: {str(e)}')
    
    # GET request - show order form
    lab_tests = LabTest.objects.filter(is_active=True, is_deleted=False).order_by('name')
    drugs = Drug.objects.filter(is_deleted=False).order_by('name')
    
    # Get reagent availability for lab tests
    test_reagent_info = {}
    for test in lab_tests:
        required_reagents = test.required_reagents.filter(is_deleted=False)
        test_reagent_info[test.id] = {
            'reagents': required_reagents,
            'all_available': all(not (r.is_low_stock or r.is_expired) for r in required_reagents),
        }
    
    context = {
        'encounter': encounter,
        'lab_tests': lab_tests,
        'drugs': drugs,
        'test_reagent_info': test_reagent_info,
    }
    return render(request, 'hospital/create_order_enhanced.html', context)


@login_required
def order_detail(request, order_id):
    """View order details with proper type handling"""
    order = get_object_or_404(Order, pk=order_id, is_deleted=False)
    
    context = {
        'order': order,
    }
    
    # Add type-specific data
    if order.order_type == 'lab':
        context['lab_results'] = order.lab_results.filter(is_deleted=False)
        # Get reagent requirements for all tests in this order
        tests = [lr.test for lr in context['lab_results']]
        reagent_requirements = {}
        for test in tests:
            reagents = test.required_reagents.filter(is_deleted=False)
            reagent_requirements[test.id] = reagents
        context['reagent_requirements'] = reagent_requirements
    
    elif order.order_type == 'imaging':
        try:
            context['imaging_study'] = order.imaging_studies.filter(is_deleted=False).first()
        except:
            context['imaging_study'] = None
    
    elif order.order_type == 'medication':
        context['prescriptions'] = order.prescriptions.filter(is_deleted=False)
    
    return render(request, 'hospital/order_detail.html', context)










