"""
Currency utilities for Ghana Cedis
"""

CURRENCY_SYMBOL = "GHS"
CURRENCY_SYMBOL_NATIVE = "₵"
CURRENCY_NAME = "Ghana Cedis"
CURRENCY_CODE = "GHS"


def format_currency(amount):
    """Format amount as Ghana Cedis"""
    try:
        from decimal import Decimal
        value = Decimal(str(amount))
        return f"GHS {value:,.2f}"
    except:
        return "GHS 0.00"


def format_currency_native(amount):
    """Format amount with native symbol ₵"""
    try:
        from decimal import Decimal
        value = Decimal(str(amount))
        return f"₵{value:,.2f}"
    except:
        return "₵0.00"

























