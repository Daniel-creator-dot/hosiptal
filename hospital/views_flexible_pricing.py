"""
World-Class Flexible Pricing Management Views
Manage Cash, Insurance, and Corporate prices
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg, Min, Max
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_http_methods
from decimal import Decimal
from datetime import date, datetime
import csv
import json

from .models import ServiceCode
from .models_flexible_pricing import PricingCategory, ServicePrice, PriceHistory, BulkPriceUpdate
from .models_insurance_companies import InsuranceCompany


@login_required
def pricing_dashboard(request):
    """World-class pricing management dashboard"""
    # Statistics
    stats = {
        'total_categories': PricingCategory.objects.filter(is_deleted=False).count(),
        'active_categories': PricingCategory.objects.filter(is_active=True, is_deleted=False).count(),
        'total_services': ServiceCode.objects.filter(is_active=True, is_deleted=False).count(),
        'priced_services': ServicePrice.objects.filter(is_active=True, is_deleted=False).values('service_code').distinct().count(),
        'total_prices': ServicePrice.objects.filter(is_active=True, is_deleted=False).count(),
    }
    
    # Pricing categories
    categories = PricingCategory.objects.filter(
        is_deleted=False
    ).annotate(
        prices_count=Count('service_prices', filter=Q(service_prices__is_deleted=False))
    ).order_by('priority', 'name')
    
    # Services without prices
    services_with_prices = ServicePrice.objects.filter(
        is_deleted=False
    ).values_list('service_code_id', flat=True).distinct()
    
    services_without_prices = ServiceCode.objects.filter(
        is_active=True,
        is_deleted=False
    ).exclude(id__in=services_with_prices).order_by('category', 'description')[:10]
    
    # Recent price changes
    recent_changes = PriceHistory.objects.filter(
        is_deleted=False
    ).select_related(
        'service_code', 'pricing_category', 'changed_by'
    ).order_by('-created')[:10]
    
    context = {
        'title': 'Pricing Management Dashboard',
        'stats': stats,
        'categories': categories,
        'services_without_prices': services_without_prices,
        'recent_changes': recent_changes,
    }
    
    return render(request, 'hospital/pricing/dashboard.html', context)


@login_required
def pricing_category_list(request):
    """List all pricing categories"""
    categories = PricingCategory.objects.filter(
        is_deleted=False
    ).annotate(
        prices_count=Count('service_prices', filter=Q(service_prices__is_deleted=False))
    ).order_by('priority', 'name')
    
    context = {
        'title': 'Pricing Categories',
        'categories': categories,
    }
    
    return render(request, 'hospital/pricing/category_list.html', context)


@login_required
def pricing_category_create(request):
    """Create new pricing category"""
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            code = request.POST.get('code').upper()
            category_type = request.POST.get('category_type', 'cash')
            description = request.POST.get('description', '')
            default_discount = request.POST.get('default_discount_percentage', '0')
            priority = request.POST.get('priority', '100')
            color_code = request.POST.get('color_code', '#3b82f6')
            insurance_company_id = request.POST.get('insurance_company')
            
            category = PricingCategory.objects.create(
                name=name,
                code=code,
                category_type=category_type,
                description=description,
                default_discount_percentage=Decimal(default_discount),
                priority=int(priority),
                color_code=color_code,
                is_active=True,
            )
            
            if insurance_company_id:
                category.insurance_company_id = insurance_company_id
                category.save(update_fields=['insurance_company'])
            
            messages.success(request, f'✅ Pricing category "{category.name}" created successfully!')
            return redirect('hospital:pricing_category_detail', pk=category.pk)
        
        except Exception as e:
            messages.error(request, f'❌ Error creating pricing category: {str(e)}')
    
    insurance_companies = InsuranceCompany.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by('name')
    
    context = {
        'title': 'Create Pricing Category',
        'insurance_companies': insurance_companies,
    }
    
    return render(request, 'hospital/pricing/category_form.html', context)


@login_required
def pricing_category_detail(request, pk):
    """View pricing category details with all prices"""
    category = get_object_or_404(PricingCategory, pk=pk, is_deleted=False)
    
    # Get services with prices in this category
    query = request.GET.get('q', '')
    service_filter = request.GET.get('service_type', '')
    
    prices = ServicePrice.objects.filter(
        pricing_category=category,
        is_deleted=False
    ).select_related('service_code').order_by('service_code__category', 'service_code__description')
    
    if query:
        prices = prices.filter(
            Q(service_code__code__icontains=query) |
            Q(service_code__description__icontains=query)
        )
    
    if service_filter:
        prices = prices.filter(service_code__category=service_filter)
    
    # Pagination
    paginator = Paginator(prices, 50)
    page = request.GET.get('page')
    prices_page = paginator.get_page(page)
    
    # Statistics
    stats = {
        'total_prices': prices.count(),
        'avg_price': prices.aggregate(Avg('price'))['price__avg'] or 0,
        'min_price': prices.aggregate(Min('price'))['price__min'] or 0,
        'max_price': prices.aggregate(Max('price'))['price__max'] or 0,
    }
    
    # Service categories for filter
    service_categories = ServiceCode.objects.filter(
        is_deleted=False
    ).values_list('category', flat=True).distinct().order_by('category')
    
    context = {
        'title': f'{category.name} Prices',
        'category': category,
        'prices': prices_page,
        'stats': stats,
        'service_categories': service_categories,
        'query': query,
        'service_filter': service_filter,
    }
    
    return render(request, 'hospital/pricing/category_detail.html', context)


@login_required
def service_price_matrix(request):
    """View price matrix comparing all categories for all services"""
    query = request.GET.get('q', '')
    service_filter = request.GET.get('service_type', '')
    
    # Get all active categories
    categories = PricingCategory.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by('priority', 'name')
    
    # Get services
    services = ServiceCode.objects.filter(
        is_active=True,
        is_deleted=False
    )
    
    if query:
        services = services.filter(
            Q(code__icontains=query) |
            Q(description__icontains=query)
        )
    
    if service_filter:
        services = services.filter(category=service_filter)
    
    services = services.order_by('category', 'description')
    
    # Build price matrix
    matrix = []
    for service in services[:100]:  # Limit to 100 for performance
        row = {
            'service': service,
            'prices': {}
        }
        
        for category in categories:
            price = ServicePrice.get_price(service, category)
            row['prices'][category.id] = price
        
        matrix.append(row)
    
    # Service categories for filter
    service_categories = ServiceCode.objects.filter(
        is_deleted=False
    ).values_list('category', flat=True).distinct().order_by('category')
    
    context = {
        'title': 'Price Matrix',
        'categories': categories,
        'matrix': matrix,
        'service_categories': service_categories,
        'query': query,
        'service_filter': service_filter,
    }
    
    return render(request, 'hospital/pricing/price_matrix.html', context)


@login_required
def bulk_price_input(request):
    """Bulk price input form"""
    if request.method == 'POST':
        try:
            category_id = request.POST.get('pricing_category')
            category = get_object_or_404(PricingCategory, pk=category_id, is_deleted=False)
            
            # Get CSV data or form data
            csv_data = request.POST.get('csv_data', '')
            
            if csv_data:
                # Process CSV
                import csv
                import io
                
                csv_file = io.StringIO(csv_data)
                reader = csv.DictReader(csv_file)
                
                created_count = 0
                updated_count = 0
                errors = []
                
                for row in reader:
                    try:
                        service_code = row.get('service_code', '').strip()
                        price = row.get('price', '0').strip()
                        
                        if not service_code or not price:
                            continue
                        
                        # Find service
                        service = ServiceCode.objects.filter(
                            code=service_code,
                            is_deleted=False
                        ).first()
                        
                        if not service:
                            errors.append(f"Service code '{service_code}' not found")
                            continue
                        
                        # Create or update price
                        service_price, created = ServicePrice.objects.update_or_create(
                            service_code=service,
                            pricing_category=category,
                            effective_from=timezone.now().date(),
                            defaults={
                                'price': Decimal(price),
                                'is_active': True,
                            }
                        )
                        
                        if created:
                            created_count += 1
                            # Create history
                            PriceHistory.objects.create(
                                service_price=service_price,
                                service_code=service,
                                pricing_category=category,
                                action='created',
                                new_price=Decimal(price),
                                changed_by=request.user,
                                notes='Bulk CSV upload'
                            )
                        else:
                            updated_count += 1
                            # Create history
                            PriceHistory.objects.create(
                                service_price=service_price,
                                service_code=service,
                                pricing_category=category,
                                action='updated',
                                old_price=service_price.price,
                                new_price=Decimal(price),
                                changed_by=request.user,
                                notes='Bulk CSV upload'
                            )
                    
                    except Exception as e:
                        errors.append(f"Error processing row: {str(e)}")
                
                if errors:
                    messages.warning(request, f"⚠️ Completed with errors. Created: {created_count}, Updated: {updated_count}. Errors: {len(errors)}")
                else:
                    messages.success(request, f"✅ Successfully processed! Created: {created_count}, Updated: {updated_count}")
                
                return redirect('hospital:pricing_category_detail', pk=category.pk)
        
        except Exception as e:
            messages.error(request, f'❌ Error processing bulk upload: {str(e)}')
    
    categories = PricingCategory.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by('name')
    
    # Sample services for selection
    services = ServiceCode.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by('category', 'description')[:100]
    
    context = {
        'title': 'Bulk Price Input',
        'categories': categories,
        'services': services,
    }
    
    return render(request, 'hospital/pricing/bulk_input.html', context)


@login_required
@require_POST
def service_price_create_api(request):
    """API endpoint to create/update service price"""
    try:
        service_code_id = request.POST.get('service_code_id')
        pricing_category_id = request.POST.get('pricing_category_id')
        price = Decimal(request.POST.get('price', '0'))
        effective_from = request.POST.get('effective_from', timezone.now().date())
        
        service_code = get_object_or_404(ServiceCode, pk=service_code_id, is_deleted=False)
        pricing_category = get_object_or_404(PricingCategory, pk=pricing_category_id, is_deleted=False)
        
        # Check if price exists
        existing_price = ServicePrice.objects.filter(
            service_code=service_code,
            pricing_category=pricing_category,
            effective_from=effective_from,
            is_deleted=False
        ).first()
        
        if existing_price:
            old_price = existing_price.price
            existing_price.price = price
            existing_price.save(update_fields=['price'])
            
            # Create history
            PriceHistory.objects.create(
                service_price=existing_price,
                service_code=service_code,
                pricing_category=pricing_category,
                action='updated',
                old_price=old_price,
                new_price=price,
                changed_by=request.user,
                notes='Manual update'
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Price updated successfully',
                'price_id': str(existing_price.id),
                'price': str(price)
            })
        else:
            new_price = ServicePrice.objects.create(
                service_code=service_code,
                pricing_category=pricing_category,
                price=price,
                effective_from=effective_from,
                is_active=True,
            )
            
            # Create history
            PriceHistory.objects.create(
                service_price=new_price,
                service_code=service_code,
                pricing_category=pricing_category,
                action='created',
                new_price=price,
                changed_by=request.user,
                notes='Manual create'
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Price created successfully',
                'price_id': str(new_price.id),
                'price': str(price)
            })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def export_prices_csv(request, category_pk):
    """Export prices to CSV"""
    category = get_object_or_404(PricingCategory, pk=category_pk, is_deleted=False)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="prices_{category.code}_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Service Code', 'Service Description', 'Category', 'Price (GHS)', 'Effective From'])
    
    prices = ServicePrice.objects.filter(
        pricing_category=category,
        is_active=True,
        is_deleted=False
    ).select_related('service_code').order_by('service_code__category', 'service_code__code')
    
    for price in prices:
        writer.writerow([
            price.service_code.code,
            price.service_code.description,
            price.service_code.category,
            str(price.price),
            price.effective_from.strftime('%Y-%m-%d')
        ])
    
    return response


@login_required
def get_service_price_api(request):
    """API endpoint to get price for a service in a specific category"""
    try:
        service_code_id = request.GET.get('service_code_id')
        pricing_category_id = request.GET.get('pricing_category_id')
        
        service_code = get_object_or_404(ServiceCode, pk=service_code_id, is_deleted=False)
        pricing_category = get_object_or_404(PricingCategory, pk=pricing_category_id, is_deleted=False)
        
        price = ServicePrice.get_price(service_code, pricing_category)
        
        return JsonResponse({
            'success': True,
            'service_code': service_code.code,
            'service_description': service_code.description,
            'pricing_category': pricing_category.name,
            'price': str(price) if price else None,
            'has_price': price is not None
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)























