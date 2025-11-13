"""
Pricing and Service Management Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count
from django.http import JsonResponse
from decimal import Decimal
from .models import ServiceCode, Payer
from .models_pricing import DefaultPrice, PayerPrice


def is_admin_or_manager(user):
    """Check if user is admin or finance manager"""
    return user.is_staff or user.groups.filter(name__in=['Admin', 'Finance Manager']).exists()


@login_required
@user_passes_test(is_admin_or_manager)
def pricing_dashboard(request):
    """Main pricing management dashboard"""
    # Get statistics
    total_services = ServiceCode.objects.filter(is_deleted=False).count()
    total_default_prices = DefaultPrice.objects.filter(is_deleted=False).count()
    total_payer_prices = PayerPrice.objects.filter(is_deleted=False).count()
    total_payers = Payer.objects.filter(is_active=True, is_deleted=False).count()
    
    # Recent services
    recent_services = ServiceCode.objects.filter(is_deleted=False).order_by('-created')[:10]
    
    # Services by category
    services_by_category = ServiceCode.objects.filter(
        is_deleted=False
    ).values('category').annotate(count=Count('id')).order_by('-count')
    
    context = {
        'total_services': total_services,
        'total_default_prices': total_default_prices,
        'total_payer_prices': total_payer_prices,
        'total_payers': total_payers,
        'recent_services': recent_services,
        'services_by_category': services_by_category,
    }
    return render(request, 'hospital/pricing_dashboard.html', context)


@login_required
@user_passes_test(is_admin_or_manager)
def service_list(request):
    """List all services with prices"""
    category_filter = request.GET.get('category', '')
    search_query = request.GET.get('q', '').strip()
    
    services = ServiceCode.objects.filter(is_deleted=False)
    
    if category_filter:
        services = services.filter(category=category_filter)
    
    if search_query:
        services = services.filter(
            Q(code__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Get all categories for filter
    categories = ServiceCode.objects.filter(
        is_deleted=False
    ).values_list('category', flat=True).distinct().order_by('category')
    
    # Get default prices for each service
    services_with_prices = []
    for service in services:
        default_price = DefaultPrice.objects.filter(
            service_code=service.code,
            is_deleted=False
        ).first()
        
        services_with_prices.append({
            'service': service,
            'default_price': default_price.price if default_price else None,
        })
    
    context = {
        'services_with_prices': services_with_prices,
        'categories': categories,
        'selected_category': category_filter,
        'search_query': search_query,
    }
    return render(request, 'hospital/service_list.html', context)


@login_required
@user_passes_test(is_admin_or_manager)
def service_create(request):
    """Create a new service"""
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        description = request.POST.get('description', '').strip()
        category = request.POST.get('category', '').strip()
        default_price = request.POST.get('default_price', '0')
        
        if not code or not description:
            messages.error(request, 'Service code and description are required.')
            return redirect('hospital:service_create')
        
        # Check if code already exists
        if ServiceCode.objects.filter(code=code, is_deleted=False).exists():
            messages.error(request, f'Service code "{code}" already exists.')
            return redirect('hospital:service_create')
        
        # Create service
        service = ServiceCode.objects.create(
            code=code,
            description=description,
            category=category if category else 'General',
            is_active=True
        )
        
        # Create default price if provided
        if default_price:
            try:
                price_decimal = Decimal(default_price)
                if price_decimal > 0:
                    DefaultPrice.objects.create(
                        service_code=code,
                        price=price_decimal
                    )
            except (ValueError, TypeError):
                pass
        
        messages.success(request, f'Service "{description}" created successfully!')
        return redirect('hospital:service_list')
    
    # Get existing categories for dropdown
    categories = ServiceCode.objects.filter(
        is_deleted=False
    ).values_list('category', flat=True).distinct().order_by('category')
    
    context = {
        'categories': categories,
    }
    return render(request, 'hospital/service_create.html', context)


@login_required
@user_passes_test(is_admin_or_manager)
def service_edit(request, pk):
    """Edit a service and its price"""
    service = get_object_or_404(ServiceCode, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        service.code = request.POST.get('code', '').strip()
        service.description = request.POST.get('description', '').strip()
        service.category = request.POST.get('category', '').strip()
        service.is_active = request.POST.get('is_active') == 'on'
        
        if service.code and service.description:
            service.save()
            
            # Update or create default price
            default_price_value = request.POST.get('default_price', '')
            if default_price_value:
                try:
                    price_decimal = Decimal(default_price_value)
                    DefaultPrice.objects.update_or_create(
                        service_code=service.code,
                        defaults={'price': price_decimal}
                    )
                except (ValueError, TypeError):
                    pass
            
            messages.success(request, f'Service "{service.description}" updated successfully!')
            return redirect('hospital:service_list')
        else:
            messages.error(request, 'Service code and description are required.')
    
    # Get current default price
    default_price = DefaultPrice.objects.filter(
        service_code=service.code,
        is_deleted=False
    ).first()
    
    # Get existing categories
    categories = ServiceCode.objects.filter(
        is_deleted=False
    ).values_list('category', flat=True).distinct().order_by('category')
    
    context = {
        'service': service,
        'default_price': default_price,
        'categories': categories,
    }
    return render(request, 'hospital/service_edit.html', context)


@login_required
@user_passes_test(is_admin_or_manager)
def payer_pricing(request):
    """Manage payer-specific pricing"""
    payer_id = request.GET.get('payer')
    
    payers = Payer.objects.filter(is_active=True, is_deleted=False).order_by('name')
    
    if payer_id:
        selected_payer = get_object_or_404(Payer, pk=payer_id, is_deleted=False)
        
        # Get all services with their payer-specific prices
        services = ServiceCode.objects.filter(is_deleted=False).order_by('category', 'code')
        
        services_with_prices = []
        for service in services:
            # Get default price
            default_price = DefaultPrice.objects.filter(
                service_code=service.code,
                is_deleted=False
            ).first()
            
            # Get payer-specific price
            payer_price = PayerPrice.objects.filter(
                payer=selected_payer,
                service_code=service.code,
                is_deleted=False
            ).first()
            
            services_with_prices.append({
                'service': service,
                'default_price': default_price.price if default_price else None,
                'payer_price': payer_price.price if payer_price else None,
                'payer_price_obj': payer_price,
            })
        
        context = {
            'payers': payers,
            'selected_payer': selected_payer,
            'services_with_prices': services_with_prices,
        }
    else:
        context = {
            'payers': payers,
        }
    
    return render(request, 'hospital/payer_pricing.html', context)


@login_required
@user_passes_test(is_admin_or_manager)
def update_payer_price(request, payer_id, service_code):
    """Update or create payer-specific price"""
    if request.method == 'POST':
        payer = get_object_or_404(Payer, pk=payer_id, is_deleted=False)
        service = get_object_or_404(ServiceCode, code=service_code, is_deleted=False)
        
        price = request.POST.get('price', '')
        
        try:
            price_decimal = Decimal(price)
            
            PayerPrice.objects.update_or_create(
                payer=payer,
                service_code=service_code,
                defaults={'price': price_decimal}
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Price updated for {service.description}'
            })
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'message': 'Invalid price value'
            }, status=400)
    
    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)


@login_required
@user_passes_test(is_admin_or_manager)
def specialist_services(request):
    """Manage specialist consultation services"""
    # Get or create specialist service categories
    specialist_categories = [
        'Cardiology',
        'Neurology',
        'Orthopedics',
        'Pediatrics',
        'Dermatology',
        'Psychiatry',
        'Oncology',
        'ENT (Ear, Nose, Throat)',
        'Ophthalmology',
        'Urology',
        'Gynecology',
        'Gastroenterology',
        'Nephrology',
        'Pulmonology',
        'Endocrinology',
    ]
    
    # Get specialist services
    specialist_services = ServiceCode.objects.filter(
        category__in=specialist_categories,
        is_deleted=False
    ).order_by('category', 'code')
    
    services_with_prices = []
    for service in specialist_services:
        default_price = DefaultPrice.objects.filter(
            service_code=service.code,
            is_deleted=False
        ).first()
        
        services_with_prices.append({
            'service': service,
            'default_price': default_price,
        })
    
    context = {
        'specialist_categories': specialist_categories,
        'services_with_prices': services_with_prices,
    }
    return render(request, 'hospital/specialist_services.html', context)


@login_required
@user_passes_test(is_admin_or_manager)
def create_specialist_service(request):
    """Create a specialist service"""
    if request.method == 'POST':
        specialty = request.POST.get('specialty', '').strip()
        service_name = request.POST.get('service_name', '').strip()
        price = request.POST.get('price', '0')
        
        if not specialty or not service_name:
            messages.error(request, 'Specialty and service name are required.')
            return redirect('hospital:specialist_services')
        
        # Generate code
        code_prefix = specialty[:3].upper()
        # Get next number for this specialty
        existing_count = ServiceCode.objects.filter(
            code__startswith=code_prefix,
            is_deleted=False
        ).count()
        code = f"{code_prefix}{existing_count + 1:03d}"
        
        # Create service
        service = ServiceCode.objects.create(
            code=code,
            description=f"{specialty} - {service_name}",
            category=specialty,
            is_active=True
        )
        
        # Create default price
        try:
            price_decimal = Decimal(price)
            if price_decimal > 0:
                DefaultPrice.objects.create(
                    service_code=code,
                    price=price_decimal
                )
        except (ValueError, TypeError):
            pass
        
        messages.success(request, f'Specialist service "{service_name}" created successfully!')
        return redirect('hospital:specialist_services')
    
    return redirect('hospital:specialist_services')


@login_required
@user_passes_test(is_admin_or_manager)
def bulk_price_update(request):
    """Bulk update prices"""
    if request.method == 'POST':
        action = request.POST.get('action')
        percentage = request.POST.get('percentage', '0')
        category = request.POST.get('category', '')
        
        try:
            percent_decimal = Decimal(percentage) / Decimal('100')
            
            # Get services to update
            services = ServiceCode.objects.filter(is_deleted=False)
            if category:
                services = services.filter(category=category)
            
            updated_count = 0
            
            for service in services:
                default_price = DefaultPrice.objects.filter(
                    service_code=service.code,
                    is_deleted=False
                ).first()
                
                if default_price:
                    if action == 'increase':
                        new_price = default_price.price * (Decimal('1') + percent_decimal)
                    elif action == 'decrease':
                        new_price = default_price.price * (Decimal('1') - percent_decimal)
                    else:
                        continue
                    
                    default_price.price = new_price.quantize(Decimal('0.01'))
                    default_price.save()
                    updated_count += 1
            
            messages.success(request, f'Successfully updated {updated_count} prices!')
        except (ValueError, TypeError) as e:
            messages.error(request, f'Error updating prices: {str(e)}')
    
    return redirect('hospital:pricing_dashboard')

