"""
Deduplicate clinical notes for display timelines (double-submit, auto-save, sync glitches).
Assumes notes are ordered newest-first before calling dedupe_clinical_notes_timeline.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, List

from django.utils import timezone


def strip_billing_amounts_from_clinical_display(text: str | None) -> str:
    """
    Remove auto-logged billing snippets from text shown in consultation prefilled / clinical
    blocks (e.g. lab batch lines that appended 'Total bill: GHS …').
    """
    if not text or not str(text).strip():
        return (text or '').strip()
    out = str(text)
    # e.g. "[Lab] Tests ordered (1). Total bill: GHS 720.00 — 2026-04-14 11:35"
    out = re.sub(
        r'\.\s*Total bill:\s*GHS\s*[\d,]+\.\d{2}\s*—\s*',
        '. — ',
        out,
        flags=re.IGNORECASE,
    )
    # Line-start variant (defensive)
    out = re.sub(
        r'^\s*Total bill:\s*GHS\s*[\d,]+\.\d{2}\s*—\s*',
        '',
        out,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    return out


def clinical_note_content_fingerprint(note: Any) -> str:
    """Stable hash of SOAP/body fields for duplicate detection."""
    parts = [
        (getattr(note, "subjective", None) or "").strip(),
        (getattr(note, "objective", None) or "").strip(),
        (getattr(note, "assessment", None) or "").strip(),
        (getattr(note, "plan", None) or "").strip(),
        (getattr(note, "notes", None) or "").strip(),
    ]
    blob = "\n".join(parts).encode("utf-8", errors="replace")
    return hashlib.sha256(blob).hexdigest()[:48]


def dedupe_clinical_notes_timeline(
    notes: List[Any],
    *,
    window_seconds: int = 180,
    progress_window_seconds: int = 60,
) -> List[Any]:
    """
    Remove duplicate rows: same encounter, note_type, and body fingerprint with `created`
    within a short window. Process in **newest-first** order so the kept row is the latest.

    Progress notes use a shorter window so intentional serial entries minutes apart stay visible.
    """
    if not notes:
        return notes

    by_id: List[Any] = []
    seen_ids: set = set()
    for n in notes:
        nid = getattr(n, "id", None)
        if nid is not None:
            if nid in seen_ids:
                continue
            seen_ids.add(nid)
        by_id.append(n)

    kept_anchor: dict = {}
    out: List[Any] = []
    for n in by_id:
        eid = getattr(n, "encounter_id", None)
        ntype = getattr(n, "note_type", None) or ""
        fp = clinical_note_content_fingerprint(n)
        key = (eid, ntype, fp)
        created = getattr(n, "created", None) or timezone.now()
        win = progress_window_seconds if ntype == "progress" else window_seconds
        anchor = kept_anchor.get(key)
        if anchor is not None:
            if abs((created - anchor).total_seconds()) <= win:
                continue
        kept_anchor[key] = created
        out.append(n)
    return out
