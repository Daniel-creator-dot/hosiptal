"""
Pharmacy Inventory Tally Sheet
Physical stock counting and reconciliation
Admin only - only admins can change/update stock levels
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Sum, F
from django.db import transaction
from decimal import Decimal
import json
import logging

from .models import PharmacyStock, Drug
from .models_procurement import Store, InventoryItem
from .views_procurement import is_admin_user, is_procurement_staff

logger = logging.getLogger(__name__)


def can_manage_pharmacy_tally(user):
    """Allow admin and procurement/stores staff to manage pharmacy tally."""
    if not user or not user.is_authenticated:
        return False
    return is_admin_user(user) or is_procurement_staff(user)


@login_required
@user_passes_test(can_manage_pharmacy_tally, login_url='/admin/login/')
def pharmacy_inventory_tally(request):
    """
    Pharmacy inventory tally sheet for physical stock counting
    """
    if request.method == 'POST':
        # Handle tally submission
        tally_data = request.POST.get('tally_data', '[]')
        location = request.POST.get('location', 'Main Pharmacy')
        
        try:
            tally_items = json.loads(tally_data)
        except json.JSONDecodeError:
            messages.error(request, 'Invalid tally data format.')
            return redirect('hospital:pharmacy_inventory_tally')
        
        updated_count = 0
        created_count = 0
        errors = []
        
        with transaction.atomic():
            for item in tally_items:
                drug_id = item.get('drug_id')
                batch_number = item.get('batch_number', '')
                expiry_date = item.get('expiry_date')
                counted_quantity = int(item.get('counted_quantity', 0))
                system_quantity = int(item.get('system_quantity', 0))
                notes = item.get('notes', '')
                
                if not drug_id or counted_quantity < 0:
                    continue
                
                try:
                    drug = Drug.objects.get(id=drug_id, is_deleted=False)
                    
                    # Find or create stock record
                    stock = PharmacyStock.objects.filter(
                        drug=drug,
                        batch_number=batch_number,
                        location=location,
                        is_deleted=False
                    ).first()
                    
                    if stock:
                        # Update existing stock
                        variance = counted_quantity - stock.quantity_on_hand
                        stock.quantity_on_hand = counted_quantity
                        if expiry_date:
                            stock.expiry_date = expiry_date
                        stock.save()
                        updated_count += 1
                    else:
                        # Create new stock record
                        if expiry_date:
                            from datetime import datetime
                            if isinstance(expiry_date, str):
                                expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                        
                        stock = PharmacyStock.objects.create(
                            drug=drug,
                            batch_number=batch_number or f'BATCH-{timezone.now().strftime("%Y%m%d")}',
                            expiry_date=expiry_date or timezone.now().date(),
                            location=location,
                            quantity_on_hand=counted_quantity,
                            unit_cost=Decimal('0.00'),
                            created_by=request.user,
                        )
                        created_count += 1
                    
                    # Log variance if significant
                    if abs(variance) > 0:
                        logger.info(
                            f"Tally variance for {drug.name}: System={system_quantity}, "
                            f"Counted={counted_quantity}, Variance={variance}"
                        )
                
                except Drug.DoesNotExist:
                    errors.append(f'Drug {drug_id} not found.')
                except Exception as e:
                    errors.append(f'Error updating {drug_id}: {str(e)}')
        
        if updated_count > 0 or created_count > 0:
            messages.success(
                request,
                f'Tally completed: {updated_count} updated, {created_count} created.'
            )
        if errors:
            for error in errors[:5]:
                messages.warning(request, error)
        
        return redirect('hospital:pharmacy_inventory_tally')
    
    # GET request - show tally sheet
    location = request.GET.get('location', 'Main Pharmacy')
    search_query = request.GET.get('search', '')
    
    # Get all pharmacy stock items
    stock_qs = PharmacyStock.objects.filter(
        location=location,
        is_deleted=False
    ).select_related('drug').order_by('drug__name', 'batch_number')
    
    # Apply search filter
    if search_query:
        stock_qs = stock_qs.filter(
            Q(drug__name__icontains=search_query) |
            Q(batch_number__icontains=search_query)
        )
    
    # Get all drugs for adding new items
    drugs = Drug.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by('name')
    
    # Calculate statistics
    total_items = stock_qs.count()
    total_quantity = stock_qs.aggregate(
        total=Sum('quantity_on_hand')
    )['total'] or 0
    total_value = stock_qs.aggregate(
        total=Sum(F('quantity_on_hand') * F('unit_cost'))
    )['total'] or Decimal('0.00')
    
    # Get locations
    locations = PharmacyStock.objects.filter(
        is_deleted=False
    ).values_list('location', flat=True).distinct()
    
    context = {
        'title': 'Pharmacy Inventory Tally Sheet',
        'stock_items': stock_qs,
        'drugs': drugs,
        'location': location,
        'locations': locations,
        'search_query': search_query,
        'total_items': total_items,
        'total_quantity': total_quantity,
        'total_value': total_value,
    }
    
    return render(request, 'hospital/pharmacy_inventory_tally.html', context)


@login_required
def pharmacy_tally_export(request):
    """
    Export tally sheet as CSV
    """
    from django.http import HttpResponse
    import csv
    
    location = request.GET.get('location', 'Main Pharmacy')
    
    stock_items = PharmacyStock.objects.filter(
        location=location,
        is_deleted=False
    ).select_related('drug').order_by('drug__name', 'batch_number')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="pharmacy_tally_{location}_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Drug Name', 'Batch Number', 'Expiry Date', 'System Quantity',
        'Counted Quantity', 'Variance', 'Location', 'Unit Cost', 'Total Value'
    ])
    
    for stock in stock_items:
        writer.writerow([
            stock.drug.name,
            stock.batch_number,
            stock.expiry_date.strftime('%Y-%m-%d') if stock.expiry_date else '',
            stock.quantity_on_hand,
            '',  # Counted quantity (empty for manual entry)
            '',  # Variance (empty for manual calculation)
            stock.location,
            stock.unit_cost,
            stock.quantity_on_hand * stock.unit_cost
        ])
    
    return response
