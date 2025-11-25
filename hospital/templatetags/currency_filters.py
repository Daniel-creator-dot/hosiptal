"""
Custom template filters for currency formatting in Ghana Cedis (GHS)
"""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def cedis(value, decimal_places=2):
    """
    Format number as Ghana Cedis (GHS)
    
    Usage: {{ amount|cedis }} or {{ amount|cedis:0 }} for no decimals
    """
    if value is None:
        return mark_safe('<span class="text-muted">-</span>')
    
    try:
        if decimal_places == 0:
            formatted = f"{float(value):,.0f}"
        else:
            formatted = f"{float(value):,.{decimal_places}f}"
        return mark_safe(f'GHS {formatted}')
    except (ValueError, TypeError):
        return mark_safe('<span class="text-muted">-</span>')


@register.filter
def cedis_symbol(value, decimal_places=2):
    """
    Format number as Ghana Cedis with symbol (₵)
    
    Usage: {{ amount|cedis_symbol }}
    """
    if value is None:
        return mark_safe('<span class="text-muted">-</span>')
    
    try:
        if decimal_places == 0:
            formatted = f"{float(value):,.0f}"
        else:
            formatted = f"{float(value):,.{decimal_places}f}"
        return mark_safe(f'₵{formatted}')
    except (ValueError, TypeError):
        return mark_safe('<span class="text-muted">-</span>')






































