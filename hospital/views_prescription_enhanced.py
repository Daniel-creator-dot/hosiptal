"""
Enhanced Prescription Views - Outstanding Drug Selection Interface
Category-based browsing for easy doctor prescription
"""
from django.http import JsonResponse
from django.db.models import Q, Count, Sum
from django.contrib.auth.decorators import login_required
from hospital.models import Drug, PharmacyStock
from decimal import Decimal


@login_required
def api_search_drugs_by_category(request):
    """
    Enhanced API endpoint for drug search with category filtering
    Returns drugs filtered by category, name, or generic name
    Perfect for prescription interface
    """
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    include_stock = request.GET.get('include_stock', 'true').lower() == 'true'
    
    # Build queryset
    drugs = Drug.objects.filter(
        is_active=True,
        is_deleted=False
    )
    
    # Filter by category if provided
    if category:
        drugs = drugs.filter(category=category)
    
    # Filter by search query
    if query:
        drugs = drugs.filter(
            Q(name__icontains=query) |
            Q(generic_name__icontains=query) |
            Q(atc_code__icontains=query)
        )
    
    # Order by category, then name for better organization
    drugs = drugs.order_by('category', 'name')[:50]
    
    # Build response
    results = []
    for drug in drugs:
        drug_data = {
            'id': drug.id,
            'name': drug.name,
            'generic_name': drug.generic_name,
            'strength': getattr(drug, 'strength', ''),
            'form': drug.form,
            'category': drug.category,
            'category_display': drug.get_category_display(),
            'unit_price': str(drug.unit_price),
            'atc_code': drug.atc_code or '',
            'is_controlled': drug.is_controlled,
        }
        
        # Add stock information if requested
        if include_stock:
            try:
                stock_qty = PharmacyStock.objects.filter(
                    drug=drug,
                    quantity_on_hand__gt=0,
                    is_deleted=False
                ).aggregate(total=Count('quantity_on_hand'))['total'] or 0
                
                # Actually sum the quantities
                stock_sum = PharmacyStock.objects.filter(
                    drug=drug,
                    quantity_on_hand__gt=0,
                    is_deleted=False
                ).aggregate(total=Sum('quantity_on_hand'))['total'] or 0
                
                drug_data['stock_available'] = int(stock_sum)
                drug_data['has_stock'] = stock_sum > 0
            except:
                drug_data['stock_available'] = 0
                drug_data['has_stock'] = False
        
        results.append(drug_data)
    
    return JsonResponse({
        'drugs': results,
        'count': len(results),
        'category': category,
        'query': query
    })


@login_required
def api_get_drug_categories(request):
    """
    Get all drug categories with counts
    Useful for building category filter dropdown
    """
    categories_with_counts = Drug.objects.filter(
        is_active=True,
        is_deleted=False
    ).values('category').annotate(
        count=Count('id')
    ).order_by('category')
    
    # Build category list with counts
    categories = []
    for item in categories_with_counts:
        category_code = item['category']
        count = item['count']
        
        # Get display name
        display_name = dict(Drug.CATEGORIES).get(category_code, category_code)
        
        categories.append({
            'code': category_code,
            'name': display_name,
            'count': count
        })
    
    return JsonResponse({
        'categories': categories,
        'total_categories': len(categories)
    })


@login_required
def api_get_drugs_by_category(request, category_code):
    """
    Get all drugs in a specific category
    Useful for category-based browsing
    """
    drugs = Drug.objects.filter(
        category=category_code,
        is_active=True,
        is_deleted=False
    ).order_by('name')
    
    results = []
    for drug in drugs:
        # Get stock
        try:
            stock_sum = PharmacyStock.objects.filter(
                drug=drug,
                quantity_on_hand__gt=0,
                is_deleted=False
            ).aggregate(total=Sum('quantity_on_hand'))['total'] or 0
        except:
            stock_sum = 0
        
        results.append({
            'id': drug.id,
            'name': drug.name,
            'generic_name': drug.generic_name,
            'strength': getattr(drug, 'strength', ''),
            'form': drug.form,
            'unit_price': str(drug.unit_price),
            'stock_available': int(stock_sum),
            'has_stock': stock_sum > 0,
        })
    
    return JsonResponse({
        'drugs': results,
        'category': category_code,
        'category_name': dict(Drug.CATEGORIES).get(category_code, category_code),
        'count': len(results)
    })

