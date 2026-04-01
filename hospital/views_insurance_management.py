"""
World-Class Insurance Company Management Views
Complete insurance company, plan, and enrollment management
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from decimal import Decimal
from datetime import date, datetime, timedelta

from .models import Patient
from .models_insurance_companies import InsuranceCompany, InsurancePlan, PatientInsurance


@login_required
def insurance_management_dashboard(request):
    """World-class insurance management dashboard"""
    # Statistics
    stats = {
        'total_companies': InsuranceCompany.objects.filter(is_deleted=False).count(),
        'active_companies': InsuranceCompany.objects.filter(is_active=True, status='active', is_deleted=False).count(),
        'total_plans': InsurancePlan.objects.filter(is_deleted=False).count(),
        'active_plans': InsurancePlan.objects.filter(is_active=True, is_deleted=False).count(),
        'enrolled_patients': PatientInsurance.objects.filter(status='active', is_deleted=False).count(),
        'expiring_soon': PatientInsurance.objects.filter(
            status='active',
            expiry_date__isnull=False,
            expiry_date__lte=timezone.now().date() + timedelta(days=30),
            expiry_date__gte=timezone.now().date(),
            is_deleted=False
        ).count(),
    }
    
    # Active insurance companies
    companies = InsuranceCompany.objects.filter(
        is_deleted=False
    ).annotate(
        enrolled_count=Count('patient_enrollments', filter=Q(
            patient_enrollments__status='active',
            patient_enrollments__is_deleted=False
        ))
    ).order_by('-enrolled_count', 'name')[:10]
    
    # Recent enrollments
    recent_enrollments = PatientInsurance.objects.filter(
        is_deleted=False
    ).select_related(
        'patient', 'insurance_company', 'insurance_plan'
    ).order_by('-created')[:10]
    
    # Expiring soon
    expiring_soon = PatientInsurance.objects.filter(
        status='active',
        expiry_date__isnull=False,
        expiry_date__lte=timezone.now().date() + timedelta(days=30),
        expiry_date__gte=timezone.now().date(),
        is_deleted=False
    ).select_related(
        'patient', 'insurance_company'
    ).order_by('expiry_date')[:10]
    
    context = {
        'title': 'Insurance Management Dashboard',
        'stats': stats,
        'companies': companies,
        'recent_enrollments': recent_enrollments,
        'expiring_soon': expiring_soon,
    }
    
    return render(request, 'hospital/insurance/management_dashboard.html', context)


@login_required
def insurance_company_list(request):
    """List all insurance companies"""
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    
    # Start with base query
    companies = InsuranceCompany.objects.filter(
        is_deleted=False
    )
    
    # Add annotations (using distinct to avoid duplicates from joins)
    companies = companies.annotate(
        plans_count=Count('plans', filter=Q(plans__is_deleted=False), distinct=True),
        enrolled_count=Count('patient_enrollments', filter=Q(
            patient_enrollments__status='active',
            patient_enrollments__is_deleted=False
        ), distinct=True)
    )
    
    if query:
        companies = companies.filter(
            Q(name__icontains=query) |
            Q(code__icontains=query) |
            Q(email__icontains=query)
        )
    
    if status_filter:
        companies = companies.filter(status=status_filter)
    
    # Order by newest first, then by name
    companies = companies.order_by('-created', 'name')
    
    # Debug: Log total count
    total_count = companies.count()
    
    paginator = Paginator(companies, 25)
    page = request.GET.get('page', 1)
    companies_page = paginator.get_page(page)
    
    context = {
        'title': 'Insurance Companies',
        'companies': companies_page,
        'query': query,
        'status_filter': status_filter,
        'total_count': total_count,  # Add for debugging
    }
    
    return render(request, 'hospital/insurance/company_list.html', context)


@login_required
def insurance_company_detail(request, pk):
    """View insurance company details"""
    company = get_object_or_404(InsuranceCompany, pk=pk, is_deleted=False)
    
    # Plans
    plans = company.plans.filter(is_deleted=False).annotate(
        enrolled_count=Count('patient_enrollments', filter=Q(
            patient_enrollments__status='active',
            patient_enrollments__is_deleted=False
        ))
    ).order_by('-is_active', 'plan_name')
    
    # Enrollments
    enrollments = PatientInsurance.objects.filter(
        insurance_company=company,
        is_deleted=False
    ).select_related('patient', 'insurance_plan').order_by('-created')[:20]
    
    # Statistics
    stats = {
        'total_plans': plans.count(),
        'active_plans': plans.filter(is_active=True).count(),
        'enrolled_patients': PatientInsurance.objects.filter(
            insurance_company=company,
            status='active',
            is_deleted=False
        ).count(),
        'total_enrollments': PatientInsurance.objects.filter(
            insurance_company=company,
            is_deleted=False
        ).count(),
    }
    
    context = {
        'title': f'{company.name} Details',
        'company': company,
        'plans': plans,
        'enrollments': enrollments,
        'stats': stats,
    }
    
    return render(request, 'hospital/insurance/company_detail.html', context)


@login_required
def insurance_company_create(request):
    """Create new insurance company"""
    if request.method == 'POST':
        # Get form data
        name = request.POST.get('name')
        code = request.POST.get('code')
        phone_number = request.POST.get('phone_number', '')
        email = request.POST.get('email', '')
        website = request.POST.get('website', '')
        address = request.POST.get('address', '')
        contract_number = request.POST.get('contract_number', '')
        payment_terms_days = request.POST.get('payment_terms_days', 30)
        billing_contact_name = request.POST.get('billing_contact_name', '')
        billing_contact_email = request.POST.get('billing_contact_email', '')
        notes = request.POST.get('notes', '')
        
        try:
            company = InsuranceCompany.objects.create(
                name=name,
                code=code.upper(),
                phone_number=phone_number,
                email=email,
                website=website,
                address=address,
                contract_number=contract_number,
                payment_terms_days=int(payment_terms_days),
                billing_contact_name=billing_contact_name,
                billing_contact_email=billing_contact_email,
                notes=notes,
                status='active',
                is_active=True,
            )
            
            # Also create a corresponding Payer for billing/claims
            from .models import Payer
            payer_type_input = request.POST.get('payer_type', 'private')  # Default to private insurance
            # Map to valid payer_type choices on Payer model
            if payer_type_input == 'nhis':
                payer_type = 'nhis'
            elif payer_type_input == 'corporate':
                payer_type = 'corporate'
            else:
                payer_type = 'private'
            payer, created = Payer.objects.get_or_create(
                name=name,
                payer_type=payer_type,
                defaults={'is_active': True, 'is_deleted': False}
            )
            
            # Ensure payer is active even if it already existed
            if not created:
                payer.is_active = True
                payer.is_deleted = False
                payer.save()
            
            if created:
                messages.success(request, f'Insurance company "{company.name}" and corresponding payer created successfully! The company is now available in all dropdowns.')
            else:
                messages.success(request, f'Insurance company "{company.name}" created successfully! (Updated existing payer)')
            
            # Redirect to list page with a flag to highlight the new company
            return redirect('hospital:insurance_company_list')
        
        except Exception as e:
            import traceback
            error_details = str(e)
            # Check for common errors
            if 'unique constraint' in error_details.lower() or 'duplicate' in error_details.lower():
                if 'code' in error_details.lower():
                    messages.error(request, f'❌ Error: Company code "{code.upper()}" already exists. Please use a different code.')
                elif 'name' in error_details.lower():
                    messages.error(request, f'❌ Error: Company name "{name}" already exists. Please use a different name.')
                else:
                    messages.error(request, f'❌ Error: A company with this information already exists. {error_details}')
            else:
                messages.error(request, f'❌ Error creating insurance company: {error_details}')
            
            # Log the full error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating insurance company: {error_details}\n{traceback.format_exc()}")
    
    context = {
        'title': 'Add New Insurance Company',
    }
    
    return render(request, 'hospital/insurance/company_form.html', context)


@login_required
def insurance_plan_create(request, company_pk):
    """Create new insurance plan"""
    company = get_object_or_404(InsuranceCompany, pk=company_pk, is_deleted=False)
    
    if request.method == 'POST':
        try:
            plan = InsurancePlan.objects.create(
                insurance_company=company,
                plan_name=request.POST.get('plan_name'),
                plan_code=request.POST.get('plan_code').upper(),
                plan_type=request.POST.get('plan_type', 'individual'),
                description=request.POST.get('description', ''),
                consultation_coverage=Decimal(request.POST.get('consultation_coverage', '100')),
                lab_coverage=Decimal(request.POST.get('lab_coverage', '100')),
                imaging_coverage=Decimal(request.POST.get('imaging_coverage', '100')),
                pharmacy_coverage=Decimal(request.POST.get('pharmacy_coverage', '80')),
                surgery_coverage=Decimal(request.POST.get('surgery_coverage', '90')),
                admission_coverage=Decimal(request.POST.get('admission_coverage', '100')),
                copay_amount=Decimal(request.POST.get('copay_amount', '0')),
                requires_pre_authorization=request.POST.get('requires_pre_authorization') == 'on',
                effective_date=request.POST.get('effective_date'),
                is_active=True,
            )
            
            # Optional annual limit
            annual_limit = request.POST.get('annual_limit', '')
            if annual_limit:
                plan.annual_limit = Decimal(annual_limit)
                plan.save(update_fields=['annual_limit'])
            
            messages.success(request, f'✅ Insurance plan "{plan.plan_name}" created successfully!')
            return redirect('hospital:insurance_company_detail', pk=company.pk)
        
        except Exception as e:
            messages.error(request, f'❌ Error creating insurance plan: {str(e)}')
    
    context = {
        'title': f'Add Plan for {company.name}',
        'company': company,
    }
    
    return render(request, 'hospital/insurance/plan_form.html', context)


@login_required
def patient_insurance_enroll(request, patient_pk):
    """Enroll patient in insurance"""
    patient = get_object_or_404(Patient, pk=patient_pk, is_deleted=False)
    
    if request.method == 'POST':
        try:
            company_id = request.POST.get('insurance_company')
            plan_id = request.POST.get('insurance_plan')
            
            company = get_object_or_404(InsuranceCompany, pk=company_id, is_deleted=False)
            plan = None
            if plan_id:
                plan = get_object_or_404(InsurancePlan, pk=plan_id, is_deleted=False)
            
            # Check for existing enrollment to prevent duplicates
            existing_enrollment = PatientInsurance.objects.filter(
                patient=patient,
                insurance_company=company,
                is_deleted=False
            ).first()
            
            if existing_enrollment:
                # Update existing enrollment instead of creating duplicate
                existing_enrollment.insurance_plan = plan
                existing_enrollment.policy_number = request.POST.get('policy_number')
                existing_enrollment.member_id = request.POST.get('member_id')
                existing_enrollment.group_number = request.POST.get('group_number', '')
                existing_enrollment.is_primary_subscriber = request.POST.get('is_primary_subscriber') == 'on'
                existing_enrollment.relationship_to_subscriber = request.POST.get('relationship_to_subscriber', 'self')
                existing_enrollment.effective_date = request.POST.get('effective_date')
                existing_enrollment.is_primary = request.POST.get('is_primary') == 'on'
                existing_enrollment.status = 'active'
                existing_enrollment.save()
                enrollment = existing_enrollment
            else:
                enrollment = PatientInsurance.objects.create(
                    patient=patient,
                    insurance_company=company,
                    insurance_plan=plan,
                    policy_number=request.POST.get('policy_number'),
                    member_id=request.POST.get('member_id'),
                    group_number=request.POST.get('group_number', ''),
                    is_primary_subscriber=request.POST.get('is_primary_subscriber') == 'on',
                    relationship_to_subscriber=request.POST.get('relationship_to_subscriber', 'self'),
                    effective_date=request.POST.get('effective_date'),
                    is_primary=request.POST.get('is_primary') == 'on',
                status='active',
            )
            
            # Optional expiry date
            expiry_date = request.POST.get('expiry_date', '')
            if expiry_date:
                enrollment.expiry_date = expiry_date
                enrollment.save(update_fields=['expiry_date'])
            
            # Update patient's primary insurance if this is marked as primary
            if enrollment.is_primary:
                from .models import Payer
                # Try to find or create a Payer for this insurance company
                payer, _ = Payer.objects.get_or_create(
                    name=company.name,
                    defaults={
                        'payer_type': 'private',
                        'is_active': True,
                    }
                )
                patient.primary_insurance = payer
                patient.insurance_company = company.name
                patient.insurance_member_id = enrollment.member_id
                patient.insurance_id = enrollment.policy_number
                patient.save(update_fields=['primary_insurance', 'insurance_company', 
                                          'insurance_member_id', 'insurance_id'])
            
            messages.success(request, f'✅ Patient enrolled in {company.name} successfully!')
            return redirect('hospital:patient_detail', pk=patient.pk)
        
        except Exception as e:
            messages.error(request, f'❌ Error enrolling patient: {str(e)}')
    
    companies = InsuranceCompany.objects.filter(is_active=True, is_deleted=False).order_by('name')
    
    context = {
        'title': f'Enroll {patient.full_name} in Insurance',
        'patient': patient,
        'companies': companies,
    }
    
    return render(request, 'hospital/insurance/patient_enrollment_form.html', context)


@login_required
def get_insurance_plans_api(request, company_pk):
    """API endpoint to get insurance plans for a company"""
    plans = InsurancePlan.objects.filter(
        insurance_company_id=company_pk,
        is_active=True,
        is_deleted=False
    ).values('id', 'plan_name', 'plan_code', 'plan_type', 'copay_amount')
    
    return JsonResponse({'plans': list(plans)})


@login_required
def verify_patient_insurance_api(request, patient_pk):
    """API endpoint to verify patient insurance"""
    try:
        patient = get_object_or_404(Patient, pk=patient_pk, is_deleted=False)
        
        # Get active insurance
        active_insurance = PatientInsurance.objects.filter(
            patient=patient,
            status='active',
            is_deleted=False
        ).select_related('insurance_company', 'insurance_plan').first()
        
        if not active_insurance:
            return JsonResponse({
                'has_insurance': False,
                'message': 'No active insurance found for this patient'
            })
        
        # Verify coverage
        verification = active_insurance.verify_coverage()
        
        response_data = {
            'has_insurance': True,
            'is_valid': verification['is_valid'],
            'errors': verification['errors'],
            'insurance_company': active_insurance.insurance_company.name,
            'insurance_company_code': active_insurance.insurance_company.code,
            'member_id': active_insurance.member_id,
            'policy_number': active_insurance.policy_number,
            'expiry_date': active_insurance.expiry_date.isoformat() if active_insurance.expiry_date else None,
        }
        
        if active_insurance.insurance_plan:
            response_data['plan_name'] = active_insurance.insurance_plan.plan_name
            response_data['copay_amount'] = str(active_insurance.insurance_plan.copay_amount)
            response_data['remaining_limit'] = str(active_insurance.remaining_annual_limit) if active_insurance.remaining_annual_limit is not None else 'Unlimited'
        
        return JsonResponse(response_data)
    
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'has_insurance': False
        }, status=400)


@login_required
def calculate_insurance_coverage_api(request):
    """API endpoint to calculate insurance coverage for a service"""
    try:
        patient_insurance_id = request.GET.get('patient_insurance_id')
        service_type = request.GET.get('service_type')
        amount = Decimal(request.GET.get('amount', '0'))
        
        patient_insurance = get_object_or_404(PatientInsurance, pk=patient_insurance_id, is_deleted=False)
        
        if not patient_insurance.insurance_plan:
            return JsonResponse({
                'error': 'No insurance plan assigned',
            }, status=400)
        
        insurance_pays, patient_pays = patient_insurance.insurance_plan.calculate_coverage(amount, service_type)
        coverage_pct = patient_insurance.insurance_plan.get_coverage_percentage(service_type)
        
        return JsonResponse({
            'total_amount': str(amount),
            'coverage_percentage': str(coverage_pct),
            'insurance_pays': str(insurance_pays),
            'patient_pays': str(patient_pays),
            'copay': str(patient_insurance.insurance_plan.copay_amount),
        })
    
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=400)























