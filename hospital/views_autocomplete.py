"""
Autocomplete API Endpoints
Provides search-as-you-type functionality for patients, items, and other entities
"""
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.models.functions import Concat
from django.db.models import Value, CharField

from .models import Patient
from .models_procurement import InventoryItem, Store


@login_required
def api_autocomplete_patients(request):
    """
    Autocomplete API for patient search
    Returns JSON with patient suggestions as user types
    """
    query = request.GET.get('q', '').strip()
    source = request.GET.get('source', 'new').strip().lower()  # new|legacy|all
    
    if len(query) < 2:
        return JsonResponse({'results': []})

    # Try to import LegacyPatient (optional)
    LegacyPatient = None
    legacy_table_exists = False
    try:
        from .models_legacy_patients import LegacyPatient  # type: ignore
        try:
            LegacyPatient.objects.count()
            legacy_table_exists = True
        except Exception:
            LegacyPatient = None
            legacy_table_exists = False
    except Exception:
        LegacyPatient = None
        legacy_table_exists = False
    
    # Enhanced search: search by full name combination
    query_parts = query.split()
    search_query = Q(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(middle_name__icontains=query) |
        Q(mrn__icontains=query) |
        Q(phone_number__icontains=query) |
        Q(email__icontains=query)
    )
    
    # If query has multiple words, search for full name combinations
    if len(query_parts) >= 2:
        first_part = query_parts[0]
        last_parts = ' '.join(query_parts[1:])
        search_query |= Q(
            Q(first_name__icontains=first_part) &
            Q(last_name__icontains=last_parts)
        )
        search_query |= Q(
            Q(first_name__icontains=last_parts) &
            Q(last_name__icontains=first_part)
        )
    
    results = []
    # New system patients
    if source in ('new', 'all'):
        patients = Patient.objects.filter(
            search_query,
            is_deleted=False
        ).select_related('primary_insurance').distinct()[:20]

        for patient in patients:
            results.append({
                'id': str(patient.id),
                'source': 'new',
                'name': patient.full_name,
                'mrn': patient.mrn or 'N/A',
                'phone': patient.phone_number or 'N/A',
                'email': patient.email or 'N/A',
                'display': f"{patient.full_name} (MRN: {patient.mrn or 'N/A'})",
                'subtext': f"Phone: {patient.phone_number or 'N/A'} | Email: {patient.email or 'N/A'}",
                'view_url': f"/hms/patients/{patient.id}/",
                'quick_visit_url': f"/hms/patients/{patient.id}/quick-visit/",
            })

    # Legacy patients (optional)
    if source in ('legacy', 'all') and LegacyPatient and legacy_table_exists:
        try:
            legacy_search = Q(
                Q(fname__icontains=query) |
                Q(lname__icontains=query) |
                Q(mname__icontains=query) |
                Q(pid__icontains=query) |
                Q(phone_cell__icontains=query) |
                Q(pmc_mrn__icontains=query)
            )
            legacy_qs = LegacyPatient.objects.filter(legacy_search).only(
                'id', 'pid', 'fname', 'lname', 'mname', 'phone_cell', 'pmc_mrn'
            )[:20]

            for lp in legacy_qs:
                try:
                    full_name = lp.full_name
                except Exception:
                    full_name = f"{getattr(lp, 'fname', '')} {getattr(lp, 'lname', '')}".strip() or 'Legacy Patient'
                try:
                    mrn_display = lp.mrn_display
                except Exception:
                    mrn_display = getattr(lp, 'pmc_mrn', '') or getattr(lp, 'pid', '') or 'N/A'
                phone = getattr(lp, 'phone_cell', '') or 'N/A'
                pid = getattr(lp, 'pid', '') or 'N/A'

                results.append({
                    'id': f"legacy-{lp.id}",
                    'source': 'legacy',
                    'name': full_name,
                    'mrn': mrn_display,
                    'phone': phone,
                    'email': 'N/A',
                    'display': f"{full_name} (MRN: {mrn_display})",
                    'subtext': f"Legacy PID: {pid} | Phone: {phone}",
                    'view_url': f"/hms/patients/legacy/{lp.id}/",
                })
        except Exception:
            # If legacy search fails for any reason, ignore rather than breaking autocomplete
            pass
    
    return JsonResponse({'results': results})


@login_required
def api_autocomplete_items(request):
    """
    Autocomplete API for inventory item search
    Returns JSON with item suggestions as user types
    """
    query = request.GET.get('q', '').strip()
    store_id = request.GET.get('store_id', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    # Build search query
    search_query = Q(
        Q(item_name__icontains=query) |
        Q(item_code__icontains=query) |
        Q(description__icontains=query)
    )
    
    # Filter by store if provided
    items_qs = InventoryItem.objects.filter(
        search_query,
        is_deleted=False,
        is_active=True
    )
    
    if store_id:
        try:
            items_qs = items_qs.filter(store_id=store_id)
        except ValueError:
            pass  # Invalid store_id, ignore
    
    items = items_qs.select_related('store', 'category', 'drug')[:20]
    
    results = []
    for item in items:
        category_name = item.category.name if item.category else 'Uncategorized'
        store_name = item.store.name if item.store else 'Unknown Store'
        
        results.append({
            'id': str(item.id),
            'name': item.item_name,
            'code': item.item_code or 'N/A',
            'quantity': item.quantity_on_hand,
            'unit_cost': str(item.unit_cost),
            'category': category_name,
            'store': store_name,
            'display': f"{item.item_name} ({item.item_code or 'No Code'})",
            'subtext': f"Store: {store_name} | Qty: {item.quantity_on_hand} | Category: {category_name}"
        })
    
    return JsonResponse({'results': results})


@login_required
def api_autocomplete_drugs(request):
    """
    Autocomplete API for drug search.
    Selling prices use get_drug_price_for_prescription (same as prescribe sales and billing).
    Optional encounter_id applies the encounter patient's payer for markup.
    """
    from .models import Drug, Staff
    from .utils_billing import get_drug_price_for_prescription

    query = request.GET.get('q', '').strip()
    encounter_id = request.GET.get('encounter_id', '').strip()
    pricing_payer = None
    if encounter_id:
        try:
            from .models import Encounter
            enc = Encounter.objects.filter(
                pk=encounter_id, is_deleted=False
            ).select_related('patient__primary_insurance').first()
            if enc and enc.patient_id:
                pricing_payer = enc.patient.primary_insurance
        except Exception:
            pricing_payer = None
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    # Check if user is a doctor or nurse (they shouldn't see prices)
    is_doctor = False
    is_nurse = False
    try:
        staff = Staff.objects.filter(user=request.user, is_deleted=False).first()
        if staff and staff.profession:
            profession_lower = staff.profession.lower()
            if profession_lower == 'doctor':
                is_doctor = True
            elif profession_lower == 'nurse':
                is_nurse = True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Error checking staff status: {e}")
        pass
    
    can_see_prices = not is_doctor and not is_nurse
    
    # Build search query
    search_query = Q(
        Q(name__icontains=query) |
        Q(generic_name__icontains=query) |
        Q(atc_code__icontains=query)
    )
    
    # Filter for active, non-deleted drugs with valid names
    drugs = list(Drug.objects.filter(
        search_query,
        is_active=True,
        is_deleted=False,
        name__isnull=False
    ).exclude(
        name__iexact=''
    ).exclude(
        name__icontains='INVALID'
    ).order_by('name')[:20])

    # Stock quantity - PharmacyStock first, InventoryItem (pharmacy store) as fallback
    stock_map = {}
    expiry_map = {}  # Soonest expiry per drug (for doctors to see expiring drugs)
    try:
        from .models import PharmacyStock
        from django.db.models import Sum, Min
        from django.utils import timezone as tz
        from datetime import timedelta
        if drugs:
            drug_ids = [d.id for d in drugs]
            stock_totals = PharmacyStock.objects.filter(
                drug_id__in=drug_ids,
                is_deleted=False
            ).values('drug_id').annotate(total=Sum('quantity_on_hand'))
            stock_map = {s['drug_id']: (s['total'] or 0) for s in stock_totals}
            # Soonest expiry per drug (within 30 days, not expired) - for doctor awareness
            today = tz.now().date()
            expiring_soon = today + timedelta(days=30)
            soonest_expiry = PharmacyStock.objects.filter(
                drug_id__in=drug_ids,
                expiry_date__gte=today,
                expiry_date__lte=expiring_soon,
                quantity_on_hand__gt=0,
                is_deleted=False
            ).values('drug_id').annotate(soonest=Min('expiry_date'))
            expiry_map = {s['drug_id']: s['soonest'] for s in soonest_expiry}
            # Fallback: add InventoryItem qty for drugs with 0 in PharmacyStock
            try:
                from .models_procurement import Store, InventoryItem
                pharmacy_store = Store.get_pharmacy_store_for_prescriptions()
                if pharmacy_store:
                    for item in InventoryItem.objects.filter(
                        store=pharmacy_store, drug_id__in=drug_ids,
                        is_deleted=False, is_active=True
                    ).values('drug_id', 'quantity_on_hand'):
                        did = item['drug_id']
                        if did and (stock_map.get(did) or 0) == 0:
                            stock_map[did] = item['quantity_on_hand'] or 0
            except Exception:
                pass
    except Exception:
        pass

    results = []
    for drug in drugs:
        price = float(get_drug_price_for_prescription(drug, pricing_payer))

        # Stock quantity - show for all users so doctors see availability
        stock_qty = stock_map.get(drug.id, 0) or 0
        if stock_qty > 0:
            stock_str = f"<strong>Stock: {stock_qty}</strong> | "
        elif stock_qty == 0:
            stock_str = "<strong>Stock: 0 (Out of stock)</strong> | "
        else:
            stock_str = ""

        # Expiry warning - show when drug has stock expiring within 30 days
        expiry_str = ""
        expiry_date = expiry_map.get(drug.id)
        expiry_fmt = None
        if expiry_date:
            from django.utils.formats import date_format
            try:
                expiry_fmt = date_format(expiry_date, format='d/m/Y')
            except Exception:
                expiry_fmt = str(expiry_date)
            expiry_str = f"<strong>Expires: {expiry_fmt}</strong> | "

        # Build subtext - exclude price for doctors and nurses; always show stock + expiry when relevant
        if can_see_prices:
            subtext = (
                stock_str + expiry_str +
                f"Generic: {drug.generic_name or 'N/A'} | "
                f"ATC: {drug.atc_code or 'N/A'} | "
                f"<strong>Price: GHS {price:.2f}</strong>"
            )
        else:
            subtext = (
                stock_str + expiry_str +
                f"Generic: {drug.generic_name or 'N/A'} | "
                f"ATC: {drug.atc_code or 'N/A'}"
            )
        
        # Display: drug name + stock + expiry badge when expiring soon
        base_display = f"{drug.name} {drug.strength or ''} {drug.form or ''}".strip()
        display_with_stock = f"{base_display} · Stock: {stock_qty}" if stock_qty >= 0 else base_display
        if expiry_fmt:
            display_with_stock = f"{display_with_stock} · Expires: {expiry_fmt}"

        cost_price = float(getattr(drug, 'cost_price', 0) or 0)
        results.append({
            'id': str(drug.id),
            'name': drug.name,
            'generic_name': drug.generic_name or 'N/A',
            'strength': drug.strength or 'N/A',
            'form': drug.form or 'N/A',
            'price': str(round(price, 2)),
            'unit_price': str(round(price, 2)),
            'cost_price': str(round(cost_price, 2)),
            'stock_qty': int(stock_qty) if stock_qty is not None else 0,
            'display': display_with_stock,
            'subtext': subtext
        })
    
    return JsonResponse({'results': results})


@login_required
def api_autocomplete_lab_tests(request):
    """
    Autocomplete API for lab test search
    Returns JSON with lab test suggestions as user types
    """
    from .models import LabTest
    
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    # Build search query
    search_query = Q(
        Q(name__icontains=query) |
        Q(code__icontains=query) |
        Q(specimen_type__icontains=query)
    )
    
    lab_tests = LabTest.objects.filter(
        search_query,
        is_active=True,
        is_deleted=False
    ).exclude(
        name__iexact=''
    ).exclude(
        name__icontains='INVALID'
    )[:20]
    
    # Check if user is a doctor or nurse (they shouldn't see prices)
    is_doctor = False
    is_nurse = False
    try:
        from .models import Staff
        staff = Staff.objects.filter(user=request.user, is_deleted=False).first()
        if staff and staff.profession:
            if staff.profession == 'doctor':
                is_doctor = True
            elif staff.profession == 'nurse':
                is_nurse = True
    except Exception:
        pass
    
    can_see_prices = not is_doctor and not is_nurse
    
    results = []
    for test in lab_tests:
        # Build subtext - exclude price for doctors and nurses
        if can_see_prices:
            subtext = f"Specimen: {test.specimen_type or 'N/A'} | <strong>Price: GHS {(float(test.price) if test.price else 0.00):.2f}</strong>"
        else:
            subtext = f"Specimen: {test.specimen_type or 'N/A'}"
        
        results.append({
            'id': str(test.id),
            'name': test.name,
            'code': test.code or 'N/A',
            'specimen_type': test.specimen_type or 'N/A',
            'price': str(float(test.price) if test.price else 0.00),
            'display': f"{test.name} ({test.code or 'No Code'})",
            'subtext': subtext
        })
    
    return JsonResponse({'results': results})


@login_required
def api_autocomplete_imaging_studies(request):
    """
    Autocomplete API for imaging study search
    Returns JSON with imaging study suggestions as user types
    """
    from .models import Staff
    
    # Check if user is a doctor or nurse (they shouldn't see prices)
    is_doctor = False
    is_nurse = False
    try:
        staff = Staff.objects.filter(user=request.user, is_deleted=False).first()
        if staff and staff.profession:
            profession_lower = staff.profession.lower()
            if profession_lower == 'doctor':
                is_doctor = True
            elif profession_lower == 'nurse':
                is_nurse = True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Error checking staff status: {e}")
        pass
    
    can_see_prices = not is_doctor and not is_nurse
    
    # Try to find ImagingCatalog model (prefer models_advanced for consistency with consultation/orders)
    try:
        from .models_advanced import ImagingCatalog
        use_catalog = True
    except ImportError:
        try:
            from .models_service_pricing import ImagingCatalog
            use_catalog = True
        except ImportError:
            use_catalog = False
    
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    results = []
    
    if use_catalog:
        # Search in ImagingCatalog
        search_query = Q(
            Q(name__icontains=query) |
            Q(code__icontains=query) |
            Q(body_part__icontains=query) |
            Q(modality__icontains=query)
        )
        
        studies = ImagingCatalog.objects.filter(
            search_query,
            is_active=True,
            is_deleted=False
        )[:20]
        
        for study in studies:
            # Build subtext - exclude price for doctors
            if is_doctor:
                subtext = f"Modality: {study.modality or 'N/A'} | Body Part: {study.body_part or 'N/A'}"
            else:
                subtext = f"Modality: {study.modality or 'N/A'} | Body Part: {study.body_part or 'N/A'} | <strong>Price: GHS {(float(study.price) if study.price else 0.00):.2f}</strong>"
            
            results.append({
                'id': str(study.id),
                'name': study.name or study.description or 'N/A',
                'code': study.code or 'N/A',
                'modality': study.modality or 'N/A',
                'body_part': study.body_part or 'N/A',
                'price': str(float(study.price) if study.price else 0.00),
                'display': f"{study.name or study.description} ({study.code or 'No Code'})",
                'subtext': subtext
            })
    else:
        # Fallback: Search in ImagingPrice or return empty
        try:
            from .models_service_pricing import ImagingPrice
            search_query = Q(
                Q(body_part__icontains=query) |
                Q(description__icontains=query) |
                Q(imaging_type__icontains=query)
            )
            
            imaging_prices = ImagingPrice.objects.filter(search_query)[:20]
            
            for img in imaging_prices:
                # Build subtext - exclude price for doctors and nurses
                if can_see_prices:
                    subtext = f"Type: {img.get_imaging_type_display()} | Body Part: {img.body_part} | Price: GHS {img.price}"
                else:
                    subtext = f"Type: {img.get_imaging_type_display()} | Body Part: {img.body_part}"
                
                results.append({
                    'id': str(img.id),
                    'name': img.description,
                    'code': img.get_imaging_type_display(),
                    'modality': img.get_imaging_type_display(),
                    'body_part': img.body_part,
                    'price': str(img.price),
                    'display': f"{img.description} ({img.body_part})",
                    'subtext': subtext
                })
        except ImportError:
            pass
    
    return JsonResponse({'results': results})


@login_required
def api_autocomplete_consumables(request):
    """
    Autocomplete API for consumables search
    Returns JSON with consumable suggestions as user types
    """
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    # Search in InventoryItem for consumables
    # Consumables are typically items that are not drugs
    search_query = Q(
        Q(item_name__icontains=query) |
        Q(item_code__icontains=query) |
        Q(description__icontains=query)
    )
    
    # Filter for consumables (items without drug reference or in consumables category)
    consumables_qs = InventoryItem.objects.filter(
        search_query,
        is_deleted=False,
        is_active=True
    ).filter(
        Q(drug__isnull=True) | Q(category__name__icontains='consumable')
    )[:20]
    
    results = []
    for item in consumables_qs:
        category_name = item.category.name if item.category else 'Consumable'
        store_name = item.store.name if item.store else 'Unknown Store'
        
        results.append({
            'id': str(item.id),
            'name': item.item_name,
            'code': item.item_code or 'N/A',
            'quantity': item.quantity_on_hand,
            'unit_cost': str(item.unit_cost),
            'category': category_name,
            'store': store_name,
            'display': f"{item.item_name} ({item.item_code or 'No Code'})",
            'subtext': f"Store: {store_name} | Qty: {item.quantity_on_hand} | Price: GHS {item.unit_cost or 0}"
        })
    
    return JsonResponse({'results': results})


@login_required
def api_autocomplete_lab_tests(request):
    """
    Autocomplete API for lab test search
    Returns JSON with lab test suggestions as user types
    """
    from .models import LabTest
    
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    # Build search query
    search_query = Q(
        Q(name__icontains=query) |
        Q(code__icontains=query) |
        Q(specimen_type__icontains=query)
    )
    
    lab_tests = LabTest.objects.filter(
        search_query,
        is_active=True,
        is_deleted=False
    ).exclude(
        name__iexact=''
    ).exclude(
        name__icontains='INVALID'
    )[:20]
    
    # Check if user is a doctor or nurse (they shouldn't see prices)
    is_doctor = False
    is_nurse = False
    try:
        from .models import Staff
        staff = Staff.objects.filter(user=request.user, is_deleted=False).first()
        if staff and staff.profession:
            if staff.profession == 'doctor':
                is_doctor = True
            elif staff.profession == 'nurse':
                is_nurse = True
    except Exception:
        pass
    
    can_see_prices = not is_doctor and not is_nurse
    
    results = []
    for test in lab_tests:
        # Build subtext - exclude price for doctors and nurses
        if can_see_prices:
            subtext = f"Specimen: {test.specimen_type or 'N/A'} | <strong>Price: GHS {(float(test.price) if test.price else 0.00):.2f}</strong>"
        else:
            subtext = f"Specimen: {test.specimen_type or 'N/A'}"
        
        results.append({
            'id': str(test.id),
            'name': test.name,
            'code': test.code or 'N/A',
            'specimen_type': test.specimen_type or 'N/A',
            'price': str(float(test.price) if test.price else 0.00),
            'display': f"{test.name} ({test.code or 'No Code'})",
            'subtext': subtext
        })
    
    return JsonResponse({'results': results})


@login_required
def api_autocomplete_imaging_studies(request):
    """
    Autocomplete API for imaging study search
    Returns JSON with imaging study suggestions as user types
    """
    from .models import Staff
    
    # Check if user is a doctor or nurse (they shouldn't see prices)
    is_doctor = False
    is_nurse = False
    try:
        staff = Staff.objects.filter(user=request.user, is_deleted=False).first()
        if staff and staff.profession:
            profession_lower = staff.profession.lower()
            if profession_lower == 'doctor':
                is_doctor = True
            elif profession_lower == 'nurse':
                is_nurse = True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Error checking staff status: {e}")
        pass
    
    can_see_prices = not is_doctor and not is_nurse
    
    # Try to find ImagingCatalog model (prefer models_advanced for consistency with consultation/orders)
    try:
        from .models_advanced import ImagingCatalog
        use_catalog = True
    except ImportError:
        try:
            from .models_service_pricing import ImagingCatalog
            use_catalog = True
        except ImportError:
            use_catalog = False
    
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    results = []
    
    if use_catalog:
        # Search in ImagingCatalog
        search_query = Q(
            Q(name__icontains=query) |
            Q(code__icontains=query) |
            Q(body_part__icontains=query) |
            Q(modality__icontains=query)
        )
        
        studies = ImagingCatalog.objects.filter(
            search_query,
            is_active=True,
            is_deleted=False
        )[:20]
        
        for study in studies:
            # Build subtext - exclude price for doctors
            if is_doctor:
                subtext = f"Modality: {study.modality or 'N/A'} | Body Part: {study.body_part or 'N/A'}"
            else:
                subtext = f"Modality: {study.modality or 'N/A'} | Body Part: {study.body_part or 'N/A'} | <strong>Price: GHS {(float(study.price) if study.price else 0.00):.2f}</strong>"
            
            results.append({
                'id': str(study.id),
                'name': study.name or study.description or 'N/A',
                'code': study.code or 'N/A',
                'modality': study.modality or 'N/A',
                'body_part': study.body_part or 'N/A',
                'price': str(float(study.price) if study.price else 0.00),
                'display': f"{study.name or study.description} ({study.code or 'No Code'})",
                'subtext': subtext
            })
    else:
        # Fallback: Search in ImagingPrice or return empty
        try:
            from .models_service_pricing import ImagingPrice
            search_query = Q(
                Q(body_part__icontains=query) |
                Q(description__icontains=query) |
                Q(imaging_type__icontains=query)
            )
            
            imaging_prices = ImagingPrice.objects.filter(search_query)[:20]
            
            for img in imaging_prices:
                # Build subtext - exclude price for doctors and nurses
                if can_see_prices:
                    subtext = f"Type: {img.get_imaging_type_display()} | Body Part: {img.body_part} | Price: GHS {img.price}"
                else:
                    subtext = f"Type: {img.get_imaging_type_display()} | Body Part: {img.body_part}"
                
                results.append({
                    'id': str(img.id),
                    'name': img.description,
                    'code': img.get_imaging_type_display(),
                    'modality': img.get_imaging_type_display(),
                    'body_part': img.body_part,
                    'price': str(img.price),
                    'display': f"{img.description} ({img.body_part})",
                    'subtext': subtext
                })
        except ImportError:
            pass
    
    return JsonResponse({'results': results})


@login_required
def api_autocomplete_consumables(request):
    """
    Autocomplete API for consumables search
    Returns JSON with consumable suggestions as user types
    """
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    # Search in InventoryItem for consumables
    # Consumables are typically items that are not drugs
    search_query = Q(
        Q(item_name__icontains=query) |
        Q(item_code__icontains=query) |
        Q(description__icontains=query)
    )
    
    # Filter for consumables (items without drug reference or in consumables category)
    consumables_qs = InventoryItem.objects.filter(
        search_query,
        is_deleted=False,
        is_active=True
    ).filter(
        Q(drug__isnull=True) | Q(category__name__icontains='consumable')
    )[:20]
    
    results = []
    for item in consumables_qs:
        category_name = item.category.name if item.category else 'Consumable'
        store_name = item.store.name if item.store else 'Unknown Store'
        
        results.append({
            'id': str(item.id),
            'name': item.item_name,
            'code': item.item_code or 'N/A',
            'quantity': item.quantity_on_hand,
            'unit_cost': str(item.unit_cost),
            'category': category_name,
            'store': store_name,
            'display': f"{item.item_name} ({item.item_code or 'No Code'})",
            'subtext': f"Store: {store_name} | Qty: {item.quantity_on_hand} | Price: GHS {item.unit_cost or 0}"
        })
    
    return JsonResponse({'results': results})
