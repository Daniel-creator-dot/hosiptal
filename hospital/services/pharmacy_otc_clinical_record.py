"""
OTC (walk-in prescribe) dispensing on the patient chart and medical-record folders.
Consumables billing is invoice-only and is intentionally excluded here.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from django.utils import timezone

logger = logging.getLogger(__name__)

OTC_RECORD_TYPE = 'otc'
OTC_RECORD_TITLE_PREFIX = 'OTC Pharmacy'


def _sale_items_payload(sale):
    lines = []
    for item in sale.items.filter(is_deleted=False).select_related('drug'):
        drug = item.drug
        name = drug.name if drug else 'Drug'
        if drug and getattr(drug, 'strength', None):
            name = f"{drug.name} {drug.strength}"
        lines.append({
            'drug': name,
            'quantity': item.quantity,
            'instructions': (item.dosage_instructions or '').strip(),
        })
    return lines


def _build_otc_record_content(sale, items_payload) -> str:
    dispensed_at = sale.dispensed_at or timezone.now()
    served = ''
    if sale.dispensed_by and getattr(sale.dispensed_by, 'user', None):
        served = sale.dispensed_by.user.get_full_name() or sale.dispensed_by.user.username
    elif sale.served_by and getattr(sale.served_by, 'user', None):
        served = sale.served_by.user.get_full_name() or sale.served_by.user.username

    lines_txt = []
    for row in items_payload:
        instr = f" — {row['instructions']}" if row.get('instructions') else ''
        lines_txt.append(f"- {row['drug']} x{row['quantity']}{instr}")

    counselling = (sale.counselling_notes or '').strip()
    parts = [
        f"OTC pharmacy dispensing ({sale.sale_number})",
        f"Dispensed: {dispensed_at.strftime('%Y-%m-%d %H:%M')}",
    ]
    if served:
        parts.append(f"Pharmacist: {served}")
    if counselling:
        parts.append(f"Counselling: {counselling}")
    parts.append('')
    parts.append('Items:')
    parts.extend(lines_txt or ['- (no line items recorded)'])
    parts.append('')
    parts.append(f"Sale ID: {sale.id}")
    return '\n'.join(parts)


def sync_otc_medical_record_for_sale(sale) -> Optional['MedicalRecord']:
    """
    Create or update a medical-record folder entry when an OTC sale is dispensed.
    """
    if not sale or not getattr(sale, 'is_dispensed', False):
        return None
    patient = sale.patient
    if not patient:
        return None

    from hospital.models import MedicalRecord

    title = f"{OTC_RECORD_TITLE_PREFIX} - {sale.sale_number}"
    items_payload = _sale_items_payload(sale)
    content = _build_otc_record_content(sale, items_payload)

    record = MedicalRecord.objects.filter(
        patient=patient,
        record_type=OTC_RECORD_TYPE,
        title=title,
        is_deleted=False,
    ).first()
    if record:
        record.content = content
        if sale.dispensed_by and not record.created_by_id:
            record.created_by = sale.dispensed_by
        record.save()
        return record

    try:
        return MedicalRecord.objects.create(
            patient=patient,
            encounter=None,
            record_type=OTC_RECORD_TYPE,
            title=title,
            content=content,
            created_by=sale.dispensed_by or sale.served_by,
        )
    except Exception:
        logger.exception('Failed to create OTC medical record for sale %s', sale.sale_number)
        return None


def get_patient_otc_dispenses(patient, limit: int = 50) -> List[dict]:
    """Dispensed OTC sales for patient file (doctors see meds, not prices)."""
    from hospital.models import MedicalRecord
    from hospital.models_pharmacy_walkin import WalkInPharmacySale

    if not patient:
        return []

    sales = (
        WalkInPharmacySale.objects.filter(
            patient=patient,
            is_deleted=False,
            is_dispensed=True,
        )
        .select_related('dispensed_by__user', 'served_by__user')
        .prefetch_related('items__drug')
        .order_by('-dispensed_at', '-sale_date')[:limit]
    )

    rows = []
    for sale in sales:
        title = f"{OTC_RECORD_TITLE_PREFIX} - {sale.sale_number}"
        if not MedicalRecord.objects.filter(
            patient=patient,
            record_type=OTC_RECORD_TYPE,
            title=title,
            is_deleted=False,
        ).exists():
            sync_otc_medical_record_for_sale(sale)
        items = []
        for item in sale.items.filter(is_deleted=False):
            drug = item.drug
            label = drug.name if drug else 'Drug'
            if drug and getattr(drug, 'strength', None):
                label = f"{drug.name} {drug.strength}"
            items.append({
                'drug_name': label,
                'quantity': item.quantity,
                'dosage_instructions': (item.dosage_instructions or '').strip(),
            })
        rows.append({
            'sale': sale,
            'sale_number': sale.sale_number,
            'dispensed_at': sale.dispensed_at or sale.sale_date,
            'items': items,
            'counselling_notes': (sale.counselling_notes or '').strip(),
            'dispensed_by_name': (
                sale.dispensed_by.user.get_full_name()
                if sale.dispensed_by and getattr(sale.dispensed_by, 'user', None)
                else ''
            ),
        })
    return rows
