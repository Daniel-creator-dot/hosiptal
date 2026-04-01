from django import template

from hospital.utils_roles import get_role_navigation

register = template.Library()


@register.simple_tag(takes_context=True)
def role_navigation(context):
    """Return sidebar navigation entries for the current user."""
    request = context.get('request')
    user = getattr(request, 'user', None)
    if not user:
        return []

    items = list(get_role_navigation(user) or [])

    # Safety fallback: procurement/stores users should always see Pharmacy entry.
    # This keeps navigation correct even when a user has mixed groups/professions.
    try:
        from hospital.utils_roles import is_procurement_staff
        if is_procurement_staff(user):
            has_pharmacy = any((it.get('url') or '').startswith('/hms/pharmacy/') for it in items if isinstance(it, dict))
            if not has_pharmacy:
                items.insert(1, {'title': 'Pharmacy', 'url': '/hms/pharmacy/', 'icon': 'capsule'})
    except Exception:
        pass

    return items


@register.filter
def startswith(text, prefix):
    """Template helper to check if text starts with prefix."""
    try:
        return text.startswith(prefix)
    except Exception:
        return False












