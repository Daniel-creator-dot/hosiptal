"""
Go-live date (settings.BILLS_LIST_GO_LIVE_DATE) for billing UIs: list filters and
hiding pre-go-live registration fee lines on itemized views.
"""
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings


def get_bills_go_live_date():
    raw = getattr(settings, 'BILLS_LIST_GO_LIVE_DATE', None)
    if raw is None:
        return date(2026, 3, 10)
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        return date.fromisoformat(raw.strip()[:10])
    return date(2026, 3, 10)


def resolve_date_from_for_listing(date_from_raw: str, include_legacy: bool) -> tuple[str, str]:
    """
    Returns (date_from_effective, date_from_form_value) as ISO date strings.
    date_from_effective is '' when include_legacy and no from-date (no lower bound).
    """
    floor = get_bills_go_live_date()
    if include_legacy:
        return (date_from_raw if date_from_raw else ''), date_from_raw
    if not date_from_raw:
        return floor.isoformat(), floor.isoformat()
    try:
        ud = date.fromisoformat(date_from_raw)
        ed = max(ud, floor)
        return ed.isoformat(), date_from_raw
    except ValueError:
        return floor.isoformat(), floor.isoformat()


def invoice_line_effective_date(line):
    if getattr(line, 'created', None):
        c = line.created
        if isinstance(c, datetime):
            return c.date()
        if isinstance(c, date):
            return c
    inv = getattr(line, 'invoice', None)
    if inv is not None and getattr(inv, 'issued_at', None):
        ia = inv.issued_at
        return ia.date() if isinstance(ia, datetime) else ia
    return None


def is_registration_invoice_line(line):
    sc = getattr(line, 'service_code', None)
    if sc:
        code = (getattr(sc, 'code', None) or '').strip().upper()
        if code in frozenset({'REG', 'REG-FEE', 'REGISTRATION', 'PAT-REG', 'PAT_REG'}):
            return True
        if code.startswith('REG'):
            return True
        cat = getattr(sc, 'category', None)
        if cat is not None and str(cat).strip().lower() == 'registration':
            return True
    desc = (getattr(line, 'description', None) or '').lower()
    if 'registration fee' in desc:
        return True
    if desc.strip() == 'registration':
        return True
    if 'registration' in desc and 'deregistration' not in desc and 'deregister' not in desc:
        if 'fee' in desc or len(desc) < 45:
            return True
    return False


def should_hide_pre_go_live_registration_line(line, *, include_legacy: bool) -> bool:
    if include_legacy:
        return False
    if not is_registration_invoice_line(line):
        return False
    eff = invoice_line_effective_date(line)
    if eff is None:
        return False
    return eff < get_bills_go_live_date()


def filter_visible_invoice_lines(lines, *, include_legacy: bool):
    """Returns (visible_lines, hidden_count, hidden_amount)."""
    visible = []
    h_count = 0
    h_amt = Decimal('0')
    for line in lines:
        if should_hide_pre_go_live_registration_line(line, include_legacy=include_legacy):
            h_count += 1
            h_amt += line.display_line_total or Decimal('0')
            continue
        visible.append(line)
    return visible, h_count, h_amt
