from datetime import timedelta
from django.middleware.csrf import get_token
from django.utils import timezone
from django.db.models import Q
from django.core.cache import cache


def global_csrf_token(request):
    """
    Expose the current CSRF token to all templates so that
    JavaScript can read it via meta tags when cookies are HttpOnly.
    """
    return {
        'global_csrf_token': get_token(request),
    }


# Cache activities for 5 minutes per user to avoid DB hit on every page load
STAFF_ACTIVITIES_CACHE_TTL = 300  # seconds


def staff_activity_reminders(request):
    """Add upcoming hospital activities for staff - visible on ALL dashboards (cached per user)."""
    if not request.user.is_authenticated:
        return {}
    cache_key = f'hms:staff_activities:{request.user.id}'
    try:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        from .models import Staff
        from .models_hr_activities import HospitalActivity
        today = timezone.now().date()
        base_q = Q(all_staff=True)  # Always show all-staff activities
        staff = Staff.objects.filter(user=request.user, is_deleted=False).select_related('department').first()
        if staff:
            base_q |= Q(specific_staff=staff)
            if staff.department_id:
                base_q |= Q(departments=staff.department)
        activities = list(HospitalActivity.objects.filter(
            base_q,
            start_date__gte=today,
            start_date__lte=today + timedelta(days=30),
            is_deleted=False,
            is_published=True
        ).order_by('start_date', 'start_time')[:15])
        result = {
            'global_upcoming_activities': activities,
            'global_next_activity': activities[0] if activities else None,
        }
        cache.set(cache_key, result, STAFF_ACTIVITIES_CACHE_TTL)
        return result
    except Exception:
        return {}


