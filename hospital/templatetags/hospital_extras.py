"""
Custom template filters for hospital app
"""
from django import template

register = template.Library()


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
