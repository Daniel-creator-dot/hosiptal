"""
Custom template filters for hospital app
"""
from django import template
from django.urls import reverse, NoReverseMatch
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def safe_url(view_name, *args, **kwargs):
    """Resolve a URL by name; returns empty string if not found (e.g. during deployment)."""
    try:
        return reverse(view_name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        return ''


@register.simple_tag
def lab_unit_select(param_name, default_unit, details, options=None):
    """
    Render a dropdown select for lab parameter units.
    Usage: {% lab_unit_select 'rbs' 'mmol/L' details ['mmol/L','mg/dL'] %}
    Or: {% lab_unit_select 'wbc' '×10⁹/L' details %}
    """
    from ..utils_lab_templates import get_param_unit_options
    if options is None:
        options = get_param_unit_options(param_name)
    if not options:
        options = [default_unit]
    saved = (details or {}).get(f'{param_name}_unit', default_unit) or default_unit
    opts_html = ''
    for opt in options:
        sel = ' selected' if str(saved) == str(opt) else ''
        opts_html += f'<option value="{opt}"{sel}>{opt}</option>'
    return mark_safe(f'<select name="{param_name}_unit" class="form-select form-select-sm unit-select" title="Unit">{opts_html}</select>')


@register.simple_tag
def lab_result_entry_url(result):
    """
    URL to enter/save lab results: single-value tests (e.g. D-Dimer) use the simple form;
    panel tests use the tabular form.
    """
    from ..utils_lab_templates import is_single_value_template

    if result is None:
        return ''
    rid = getattr(result, 'pk', None)
    if rid is None:
        return ''
    test = getattr(result, 'test', None)
    try:
        if test and is_single_value_template(test):
            return reverse('hospital:edit_lab_result', kwargs={'result_id': rid})
        return reverse('hospital:tabular_lab_report', kwargs={'result_id': rid})
    except NoReverseMatch:
        return ''


@register.filter
def split(value, arg):
    """Split a string by a delimiter and strip whitespace"""
    if value:
        return [item.strip() for item in value.split(arg) if item.strip()]
    return []


@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    if dictionary and isinstance(dictionary, dict):
        # Convert UUID keys to string for lookup
        if hasattr(key, '__str__'):
            key = str(key)
        return dictionary.get(key, None)
    return None


@register.filter
def replace(value, arg):
    """
    Replace occurrences of a substring in a string.
    Usage: {{ value|replace:"old":"new" }}
    """
    if not value:
        return value
    if ':' not in arg:
        return value
    old, new = arg.split(':', 1)
    return str(value).replace(old, new)


@register.filter
def get_index(list_obj, index):
    """Get item from list by index"""
    try:
        if list_obj and isinstance(list_obj, (list, tuple)):
            idx = int(index)
            if 0 <= idx < len(list_obj):
                return list_obj[idx]
    except (ValueError, TypeError):
        pass
    return None


@register.filter
def is_it_or_admin(user):
    """
    Check if user is IT staff or Admin.
    Returns True if user is:
    - Superuser
    - In IT, it_staff, or IT Operations group
    - Staff with admin profession (as fallback)
    """
    if not user or not user.is_authenticated:
        return False
    
    # Superuser always has access
    if user.is_superuser:
        return True
    
    # Check if user is in IT/Admin groups
    user_groups = user.groups.values_list('name', flat=True)
    for group_name in user_groups:
        group_lower = group_name.lower().replace(' ', '_')
        if group_lower in ['it', 'it_staff', 'it_operations', 'it_support', 'admin', 'administrator']:
            return True
    
    # Do NOT grant admin access based on staff.profession or user.is_staff.
    # Admin/IT access must come from explicit groups or superuser.
    return False


@register.filter
def mul(value, arg):
    """Multiply value by argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def add(value, arg):
    """Add argument to value"""
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        try:
            return int(value) + int(arg)
        except (ValueError, TypeError):
            return value


@register.filter
def sub(value, arg):
    """Subtract argument from value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        try:
            return int(value) - int(arg)
        except (ValueError, TypeError):
            return value


@register.filter
def percentage(value, total):
    """Calculate percentage of value from total"""
    try:
        if not total or total == 0:
            return 0
        return round((float(value) / float(total)) * 100, 1)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.filter(name='humanize_label')
def humanize_label(value):
    """Convert snake_case or underscored text into human readable form"""
    if value is None:
        return ''
    text = str(value)
    return text.replace('_', ' ').strip()


# ---------- Pagination helpers (up to 25 page numbers + Next/Last) ----------

@register.simple_tag(takes_context=True)
def query_string_for_page(context, page_num):
    """Build query string with page=N and all current GET params preserved."""
    request = context.get('request')
    if not request:
        return 'page=%s' % page_num
    q = request.GET.copy()
    q['page'] = page_num
    return q.urlencode()


@register.inclusion_tag('hospital/includes/pagination_enhanced.html', takes_context=True)
def pagination_enhanced(context, page_obj, max_visible=25):
    """
    Render pagination with Page X of Y, up to max_visible page number links, Next, and Last.
    Usage: {% pagination_enhanced page_obj %} or {% pagination_enhanced page_obj 25 %}
    Pass the paginator page object (e.g. page_obj, invoices, encounters) as page_obj.
    """
    if not page_obj or not hasattr(page_obj, 'paginator'):
        return {'page_obj': None, 'page_numbers': []}
    paginator = page_obj.paginator
    current = page_obj.number
    num_pages = paginator.num_pages
    max_visible = min(max(1, int(max_visible)), 25)
    page_numbers = _pagination_window(current, num_pages, max_visible)
    return {
        'page_obj': page_obj,
        'page_numbers': page_numbers,
        'request': context.get('request'),
    }


def _pagination_window(current, num_pages, max_visible):
    """
    Return a list of page numbers and None (for ellipsis) to show in pagination.
    At most max_visible numbers; always includes 1 and num_pages when num_pages > 1.
    """
    if num_pages <= 0:
        return []
    if num_pages <= max_visible:
        return [(i, False) for i in range(1, num_pages + 1)]  # (num, is_ellipsis)
    half = max_visible - 4  # reserve for 1, ellipsis, ..., ellipsis, last
    half = max(half, 3)
    start = max(2, current - half // 2)
    end = min(num_pages - 1, start + half - 1)
    if end - start + 1 < half:
        start = max(2, end - half + 1)
    result = []
    result.append((1, False))
    if start > 2:
        result.append((None, True))
    for i in range(start, end + 1):
        result.append((i, False))
    if end < num_pages - 1:
        result.append((None, True))
    if num_pages > 1:
        result.append((num_pages, False))
    return result


@register.simple_tag
def patient_payer_badges(patient, encounter=None):
    """
    Render deduplicated insurance / corporate payer badges next to patient names.
    Usage: {% load hospital_extras %}
           {% patient_payer_badges patient %}
           {% patient_payer_badges encounter.patient encounter %}
    """
    from hospital.utils_billing import patient_payer_display_labels

    if not patient:
        return ''
    try:
        labels = patient_payer_display_labels(patient, encounter)
    except Exception:
        labels = []
    if not labels:
        return ''
    badge_classes = ('bg-info', 'bg-primary', 'bg-secondary')
    parts = []
    for i, pl in enumerate(labels):
        cls = badge_classes[min(i, len(badge_classes) - 1)]
        text = escape(str(pl))
        parts.append(
            f'<span class="badge {cls} text-wrap ms-1 align-middle" '
            f'style="font-size: 0.75rem; font-weight: 600; max-width: 12rem;" '
            f'title="Insurance or corporate billing">{text}</span>'
        )
    return mark_safe(''.join(parts))
