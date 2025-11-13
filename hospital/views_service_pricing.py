"""
💰 SERVICE PRICING MANAGEMENT VIEWS
Manage prices for all hospital services
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from decimal import Decimal
import logging

from .models import LabTest, Drug, Department
from .models_service_pricing import (
    ServicePriceList,
    ConsultationPrice,
    ImagingPrice,
    ProcedurePrice,
    BedPrice,
    ServicePackage,
    get_service_price
)

logger = logging.getLogger(__name__)


def is_admin(user):
    """Check if user is admin"""
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_admin)
def pricing_dashboard(request):
    """
    Main pricing dashboard
    Overview of all service prices
    """
    # Lab tests without prices
    labs_no_price = LabTest.objects.filter(
        is_deleted=False,
        price=0
    ).count()
    
    # Drugs without prices
    drugs_no_price = Drug.objects.filter(
        is_deleted=False
    ).exclude(
        unit_price__gt=0
    ).count()
    
    # Price lists
    price_lists = ServicePriceList.objects.filter(
        is_deleted=False,
        is_active=True
    ).order_by('-created')[:5]
    
    # Recent lab tests
    recent_labs = LabTest.objects.filter(
        is_deleted=False
    ).order_by('-modified')[:10]
    
    # Recent drugs
    recent_drugs = Drug.objects.filter(
        is_deleted=False
    ).order_by('-modified')[:10]
    
    stats = {
        'total_labs': LabTest.objects.filter(is_deleted=False).count(),
        'labs_with_price': LabTest.objects.filter(is_deleted=False, price__gt=0).count(),
        'labs_no_price': labs_no_price,
        'total_drugs': Drug.objects.filter(is_deleted=False).count(),
        'drugs_with_price': Drug.objects.filter(is_deleted=False).exclude(unit_price=0).count(),
        'drugs_no_price': drugs_no_price,
        'active_price_lists': price_lists.count(),
    }
    
    context = {
        'title': '💰 Service Pricing Management',
        'stats': stats,
        'price_lists': price_lists,
        'recent_labs': recent_labs,
        'recent_drugs': recent_drugs,
    }
    return render(request, 'hospital/pricing_dashboard.html', context)


@login_required
@user_passes_test(is_admin)
def lab_pricing_list(request):
    """Manage lab test prices"""
    search = request.GET.get('search', '')
    
    labs = LabTest.objects.filter(is_deleted=False)
    
    if search:
        labs = labs.filter(
            Q(code__icontains=search) |
            Q(name__icontains=search)
        )
    
    labs = labs.order_by('name')
    
    context = {
        'title': 'Lab Test Pricing',
        'labs': labs,
        'search': search,
    }
    return render(request, 'hospital/lab_pricing_list.html', context)


@login_required
@user_passes_test(is_admin)
def lab_pricing_update(request, lab_id):
    """Update lab test price"""
    lab = get_object_or_404(LabTest, id=lab_id, is_deleted=False)
    
    if request.method == 'POST':
        price = request.POST.get('price')
        try:
            lab.price = Decimal(price)
            lab.save()
            messages.success(request, f'✅ Price updated for {lab.name}: GHS {lab.price}')
            return redirect('hospital:lab_pricing_list')
        except Exception as e:
            messages.error(request, f'❌ Error updating price: {str(e)}')
    
    context = {
        'title': f'Update Price - {lab.name}',
        'lab': lab,
    }
    return render(request, 'hospital/lab_pricing_update.html', context)


@login_required
@user_passes_test(is_admin)
def drug_pricing_list(request):
    """Manage drug prices"""
    search = request.GET.get('search', '')
    
    drugs = Drug.objects.filter(is_deleted=False)
    
    if search:
        drugs = drugs.filter(
            Q(name__icontains=search) |
            Q(generic_name__icontains=search)
        )
    
    drugs = drugs.order_by('name')
    
    context = {
        'title': 'Drug Pricing',
        'drugs': drugs,
        'search': search,
    }
    return render(request, 'hospital/drug_pricing_list.html', context)


@login_required
@user_passes_test(is_admin)
def drug_pricing_update(request, drug_id):
    """Update drug price"""
    drug = get_object_or_404(Drug, id=drug_id, is_deleted=False)
    
    if request.method == 'POST':
        unit_price = request.POST.get('unit_price')
        cost_price = request.POST.get('cost_price', '0.00')
        
        try:
            drug.unit_price = Decimal(unit_price)
            drug.cost_price = Decimal(cost_price)
            drug.save()
            messages.success(request, f'✅ Price updated for {drug.name}: GHS {drug.unit_price}')
            return redirect('hospital:drug_pricing_list')
        except Exception as e:
            messages.error(request, f'❌ Error updating price: {str(e)}')
    
    context = {
        'title': f'Update Price - {drug.name}',
        'drug': drug,
    }
    return render(request, 'hospital/drug_pricing_update.html', context)


@login_required
@user_passes_test(is_admin)
def bulk_price_update(request):
    """Bulk update prices"""
    if request.method == 'POST':
        service_type = request.POST.get('service_type')
        percentage = request.POST.get('percentage')
        action = request.POST.get('action')  # 'increase' or 'decrease'
        
        try:
            percentage = Decimal(percentage)
            
            if service_type == 'lab':
                labs = LabTest.objects.filter(is_deleted=False, price__gt=0)
                for lab in labs:
                    if action == 'increase':
                        lab.price = lab.price * (1 + percentage / 100)
                    else:
                        lab.price = lab.price * (1 - percentage / 100)
                    lab.save()
                messages.success(request, f'✅ Updated {labs.count()} lab test prices')
                
            elif service_type == 'drug':
                drugs = Drug.objects.filter(is_deleted=False).exclude(unit_price=0)
                for drug in drugs:
                    if action == 'increase':
                        drug.unit_price = drug.unit_price * (1 + percentage / 100)
                    else:
                        drug.unit_price = drug.unit_price * (1 - percentage / 100)
                    drug.save()
                messages.success(request, f'✅ Updated {drugs.count()} drug prices')
            
            return redirect('hospital:pricing_dashboard')
            
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
    
    context = {
        'title': 'Bulk Price Update',
    }
    return render(request, 'hospital/bulk_price_update.html', context)


@login_required
def get_service_price_api(request, service_type, service_id):
    """
    API endpoint to get service price
    Used by billing system
    """
    payer_type = request.GET.get('payer_type', 'cash')
    
    try:
        price = get_service_price(service_type, service_id, payer_type)
        
        return JsonResponse({
            'success': True,
            'price': str(price),
            'service_type': service_type,
            'payer_type': payer_type
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)













