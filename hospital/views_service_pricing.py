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
from .utils_roles import get_user_role
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
    """Strict admin check (no is_staff fallback)."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return get_user_role(user) == 'admin'


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
    """Manage lab test prices - Catalog with add/delete functionality"""
    from django.core.paginator import Paginator
    from decimal import Decimal
    
    # Handle POST actions: add, delete, update prices
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_lab_item':
            # Add new lab test
            try:
                code = request.POST.get('code', '').strip()
                name = request.POST.get('name', '').strip()
                specimen_type = request.POST.get('specimen_type', '').strip()
                tat_minutes = int(request.POST.get('tat_minutes', 60) or 60)
                price = Decimal(request.POST.get('price', '0') or '0')
                
                if not code or not name:
                    messages.error(request, 'Code and name are required.')
                else:
                    # Check if code already exists
                    if LabTest.objects.filter(code=code, is_deleted=False).exists():
                        messages.error(request, f'Lab test with code "{code}" already exists.')
                    else:
                        lab_test = LabTest.objects.create(
                            code=code,
                            name=name,
                            specimen_type=specimen_type,
                            tat_minutes=tat_minutes,
                            price=price,
                            is_active=True
                        )
                        messages.success(request, f'Lab test "{lab_test.name}" added successfully.')
            except Exception as e:
                messages.error(request, f'Error adding lab test: {str(e)}')
            return redirect('hospital:lab_pricing_list')
        
        elif action == 'delete_lab_item':
            # Delete lab test (soft delete)
            try:
                lab_id = request.POST.get('lab_id')
                if lab_id:
                    lab = LabTest.objects.filter(pk=lab_id, is_deleted=False).first()
                    if lab:
                        lab.is_deleted = True
                        lab.save()
                        messages.success(request, f'Lab test "{lab.name}" deleted successfully.')
                    else:
                        messages.error(request, 'Lab test not found.')
            except Exception as e:
                messages.error(request, f'Error deleting lab test: {str(e)}')
            return redirect('hospital:lab_pricing_list')
        
        elif action == 'update_prices':
            # Update prices (and optionally TAT) for an existing lab test
            lab_id = request.POST.get('lab_id')

            def _decimal(val, default=None):
                try:
                    s = (val or '').strip()
                    if s == '':
                        return None
                    v = Decimal(s)
                    return v if v >= 0 else (default or Decimal('0.00'))
                except Exception:
                    return default or Decimal('0.00')

            def _int(val, default=None):
                try:
                    s = (val or '').strip()
                    if s == '':
                        return None
                    v = int(float(s))
                    return v if v >= 0 else default
                except Exception:
                    return default

            price_val = _decimal(request.POST.get('price'), Decimal('0.00')) or Decimal('0.00')
            tat_val = _int(request.POST.get('tat_minutes'), None)

            if lab_id:
                lab = LabTest.objects.filter(pk=lab_id, is_deleted=False).first()
                if lab:
                    fields_to_update = []
                    if lab.price != price_val:
                        lab.price = price_val
                        fields_to_update.append('price')
                    # Only update TAT when a value is explicitly provided in the form;
                    # leave existing value untouched when field is left blank.
                    if tat_val is not None:
                        current_tat = lab.tat_minutes
                        if current_tat is None or int(current_tat) != int(tat_val):
                            lab.tat_minutes = tat_val
                            fields_to_update.append('tat_minutes')

                    if fields_to_update:
                        fields_to_update.append('modified')
                        lab.save(update_fields=fields_to_update)
                        messages.success(
                            request,
                            f'Updated {lab.name}: '
                            f'price {"& TAT " if "tat_minutes" in fields_to_update and "price" in fields_to_update else ""}'
                            f'{"price" if "price" in fields_to_update and "tat_minutes" not in fields_to_update else ""}'
                            f'{"TAT" if "tat_minutes" in fields_to_update and "price" not in fields_to_update else ""}.'
                        )
                    else:
                        messages.info(request, f'No changes detected for {lab.name}.')

            return redirect('hospital:lab_pricing_list')
    
    # GET request - list lab tests
    search = request.GET.get('search', '').strip()
    
    labs = LabTest.objects.filter(is_deleted=False)
    
    if search:
        labs = labs.filter(
            Q(code__icontains=search) |
            Q(name__icontains=search) |
            Q(specimen_type__icontains=search)
        )
    
    labs = labs.order_by('name')
    
    # Pagination
    paginator = Paginator(labs, 25)
    page = request.GET.get('page', 1)
    labs_page = paginator.get_page(page)
    
    context = {
        'title': 'Lab Test Catalog & Prices',
        'labs': labs_page,
        'labs_page': labs_page,  # For pagination
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

























