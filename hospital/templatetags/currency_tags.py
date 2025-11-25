"""
Custom template tags for currency formatting
Ghana Cedis (GHS) - ₵
"""
from django import template
from decimal import Decimal

register = template.Library()


@register.filter(name='ghs')
def ghs(value):
    """Format value as Ghana Cedis"""
    try:
        amount = Decimal(str(value))
        return f"GHS {amount:,.2f}"
    except:
        return f"GHS 0.00"


@register.filter(name='cedis')
def cedis(value):
    """Format value with Ghana Cedis symbol ₵"""
    try:
        amount = Decimal(str(value))
        return f"₵{amount:,.2f}"
    except:
        return f"₵0.00"


@register.simple_tag
def currency_symbol():
    """Return the currency symbol"""
    return "GHS"


@register.simple_tag
def currency_symbol_native():
    """Return the native currency symbol"""
    return "₵"

























