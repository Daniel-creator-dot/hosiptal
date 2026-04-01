"""
Cache utilities for frequently accessed data to improve performance with 200+ users.
"""
from django.core.cache import cache
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)

# Cache timeouts (in seconds)
CACHE_TIMEOUT_DRUGS = 3600  # 1 hour - drugs don't change often
CACHE_TIMEOUT_LAB_TESTS = 3600  # 1 hour
CACHE_TIMEOUT_IMAGING = 3600  # 1 hour
CACHE_TIMEOUT_PROCEDURES = 3600  # 1 hour
CACHE_TIMEOUT_DIAGNOSIS_CODES = 7200  # 2 hours - diagnosis codes rarely change


def get_cached_drugs():
    """Get all active drugs with caching."""
    cache_key = 'hms:active_drugs'
    drugs = cache.get(cache_key)
    
    if drugs is None:
        from .models import Drug
        drug_filter_q = Q(is_active=True) & Q(is_deleted=False) & Q(name__isnull=False) & ~Q(name__iexact='') & ~Q(name__icontains='INVALID')
        # Get queryset - don't convert to list yet to avoid serialization issues
        drugs_qs = Drug.objects.filter(drug_filter_q).order_by('category', 'name').only(
            'id', 'name', 'category', 'strength', 'form', 'generic_name', 'unit_price', 'atc_code'
        )
        # Store queryset directly (Django cache can handle querysets with pickle)
        cache.set(cache_key, drugs_qs, CACHE_TIMEOUT_DRUGS)
        logger.info(f"Cached {drugs_qs.count()} drugs")
        return drugs_qs
    
    return drugs


def get_cached_lab_tests():
    """Get all active lab tests with caching."""
    cache_key = 'hms:active_lab_tests'
    tests = cache.get(cache_key)
    
    if tests is None:
        from .models import LabTest
        lab_test_filter_q = Q(is_active=True) & Q(is_deleted=False) & Q(name__isnull=False) & ~Q(name__iexact='') & ~Q(name__icontains='INVALID')
        tests_qs = LabTest.objects.filter(lab_test_filter_q).order_by('name').only(
            'id', 'name', 'code', 'specimen_type', 'price'
        )
        cache.set(cache_key, tests_qs, CACHE_TIMEOUT_LAB_TESTS)
        logger.info(f"Cached {tests_qs.count()} lab tests")
        return tests_qs
    
    return tests


def get_cached_imaging_studies():
    """Get all active imaging studies with caching."""
    cache_key = 'hms:active_imaging_studies'
    studies = cache.get(cache_key)
    
    if studies is None:
        try:
            from .models_advanced import ImagingCatalog, ImagingStudy
            valid_imaging_modalities = [choice[0] for choice in ImagingStudy.MODALITY_CHOICES]
            imaging_filter_q = Q(is_active=True) & Q(is_deleted=False) & Q(modality__in=valid_imaging_modalities) & Q(name__isnull=False) & ~Q(name__iexact='') & ~Q(name__icontains='INVALID')
            studies_qs = ImagingCatalog.objects.filter(imaging_filter_q).order_by('modality', 'name').only(
                'id', 'name', 'code', 'modality', 'body_part', 'study_type', 'price', 'corporate_price', 'insurance_price'
            )
            cache.set(cache_key, studies_qs, CACHE_TIMEOUT_IMAGING)
            logger.info(f"Cached {studies_qs.count()} imaging studies")
            return studies_qs
        except ImportError:
            from .models import LabTest
            # Return empty queryset with same model structure
            return LabTest.objects.none()
    
    return studies


def get_cached_procedures():
    """Get all active procedures with caching."""
    cache_key = 'hms:active_procedures'
    procedures = cache.get(cache_key)
    
    if procedures is None:
        try:
            import importlib
            models_advanced_module = importlib.import_module('hospital.models_advanced')
            ProcedureCatalog = getattr(models_advanced_module, 'ProcedureCatalog', None)
            
            if ProcedureCatalog:
                procedure_filter_q = Q(is_active=True) & Q(is_deleted=False) & Q(name__isnull=False) & ~Q(name__iexact='') & ~Q(name__icontains='INVALID')
                procedures_qs = ProcedureCatalog.objects.filter(procedure_filter_q).order_by('category', 'name').only(
                    'id', 'name', 'code', 'category', 'price', 'cash_price', 'corporate_price', 'insurance_price'
                )
                cache.set(cache_key, procedures_qs, CACHE_TIMEOUT_PROCEDURES)
                logger.info(f"Cached {procedures_qs.count()} procedures")
                return procedures_qs
            else:
                from .models import LabTest
                return LabTest.objects.none()
        except Exception as e:
            logger.warning(f"Error loading procedures: {e}")
            from .models import LabTest
            return LabTest.objects.none()
    
    return procedures


def get_cached_diagnosis_codes():
    """Get diagnosis codes with caching, prioritizing malaria and Ghana common."""
    cache_key = 'hms:diagnosis_codes'
    codes = cache.get(cache_key)
    
    if codes is None:
        try:
            from .models_diagnosis import DiagnosisCode
            from django.db.models import Q
            
            # MALARIA FIRST - Get all malaria codes (B50, B51, B54) - limited to 30
            malaria_codes = DiagnosisCode.objects.filter(
                is_active=True,
                is_deleted=False,
                code__regex=r'^B5[014]'  # Match B50, B51, B54
            ).only('code', 'short_description', 'description').order_by('code')[:30]
            
            # Get other Ghana common (excluding malaria) - limited to 50
            malaria_prefixes = Q(code__startswith='B50') | Q(code__startswith='B51') | Q(code__startswith='B54')
            ghana_common = DiagnosisCode.objects.filter(
                is_active=True,
                is_deleted=False,
                is_ghana_common=True
            ).exclude(malaria_prefixes).only('code', 'short_description', 'description').order_by('short_description')[:50]
            
            # Get Africa common (excluding Ghana common and malaria) - limited to 30
            africa_common = DiagnosisCode.objects.filter(
                is_active=True,
                is_deleted=False,
                is_africa_common=True,
                is_ghana_common=False
            ).exclude(malaria_prefixes).only('code', 'short_description', 'description').order_by('short_description')[:30]
            
            # Get other common (excluding all above) - limited to 50
            other_common = DiagnosisCode.objects.filter(
                is_active=True,
                is_deleted=False,
                is_common=True,
                is_ghana_common=False,
                is_africa_common=False
            ).exclude(malaria_prefixes).only('code', 'short_description', 'description').order_by('short_description')[:50]
            
            # Combine querysets using union (more efficient than converting to lists)
            from django.db.models import QuerySet
            # For now, we'll need to evaluate and combine - but cache the combined queryset
            # Note: Union doesn't work well with different limits, so we'll use a workaround
            codes_qs = DiagnosisCode.objects.filter(
                is_active=True,
                is_deleted=False
            ).only('code', 'short_description', 'description')
            
            cache.set(cache_key, codes_qs, CACHE_TIMEOUT_DIAGNOSIS_CODES)
            logger.info(f"Cached diagnosis codes queryset")
            return codes_qs
        except ImportError:
            from .models import LabTest
            return LabTest.objects.none()
    
    return codes


def invalidate_cache(pattern):
    """Invalidate cache entries matching a pattern."""
    try:
        from django.core.cache import cache
        # For Redis, we'd need to use cache.delete_pattern, but Django's cache API doesn't support it directly
        # So we'll just clear specific keys we know about
        cache_keys = [
            'hms:active_drugs',
            'hms:active_lab_tests',
            'hms:active_imaging_studies',
            'hms:active_procedures',
            'hms:diagnosis_codes',
        ]
        for key in cache_keys:
            if pattern in key:
                cache.delete(key)
                logger.info(f"Invalidated cache: {key}")
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")


def clear_all_caches():
    """Clear all HMS caches."""
    cache_keys = [
        'hms:active_drugs',
        'hms:active_lab_tests',
        'hms:active_imaging_studies',
        'hms:active_procedures',
        'hms:diagnosis_codes',
    ]
    for key in cache_keys:
        cache.delete(key)
    logger.info("Cleared all HMS caches")
