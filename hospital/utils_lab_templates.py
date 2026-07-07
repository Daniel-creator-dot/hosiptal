"""
Central mapping of lab tests to result entry templates.
Used by tabular_lab_report and edit_lab_result so lab techs always get the correct form
for the ordered test (FBC, LFT, RFT, Lipid, TFT, Glucose, Electrolytes, Urine, Stool, or Single value).

Invariant: each test code appears at most once in CODE_TO_TEMPLATE (dict mapping would otherwise
silently drop or override entries — same class of bug as duplicate UEC).
"""
import json
import re
from collections import Counter
from typing import List, Optional

# Template types matching TabularLabReportForm and lab_report_tabular.html
TEMPLATE_FBC = 'fbc'
TEMPLATE_LFT = 'lft'
TEMPLATE_RFT = 'rft'
TEMPLATE_LIPID = 'lipid'
TEMPLATE_TFT = 'tft'
TEMPLATE_GLUCOSE = 'glucose'
TEMPLATE_BUE = 'bue'  # Blood Urea & Electrolytes (no creatinine/eGFR/uric acid)
TEMPLATE_ELECTROLYTES = 'electrolytes'
TEMPLATE_URINE = 'urine'
TEMPLATE_STOOL = 'stool'
TEMPLATE_MALARIA = 'malaria'
TEMPLATE_BLOOD_GROUP = 'blood_group'
TEMPLATE_SICKLE = 'sickle'
TEMPLATE_COAGULATION = 'coagulation'
TEMPLATE_SEROLOGY = 'serology'
TEMPLATE_SEMEN = 'semen'
TEMPLATE_AFB = 'afb'
TEMPLATE_SINGLE = 'single'

# Exact test codes → template (from seed_ghana_lab_tests and common usage)
# Order matters only for codes that could match multiple; first match wins.
CODE_TO_TEMPLATE = [
    # FBC / CBC
    ('FBC', TEMPLATE_FBC),
    ('CBC', TEMPLATE_FBC),
    # LFT (Liver) — panel and individual liver tests use LFT form
    ('LFT', TEMPLATE_LFT),
    ('ALT', TEMPLATE_LFT),
    ('AST', TEMPLATE_LFT),
    ('ALP', TEMPLATE_LFT),
    ('TBIL', TEMPLATE_LFT),
    ('DBIL', TEMPLATE_LFT),
    ('TPROT', TEMPLATE_LFT),
    ('ALB', TEMPLATE_LFT),
    # RFT / Renal / Kidney
    ('KFT', TEMPLATE_RFT),
    ('RFT', TEMPLATE_RFT),
    ('UREA', TEMPLATE_RFT),
    ('CREAT', TEMPLATE_RFT),
    ('BUN', TEMPLATE_RFT),
    # BUE / U&E: urea + electrolytes only (distinct from Uric Acid and from full RFT/UEC)
    ('BUE', TEMPLATE_BUE),
    ('UEC', TEMPLATE_RFT),  # Urea, Electrolytes & Creatinine
    # Lipid
    ('LIPID', TEMPLATE_LIPID),
    ('CHOL', TEMPLATE_LIPID),
    ('HDL', TEMPLATE_LIPID),
    ('LDL', TEMPLATE_LIPID),
    ('TG', TEMPLATE_LIPID),
    # TFT (Thyroid)
    ('TFT', TEMPLATE_TFT),
    ('TSH', TEMPLATE_TFT),
    ('T3', TEMPLATE_TFT),
    ('T4', TEMPLATE_TFT),
    ('FREE-T3', TEMPLATE_TFT),
    ('FREE-T4', TEMPLATE_TFT),
    # Glucose
    ('FBS', TEMPLATE_GLUCOSE),
    ('RBS', TEMPLATE_GLUCOSE),
    ('OGTT', TEMPLATE_GLUCOSE),
    ('HBA1C', TEMPLATE_GLUCOSE),
    # Electrolytes — panel and individual (use electrolytes form)
    ('ELECT', TEMPLATE_ELECTROLYTES),
    ('NA', TEMPLATE_ELECTROLYTES),
    ('K', TEMPLATE_ELECTROLYTES),
    ('CL', TEMPLATE_ELECTROLYTES),
    ('HCO3', TEMPLATE_ELECTROLYTES),
    # Urine Routine / Urinalysis (CHEMISTRY + MICROSCOPY)
    ('URINE', TEMPLATE_URINE),
    ('URINE-MS', TEMPLATE_URINE),
    ('URINALYSIS', TEMPLATE_URINE),
    # Stool Routine Examination
    ('STOOL-R/E', TEMPLATE_STOOL),
    ('STOOL-R', TEMPLATE_STOOL),
    ('STOOL-O&P', TEMPLATE_STOOL),
    # Malaria (WHO standard) — BF = Blood Film, BF-MP = Blood Film for MP
    ('BF', TEMPLATE_MALARIA),
    ('BF-MP', TEMPLATE_MALARIA),
    ('MP-RDT', TEMPLATE_MALARIA),
    ('MP-BS', TEMPLATE_MALARIA),
    ('MP-QBC', TEMPLATE_MALARIA),
    # Blood Group & Rhesus (ISBT standard)
    ('BG', TEMPLATE_BLOOD_GROUP),
    ('RH', TEMPLATE_BLOOD_GROUP),
    ('BG-RH', TEMPLATE_BLOOD_GROUP),
    # Sickle Cell
    ('HB-S', TEMPLATE_SICKLE),
    ('HB-ELEC', TEMPLATE_SICKLE),
    ('SCREEN', TEMPLATE_SICKLE),
    # Coagulation (PT / INR / APTT / Fibrinogen panel)
    ('PT', TEMPLATE_COAGULATION),
    ('APTT', TEMPLATE_COAGULATION),
    ('INR', TEMPLATE_COAGULATION),
    # D-Dimer is a single quantitative result (ng/mL FEU etc.), not the PT/INR/APTT panel
    ('D-DIM', TEMPLATE_SINGLE),
    # Serology (HIV, HBsAg, VDRL, etc.)
    ('HIV', TEMPLATE_SEROLOGY),
    ('HIV-ELISA', TEMPLATE_SEROLOGY),
    ('HBsAg', TEMPLATE_SEROLOGY),
    ('HBV', TEMPLATE_SEROLOGY),
    ('HCV', TEMPLATE_SEROLOGY),
    ('VDRL', TEMPLATE_SEROLOGY),
    ('TPHA', TEMPLATE_SEROLOGY),
    ('TYPH-RDT', TEMPLATE_SEROLOGY),
    ('WIDAL', TEMPLATE_SEROLOGY),
    ('H-PYLORI', TEMPLATE_SEROLOGY),
    # Semen Analysis (WHO)
    ('SEMEN', TEMPLATE_SEMEN),
    # AFB / Sputum
    ('AFB', TEMPLATE_AFB),
    ('TB-GENE', TEMPLATE_AFB),
    # Synovial fluid / crystal (qualitative: Seen / Not seen)
    ('KNEE-UA', TEMPLATE_SINGLE),
    # High vaginal swab C&S (culture narrative / sensitivities)
    ('HV-CS', TEMPLATE_SINGLE),
    # Single analyte — never use RFT panel (shared uric_acid field caused BUE/RFT mix-ups)
    ('URIC', TEMPLATE_SINGLE),
]

_code_counts = Counter(c for c, _ in CODE_TO_TEMPLATE)
_dup_lab_codes = sorted(c for c, v in _code_counts.items() if v > 1)
if _dup_lab_codes:
    raise ValueError(
        f'Duplicate lab test code(s) in CODE_TO_TEMPLATE (would break CODE_MAP): {_dup_lab_codes}'
    )
CODE_MAP = dict(CODE_TO_TEMPLATE)

# Phrases: if test is coded LFT but name clearly indicates glucose, use glucose template (common miscoding).
_LFT_TO_GLUCOSE_NAME_PHRASES = (
    'fasting blood sugar',
    'fasting glucose',
    'fasting plasma glucose',
    'random blood sugar',
    'blood sugar',
    'fbs',
    'rbs',
    'hba1c',
    'glycated hemoglobin',
    'glycated',
    'ogtt',
    'post prandial',
    'post-prandial',
    'ppbs',
)

# Keyword fallback: substrings in test name or code → template
# Used only when code is not in CODE_MAP. Order: urine/stool before single so they get proper templates.
KEYWORDS_URINE = ['urine routine', 'urinalysis', 'urine microscopy', 'urine exam', 'urine re']
KEYWORDS_STOOL = ['stool routine', 'stool r/e', 'stool examination', 'stool o&p', 'stool ova', 'stool parasites']
KEYWORDS_MALARIA = ['malaria', 'mp-', 'parasite', 'rdt', 'blood smear', 'blood film', 'bf for mp']
# Do not use bare 'bg' / 'rh' as substrings (e.g. "subgroup"); see _keyword_match_blood_group
KEYWORDS_BLOOD_GROUP_PHRASES = ['blood group', 'rhesus', 'abo typing', 'abo group']
# Avoid bare 'electrophoresis' (serum/protein electrophoresis is not sickle cell)
KEYWORDS_SICKLE = [
    'sickle', 'hb-s', 'hb electrophoresis', 'hemoglobin electrophoresis', 'haemoglobin electrophoresis',
    'solubility',
]
KEYWORDS_COAGULATION = [
    'pt', 'aptt', 'inr', 'coagulation', 'prothrombin',
    'clotting', 'clotting profile', 'bleeding profile',
]
KEYWORDS_SEROLOGY = ['hiv', 'hbsag', 'vdrl', 'tpha', 'typhoid', 'widal', 'h. pylori', 'hcv']
KEYWORDS_SEMEN = ['semen', 'sperm']
KEYWORDS_AFB = ['afb', 'acid fast', 'sputum', 'tb gene', 'gene xpert']
KEYWORDS_SINGLE = [
    'prolactin', 'prol', 'testosterone', 'cortisol', 'estrogen', 'progesterone',
    'hormone', 'ferritin', 'psa', 'hcg', 'beta hcg', 'folate', 'vitamin d', 'b12',
    'fsh', 'lh', 'cea', 'afp', 'ca125', 'ca-125', 'ca199', 'tumor marker',
    'insulin', 'ferr', 'testo', 'prog', 'vit-d', 'vit-b12', 'folate',
    'esr', 'crp', 'pregnancy', 'qualitative',
    # Urine/stool tests that are single-value (culture, pregnancy, occult blood)
    'urine culture', 'urine c&s', 'urine pregn', 'stool occult', 'stool mcs',
    'high vaginal', 'vaginal swab culture',
]
KEYWORDS_FBC = ['fbc', 'cbc', 'complete blood count', 'full blood count', 'full blood', 'complete blood']
# LFT short tokens use word boundaries — 'alt'/'ast' match inside "salt"/"fast" if substring-only
_LFT_SUBSTRING_PHRASES = (
    'lft', 'liver function', 'hepatic', 'bilirubin', 'albumin', 'total protein',
)
_LFT_BOUNDARY_TOKENS = ('alt', 'ast', 'alp', 'ggt')
KEYWORDS_RFT = ['rft', 'renal', 'kidney function', 'creatinine', 'kft', 'bun', 'egfr']
# Note: bare 'urea' is not here — use BUE matcher or code UREA/RFT so "Uric Acid" is never classified as RFT
KEYWORDS_BUE = ['u&e', 'u & e', 'u and e', 'blood urea and electrolyte', 'blood urea & electrolyte']
KEYWORDS_LIPID = ['lipid', 'cholesterol', 'triglyceride', 'hdl', 'ldl', 'vldl']
_TFT_SUBSTRING_PHRASES = ('tft', 'thyroid', 'thyroxine', 'triiodothyronine')
_TFT_BOUNDARY_TOKENS = ('tsh', 't3', 't4')
# No bare 'fasting' — would match "Fasting Lipid Panel" and force glucose template before code/lipid checks.
KEYWORDS_GLUCOSE = [
    'glucose', 'blood sugar', 'fbs', 'rbs', 'hba1c', 'glycated', 'ogtt',
    'fasting blood sugar', 'fasting glucose', 'fasting plasma glucose',
    'random blood sugar', 'glycated hemoglobin',
    'post prandial', 'post-prandial', 'ppbs',
]
# No 'elect' — matches unrelated words (e.g. "select", "electrophoresis" context)
KEYWORDS_ELECTROLYTES = ['electrolyte', 'sodium', 'potassium', 'chloride', 'bicarbonate']


def _is_bue_panel(name: str, code: str) -> bool:
    """Blood urea + electrolytes without creatinine / full renal panel / uric acid test."""
    n = (name or '').strip().lower()
    if not n:
        return False
    if 'uric' in n:
        return False
    if 'creatinine' in n or 'egfr' in n or 'gfr' in n:
        return False
    if 'renal function' in n or 'kidney function' in n:
        return False
    if any(k in n for k in KEYWORDS_BUE):
        return True
    if 'blood urea' in n and 'electrolyte' in n:
        return True
    if 'urea' in n and 'electrolyte' in n:
        return True
    return False


def _name_overrides_lft_to_glucose(name: str) -> bool:
    n = (name or '').strip().lower()
    if not n:
        return False
    return any(p in n for p in _LFT_TO_GLUCOSE_NAME_PHRASES)


def _keyword_match_blood_group(name: str, code_lower: str) -> bool:
    n = (name or '').strip().lower()
    if any(p in n for p in KEYWORDS_BLOOD_GROUP_PHRASES):
        return True
    if re.search(r'\bbg\b', n) or re.search(r'\brh\b', n):
        return True
    if code_lower in ('bg', 'rh', 'bg-rh'):
        return True
    return False


def _name_suggests_uric_acid_single(name: str) -> bool:
    n = (name or '').strip().lower()
    if 'uric acid' in n:
        return True
    return bool(re.search(r'\buric\b', n))


def _keyword_match_lft(name: str, code_lower: str) -> bool:
    n = (name or '').strip().lower()
    if any(p in n for p in _LFT_SUBSTRING_PHRASES):
        return True
    for tok in _LFT_BOUNDARY_TOKENS:
        if re.search(rf'(?<![a-z0-9]){re.escape(tok)}(?![a-z0-9])', n):
            return True
    return False


def _keyword_match_tft(name: str, code_lower: str) -> bool:
    n = (name or '').strip().lower()
    if any(p in n for p in _TFT_SUBSTRING_PHRASES):
        return True
    for tok in _TFT_BOUNDARY_TOKENS:
        if re.search(rf'(?<![a-z0-9]){re.escape(tok)}(?![a-z0-9])', n):
            return True
    return False


def get_lab_result_template_type(test) -> str:
    """
    Return the template type for a LabTest instance: fbc, lft, rft, bue, lipid, tft, glucose,
    electrolytes, urine, stool, or single.
    Uses exact code first (prevents lipid/TFT panels from being overridden by loose name keywords),
    then keyword matching. Never returns FBC for non-FBC tests.
    """
    if test is None:
        return TEMPLATE_SINGLE
    code = (getattr(test, 'code', None) or '').strip().upper()
    name = (getattr(test, 'name', None) or '').strip().lower()
    code_lower = code.lower()

    # 1) Exact code match (canonical)
    if code and code in CODE_MAP:
        mapped = CODE_MAP[code]
        if mapped == TEMPLATE_LFT and _name_overrides_lft_to_glucose(name):
            return TEMPLATE_GLUCOSE
        return mapped

    # 2) BUE by name (uncoded urea + electrolyte panels)
    if _is_bue_panel(name, code):
        return TEMPLATE_BUE

    # 3) Keyword matching — structured templates before single
    if any(k in name or k in code_lower for k in KEYWORDS_URINE):
        return TEMPLATE_URINE
    if any(k in name or k in code_lower for k in KEYWORDS_STOOL):
        return TEMPLATE_STOOL
    if any(k in name or k in code_lower for k in KEYWORDS_MALARIA):
        return TEMPLATE_MALARIA
    if _keyword_match_blood_group(name, code_lower):
        return TEMPLATE_BLOOD_GROUP
    if any(k in name or k in code_lower for k in KEYWORDS_SICKLE):
        return TEMPLATE_SICKLE
    # D-Dimer: single value; must run before KEYWORDS_COAGULATION ('d-dim' matches 'd-dimer' as substring)
    if 'd-dimer' in name or 'd dimer' in name or code_lower in ('d-dim', 'ddim', 'd-dimer'):
        return TEMPLATE_SINGLE
    if any(k in name or k in code_lower for k in KEYWORDS_COAGULATION):
        return TEMPLATE_COAGULATION
    if any(k in name or k in code_lower for k in KEYWORDS_SEROLOGY):
        return TEMPLATE_SEROLOGY
    if any(k in name or k in code_lower for k in KEYWORDS_SEMEN):
        return TEMPLATE_SEMEN
    if any(k in name or k in code_lower for k in KEYWORDS_AFB):
        return TEMPLATE_AFB
    # Uric acid: single analyte only (word boundary — avoid substring false positives vs "urea")
    if _name_suggests_uric_acid_single(name):
        return TEMPLATE_SINGLE
    if any(k in name or k in code_lower for k in KEYWORDS_SINGLE):
        return TEMPLATE_SINGLE
    if any(k in name or k in code_lower for k in KEYWORDS_FBC):
        return TEMPLATE_FBC
    if _keyword_match_lft(name, code_lower):
        return TEMPLATE_LFT
    if any(k in name or k in code_lower for k in KEYWORDS_RFT):
        return TEMPLATE_RFT
    # Standalone "urea" analyte / serum urea (not BUE — already handled; not uric acid — handled as single)
    if 'urea' in name or 'urea' in code_lower:
        return TEMPLATE_RFT
    if any(k in name or k in code_lower for k in KEYWORDS_LIPID):
        return TEMPLATE_LIPID
    if _keyword_match_tft(name, code_lower):
        return TEMPLATE_TFT
    if any(k in name or k in code_lower for k in KEYWORDS_GLUCOSE):
        return TEMPLATE_GLUCOSE
    if any(k in name or k in code_lower for k in KEYWORDS_ELECTROLYTES):
        return TEMPLATE_ELECTROLYTES

    # Default: single value (never FBC)
    return TEMPLATE_SINGLE


def is_single_value_template(test) -> bool:
    """True if this test should use the single-value result form (e.g. Prolactin, HIV)."""
    return get_lab_result_template_type(test) == TEMPLATE_SINGLE


def is_urine_template(test) -> bool:
    """True if this test should use the urine routine (CHEMISTRY + MICROSCOPY) form."""
    return get_lab_result_template_type(test) == TEMPLATE_URINE


def is_stool_template(test) -> bool:
    """True if this test should use the stool routine examination form."""
    return get_lab_result_template_type(test) == TEMPLATE_STOOL


def is_fbc_template(test) -> bool:
    """True if this test should use the FBC/CBC result form."""
    return get_lab_result_template_type(test) == TEMPLATE_FBC


def is_structured_template(test) -> bool:
    """True if test has a dedicated template (not single-value)."""
    t = get_lab_result_template_type(test)
    return t != TEMPLATE_SINGLE


# Human-readable parameter names for print reports (urine, stool, FBC, LFT, etc.)
PARAM_DISPLAY_NAMES = {
    # FBC (Evans Lab format: WBC, Lymph#, Mid#, Gran#, Lymph%, Mid%, Gran%, PLT, MPV, PDW, PCT)
    'wbc': 'WBC', 'lymph_count': 'Lymph#', 'mid_count': 'Mid#', 'gran_count': 'Gran#',
    'lymph_perc': 'Lymph%', 'mid_perc': 'Mid%', 'gran_perc': 'Gran%',
    'plt': 'PLT', 'mpv': 'MPV', 'pdw': 'PDW', 'pct': 'PCT',
    'rbc': 'RBC', 'hgb': 'HGB', 'hct': 'HCT', 'mcv': 'MCV', 'mch': 'MCH',
    'mchc': 'MCHC', 'rdw_cv': 'RDW-CV', 'rdw_sd': 'RDW-SD',
    'neut_perc': 'Neutrophils %', 'mono_perc': 'Monocytes %',
    'eos_perc': 'Eosinophils %', 'baso_perc': 'Basophils %',
    # LFT
    'total_bili': 'Bilirubin-Total (Serum, Diazo)', 'direct_bili': 'Bilirubin-Direct (Serum, Diazo)', 'indirect_bili': 'Bilirubin-Indirect (Serum, Calculated)',
    'alt': 'SGPT (ALT)', 'ast': 'SGOT (AST)', 'alp': 'Alkaline Phosphatase', 'ggt': 'Gamma GT (GGTP)', 'ast_alt_ratio': 'AST/ALT Ratio',
    'total_protein': 'Total Proteins (Serum, Colorimetry)', 'albumin': 'Albumin (Serum, Bromocresol green)', 'globulin': 'Globulin (Serum)', 'ag_ratio': 'A/G Ratio (Serum)',
    # RFT
    'urea': 'Urea', 'bun': 'BUN', 'creatinine': 'Creatinine', 'egfr': 'eGFR', 'uric_acid': 'Uric Acid',
    # Electrolytes
    'sodium': 'Sodium', 'potassium': 'Potassium', 'chloride': 'Chloride', 'bicarbonate': 'Bicarbonate',
    'calcium': 'Calcium', 'magnesium': 'Magnesium', 'phosphorus': 'Phosphorus',
    # Lipid
    'total_chol': 'Total Cholesterol', 'triglycerides': 'Triglycerides', 'hdl': 'HDL', 'ldl': 'LDL',
    'vldl': 'VLDL', 'chol_hdl_ratio': 'Chol/HDL Ratio', 'ldl_hdl_ratio': 'LDL/HDL Ratio', 'non_hdl': 'Non-HDL',
    # TFT
    'tsh': 'TSH', 'free_t4': 'Free T4', 'total_t4': 'Total T4', 'free_t3': 'Free T3', 'total_t3': 'Total T3',
    # Glucose
    'fbs': 'FBS', 'rbs': 'RBS', 'hba1c': 'HbA1c', 'ppbs': '2hr PPBS',
    # Urine Routine
    'urine_appearance': 'Appearance',
    'urine_colour': 'Colour',
    'urine_ph': 'pH',
    'urine_sgravity': 'S. Gravity',
    'urine_protein': 'Protein',
    'urine_glucose': 'Glucose',
    'urine_ketones': 'Ketones',
    'urine_blood': 'Blood',
    'urine_nitrite': 'Nitrite',
    'urine_bilirubin': 'Bilirubin',
    'urine_urobilinogen': 'Urobilinogen',
    'urine_leucocyte': 'Leucocyte',
    'urine_pus_cells': 'Pus cells',
    'urine_epithelial_cells': 'Epithelial cells',
    'urine_rbc': 'RBC',
    'urine_cast': 'Cast',
    'urine_crystals': 'Crystals',
    'urine_ova_cyst': 'Ova or cyst',
    'urine_t_vaginalis': 'T. vaginalis',
    'urine_bacteria': 'Bacteria',
    'urine_yeast': 'Yeast like cells',
    'stool_consistency': 'Consistency',
    'stool_colour': 'Colour',
    'stool_mucus': 'Mucus',
    'stool_blood': 'Blood',
    'stool_pus': 'Pus',
    'stool_ova': 'Ova',
    'stool_parasites': 'Parasites',
    'stool_cysts': 'Cysts',
    'stool_undigested_food': 'Undigested food',
    'stool_fat_globules': 'Fat globules',
    'stool_rbc': 'RBC',
    'stool_wbc': 'WBC',
    # Malaria
    'malaria_result': 'Result', 'malaria_species': 'Species', 'malaria_count': 'Parasite Count',
    'malaria_parasitemia': '% Parasitemia', 'malaria_stage': 'Stage',
    # Blood Group
    'bg_group': 'Blood Group', 'bg_rhesus': 'Rhesus',
    # Sickle
    'sickle_solubility': 'Solubility Test', 'sickle_electrophoresis': 'Electrophoresis',
    # Coagulation
    'coag_pt': 'PT', 'coag_inr': 'INR', 'coag_aptt': 'APTT', 'coag_fibrinogen': 'Fibrinogen',
    # Serology
    'serology_result': 'Result', 'serology_titer': 'Titer',
    # Semen
    'semen_volume': 'Volume', 'semen_liquefaction': 'Liquefaction', 'semen_ph': 'pH',
    'semen_count': 'Sperm Count', 'semen_motility': 'Motility', 'semen_morphology': 'Morphology',
    'semen_wbc': 'WBC', 'semen_vitality': 'Vitality',
    # AFB
    'afb_result': 'Result', 'afb_grade': 'Grade', 'afb_organism': 'Organism',
}


def get_param_display_name(key: str) -> str:
    """Return human-readable parameter name for print/display."""
    return PARAM_DISPLAY_NAMES.get(key.lower(), key.replace('_', ' ').title())


# Reference ranges for each parameter (for lab report print)
PARAM_REF_RANGES = {
    # FBC
    'wbc': '4.0 - 11.0', 'lymph_count': '1.0 - 4.0', 'mid_count': '0.2 - 1.0', 'gran_count': '2.0 - 7.5',
    'lymph_perc': '20 - 45', 'mid_perc': '2 - 10', 'gran_perc': '40 - 75',
    'plt': '150 - 450', 'mpv': '7.5 - 11.5', 'pdw': '9 - 17', 'pct': '0.15 - 0.40',
    'rbc': 'M: 4.5-5.9, F: 3.8-5.2', 'hgb': 'M: 13.5-17.5, F: 12.0-16.0',
    'hct': 'M: 38-52, F: 36-46', 'mcv': '80 - 100', 'mch': '27 - 33', 'mchc': '31 - 36',
    'rdw_cv': '11.5 - 14.5', 'rdw_sd': '39 - 46',
    'neut_perc': '40 - 75', 'mono_perc': '2 - 10', 'eos_perc': '1 - 6', 'baso_perc': '0 - 2',
    # LFT (Serum; bilirubin µmol/L, proteins g/L)
    'total_bili': '3.42 - 20.52', 'direct_bili': '≤ 4.3', 'indirect_bili': '1.71 - 17.1',
    'alt': '0 - 42', 'ast': '0 - 40', 'alp': '25 - 147', 'ggt': '9 - 55', 'ast_alt_ratio': '< 1',
    'total_protein': '64 - 83', 'albumin': '38 - 50', 'globulin': '29 - 33', 'ag_ratio': '1.0 - 2.3',
    # RFT / Renal / Electrolytes (Serum)
    'urea': '1.7 - 8.3', 'bun': '7 - 20', 'creatinine': '30 - 120',
    'egfr': 'Normal/mild: >59; Moderate: 30-59; Severe: 15-29; End stage: <15',
    'uric_acid': '200 - 420',
    'sodium': '135 - 155', 'potassium': '3.6 - 5.5', 'chloride': '98 - 107', 'bicarbonate': '22 - 29',
    'calcium': '8.5 - 10.5', 'magnesium': '1.7 - 2.2', 'phosphorus': '2.5 - 4.5',
    # Lipid (mmol/L)
    'total_chol': 'Desirable ≤5.13; Borderline 5.15-6.13; High >6.13',
    'triglycerides': 'Normal <1.65; Borderline 1.65-2.19; Very high ≥5.5',
    'hdl': 'Major risk <1.05; Negative risk ≥1.55',
    'ldl': 'Optimal <2.56; Near 2.56-3.30; Borderline 3.33-4.07; High 4.10-4.84; Very high ≥4.87',
    'vldl': '0.16 - 1.04', 'chol_hdl_ratio': 'Target <5.1; Ideal ≤3.5',
    'ldl_hdl_ratio': 'Target <3.5:1; Ideal ≤2.5:1',
    'non_hdl': 'Optimal <3.4; Near 3.4-4.1; Borderline 4.15-4.90; High 4.9-5.7; Very high >5.7',
    # TFT (Serum, FIA)
    'tsh': '0.3 - 4.2', 'free_t4': '0.8 - 1.8', 'total_t4': '66 - 181',
    'free_t3': '2.3 - 4.2', 'total_t3': '1.23 - 3.07',
    # Glucose (mmol/L)
    'fbs': '3.6 - 6.4', 'rbs': '3.6 - 10.3', 'hba1c': '4.0 - 5.6', 'ppbs': '< 7.8',
    # Urine
    'urine_appearance': 'Clear / Hazy / Turbid', 'urine_colour': 'Straw / Yellow / Dark',
    'urine_ph': '4.5 - 8.0', 'urine_sgravity': '1.005 - 1.030',
    'urine_protein': 'Negative', 'urine_glucose': 'Negative', 'urine_ketones': 'Negative',
    'urine_blood': 'Negative', 'urine_nitrite': 'Negative', 'urine_bilirubin': 'Negative',
    'urine_urobilinogen': 'Normal', 'urine_leucocyte': 'Negative',
    'urine_pus_cells': '/HPF', 'urine_epithelial_cells': '/HPF', 'urine_rbc': '/HPF',
    'urine_cast': 'Not seen', 'urine_crystals': 'Not seen', 'urine_ova_cyst': 'Not seen',
    'urine_t_vaginalis': 'Not seen', 'urine_bacteria': 'Not seen', 'urine_yeast': 'Not seen',
    # Stool
    'stool_consistency': 'Formed / Soft / Loose', 'stool_colour': 'Brown', 'stool_mucus': 'Absent',
    'stool_blood': 'Absent', 'stool_pus': 'Absent', 'stool_ova': 'Not seen', 'stool_parasites': 'Not seen',
    'stool_cysts': 'Not seen', 'stool_rbc': 'Not seen', 'stool_wbc': 'Not seen',
    'stool_undigested_food': 'Absent', 'stool_fat_globules': 'Absent',
    # Malaria
    'malaria_result': 'Positive / Negative', 'malaria_species': 'P. falciparum / P. vivax / Mixed',
    'malaria_count': '/μL or /200 WBC', 'malaria_parasitemia': '% of parasitized RBCs',
    'malaria_stage': 'Trophozoites / Schizonts / Gametocytes',
    # Blood Group
    'bg_group': 'A / B / AB / O', 'bg_rhesus': 'Positive / Negative',
    # Sickle
    'sickle_solubility': 'Positive / Negative', 'sickle_electrophoresis': 'AA / AS / SS / AC',
    # Coagulation
    'coag_pt': '11 - 14', 'coag_inr': '0.8 - 1.2', 'coag_aptt': '25 - 35', 'coag_fibrinogen': '200 - 400',
    # Serology
    'serology_result': 'Reactive / Non-Reactive / Equivocal', 'serology_titer': 'VDRL, Widal, etc.',
    # Semen
    'semen_volume': '≥ 1.5 mL', 'semen_liquefaction': 'Complete < 60 min', 'semen_ph': '≥ 7.2',
    'semen_count': '≥ 15 ×10⁶/mL', 'semen_motility': '≥ 40% progressive', 'semen_morphology': '≥ 4% normal',
    'semen_wbc': '< 1 ×10⁶/mL', 'semen_vitality': '≥ 58% live',
    # AFB
    'afb_result': 'Positive / Negative', 'afb_grade': 'Scanty / 1+ / 2+ / 3+', 'afb_organism': 'M. tuberculosis / NTM',
}


def get_param_ref_range(key: str) -> str:
    """Return reference range for a parameter key."""
    return PARAM_REF_RANGES.get(key.lower(), '-')


# Units for each parameter (for lab report print)
PARAM_UNITS = {
    # FBC
    'wbc': '×10⁹/L', 'lymph_count': '×10⁹/L', 'mid_count': '×10⁹/L', 'gran_count': '×10⁹/L',
    'lymph_perc': '%', 'mid_perc': '%', 'gran_perc': '%',
    'plt': '×10⁹/L', 'mpv': 'fL', 'pdw': '%', 'pct': '%',
    'rbc': '×10¹²/L', 'hgb': 'g/dL', 'hct': '%', 'mcv': 'fL', 'mch': 'pg',
    'mchc': 'g/dL', 'rdw_cv': '%', 'rdw_sd': 'fL',
    'neut_perc': '%', 'mono_perc': '%', 'eos_perc': '%', 'baso_perc': '%',
    # LFT (Serum)
    'total_bili': 'µmol/L', 'direct_bili': 'µmol/L', 'indirect_bili': 'µmol/L',
    'alt': 'U/L', 'ast': 'U/L', 'alp': 'U/L', 'ggt': 'U/L', 'ast_alt_ratio': '',
    'total_protein': 'g/L', 'albumin': 'g/L', 'globulin': 'g/L', 'ag_ratio': '',
    # RFT / Electrolytes (Serum)
    'urea': 'mmol/L', 'bun': 'mg/dL', 'creatinine': 'µmol/L', 'egfr': 'mL/min/1.73m²',
    'uric_acid': 'µmol/L',
    'sodium': 'mmol/L', 'potassium': 'mmol/L', 'chloride': 'mmol/L', 'bicarbonate': 'mmol/L',
    'calcium': 'mg/dL', 'magnesium': 'mg/dL', 'phosphorus': 'mg/dL',
    # Lipid (Serum)
    'total_chol': 'mmol/L', 'triglycerides': 'mmol/L', 'hdl': 'mmol/L', 'ldl': 'mmol/L',
    'vldl': 'mmol/L', 'chol_hdl_ratio': '', 'ldl_hdl_ratio': '', 'non_hdl': 'mmol/L',
    # TFT (Serum)
    'tsh': 'mIU/L', 'free_t4': 'ng/dL', 'total_t4': 'nmol/L', 'free_t3': 'pg/mL', 'total_t3': 'nmol/L',
    # Glucose (mmol/L - Ghana/WEST AFRICA standard)
    'fbs': 'mmol/L', 'rbs': 'mmol/L', 'hba1c': '%', 'ppbs': 'mmol/L',
    # Urine (qualitative/categorical)
    'urine_appearance': '', 'urine_colour': '', 'urine_ph': '', 'urine_sgravity': '',
    'urine_protein': '', 'urine_glucose': '', 'urine_ketones': '', 'urine_blood': '',
    'urine_nitrite': '', 'urine_bilirubin': '', 'urine_urobilinogen': '', 'urine_leucocyte': '',
    'urine_pus_cells': '/HPF', 'urine_epithelial_cells': '/HPF', 'urine_rbc': '/HPF',
    'urine_cast': '', 'urine_crystals': '', 'urine_ova_cyst': '', 'urine_t_vaginalis': '',
    'urine_bacteria': '', 'urine_yeast': '',
    # Stool
    'stool_consistency': '', 'stool_colour': '', 'stool_mucus': '', 'stool_blood': '',
    'stool_pus': '', 'stool_ova': '', 'stool_parasites': '', 'stool_cysts': '',
    'stool_rbc': '', 'stool_wbc': '', 'stool_undigested_food': '', 'stool_fat_globules': '',
    # Malaria
    'malaria_result': 'Qualitative', 'malaria_species': '', 'malaria_count': '/μL',
    'malaria_parasitemia': '%', 'malaria_stage': '',
    # Blood Group
    'bg_group': '', 'bg_rhesus': '',
    # Sickle
    'sickle_solubility': 'Qualitative', 'sickle_electrophoresis': '',
    # Coagulation
    'coag_pt': 'sec', 'coag_inr': '', 'coag_aptt': 'sec', 'coag_fibrinogen': 'mg/dL',
    # Serology
    'serology_result': 'Qualitative', 'serology_titer': '',
    # Semen
    'semen_volume': 'mL', 'semen_liquefaction': '', 'semen_ph': '', 'semen_count': '×10⁶/mL',
    'semen_motility': '%', 'semen_morphology': '%', 'semen_wbc': '×10⁶/mL', 'semen_vitality': '%',
    # AFB
    'afb_result': 'Qualitative', 'afb_grade': '', 'afb_organism': '',
}


def get_param_units(key: str, details: Optional[dict] = None) -> str:
    """Return units for a parameter key. If details has key_unit, use that override."""
    if details is not None:
        raw = details.get(f'{key}_unit', '')
        override = str(raw).strip() if raw is not None else ''
        if override:
            return override
    u = PARAM_UNITS.get(key.lower(), '')
    return u if u else 'N/A'


# Unit options for dropdowns (param -> list of unit strings). Empty list = use default only.
PARAM_UNIT_OPTIONS = {
    # Glucose: mmol/L (intl) vs mg/dL (US)
    'fbs': ['mmol/L', 'mg/dL'],
    'rbs': ['mmol/L', 'mg/dL'],
    'ppbs': ['mmol/L', 'mg/dL'],
    # HbA1c: % vs mmol/mol (IFCC)
    'hba1c': ['%', 'mmol/mol'],
    # Creatinine, urea
    'creatinine': ['mg/dL', 'μmol/L'],
    'uric_acid': ['µmol/L', 'mg/dL'],
    'urea': ['mg/dL', 'mmol/L'],
    'bun': ['mg/dL', 'mmol/L'],
    # Electrolytes
    'sodium': ['mmol/L', 'mEq/L'],
    'potassium': ['mmol/L', 'mEq/L'],
    'chloride': ['mmol/L', 'mEq/L'],
    'bicarbonate': ['mmol/L', 'mEq/L'],
    # Lipids
    'total_chol': ['mg/dL', 'mmol/L'],
    'triglycerides': ['mg/dL', 'mmol/L'],
    'hdl': ['mg/dL', 'mmol/L'],
    'ldl': ['mg/dL', 'mmol/L'],
    'vldl': ['mg/dL', 'mmol/L'],
    'non_hdl': ['mg/dL', 'mmol/L'],
    # LFT: bilirubin µmol/L (SI) vs mg/dL; proteins g/L vs g/dL
    'total_bili': ['µmol/L', 'mg/dL'],
    'direct_bili': ['µmol/L', 'mg/dL'],
    'indirect_bili': ['µmol/L', 'mg/dL'],
    'total_protein': ['g/L', 'g/dL'],
    'albumin': ['g/L', 'g/dL'],
    'globulin': ['g/L', 'g/dL'],
}


def get_param_unit_options(key: str) -> list:
    """Return list of unit options for a parameter's dropdown. Includes default from PARAM_UNITS."""
    opts = PARAM_UNIT_OPTIONS.get(key.lower(), [])
    default = PARAM_UNITS.get(key.lower(), '')
    if opts:
        return opts
    return [default] if default else []


def _parse_numeric(value_str: str):
    """Parse a numeric value from string. Returns float or None if not numeric."""
    if value_str is None:
        return None
    s = str(value_str).strip().replace(',', '')
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_ref_range(ref_str: str, patient_gender=None) -> tuple:
    """
    Parse reference range string into (low, high) for numeric comparison.
    - Simple: "4.0 - 11.0", "0-42" -> (4.0, 11.0), (0, 42)
    - One-sided: "> 60", "< 200", "≥ 60" -> (60, None) or (None, 200)
    - Gender-specific: "M: 4.5-5.9, F: 3.8-5.2" -> use patient gender if available
    Returns (low, high) where either can be None for unbounded.
    """
    if not ref_str or not isinstance(ref_str, str):
        return (None, None)
    ref = ref_str.strip()
    if not ref:
        return (None, None)

    # Gender-specific: "M: 4.5-5.9, F: 3.8-5.2"
    gender_match = re.match(r'(?i)M:\s*([\d.]+)\s*[-–]\s*([\d.]+).*F:\s*([\d.]+)\s*[-–]\s*([\d.]+)', ref)
    if gender_match:
        m_lo, m_hi, f_lo, f_hi = map(float, gender_match.groups())
        if patient_gender and str(patient_gender).upper() in ('F', 'FEMALE'):
            return (f_lo, f_hi)
        return (m_lo, m_hi)  # Default to male range

    # One-sided: "> 60", "≥ 60", "< 200", "<= 200"
    gt_match = re.match(r'(?:>|≥)\s*([\d.]+)', ref)
    if gt_match:
        return (float(gt_match.group(1)), None)
    lt_match = re.match(r'(?:<|≤)\s*([\d.]+)', ref)
    if lt_match:
        return (None, float(lt_match.group(1)))

    # Simple range: "4.0 - 11.0" or "4.0-11.0" or "0-42"
    range_match = re.match(r'([\d.]+)\s*[-–]\s*([\d.]+)', ref)
    if range_match:
        return (float(range_match.group(1)), float(range_match.group(2)))

    # Compact "4.0-11.0" (no spaces)
    compact = re.match(r'^([\d.]+)\s*[-–]\s*([\d.]+)', ref.replace(' ', ''))
    if compact:
        return (float(compact.group(1)), float(compact.group(2)))

    return (None, None)


def resolve_lab_row_flag(
    key: str,
    value,
    details: Optional[dict],
    ref_range_str: str,
    is_abnormal_model: bool,
    patient_gender=None,
) -> tuple:
    """
    Returns (flag_display, value_flag) for printed lab rows.
    If details[key+'_flag'] is set to NORMAL, ABNORMAL, H, or L, that choice is used (manual).
    Empty or missing _flag falls back to automatic rules (reference range + qualitative heuristics).
    """
    d = details or {}
    manual = d.get(f'{key}_flag')
    if manual is not None:
        m = str(manual).strip().upper()
        if m in ('', 'AUTO'):
            m = ''
        if m in ('NORMAL', 'ABNORMAL', 'H', 'L'):
            vf = m if m in ('H', 'L') else None
            return m, vf
    value_flag = compute_value_flag(str(value), ref_range_str, patient_gender)
    if value_flag:
        return value_flag, value_flag
    flag_val = get_qualitative_flag(str(value), is_abnormal_model)
    return flag_val, None


def compute_value_flag(value_str: str, ref_range_str: str, patient_gender=None) -> Optional[str]:
    """
    Determine if a numeric lab value is High (H), Low (L), or Normal.
    Returns 'H', 'L', or None (normal). For non-numeric values or non-parseable
    ref ranges, returns None.
    Used to auto-color values red and show H/L in print reports.
    """
    num_val = _parse_numeric(value_str)
    if num_val is None:
        return None
    low, high = _parse_ref_range(ref_range_str, patient_gender)
    if low is None and high is None:
        return None
    if low is not None and num_val < low:
        return 'L'
    if high is not None and num_val > high:
        return 'H'
    return None  # Normal


def get_qualitative_flag(result_text: str, is_abnormal: bool) -> str:
    """
    Derive NORMAL/ABNORMAL flag from qualitative result text.
    Non-Reactive, Negative, Normal -> NORMAL. Reactive, Positive, Equivocal -> ABNORMAL.
    Parasitemia, mps seen, parasites seen -> ABNORMAL (malaria positive).
    """
    if is_abnormal:
        return 'ABNORMAL'
    text = (result_text or '').upper()
    # Check for abnormal: REACTIVE (excluding NON-REACTIVE), POSITIVE, EQUIVOCAL
    remainder = text.replace('NON-REACTIVE', '')
    if 'REACTIVE' in remainder:
        return 'ABNORMAL'
    if 'POSITIVE' in text or 'EQUIVOCAL' in text or 'ABNORMAL' in text:
        return 'ABNORMAL'
    # Malaria/parasite: parasitemia, mps seen, parasites seen = positive = ABNORMAL
    if 'PARASITEMIA' in text:
        return 'ABNORMAL'
    if 'SEEN' in text and ('MPS' in text or 'PARA' in text or 'PARASITE' in text):
        return 'ABNORMAL'
    return 'NORMAL'  # Non-Reactive, Negative, Normal, or default


def infer_units_from_result(result_text: str) -> str:
    """
    Infer units from result text when not explicitly stored.
    E.g. "1,435 para/uL" -> parasites/μL, "5.2 mmol/L" -> mmol/L.
    """
    if not result_text:
        return ''
    text = (result_text or '').lower()
    if 'para/ul' in text or 'para/μl' in text or 'parasites/ul' in text or '/μl' in text:
        return 'parasites/μL'
    if 'mmol/l' in text:
        return 'mmol/L'
    if 'mg/dl' in text:
        return 'mg/dL'
    if 'g/dl' in text:
        return 'g/dL'
    return ''


# Ordered keys for urine and stool reports (CHEMISTRY before MICROSCOPY)
URINE_ORDERED_KEYS = [
    'urine_appearance', 'urine_colour', 'urine_ph', 'urine_sgravity',
    'urine_protein', 'urine_glucose', 'urine_ketones', 'urine_blood',
    'urine_nitrite', 'urine_bilirubin', 'urine_urobilinogen', 'urine_leucocyte',
    'urine_pus_cells', 'urine_epithelial_cells', 'urine_rbc', 'urine_cast',
    'urine_crystals', 'urine_ova_cyst', 'urine_t_vaginalis', 'urine_bacteria', 'urine_yeast',
]
STOOL_ORDERED_KEYS = [
    'stool_consistency', 'stool_colour', 'stool_mucus', 'stool_blood', 'stool_pus',
    'stool_ova', 'stool_parasites', 'stool_cysts', 'stool_rbc', 'stool_wbc',
    'stool_undigested_food', 'stool_fat_globules',
]
# FBC ordered keys (Evans Lab format)
FBC_ORDERED_KEYS = [
    'wbc', 'lymph_count', 'mid_count', 'gran_count', 'lymph_perc', 'mid_perc', 'gran_perc',
    'plt', 'mpv', 'pdw', 'pct',
    'rbc', 'hgb', 'hct', 'mcv', 'mch', 'mchc', 'rdw_cv', 'rdw_sd',
    'neut_perc', 'mono_perc', 'eos_perc', 'baso_perc',
]
MALARIA_ORDERED_KEYS = ['malaria_result', 'malaria_species', 'malaria_count', 'malaria_parasitemia', 'malaria_stage']
BLOOD_GROUP_ORDERED_KEYS = ['bg_group', 'bg_rhesus']
SICKLE_ORDERED_KEYS = ['sickle_solubility', 'sickle_electrophoresis']
COAGULATION_ORDERED_KEYS = ['coag_pt', 'coag_inr', 'coag_aptt', 'coag_fibrinogen']
SEROLOGY_ORDERED_KEYS = ['serology_result', 'serology_titer']
SEMEN_ORDERED_KEYS = ['semen_volume', 'semen_liquefaction', 'semen_ph', 'semen_count', 'semen_motility', 'semen_morphology', 'semen_wbc', 'semen_vitality']
AFB_ORDERED_KEYS = ['afb_result', 'afb_grade', 'afb_organism']

# RFT: renal panel + electrolytes (uric acid is a separate test — TEMPLATE_SINGLE / result_value)
RFT_ORDERED_KEYS = [
    'urea', 'bun', 'creatinine', 'egfr',
    'sodium', 'potassium', 'chloride', 'bicarbonate', 'calcium', 'magnesium', 'phosphorus',
]
# BUE / U&E: urea + electrolytes only (no creatinine, eGFR, uric acid)
BUE_ORDERED_KEYS = [
    'urea', 'bun',
    'sodium', 'potassium', 'chloride', 'bicarbonate', 'calcium', 'magnesium', 'phosphorus',
]
LFT_ORDERED_KEYS = [
    'total_protein', 'albumin', 'globulin', 'ag_ratio',
    'total_bili', 'direct_bili', 'indirect_bili',
    'alt', 'ast', 'ast_alt_ratio', 'alp', 'ggt',
]
LIPID_ORDERED_KEYS = [
    'total_chol', 'triglycerides', 'hdl', 'ldl', 'vldl',
    'chol_hdl_ratio', 'ldl_hdl_ratio', 'non_hdl',
]
TFT_ORDERED_KEYS = ['tsh', 'free_t4', 'total_t4', 'free_t3', 'total_t3']
GLUCOSE_ORDERED_KEYS = ['fbs', 'rbs', 'hba1c', 'ppbs']
ELECTROLYTES_ORDERED_KEYS = ['sodium', 'potassium', 'chloride', 'bicarbonate', 'calcium', 'magnesium', 'phosphorus']

# Allowed detail keys per template for SAVE — only these keys are stored for each test type.
# Prevents FBC result from storing uric_acid, RFT params, etc. from hidden form sections.
ORDERED_KEYS_BY_TEMPLATE = {
    TEMPLATE_FBC: FBC_ORDERED_KEYS,
    TEMPLATE_LFT: LFT_ORDERED_KEYS,
    TEMPLATE_RFT: RFT_ORDERED_KEYS,
    TEMPLATE_BUE: BUE_ORDERED_KEYS,
    TEMPLATE_LIPID: LIPID_ORDERED_KEYS,
    TEMPLATE_TFT: TFT_ORDERED_KEYS,
    TEMPLATE_GLUCOSE: GLUCOSE_ORDERED_KEYS,
    TEMPLATE_ELECTROLYTES: ELECTROLYTES_ORDERED_KEYS,
    TEMPLATE_URINE: URINE_ORDERED_KEYS,
    TEMPLATE_STOOL: STOOL_ORDERED_KEYS,
    TEMPLATE_MALARIA: MALARIA_ORDERED_KEYS,
    TEMPLATE_BLOOD_GROUP: BLOOD_GROUP_ORDERED_KEYS,
    TEMPLATE_SICKLE: SICKLE_ORDERED_KEYS,
    TEMPLATE_COAGULATION: COAGULATION_ORDERED_KEYS,
    TEMPLATE_SEROLOGY: SEROLOGY_ORDERED_KEYS,
    TEMPLATE_SEMEN: SEMEN_ORDERED_KEYS,
    TEMPLATE_AFB: AFB_ORDERED_KEYS,
}


def get_ordered_keys_for_result_display(test_type: Optional[str]) -> Optional[List[str]]:
    """Stable row order for printed/panel reports; None → caller may fall back to details.keys()."""
    if not test_type or test_type == TEMPLATE_SINGLE:
        return None
    return ORDERED_KEYS_BY_TEMPLATE.get(test_type)


def get_allowed_detail_keys_for_save(test_type: str):
    """
    Return set of allowed detail keys (and their _unit variants) for the given template.
    Used when saving lab results so only params for THIS test are stored (no cross-test mixing).
    """
    allowed = set()
    keys_list = ORDERED_KEYS_BY_TEMPLATE.get(test_type)
    if keys_list:
        for k in keys_list:
            allowed.add(k)
            allowed.add(f'{k}_unit')
            allowed.add(f'{k}_flag')
    if test_type == TEMPLATE_SINGLE:
        allowed.update(['result_value', 'result_unit', 'RESULT_VALUE', 'RESULT_UNIT', 'result_value_flag'])
    return allowed


def build_lab_result_display_rows(result, patient_gender: Optional[str] = None) -> List[dict]:
    """
    Build display rows from a LabResult, matching the shape used by print views:
    {parameter, result, units, ref_range, flag, value_flag}.
    """
    result_rows: List[dict] = []
    raw_details = getattr(result, 'details', None) or {}
    details: dict = {}
    if isinstance(raw_details, dict):
        details = raw_details
    elif isinstance(raw_details, str) and raw_details.strip():
        try:
            parsed = json.loads(raw_details)
            if isinstance(parsed, dict):
                details = parsed
        except (json.JSONDecodeError, TypeError, ValueError):
            details = {}

    if isinstance(details, dict):
        test = getattr(result, 'test', None)
        test_type = get_lab_result_template_type(test) if test else None
        result_value = details.get('result_value') or details.get('RESULT_VALUE')

        # Panel tests must use the panel branch even if a stray result_value key exists.
        if test_type and test_type != TEMPLATE_SINGLE:
            ordered_keys = get_ordered_keys_for_result_display(test_type)
            keys_to_iterate = ordered_keys if ordered_keys else list(details.keys())
            for key in keys_to_iterate:
                if key.lower() in ('result_value', 'result_unit'):
                    continue
                if key.endswith('_unit') or key.endswith('_flag'):
                    continue
                value = details.get(key)
                if value is None or str(value).strip() == '':
                    continue
                param_label = get_param_display_name(key)
                ref_range = get_param_ref_range(key)
                units_val = get_param_units(key, details)
                flag_val, value_flag = resolve_lab_row_flag(
                    key, value, details, ref_range, getattr(result, 'is_abnormal', False), patient_gender
                )
                result_rows.append({
                    'parameter': param_label,
                    'result': value,
                    'units': units_val,
                    'ref_range': ref_range,
                    'flag': flag_val,
                    'value_flag': value_flag,
                })
        elif result_value:
            ref = '-'
            if getattr(result, 'range_low', None) and getattr(result, 'range_high', None):
                ref = f'{result.range_low} - {result.range_high}'
            elif getattr(result, 'range_low', None):
                ref = result.range_low
            elif getattr(result, 'range_high', None):
                ref = result.range_high
            units_val = (
                details.get('result_unit') or details.get('RESULT_UNIT') or getattr(result, 'units', None) or
                infer_units_from_result(result_value) or 'N/A'
            )
            flag_val, value_flag = resolve_lab_row_flag(
                'result_value', result_value, details, ref, getattr(result, 'is_abnormal', False), patient_gender
            )
            result_rows.append({
                'parameter': getattr(test, 'name', None) or 'Result',
                'result': result_value,
                'units': units_val,
                'ref_range': ref,
                'flag': flag_val,
                'value_flag': value_flag,
            })

        # Misclassified templates (often default SINGLE) and legacy rows: tabular save still stores
        # keys like serology_result / bg_group without result_value — iterate all detail keys.
        if not result_rows and details:
            for key in sorted(details.keys()):
                if key.lower() in ('result_value', 'result_unit'):
                    continue
                if key.endswith('_unit') or key.endswith('_flag'):
                    continue
                value = details.get(key)
                if value is None or str(value).strip() == '':
                    continue
                param_label = get_param_display_name(key)
                ref_range = get_param_ref_range(key)
                units_val = get_param_units(key, details)
                flag_val, value_flag = resolve_lab_row_flag(
                    key, value, details, ref_range, getattr(result, 'is_abnormal', False), patient_gender
                )
                result_rows.append({
                    'parameter': param_label,
                    'result': value,
                    'units': units_val,
                    'ref_range': ref_range,
                    'flag': flag_val,
                    'value_flag': value_flag,
                })

    if not result_rows and getattr(result, 'value', None):
        ref = '-'
        if getattr(result, 'range_low', None) and getattr(result, 'range_high', None):
            ref = f'{result.range_low} - {result.range_high}'
        elif getattr(result, 'range_low', None) or getattr(result, 'range_high', None):
            low = getattr(result, 'range_low', '') or ''
            high = getattr(result, 'range_high', '') or ''
            ref = (low + (' - ' if low and high else '') + high) or '-'
        units_val = getattr(result, 'units', None) or 'N/A'
        flag_val, value_flag = resolve_lab_row_flag(
            'result_value', result.value, details if isinstance(details, dict) else {}, ref,
            getattr(result, 'is_abnormal', False), patient_gender
        )
        result_rows.append({
            'parameter': getattr(getattr(result, 'test', None), 'name', None) or 'Result',
            'result': result.value,
            'units': units_val,
            'ref_range': ref,
            'flag': flag_val,
            'value_flag': value_flag,
        })

    if not result_rows and getattr(result, 'qualitative_result', None):
        qual = getattr(result, 'qualitative_result', None)
        flag_val = get_qualitative_flag(qual, getattr(result, 'is_abnormal', False))
        units_val = infer_units_from_result(qual) or 'Qualitative'
        result_rows.append({
            'parameter': getattr(getattr(result, 'test', None), 'name', None) or 'Result',
            'result': qual,
            'units': units_val,
            'ref_range': 'Reactive / Non-Reactive / Equivocal',
            'flag': flag_val,
            'value_flag': None,
        })

    return result_rows


def lab_result_list_summary(result, patient_gender: Optional[str] = None) -> dict:
    """
    Summary for list tables where only one cell exists for Result/Unit/Reference.
    Returns: {result_text, unit_text, ref_text, is_pending}.
    """
    rows = build_lab_result_display_rows(result, patient_gender=patient_gender)
    if rows:
        max_items = 2
        parts: List[str] = []
        for r in rows[:max_items]:
            label = str(r.get('parameter') or '').strip()
            val = str(r.get('result') or '').strip()
            if label and val:
                parts.append(f'{label}: {val}')
            elif val:
                parts.append(val)
        more = len(rows) - len(parts)
        result_text = '; '.join(parts)
        if more > 0:
            result_text = f'{result_text} (+{more} more)' if result_text else f'(+{more} more)'

        unit_text = next(
            (str(r.get('units') or '').strip() for r in rows if str(r.get('units') or '').strip() not in ('', '-', 'N/A', 'Qualitative')),
            str(rows[0].get('units') or '').strip()
        )
        unit_text = unit_text or '—'

        refs = [str(r.get('ref_range') or '').strip() for r in rows if str(r.get('ref_range') or '').strip() and str(r.get('ref_range') or '').strip() != '-']
        ref_text = refs[0] if refs else '—'
        if len(set(refs)) > 1:
            ref_text = 'Multiple (see report)'

        return {'result_text': result_text or '—', 'unit_text': unit_text, 'ref_text': ref_text, 'is_pending': False}

    # Fallback to legacy scalar fields
    value = (getattr(result, 'value', None) or '').strip() if hasattr(getattr(result, 'value', ''), 'strip') else getattr(result, 'value', None)
    qualitative = (getattr(result, 'qualitative_result', None) or '').strip() if hasattr(getattr(result, 'qualitative_result', ''), 'strip') else getattr(result, 'qualitative_result', None)
    units = (getattr(result, 'units', None) or '').strip() if hasattr(getattr(result, 'units', ''), 'strip') else getattr(result, 'units', None)
    low = (getattr(result, 'range_low', None) or '').strip() if hasattr(getattr(result, 'range_low', ''), 'strip') else getattr(result, 'range_low', None)
    high = (getattr(result, 'range_high', None) or '').strip() if hasattr(getattr(result, 'range_high', ''), 'strip') else getattr(result, 'range_high', None)

    result_text = value or qualitative or ''
    if low and high:
        ref_text = f'{low} – {high}'
    elif low:
        ref_text = f'≥ {low}'
    elif high:
        ref_text = f'≤ {high}'
    else:
        ref_text = '—'

    if not (result_text and str(result_text).strip()) and getattr(result, 'attachment', None):
        return {
            'result_text': 'See attached report',
            'unit_text': '—',
            'ref_text': '—',
            'is_pending': False,
        }

    return {
        'result_text': result_text or '—',
        'unit_text': units or '—',
        'ref_text': ref_text,
        'is_pending': not bool(result_text),
    }
