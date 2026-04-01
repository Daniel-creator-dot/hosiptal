"""
Resolve human-readable context for ActivityLog entries (patient names, drugs sold, etc.).
Used by AuditMiddleware so audit trails show what actually happened, not only raw paths.
"""
from __future__ import annotations

import logging
import re
import uuid as uuid_lib
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _parse_uuid(value: Optional[str]) -> Optional[uuid_lib.UUID]:
    if not value:
        return None
    try:
        return uuid_lib.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _hms_segments(path: str) -> List[str]:
    segs = [p for p in (path or "").strip("/").split("/") if p]
    if segs and segs[0].lower() == "hms":
        segs = segs[1:]
    return segs


def _patient_blob(p) -> Dict[str, Any]:
    if not p:
        return {}
    name = getattr(p, "full_name", None) or ""
    if not name.strip():
        name = f"{getattr(p, 'first_name', '')} {getattr(p, 'last_name', '')}".strip()
    return {
        "id": str(p.pk),
        "name": name or "Unknown",
        "mrn": getattr(p, "mrn", "") or "",
    }


def _post_patient_hints(request) -> Tuple[Dict[str, Any], List[str]]:
    """From POST body: new patient name or existing patient id."""
    meta: Dict[str, Any] = {}
    bits: List[str] = []
    if request.method not in ("POST", "PUT", "PATCH"):
        return meta, bits
    try:
        post = request.POST
    except Exception:
        return meta, bits
    fn = (post.get("first_name") or post.get("firstname") or "").strip()
    ln = (post.get("last_name") or post.get("lastname") or "").strip()
    if fn or ln:
        submitted = f"{fn} {ln}".strip()
        meta["submitted_patient_name"] = submitted
        bits.append(f"Patient name (form): {submitted}")
    for key in ("patient", "patient_id", "patient_pk"):
        raw = post.get(key)
        if raw:
            uid = _parse_uuid(str(raw).strip())
            if uid:
                try:
                    from .models import Patient

                    p = Patient.objects.filter(pk=uid, is_deleted=False).only(
                        "id", "first_name", "last_name", "middle_name", "mrn"
                    ).first()
                    if p:
                        meta["patient"] = _patient_blob(p)
                        bits.append(f"Patient: {meta['patient']['name']} (MRN {meta['patient']['mrn'] or '—'})")
                except Exception as exc:
                    logger.debug("Activity log patient resolve from POST failed: %s", exc)
            break
    return meta, bits


def resolve_activity_context(request) -> Tuple[str, Dict[str, Any]]:
    """
    Returns (description_line, metadata_dict).
    description_line is capped for ActivityLog.description (255 chars); full detail lives in metadata.
    """
    path = getattr(request, "path", "") or ""
    method = getattr(request, "method", "") or ""
    base_meta: Dict[str, Any] = {
        "path": path,
        "method": method,
        "query_params": dict(getattr(request, "GET", {})),
    }
    summary_bits: List[str] = []
    merged: Dict[str, Any] = dict(base_meta)

    segs = _hms_segments(path)

    # --- POST hints (e.g. new patient before UUID exists) ---
    post_meta, post_bits = _post_patient_hints(request)
    merged.update(post_meta)
    summary_bits.extend(post_bits)

    def set_primary_patient(blob: Dict[str, Any]) -> None:
        if not blob:
            return
        if "patient" not in merged:
            merged["patient"] = blob
        elif merged.get("patient", {}).get("id") != blob.get("id"):
            others = merged.setdefault("related_patients", [])
            if blob not in others and all(o.get("id") != blob.get("id") for o in others):
                others.append(blob)

    try:
        from .models import Encounter, LabResult, Patient, Prescription
        from .models_advanced import ImagingStudy
        from .models_payment_verification import PharmacyDispensing
        from .models_pharmacy_walkin import WalkInPharmacySale
    except Exception as exc:
        logger.warning("Activity log context imports failed: %s", exc)
        line = _compose_description(method, path, summary_bits)
        return line, merged

    # --- Walk URL segments ---
    i = 0
    while i < len(segs):
        seg = segs[i]

        if seg == "patients" and i + 1 < len(segs):
            nxt = segs[i + 1]
            if UUID_PATTERN.match(nxt):
                uid = _parse_uuid(nxt)
                if uid:
                    p = (
                        Patient.objects.filter(pk=uid, is_deleted=False)
                        .only("id", "first_name", "last_name", "middle_name", "mrn")
                        .first()
                    )
                    if p:
                        blob = _patient_blob(p)
                        set_primary_patient(blob)
                        summary_bits.append(
                            f"Patient: {blob['name']}" + (f" (MRN {blob['mrn']})" if blob["mrn"] else "")
                        )
            i += 2
            continue

        if seg == "encounters" and i + 1 < len(segs):
            if UUID_PATTERN.match(segs[i + 1]):
                uid = _parse_uuid(segs[i + 1])
                if uid:
                    enc = (
                        Encounter.objects.filter(pk=uid, is_deleted=False)
                        .select_related("patient")
                        .first()
                    )
                    if enc and enc.patient:
                        blob = _patient_blob(enc.patient)
                        set_primary_patient(blob)
                        summary_bits.append(f"Encounter for {blob['name']}")
            i += 2
            continue

        if seg == "pharmacy" and i + 1 < len(segs):
            nxt = segs[i + 1]
            if nxt == "prescription" and i + 2 < len(segs) and UUID_PATTERN.match(segs[i + 2]):
                sale_id = _parse_uuid(segs[i + 2])
                if sale_id:
                    sale = (
                        WalkInPharmacySale.objects.filter(pk=sale_id, is_deleted=False)
                        .select_related("patient")
                        .prefetch_related("items__drug")
                        .first()
                    )
                    if sale:
                        merged["pharmacy_sale_number"] = sale.sale_number
                        summary_bits.append(f"Pharmacy sale {sale.sale_number}")
                        if sale.patient:
                            set_primary_patient(_patient_blob(sale.patient))
                            summary_bits.append(f"Customer/patient: {merged['patient']['name']}")
                        elif sale.customer_name:
                            merged["walk_in_customer"] = sale.customer_name
                            summary_bits.append(f"Walk-in: {sale.customer_name}")
                        drugs: List[Dict[str, Any]] = []
                        for item in sale.items.filter(is_deleted=False)[:50]:
                            d = getattr(item, "drug", None)
                            name = d.name if d else "Unknown drug"
                            drugs.append({"name": name, "quantity": item.quantity})
                        if drugs:
                            merged["drugs_sold"] = drugs
                            drug_line = ", ".join(f"{d['name']} ×{d['quantity']}" for d in drugs[:8])
                            if len(drugs) > 8:
                                drug_line += f" (+{len(drugs) - 8} more)"
                            summary_bits.append(f"Medications: {drug_line}")
                i += 3
                continue

            if nxt == "dispense" and i + 2 < len(segs) and UUID_PATTERN.match(segs[i + 2]):
                rx_id = _parse_uuid(segs[i + 2])
                if rx_id:
                    rx = (
                        Prescription.objects.filter(pk=rx_id, is_deleted=False)
                        .select_related("drug", "order__encounter__patient")
                        .first()
                    )
                    if rx:
                        drug_name = rx.drug.name if rx.drug else "Unknown drug"
                        merged["prescription_drug"] = {
                            "name": drug_name,
                            "quantity": rx.quantity,
                            "dose": rx.dose,
                        }
                        summary_bits.append(f"Dispense: {drug_name} (qty {rx.quantity})")
                        if rx.order and rx.order.encounter and rx.order.encounter.patient:
                            set_primary_patient(_patient_blob(rx.order.encounter.patient))
                            summary_bits.append(f"For patient: {merged['patient']['name']}")
                    disp = (
                        PharmacyDispensing.objects.filter(prescription_id=rx_id, is_deleted=False)
                        .select_related("patient", "substitute_drug", "prescription__drug")
                        .first()
                    )
                    if disp:
                        to_disp = disp.drug_to_dispense
                        if to_disp:
                            merged["drug_dispensed"] = to_disp.name
                            summary_bits.append(f"Dispensing record: {to_disp.name}")
                        if disp.patient:
                            set_primary_patient(_patient_blob(disp.patient))
                i += 3
                continue

            i += 1
            continue

        if seg == "laboratory" and i + 1 < len(segs) and segs[i + 1] == "result":
            if i + 2 < len(segs) and UUID_PATTERN.match(segs[i + 2]):
                rid = _parse_uuid(segs[i + 2])
                if rid:
                    lr = (
                        LabResult.objects.filter(pk=rid, is_deleted=False)
                        .select_related("test", "order__encounter__patient")
                        .first()
                    )
                    if lr:
                        test_name = lr.test.name if lr.test else "Lab test"
                        merged["lab_test"] = {"name": test_name, "status": lr.status}
                        summary_bits.append(f"Lab: {test_name}")
                        if lr.order and lr.order.encounter and lr.order.encounter.patient:
                            set_primary_patient(_patient_blob(lr.order.encounter.patient))
                            summary_bits.append(f"Patient: {merged['patient']['name']}")
            i += 3
            continue

        if seg == "imaging" and i + 1 < len(segs) and segs[i + 1] == "study":
            if i + 2 < len(segs) and UUID_PATTERN.match(segs[i + 2]):
                sid = _parse_uuid(segs[i + 2])
                if sid:
                    st = (
                        ImagingStudy.objects.filter(pk=sid, is_deleted=False)
                        .select_related("patient")
                        .first()
                    )
                    if st:
                        merged["imaging"] = {
                            "modality": st.get_modality_display() if hasattr(st, "get_modality_display") else st.modality,
                            "study_type": st.study_type,
                            "body_part": st.body_part,
                        }
                        summary_bits.append(
                            f"Imaging: {st.study_type or st.modality} ({st.body_part})"
                        )
                        if st.patient:
                            set_primary_patient(_patient_blob(st.patient))
                            summary_bits.append(f"Patient: {merged['patient']['name']}")
            i += 3
            continue

        i += 1

    # One-line summary for humans
    merged["summary"] = " · ".join(dict.fromkeys(summary_bits)) if summary_bits else ""
    line = _compose_description(method, path, summary_bits)
    return line, merged


def _compose_description(method: str, path: str, bits: List[str]) -> str:
    base = f"{method} {path}".strip()
    if not bits:
        return base[:255]
    suffix = " · ".join(dict.fromkeys(bits))
    sep = " — "
    if len(base) + len(sep) + len(suffix) <= 255:
        return base + sep + suffix
    max_suffix = 255 - len(base) - len(sep) - 1
    if max_suffix < 8:
        return base[:255]
    return base + sep + suffix[:max_suffix] + "…"
