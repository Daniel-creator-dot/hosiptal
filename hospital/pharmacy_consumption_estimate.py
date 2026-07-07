"""
Estimated pharmacy stock movement from recent dispensing, walk-in sales, and losses.

Used for reorder planning: average daily outflow, days of cover at drug level, and
suggested procurement quantities (heuristic).
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from datetime import date as date_cls
from datetime import datetime as dt_cls
from datetime import timedelta

from django.db.models import F, Max, Q, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

DEFAULT_MOVEMENT_WINDOW_DAYS = 30
DEFAULT_COVER_ALERT_DAYS = 14
DEFAULT_ORDER_HORIZON_DAYS = 28


def parse_positive_int(raw: Any, default: int, max_val: int = 365) -> int:
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return default
    if v < 1:
        return default
    return min(v, max_val)


def _dedupe_drug_ids(drug_ids: list) -> list:
    """Preserve primary-key type (e.g. UUID) and return a stable sorted list."""
    seen: set[Any] = set()
    out: list[Any] = []
    for x in drug_ids:
        if x is None:
            continue
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    out.sort(key=lambda z: str(z))
    return out


def _merge_qty_maps(*maps: dict[int, int]) -> dict[int, int]:
    out: dict[int, int] = defaultdict(int)
    for m in maps:
        for k, v in m.items():
            out[k] += int(v or 0)
    return dict(out)


def drug_ids_with_outflow_since(start_dt, end_dt=None) -> set[int]:
    """Distinct drug IDs with any inpatient/OTC dispensing or recorded loss in ``[start_dt, end_dt]``."""
    from .models import PharmacyStockLoss
    from .models_payment_verification import PharmacyDispenseHistory
    from .models_pharmacy_walkin import WalkInPharmacySaleItem

    end_dt = end_dt if end_dt is not None else timezone.now()

    ids: set[int] = set()
    rx_q = PharmacyDispenseHistory.objects.filter(
        is_deleted=False,
        dispensed_at__gte=start_dt,
        dispensed_at__lte=end_dt,
        drug_id__isnull=False,
    )
    for did in rx_q.values_list('drug_id', flat=True).distinct():
        if did:
            ids.add(did)
    walk_qs = (
        WalkInPharmacySaleItem.objects.filter(
            is_deleted=False,
            sale__is_deleted=False,
            sale__is_dispensed=True,
            drug_id__isnull=False,
        )
        .annotate(
            consumed_at=Coalesce(F('sale__dispensed_at'), F('sale__sale_date')),
        )
        .filter(consumed_at__gte=start_dt, consumed_at__lte=end_dt)
    )
    for did in walk_qs.values_list('drug_id', flat=True).distinct():
        if did:
            ids.add(did)
    for did in (
        PharmacyStockLoss.objects.filter(
            is_deleted=False,
            created__gte=start_dt,
            created__lte=end_dt,
            pharmacy_stock__drug_id__isnull=False,
        )
        .values_list('pharmacy_stock__drug_id', flat=True)
        .distinct()
    ):
        if did:
            ids.add(did)
    return ids


def drug_ids_for_utilization_report(
    start_dt,
    *,
    include_stock_catalog: bool = False,
    end_dt=None,
) -> list[int]:
    """
    Drug IDs for a utilization / consumption report.

    Always includes drugs that had any outflow since ``start_dt``. Optionally unions drugs
    that still appear on ``PharmacyStock`` or pharmacy ``InventoryItem`` rows (zero movement).
    """
    ids = drug_ids_with_outflow_since(start_dt, end_dt=end_dt)
    if include_stock_catalog:
        from .models import PharmacyStock
        from .models_procurement import InventoryCategory, InventoryItem

        ids.update(
            x
            for x in PharmacyStock.objects.filter(is_deleted=False).values_list(
                'drug_id', flat=True
            )
            if x
        )
        cat = InventoryCategory.objects.filter(is_for_pharmacy=True, is_active=True).first()
        if cat:
            ids.update(
                x
                for x in InventoryItem.objects.filter(
                    category=cat,
                    is_deleted=False,
                    drug_id__isnull=False,
                ).values_list('drug_id', flat=True)
                if x
            )
    return sorted(ids)


def drug_outflow_channel_maps_in_window(
    drug_ids: list[int],
    start_dt,
    end_dt=None,
) -> tuple[dict[int, int], dict[int, int], dict[int, int]]:
    """
    Per-drug units: inpatient/encounter dispensing (rx), walk-in OTC (walk_in), recorded losses (loss).
    """
    if not drug_ids:
        return {}, {}, {}

    from .models import PharmacyStockLoss
    from .models_payment_verification import PharmacyDispenseHistory
    from .models_pharmacy_walkin import WalkInPharmacySaleItem

    end_dt = end_dt if end_dt is not None else timezone.now()

    rx_rows = (
        PharmacyDispenseHistory.objects.filter(
            is_deleted=False,
            drug_id__in=drug_ids,
            dispensed_at__gte=start_dt,
            dispensed_at__lte=end_dt,
        )
        .values('drug_id')
        .annotate(total=Sum('quantity_dispensed'))
    )
    rx_map = {r['drug_id']: int(r['total'] or 0) for r in rx_rows if r['drug_id']}

    walk_rows = (
        WalkInPharmacySaleItem.objects.filter(
            is_deleted=False,
            sale__is_deleted=False,
            sale__is_dispensed=True,
            drug_id__in=drug_ids,
        )
        .annotate(
            consumed_at=Coalesce(F('sale__dispensed_at'), F('sale__sale_date')),
        )
        .filter(consumed_at__gte=start_dt, consumed_at__lte=end_dt)
        .values('drug_id')
        .annotate(total=Sum('quantity'))
    )
    walk_map = {r['drug_id']: int(r['total'] or 0) for r in walk_rows if r['drug_id']}

    loss_rows = (
        PharmacyStockLoss.objects.filter(
            is_deleted=False,
            created__gte=start_dt,
            created__lte=end_dt,
            pharmacy_stock__drug_id__in=drug_ids,
        )
        .values('pharmacy_stock__drug_id')
        .annotate(total=Sum('quantity'))
    )
    loss_map = {
        r['pharmacy_stock__drug_id']: int(r['total'] or 0)
        for r in loss_rows
        if r['pharmacy_stock__drug_id']
    }

    return rx_map, walk_map, loss_map


def drug_outflow_totals_in_window(
    drug_ids: list[int],
    start_dt,
    end_dt=None,
) -> dict[int, int]:
    """Units leaving pharmacy stock via dispensing + walk-in + recorded losses."""
    rx_map, walk_map, loss_map = drug_outflow_channel_maps_in_window(
        drug_ids, start_dt, end_dt=end_dt
    )
    return _merge_qty_maps(rx_map, walk_map, loss_map)


def global_outflow_by_channel_since(start_dt, end_dt=None) -> dict[str, int]:
    """Site-wide units out by channel in ``[start_dt, end_dt]`` (not broken down by drug)."""
    from .models import PharmacyStockLoss
    from .models_payment_verification import PharmacyDispenseHistory
    from .models_pharmacy_walkin import WalkInPharmacySaleItem

    end_dt = end_dt if end_dt is not None else timezone.now()

    rx = (
        PharmacyDispenseHistory.objects.filter(
            is_deleted=False,
            drug_id__isnull=False,
            dispensed_at__gte=start_dt,
            dispensed_at__lte=end_dt,
        ).aggregate(t=Sum('quantity_dispensed'))['t']
        or 0
    )
    walk = (
        WalkInPharmacySaleItem.objects.filter(
            is_deleted=False,
            sale__is_deleted=False,
            sale__is_dispensed=True,
            drug_id__isnull=False,
        )
        .annotate(
            consumed_at=Coalesce(F('sale__dispensed_at'), F('sale__sale_date')),
        )
        .filter(consumed_at__gte=start_dt, consumed_at__lte=end_dt)
        .aggregate(t=Sum('quantity'))['t']
        or 0
    )
    loss = (
        PharmacyStockLoss.objects.filter(
            is_deleted=False,
            created__gte=start_dt,
            created__lte=end_dt,
        ).aggregate(t=Sum('quantity'))['t']
        or 0
    )
    rx_i, walk_i, loss_i = int(rx), int(walk), int(loss)
    return {
        'rx': rx_i,
        'walk_in': walk_i,
        'loss': loss_i,
        'total': rx_i + walk_i + loss_i,
    }


def daily_global_outflow_counts(start_dt, end_dt=None) -> list[dict[str, Any]]:
    """
    Per calendar day (hospital TZ) merged rx + walk-in + loss totals for charts.

    Returns sorted list of dicts: ``date`` (``date``), ``date_iso``, ``rx``, ``walk_in``, ``loss``, ``total``.
    """
    from .models import PharmacyStockLoss
    from .models_payment_verification import PharmacyDispenseHistory
    from .models_pharmacy_walkin import WalkInPharmacySaleItem

    end_dt = end_dt if end_dt is not None else timezone.now()
    tz = timezone.get_current_timezone()

    by_day: dict[Any, dict[str, int]] = defaultdict(lambda: {'rx': 0, 'walk_in': 0, 'loss': 0})

    def _norm_day(val):
        if val is None:
            return None
        if isinstance(val, dt_cls):
            return timezone.localtime(val, tz).date()
        if isinstance(val, date_cls):
            return val
        if isinstance(val, str):
            try:
                return dt_cls.strptime(val[:10], '%Y-%m-%d').date()
            except Exception:
                return None
        return None

    for r in (
        PharmacyDispenseHistory.objects.filter(
            is_deleted=False,
            drug_id__isnull=False,
            dispensed_at__gte=start_dt,
            dispensed_at__lte=end_dt,
        )
        .annotate(d=TruncDate('dispensed_at', tzinfo=tz))
        .values('d')
        .annotate(total=Sum('quantity_dispensed'))
    ):
        d = _norm_day(r['d'])
        if d:
            by_day[d]['rx'] += int(r['total'] or 0)

    for r in (
        WalkInPharmacySaleItem.objects.filter(
            is_deleted=False,
            sale__is_deleted=False,
            sale__is_dispensed=True,
            drug_id__isnull=False,
        )
        .annotate(
            consumed_at=Coalesce(F('sale__dispensed_at'), F('sale__sale_date')),
        )
        .filter(consumed_at__gte=start_dt, consumed_at__lte=end_dt)
        .annotate(d=TruncDate('consumed_at', tzinfo=tz))
        .values('d')
        .annotate(total=Sum('quantity'))
    ):
        d = _norm_day(r['d'])
        if d:
            by_day[d]['walk_in'] += int(r['total'] or 0)

    for r in (
        PharmacyStockLoss.objects.filter(
            is_deleted=False,
            created__gte=start_dt,
            created__lte=end_dt,
        )
        .annotate(d=TruncDate('created', tzinfo=tz))
        .values('d')
        .annotate(total=Sum('quantity'))
    ):
        d = _norm_day(r['d'])
        if d:
            by_day[d]['loss'] += int(r['total'] or 0)

    d0 = timezone.localtime(start_dt, tz).date()
    d1 = timezone.localtime(end_dt, tz).date()
    out: list[dict[str, Any]] = []
    cur = d0
    while cur <= d1:
        bucket = by_day.get(cur, {'rx': 0, 'walk_in': 0, 'loss': 0})
        rx_i = int(bucket['rx'])
        wi = int(bucket['walk_in'])
        lo = int(bucket['loss'])
        tot = rx_i + wi + lo
        out.append(
            {
                'date': cur,
                'date_iso': cur.isoformat(),
                'rx': rx_i,
                'walk_in': wi,
                'loss': lo,
                'total': tot,
            }
        )
        cur += timedelta(days=1)

    return out


def drug_batch_position_map(drug_ids: list[int]) -> dict[int, dict[str, Any]]:
    """Per-drug totals from PharmacyStock batches (sellable batches)."""
    if not drug_ids:
        return {}

    from .models import PharmacyStock

    rows = (
        PharmacyStock.objects.filter(is_deleted=False, drug_id__in=drug_ids)
        .values('drug_id')
        .annotate(
            total_on_hand=Sum('quantity_on_hand'),
            reorder_any=Max('reorder_level'),
            reorder_active=Max('reorder_level', filter=Q(quantity_on_hand__gt=0)),
        )
    )
    out: dict[int, dict[str, Any]] = {}
    for r in rows:
        did = r['drug_id']
        total_on_hand = int(r['total_on_hand'] or 0)
        r_active = r['reorder_active']
        reorder_point = int(r_active if r_active is not None else (r['reorder_any'] or 0))
        out[did] = {
            'total_on_hand': total_on_hand,
            'reorder_point': reorder_point,
        }
    return out


def compute_pharmacy_drug_movement_metrics(
    drug_ids: list[int],
    *,
    movement_window_days: int = DEFAULT_MOVEMENT_WINDOW_DAYS,
    cover_alert_days: int = DEFAULT_COVER_ALERT_DAYS,
    order_horizon_days: int = DEFAULT_ORDER_HORIZON_DAYS,
    window_start=None,
    window_end=None,
) -> dict[int, dict[str, Any]]:
    """
    Returns per drug_id:
      - total_out_window: units in window
      - out_rx, out_walk_in, out_loss; pct_rx, pct_walk_in, pct_loss (0--100 floats)
      - avg_daily_out: float
      - total_on_hand, reorder_point (batch aggregates)
      - days_cover: None if no consumption signal
      - suggested_order_qty: int heuristic for procurement line
      - is_runout_risk: True if cover below alert or static low with no history

    If ``window_start`` and ``window_end`` are set (e.g. calendar month), they define the
    inclusive reporting window in real time; average daily out divides by inclusive local
    calendar day count. Otherwise a rolling window of ``movement_window_days`` ending at
    ``timezone.now()`` is used (divisor = movement_window_days, unchanged from legacy).
    """
    drug_ids = _dedupe_drug_ids(list(drug_ids))
    if not drug_ids:
        return {}

    tz = timezone.get_current_timezone()
    now = timezone.now()

    if window_start is not None and window_end is not None:
        start_dt = window_start
        end_dt = window_end
        d0 = timezone.localtime(start_dt, tz).date()
        d1 = timezone.localtime(end_dt, tz).date()
        window_days = max(1, (d1 - d0).days + 1)
    else:
        window_days = max(1, int(movement_window_days))
        end_dt = now
        start_dt = end_dt - timezone.timedelta(days=window_days)

    rx_map, walk_map, loss_map = drug_outflow_channel_maps_in_window(
        drug_ids, start_dt, end_dt=end_dt
    )
    outflow = _merge_qty_maps(rx_map, walk_map, loss_map)
    positions = drug_batch_position_map(drug_ids)

    metrics: dict[int, dict[str, Any]] = {}
    for did in drug_ids:
        total_out = int(outflow.get(did, 0))
        o_rx = int(rx_map.get(did, 0))
        o_wi = int(walk_map.get(did, 0))
        o_lo = int(loss_map.get(did, 0))
        avg_daily = total_out / float(window_days)
        pos = positions.get(did) or {'total_on_hand': 0, 'reorder_point': 0}
        total_on_hand = int(pos['total_on_hand'])
        reorder_point = int(pos['reorder_point'] or 0)

        if avg_daily > 0:
            days_cover = total_on_hand / avg_daily
        else:
            days_cover = None

        deficit_below_reorder = max(0, reorder_point - total_on_hand)
        if avg_daily > 0:
            target_level = reorder_point + int(
                math.ceil(order_horizon_days * avg_daily)
            )
            suggested_order_qty = max(0, target_level - total_on_hand)
        else:
            suggested_order_qty = deficit_below_reorder
        suggested_order_qty = int(min(999_999, suggested_order_qty))

        is_runout_risk = False
        if avg_daily > 0 and days_cover is not None:
            if days_cover < float(cover_alert_days):
                is_runout_risk = True
        else:
            if total_on_hand <= reorder_point:
                is_runout_risk = True

        if total_out > 0:
            pct_rx = 100.0 * o_rx / float(total_out)
            pct_walk_in = 100.0 * o_wi / float(total_out)
            pct_loss = 100.0 * o_lo / float(total_out)
        else:
            pct_rx = pct_walk_in = pct_loss = 0.0

        metrics[did] = {
            'window_days': window_days,
            'total_out_window': total_out,
            'out_rx': o_rx,
            'out_walk_in': o_wi,
            'out_loss': o_lo,
            'pct_rx': pct_rx,
            'pct_walk_in': pct_walk_in,
            'pct_loss': pct_loss,
            'avg_daily_out': avg_daily,
            'avg_daily_out_display': f'{avg_daily:.2f}',
            'total_on_hand': total_on_hand,
            'reorder_point': reorder_point,
            'days_cover': days_cover,
            'days_cover_display': (
                f'{days_cover:.1f} d' if days_cover is not None else '—'
            ),
            'suggested_order_qty': suggested_order_qty,
            'is_runout_risk': is_runout_risk,
        }
    return metrics


TOP_DRUG_RANK_LIMIT = 40


def top_expensive_formulary_drugs(limit: int = TOP_DRUG_RANK_LIMIT) -> list[dict[str, Any]]:
    """Active formulary drugs ranked by selling price (unit_price), highest first."""
    from decimal import Decimal

    from .models import Drug

    drugs = list(
        Drug.objects.filter(
            is_active=True,
            is_deleted=False,
            unit_price__gt=0,
        ).order_by('-unit_price', 'name')[:limit]
    )
    if not drugs:
        return []

    positions = drug_batch_position_map([d.id for d in drugs])
    rows: list[dict[str, Any]] = []
    for rank, drug in enumerate(drugs, 1):
        on_hand = int((positions.get(drug.id) or {}).get('total_on_hand', 0))
        unit_price = Decimal(str(drug.unit_price or 0))
        rows.append(
            {
                'rank': rank,
                'drug': drug,
                'unit_price': unit_price,
                'cost_price': Decimal(str(drug.cost_price or 0)),
                'total_on_hand': on_hand,
                'stock_value': unit_price * on_hand,
            }
        )
    return rows


def top_moving_drugs_ranked(
    start_dt,
    *,
    end_dt=None,
    movement_window_days: int = DEFAULT_MOVEMENT_WINDOW_DAYS,
    window_start=None,
    window_end=None,
    limit: int = TOP_DRUG_RANK_LIMIT,
) -> list[dict[str, Any]]:
    """Top drugs by units out in the reporting window (global, ignores table filters)."""
    from .models import Drug

    drug_ids = sorted(drug_ids_with_outflow_since(start_dt, end_dt=end_dt))
    if not drug_ids:
        return []

    if window_start is not None and window_end is not None:
        metrics = compute_pharmacy_drug_movement_metrics(
            drug_ids,
            movement_window_days=movement_window_days,
            window_start=window_start,
            window_end=window_end,
        )
    else:
        metrics = compute_pharmacy_drug_movement_metrics(
            drug_ids,
            movement_window_days=movement_window_days,
        )

    ranked = sorted(
        metrics.items(),
        key=lambda x: (-int(x[1].get('total_out_window', 0) or 0), str(x[0])),
    )[:limit]
    drug_map = {
        d.id: d for d in Drug.objects.filter(id__in=[did for did, _ in ranked])
    }

    rows: list[dict[str, Any]] = []
    for rank, (did, m) in enumerate(ranked, 1):
        drug = drug_map.get(did)
        if drug is None:
            continue
        rows.append({'rank': rank, 'drug': drug, 'm': m})
    return rows


def apply_movement_risk_filter(
    stock_qs,
    inventory_qs,
    drug_metrics: dict[int, dict[str, Any]],
):
    risk_ids = [did for did, m in drug_metrics.items() if m.get('is_runout_risk')]
    if not risk_ids:
        return stock_qs.none(), inventory_qs.none()
    return (
        stock_qs.filter(drug_id__in=risk_ids),
        inventory_qs.filter(drug_id__in=risk_ids),
    )
