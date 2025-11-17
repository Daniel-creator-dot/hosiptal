from django import template

from hospital.utils_roles import get_role_navigation

register = template.Library()


@register.simple_tag(takes_context=True)
def role_navigation(context):
    """Return sidebar navigation entries for the current user."""
    request = context.get('request')
    user = getattr(request, 'user', None)
    return get_role_navigation(user) if user else []


@register.filter
def startswith(text, prefix):
    """Template helper to check if text starts with prefix."""
    try:
        return text.startswith(prefix)
    except Exception:
        return False






