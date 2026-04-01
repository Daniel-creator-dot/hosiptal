"""
Prescription Assistant Service — AI-style drug suggestion and dosing support.
Maps indications to drug categories, suggests dosing, and checks interactions.
Powers the Prescription Top-Up chat that leads to prescription.
"""
import re
from django.db.models import Q, Sum
from ..models import Drug, Prescription
from ..models_missing_features import DrugInteraction
from .drug_interaction_service import DrugInteractionService


# Indication keywords → (category_codes, short_label)
INDICATION_MAP = {
    # Infections
    'uti': (['antibiotic', 'antibacterial'], 'Urinary tract infection'),
    'urinary': (['antibiotic', 'antibacterial'], 'UTI'),
    'respiratory infection': (['antibiotic', 'antibacterial'], 'Respiratory infection'),
    'cough': (['cough_suppressant', 'expectorant', 'antibiotic'], 'Cough'),
    'cold': (['cold_cure', 'decongestant', 'antihistamine', 'antipyretic'], 'Common cold'),
    'flu': (['antiviral', 'antipyretic', 'analgesic'], 'Influenza'),
    'malaria': (['antibiotic'], 'Malaria'),  # antimalarials may be under antibiotic/other
    'bacterial': (['antibiotic', 'antibacterial'], 'Bacterial infection'),
    'fungal': (['antifungal'], 'Fungal infection'),
    'viral': (['antiviral'], 'Viral infection'),
    'infection': (['antibiotic', 'antibacterial', 'antiviral', 'antifungal'], 'Infection'),
    # Pain & fever
    'pain': (['analgesic', 'anti_inflammatory'], 'Pain'),
    'fever': (['antipyretic', 'analgesic'], 'Fever'),
    'headache': (['analgesic', 'antipyretic'], 'Headache'),
    'arthritis': (['anti_inflammatory', 'analgesic', 'corticosteroid'], 'Arthritis'),
    'inflammation': (['anti_inflammatory', 'corticosteroid'], 'Inflammation'),
    # Cardiovascular
    'hypertension': (['antihypertensive', 'diuretic', 'beta_blocker'], 'Hypertension'),
    'blood pressure': (['antihypertensive', 'diuretic', 'beta_blocker'], 'Hypertension'),
    'heart': (['antihypertensive', 'beta_blocker', 'anticoagulant'], 'Cardiac'),
    'diuretic': (['diuretic'], 'Fluid overload'),
    # Gastrointestinal
    'ulcer': (['antacid'], 'Peptic ulcer / dyspepsia'),
    'acid': (['antacid'], 'Acid-related'),
    'nausea': (['antiemetic'], 'Nausea/vomiting'),
    'vomiting': (['antiemetic'], 'Vomiting'),
    'diarrhea': (['antidiarrheal'], 'Diarrhea'),
    'constipation': (['laxative'], 'Constipation'),
    # Respiratory
    'asthma': (['bronchodilator', 'corticosteroid'], 'Asthma'),
    'wheezing': (['bronchodilator'], 'Bronchospasm'),
    # CNS / Psychiatric
    'anxiety': (['antianxiety', 'sedative'], 'Anxiety'),
    'depression': (['antidepressant'], 'Depression'),
    'insomnia': (['sleeping_drug', 'sedative', 'antianxiety'], 'Insomnia'),
    'diabetes': (['oral_hypoglycemic', 'hormone'], 'Diabetes'),
    'allergy': (['antihistamine'], 'Allergy'),
    'allergic': (['antihistamine'], 'Allergic reaction'),
    # Musculoskeletal
    'muscle spasm': (['muscle_relaxant', 'antianxiety'], 'Muscle spasm'),
    'backache': (['analgesic', 'muscle_relaxant', 'anti_inflammatory'], 'Back pain'),
    # Vitamins / supplements
    'vitamin': (['vitamin'], 'Vitamins/supplements'),
    'anemia': (['vitamin'], 'Anemia (consider haematinics)'),
    'iron': (['vitamin'], 'Iron deficiency'),
}


# Default dosing hints by category (dose, route, frequency, duration)
DOSING_HINTS = {
    'antibiotic': {'dose': 'As per sensitivity', 'route': 'oral', 'frequency': 'Twice daily (BD)', 'duration': '5–7 days'},
    'antibacterial': {'dose': 'As per sensitivity', 'route': 'oral', 'frequency': 'Twice daily (BD)', 'duration': '5–7 days'},
    'analgesic': {'dose': '1–2 tablets', 'route': 'oral', 'frequency': 'Every 6–8 hours', 'duration': 'As needed'},
    'antipyretic': {'dose': '500mg–1g', 'route': 'oral', 'frequency': 'Every 6–8 hours', 'duration': 'Until afebrile'},
    'anti_inflammatory': {'dose': 'As per strength', 'route': 'oral', 'frequency': 'Twice daily (BD)', 'duration': '5–7 days'},
    'antihypertensive': {'dose': 'As per protocol', 'route': 'oral', 'frequency': 'Once daily (OD)', 'duration': 'Long-term'},
    'diuretic': {'dose': 'As per protocol', 'route': 'oral', 'frequency': 'Once daily (OD)', 'duration': 'As prescribed'},
    'antacid': {'dose': '1–2 tablets', 'route': 'oral', 'frequency': 'As needed (PRN)', 'duration': 'As needed'},
    'antiemetic': {'dose': 'As per strength', 'route': 'oral', 'frequency': 'Every 8 hours', 'duration': 'As needed'},
    'antidiarrheal': {'dose': 'As per product', 'route': 'oral', 'frequency': 'After each loose stool', 'duration': 'Until controlled'},
    'antihistamine': {'dose': 'As per strength', 'route': 'oral', 'frequency': 'Once daily (OD)', 'duration': 'As needed'},
    'bronchodilator': {'dose': '2 puffs', 'route': 'inhalation', 'frequency': 'Every 4–6 hours', 'duration': 'As needed'},
    'cough_suppressant': {'dose': 'As per product', 'route': 'oral', 'frequency': 'Three times daily (TDS)', 'duration': '5–7 days'},
    'expectorant': {'dose': 'As per product', 'route': 'oral', 'frequency': 'Three times daily (TDS)', 'duration': '5–7 days'},
    'oral_hypoglycemic': {'dose': 'As per protocol', 'route': 'oral', 'frequency': 'Once or twice daily', 'duration': 'Long-term'},
    'vitamin': {'dose': 'As per product', 'route': 'oral', 'frequency': 'Once daily (OD)', 'duration': 'As prescribed'},
    'antianxiety': {'dose': 'As per strength', 'route': 'oral', 'frequency': 'As needed (PRN)', 'duration': 'Short-term'},
    'antidepressant': {'dose': 'As per protocol', 'route': 'oral', 'frequency': 'Once daily (OD)', 'duration': 'Weeks–months'},
    'laxative': {'dose': 'As per product', 'route': 'oral', 'frequency': 'At bedtime (HS)', 'duration': 'As needed'},
    'other': {'dose': 'As per product', 'route': 'oral', 'frequency': 'As directed', 'duration': 'As prescribed'},
}


def _normalize(text):
    if not text:
        return ''
    return re.sub(r'\s+', ' ', text.lower().strip())


def _match_indication(query):
    """Return list of (category_codes, label) for the first matching indication."""
    n = _normalize(query)
    for keyword, (categories, label) in INDICATION_MAP.items():
        if keyword in n:
            return categories, label
    return None


def get_drugs_for_categories(category_codes, include_stock=True, limit=20):
    """Return active drugs in given categories, optionally with stock."""
    qs = Drug.objects.filter(
        category__in=category_codes,
        is_active=True,
        is_deleted=False
    ).order_by('name')[:limit]
    drugs = list(qs)
    if not include_stock:
        return [{'id': str(d.id), 'name': d.name, 'generic_name': d.generic_name or '', 'strength': d.strength, 'form': d.form, 'category': d.category, 'category_display': d.get_category_display(), 'stock_available': None, 'has_stock': None} for d in drugs]
    from ..models import PharmacyStock
    drug_ids = [d.id for d in drugs]
    stock_totals = PharmacyStock.objects.filter(
        drug_id__in=drug_ids,
        is_deleted=False
    ).values('drug_id').annotate(total=Sum('quantity_on_hand'))
    stock_map = {s['drug_id']: (s['total'] or 0) for s in stock_totals}
    out = []
    for d in drugs:
        total = stock_map.get(d.id, 0)
        out.append({
            'id': str(d.id),
            'name': d.name,
            'generic_name': d.generic_name or '',
            'strength': d.strength,
            'form': d.form,
            'category': d.category,
            'category_display': d.get_category_display(),
            'stock_available': int(total),
            'has_stock': total > 0,
        })
    return out


def get_dosing_hint(category_code):
    """Return dosing hint dict for a category."""
    return DOSING_HINTS.get(category_code, DOSING_HINTS['other']).copy()


def search_drugs_free_text(query, limit=15, include_stock=True):
    """Search drugs by name/generic/ATC."""
    if not _normalize(query):
        return []
    qs = Drug.objects.filter(
        is_active=True,
        is_deleted=False
    ).filter(
        Q(name__icontains=query) | Q(generic_name__icontains=query) | Q(atc_code__icontains=query)
    ).order_by('name')[:limit]
    drugs = list(qs)
    if not include_stock:
        return [{'id': str(d.id), 'name': d.name, 'generic_name': d.generic_name or '', 'strength': d.strength, 'form': d.form, 'category': d.category, 'category_display': d.get_category_display(), 'stock_available': None, 'has_stock': None} for d in drugs]
    from ..models import PharmacyStock
    drug_ids = [d.id for d in drugs]
    stock_totals = PharmacyStock.objects.filter(drug_id__in=drug_ids, is_deleted=False).values('drug_id').annotate(total=Sum('quantity_on_hand'))
    stock_map = {s['drug_id']: (s['total'] or 0) for s in stock_totals}
    return [{
        'id': str(d.id),
        'name': d.name,
        'generic_name': d.generic_name or '',
        'strength': d.strength,
        'form': d.form,
        'category': d.category,
        'category_display': d.get_category_display(),
        'stock_available': int(stock_map.get(d.id, 0)),
        'has_stock': (stock_map.get(d.id, 0) or 0) > 0,
    } for d in drugs]


def check_interactions_for_drug_ids(drug_ids, patient=None):
    """Return interaction warnings for given drug IDs and optional patient."""
    if not drug_ids:
        return {'warnings': [], 'has_critical': False}
    drugs = list(Drug.objects.filter(pk__in=drug_ids, is_deleted=False))
    result = DrugInteractionService.check_interactions(drugs, patient=patient)
    return {'warnings': result['warnings'], 'has_critical': result.get('has_critical', False)}


def build_chat_response(message, encounter_id=None, selected_drug_ids=None):
    """
    Build assistant reply and suggested drugs from user message.
    Returns: {
        'reply': str,
        'suggested_drugs': list of drug dicts,
        'dosing_hint': dict or None,
        'indication_label': str or None,
        'interactions': list of warning dicts,
        'has_critical_interaction': bool,
    }
    """
    selected_drug_ids = selected_drug_ids or []
    patient = None
    if encounter_id:
        from ..models import Encounter
        try:
            enc = Encounter.objects.select_related('patient').get(pk=encounter_id, is_deleted=False)
            patient = enc.patient
        except Encounter.DoesNotExist:
            pass

    msg = _normalize(message)
    reply_parts = []
    suggested_drugs = []
    dosing_hint = None
    indication_label = None

    # 1) Interaction check if user asked to check interactions
    if 'interaction' in msg or ('check' in msg and 'interaction' in msg):
        if not selected_drug_ids:
            return {
                'reply': '**Drug interaction check:** Select at least one drug from the suggestions above, then say "check interactions" again, or add drugs in the consultation and use this assistant with that encounter.',
                'suggested_drugs': [],
                'dosing_hint': None,
                'indication_label': None,
                'interactions': [],
                'has_critical_interaction': False,
            }
        result = check_interactions_for_drug_ids(selected_drug_ids, patient)
        if result['warnings']:
            reply_parts.append('**Drug interaction check:**')
            for w in result['warnings']:
                reply_parts.append(f"• {w.get('message', w)}")
            if result['has_critical']:
                reply_parts.append('Consider avoiding or monitoring combination.')
        else:
            reply_parts.append('No significant drug-drug interactions found for the selected drugs. Always confirm with your clinical judgment.')
        return {
            'reply': '\n'.join(reply_parts),
            'suggested_drugs': [],
            'dosing_hint': None,
            'indication_label': None,
            'interactions': result['warnings'],
            'has_critical_interaction': result['has_critical'],
        }

    # 2) Indication-based suggestion
    match = _match_indication(message)
    if match:
        category_codes, indication_label = match
        suggested_drugs = get_drugs_for_categories(category_codes, include_stock=True, limit=15)
        first_cat = category_codes[0] if category_codes else 'other'
        dosing_hint = get_dosing_hint(first_cat)
        reply_parts.append(f"**Indication:** {indication_label}")
        reply_parts.append(f"Suggested drug classes: {', '.join(category_codes)}.")
        if suggested_drugs:
            reply_parts.append(f"Found **{len(suggested_drugs)}** drug(s) in formulary. Select one to add to prescription and adjust dose/route/frequency as needed.")
        else:
            reply_parts.append("No matching drugs in formulary for this indication. Try Drug Classification browser or search by name.")
    else:
        # 3) Free-text drug search
        if len(msg) >= 2:
            suggested_drugs = search_drugs_free_text(message, limit=15, include_stock=True)
            if suggested_drugs:
                reply_parts.append(f"Found **{len(suggested_drugs)}** drug(s) matching \"{message.strip()}\". Select to add to prescription.")
            else:
                reply_parts.append("No drugs found. Try indication (e.g. 'antibiotic for UTI', 'pain relief') or browse Drug Classification.")
        else:
            reply_parts.append("Type an **indication** (e.g. 'antibiotic for UTI', 'pain', 'hypertension') or a **drug name** to get suggestions. You can also say **'check interactions'** after selecting drugs.")

    # Interaction check for suggested drugs if we have current selection
    interactions = []
    has_critical = False
    if selected_drug_ids:
        res = check_interactions_for_drug_ids(selected_drug_ids, patient)
        interactions = res['warnings']
        has_critical = res['has_critical']
        if interactions:
            reply_parts.append('')
            reply_parts.append('**Interaction alert** for current selection:')
            for w in interactions[:5]:
                reply_parts.append(f"• {w.get('message', w)}")

    return {
        'reply': '\n'.join(reply_parts),
        'suggested_drugs': suggested_drugs,
        'dosing_hint': dosing_hint,
        'indication_label': indication_label,
        'interactions': interactions,
        'has_critical_interaction': has_critical,
    }
