"""
Contract and Certificate Management Views
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse
from datetime import timedelta

from .models_contracts import Contract, Certificate, ContractCategory, ContractRenewal


@login_required
def contracts_dashboard(request):
    """Contracts and Certificates Dashboard with expiry alerts"""
    today = timezone.now().date()
    
    # Contract Statistics
    contract_stats = {
        'total_contracts': Contract.objects.filter(is_deleted=False).count(),
        'active_contracts': Contract.objects.filter(status='active', is_deleted=False).count(),
        'expiring_soon': Contract.objects.filter(
            status='expiring_soon',
            is_deleted=False
        ).count(),
        'expired': Contract.objects.filter(status='expired', is_deleted=False).count(),
    }
    
    # Certificate Statistics
    certificate_stats = {
        'total_certificates': Certificate.objects.filter(is_deleted=False).count(),
        'valid_certificates': Certificate.objects.filter(status='valid', is_deleted=False).count(),
        'expiring_soon': Certificate.objects.filter(
            status='expiring_soon',
            is_deleted=False
        ).count(),
        'expired': Certificate.objects.filter(status='expired', is_deleted=False).count(),
    }
    
    # Contracts expiring in next 30 days
    contracts_expiring = Contract.objects.filter(
        end_date__gte=today,
        end_date__lte=today + timedelta(days=30),
        is_deleted=False
    ).select_related('category').order_by('end_date')[:10]
    
    # Certificates expiring in next 60 days
    certificates_expiring = Certificate.objects.filter(
        expiry_date__gte=today,
        expiry_date__lte=today + timedelta(days=60),
        is_deleted=False
    ).order_by('expiry_date')[:10]
    
    # Recently added
    recent_contracts = Contract.objects.filter(
        is_deleted=False
    ).select_related('category').order_by('-created')[:5]
    
    context = {
        'title': 'Contracts & Certificates Management',
        'contract_stats': contract_stats,
        'certificate_stats': certificate_stats,
        'contracts_expiring': contracts_expiring,
        'certificates_expiring': certificates_expiring,
        'recent_contracts': recent_contracts,
        'today': today,
    }
    
    return render(request, 'hospital/contracts/dashboard.html', context)


@login_required
def contract_create(request):
    """Create new contract"""
    if request.method == 'POST':
        try:
            contract = Contract.objects.create(
                contract_number=request.POST.get('contract_number'),
                contract_name=request.POST.get('contract_name'),
                category_id=request.POST.get('category'),
                company_name=request.POST.get('company_name'),
                company_contact_person=request.POST.get('company_contact_person', ''),
                company_phone=request.POST.get('company_phone', ''),
                company_email=request.POST.get('company_email', ''),
                description=request.POST.get('description'),
                start_date=request.POST.get('start_date'),
                end_date=request.POST.get('end_date'),
                value_amount=request.POST.get('value_amount') or None,
                payment_terms=request.POST.get('payment_terms', ''),
                alert_days_before=int(request.POST.get('alert_days_before', 30)),
                auto_renew=request.POST.get('auto_renew') == 'on',
                responsible_person_id=request.POST.get('responsible_person') or None,
                notes=request.POST.get('notes', ''),
                status='active',
                created_by=request.user,
            )
            
            # Handle file upload
            if 'contract_document' in request.FILES:
                contract.contract_document = request.FILES['contract_document']
                contract.save(update_fields=['contract_document'])
            
            messages.success(request, f'✅ Contract "{contract.contract_name}" created successfully!')
            return redirect('hospital:contract_detail', pk=contract.pk)
        
        except Exception as e:
            messages.error(request, f'❌ Error creating contract: {str(e)}')
    
    categories = ContractCategory.objects.filter(is_deleted=False).order_by('name')
    
    from django.contrib.auth.models import User
    users = User.objects.filter(is_active=True).order_by('last_name', 'first_name')
    
    context = {
        'title': 'Create Contract',
        'categories': categories,
        'users': users,
    }
    
    return render(request, 'hospital/contracts/contract_form.html', context)


@login_required
def contract_list(request):
    """List all contracts with filtering"""
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')
    
    contracts = Contract.objects.filter(
        is_deleted=False
    ).select_related('category', 'responsible_person')
    
    if query:
        contracts = contracts.filter(
            Q(contract_name__icontains=query) |
            Q(contract_number__icontains=query) |
            Q(company_name__icontains=query)
        )
    
    if status_filter:
        contracts = contracts.filter(status=status_filter)
    
    if category_filter:
        contracts = contracts.filter(category_id=category_filter)
    
    contracts = contracts.order_by('-end_date')
    
    categories = ContractCategory.objects.filter(is_deleted=False)
    
    paginator = Paginator(contracts, 25)
    page = request.GET.get('page')
    contracts_page = paginator.get_page(page)
    
    context = {
        'title': 'All Contracts',
        'contracts': contracts_page,
        'categories': categories,
        'query': query,
        'status_filter': status_filter,
        'category_filter': category_filter,
    }
    
    return render(request, 'hospital/contracts/contract_list.html', context)


@login_required
def contract_detail(request, pk):
    """View contract details"""
    contract = get_object_or_404(Contract, pk=pk, is_deleted=False)
    
    # Update status
    contract.update_status()
    
    # Get renewal history
    renewals = contract.renewals.all().order_by('-renewal_date')
    
    # Get related certificates
    related_certificates = contract.certificates.filter(is_deleted=False)
    
    context = {
        'title': f'Contract: {contract.contract_name}',
        'contract': contract,
        'renewals': renewals,
        'related_certificates': related_certificates,
    }
    
    return render(request, 'hospital/contracts/contract_detail.html', context)


@login_required
def certificate_create(request):
    """Create new certificate"""
    if request.method == 'POST':
        try:
            certificate = Certificate.objects.create(
                certificate_number=request.POST.get('certificate_number'),
                certificate_name=request.POST.get('certificate_name'),
                certificate_type=request.POST.get('certificate_type'),
                issuing_authority=request.POST.get('issuing_authority'),
                description=request.POST.get('description'),
                issue_date=request.POST.get('issue_date'),
                expiry_date=request.POST.get('expiry_date'),
                alert_days_before=int(request.POST.get('alert_days_before', 60)),
                responsible_person_id=request.POST.get('responsible_person') or None,
                notes=request.POST.get('notes', ''),
                status='valid',
                created_by=request.user,
            )
            
            # Handle file upload
            if 'certificate_document' in request.FILES:
                certificate.certificate_document = request.FILES['certificate_document']
                certificate.save(update_fields=['certificate_document'])
            
            messages.success(request, f'✅ Certificate "{certificate.certificate_name}" added successfully!')
            return redirect('hospital:certificate_detail', pk=certificate.pk)
        
        except Exception as e:
            messages.error(request, f'❌ Error creating certificate: {str(e)}')
    
    from django.contrib.auth.models import User
    users = User.objects.filter(is_active=True).order_by('last_name', 'first_name')
    
    context = {
        'title': 'Add Certificate',
        'users': users,
    }
    
    return render(request, 'hospital/contracts/certificate_form.html', context)


@login_required
def certificate_list(request):
    """List all certificates"""
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')
    
    certificates = Certificate.objects.filter(
        is_deleted=False
    )
    
    if query:
        certificates = certificates.filter(
            Q(certificate_name__icontains=query) |
            Q(certificate_number__icontains=query) |
            Q(issuing_authority__icontains=query)
        )
    
    if status_filter:
        certificates = certificates.filter(status=status_filter)
    
    if type_filter:
        certificates = certificates.filter(certificate_type=type_filter)
    
    certificates = certificates.order_by('expiry_date')
    
    paginator = Paginator(certificates, 25)
    page = request.GET.get('page')
    certificates_page = paginator.get_page(page)
    
    context = {
        'title': 'All Certificates',
        'certificates': certificates_page,
        'query': query,
        'status_filter': status_filter,
        'type_filter': type_filter,
    }
    
    return render(request, 'hospital/contracts/certificate_list.html', context)


@login_required
def certificate_detail(request, pk):
    """View certificate details"""
    certificate = get_object_or_404(Certificate, pk=pk, is_deleted=False)
    
    # Update status
    certificate.update_status()
    
    context = {
        'title': f'Certificate: {certificate.certificate_name}',
        'certificate': certificate,
    }
    
    return render(request, 'hospital/contracts/certificate_detail.html', context)


@login_required
def get_expiring_items_api(request):
    """API endpoint to get expiring contracts and certificates"""
    today = timezone.now().date()
    days = int(request.GET.get('days', 30))
    
    # Expiring contracts
    contracts = Contract.objects.filter(
        end_date__gte=today,
        end_date__lte=today + timedelta(days=days),
        is_deleted=False
    ).values('id', 'contract_name', 'company_name', 'end_date', 'days_until_expiry')
    
    # Expiring certificates
    certificates = Certificate.objects.filter(
        expiry_date__gte=today,
        expiry_date__lte=today + timedelta(days=days),
        is_deleted=False
    ).values('id', 'certificate_name', 'issuing_authority', 'expiry_date', 'days_until_expiry')
    
    return JsonResponse({
        'contracts': list(contracts),
        'certificates': list(certificates),
        'alert_period_days': days
    })























