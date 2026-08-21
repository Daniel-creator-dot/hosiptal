"""
PrimeCare measurable (kit) vs immeasurable (chemistry) lab stock catalog.

Source: Laboratory letter, 20 May 2024 — kit tests counted by piece;
chemistry reagents counted as remaining tests per kit.
"""
from __future__ import annotations

import re

STOCK_TRACKING_UNTRACKED = "untracked"
STOCK_TRACKING_MEASURABLE = "measurable"
STOCK_TRACKING_IMMEASURABLE = "immeasurable"

STOCK_TRACKING_CHOICES = [
    (STOCK_TRACKING_UNTRACKED, "Not tracked"),
    (STOCK_TRACKING_MEASURABLE, "Measurable (kit / cassette)"),
    (STOCK_TRACKING_IMMEASURABLE, "Immeasurable (chemistry reagent)"),
]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def name_matches_aliases(name: str, code: str, aliases: list[str]) -> bool:
    blob = f"{_norm(name)} {_norm(code)}".strip()
    if not blob:
        return False
    padded = f" {blob} "
    for alias in aliases:
        a = _norm(alias)
        if not a:
            continue
        if f" {a} " in padded:
            return True
    return False


# Kit / cassette tests: opening a box adds qty_per_box pieces; each completed test uses 1.
MEASURABLE_KITS = [
    {
        "code": "KIT-TYPH",
        "name": "Typhoid IgG/IgM",
        "qty_per_box": 25,
        "aliases": ["typhoid", "typhidot", "typhi dot", "salmonella typhi"],
    },
    {
        "code": "KIT-BF-RDT",
        "name": "Malaria BF RDT",
        "qty_per_box": 25,
        "aliases": ["bf rdt", "malaria rdt", "malaria pf", "mrdt", "p falciparum rdt"],
    },
    {
        "code": "KIT-HPYL",
        "name": "H. pylori Ab/Ag",
        "qty_per_box": 25,
        "aliases": ["h pylori", "hpylori", "helicobacter"],
    },
    {
        "code": "KIT-HBA1C",
        "name": "HbA1c kit",
        "qty_per_box": 25,
        "aliases": ["hba1c", "hb a1c", "glycated haemoglobin", "glycated hemoglobin", "a1c"],
    },
    {
        "code": "KIT-PREG",
        "name": "Pregnancy test",
        "qty_per_box": 25,
        "aliases": ["pregnancy", "urine pregnancy", "upt"],
    },
    {
        "code": "KIT-URINE-RE",
        "name": "Urine RE strips",
        "qty_per_box": 100,
        "aliases": ["urine re", "urine r e", "urinalysis", "urine routine", "urine dipstick"],
    },
    {
        "code": "KIT-HBSAG",
        "name": "HBsAg (Hepatitis B)",
        "qty_per_box": 25,
        "aliases": ["hbsag", "hbs ag", "hepatitis b", "hep b"],
    },
    {
        "code": "KIT-HCV",
        "name": "HCV (Hepatitis C)",
        "qty_per_box": 25,
        "aliases": ["hcv", "hepatitis c", "hep c"],
    },
    {
        "code": "KIT-VDRL",
        "name": "VDRL / Syphilis",
        "qty_per_box": 25,
        "aliases": ["vdrl", "syphilis", "rpr", "tpha"],
    },
    {
        "code": "KIT-HIV",
        "name": "HIV Retroscreen",
        "qty_per_box": 25,
        "aliases": ["retroscreen", "hiv rapid", "hiv 1", "hiv 2", "hiv i ii", "hiv"],
    },
    {
        "code": "KIT-HBV-PROF",
        "name": "HBV profile",
        "qty_per_box": 25,
        "aliases": ["hbv profile", "hepatitis b profile"],
    },
    {
        "code": "KIT-OVUL",
        "name": "Ovulation test",
        "qty_per_box": 25,
        "aliases": ["ovulation"],
    },
    {
        "code": "KIT-GONO",
        "name": "Gonorrhea Abs",
        "qty_per_box": 25,
        "aliases": ["gonorrhea", "gonorrhoea", "neisseria gonorrhoeae"],
    },
    {
        "code": "KIT-CHLAM",
        "name": "Chlamydia",
        "qty_per_box": 25,
        "aliases": ["chlamydia"],
    },
    {
        "code": "KIT-T3",
        "name": "T3 kit",
        "qty_per_box": 25,
        "aliases": ["free t3", "t3"],
        "skip_if_name_has": ["tft", "thyroid function"],
    },
    {
        "code": "KIT-T4",
        "name": "T4 kit",
        "qty_per_box": 25,
        "aliases": ["free t4", "t4"],
        "skip_if_name_has": ["tft", "thyroid function"],
    },
    {
        "code": "KIT-TSH",
        "name": "TSH kit",
        "qty_per_box": 25,
        "aliases": ["tsh"],
        "skip_if_name_has": ["tft", "thyroid function"],
    },
    {
        "code": "KIT-TFT",
        "name": "Thyroid function (T3/T4/TSH)",
        "qty_per_box": 25,
        "aliases": ["thyroid function", "tft"],
        "also_link_codes": ["KIT-T3", "KIT-T4", "KIT-TSH"],
    },
    {
        "code": "KIT-PSA",
        "name": "PSA kit",
        "qty_per_box": 25,
        "aliases": ["psa", "prostate specific"],
    },
    {
        "code": "KIT-DDIMER",
        "name": "D-dimer kit",
        "qty_per_box": 25,
        "aliases": ["d dimer", "ddimer"],
    },
    {
        "code": "KIT-BHCG",
        "name": "B-HCG kit",
        "qty_per_box": 25,
        "aliases": ["bhcg", "b hcg", "beta hcg", "serum hcg"],
    },
    {
        "code": "KIT-AMH",
        "name": "AMH kit",
        "qty_per_box": 25,
        "aliases": ["amh", "anti mullerian"],
    },
    {
        "code": "KIT-PROG",
        "name": "Progesterone kit",
        "qty_per_box": 25,
        "aliases": ["progesterone"],
    },
    {
        "code": "KIT-FSH",
        "name": "FSH kit",
        "qty_per_box": 25,
        "aliases": ["fsh"],
    },
    {
        "code": "KIT-LH",
        "name": "LH kit",
        "qty_per_box": 25,
        "aliases": ["lh", "luteinizing"],
    },
    {
        "code": "KIT-E2",
        "name": "Estradiol kit",
        "qty_per_box": 25,
        "aliases": ["estradiol", "oestradiol"],
    },
    {
        "code": "KIT-TROP",
        "name": "Troponin I kit",
        "qty_per_box": 25,
        "aliases": ["troponin"],
    },
]


# Chemistry: opening a kit adds tests_per_kit remaining tests; each completed test uses 1.
IMMEASURABLE_REAGENTS = [
    {
        "code": "CHEM-UREA",
        "name": "Urea reagent",
        "tests_per_kit": 330,
        "volume_note": "R1: 4x35ml; R2: 2x18ml",
        "aliases": ["urea"],
        "panel_aliases": ["bue", "uec", "kidney function", "rft"],
    },
    {
        "code": "CHEM-CREAT",
        "name": "Creatinine reagent",
        "tests_per_kit": 100,
        "volume_note": "R1: 2x27ml; R2: 1x18ml",
        "aliases": ["creatinine", "creat"],
        "panel_aliases": ["bue", "uec", "kidney function", "rft"],
    },
    {
        "code": "CHEM-NA",
        "name": "Sodium (Na) reagent",
        "tests_per_kit": 150,
        "volume_note": "2x100ml",
        "aliases": ["sodium"],
        "panel_aliases": ["electrolyte", "uec"],
    },
    {
        "code": "CHEM-K",
        "name": "Potassium (K) reagent",
        "tests_per_kit": 150,
        "volume_note": "2x100ml",
        "aliases": ["potassium"],
        "panel_aliases": ["electrolyte", "uec"],
    },
    {
        "code": "CHEM-CL",
        "name": "Chloride (Cl) reagent",
        "tests_per_kit": 80,
        "volume_note": "2x50ml",
        "aliases": ["chloride"],
        "panel_aliases": ["electrolyte", "uec"],
    },
    {
        "code": "CHEM-TP",
        "name": "Total protein reagent",
        "tests_per_kit": 630,
        "volume_note": "4x40ml",
        "aliases": ["total protein"],
        "panel_aliases": ["lft", "liver function"],
    },
    {
        "code": "CHEM-ALB",
        "name": "Albumin reagent",
        "tests_per_kit": 390,
        "volume_note": "4x40ml",
        "aliases": ["albumin"],
        "panel_aliases": ["lft", "liver function"],
    },
    {
        "code": "CHEM-TBIL",
        "name": "Total bilirubin reagent",
        "tests_per_kit": 370,
        "volume_note": "R1: 4x20ml; R2: 1x20ml",
        "aliases": ["total bilirubin"],
        "panel_aliases": ["lft", "liver function"],
    },
    {
        "code": "CHEM-DBIL",
        "name": "Direct bilirubin reagent",
        "tests_per_kit": 370,
        "volume_note": "R1: 4x20ml; R2: 1x20ml",
        "aliases": ["direct bilirubin", "conjugated bilirubin"],
        "panel_aliases": ["lft", "liver function"],
    },
    {
        "code": "CHEM-ALT",
        "name": "ALT reagent",
        "tests_per_kit": 500,
        "volume_note": "R1: 4x35ml; R2: 2x18ml",
        "aliases": ["alt", "sgpt", "alanine amino"],
        "panel_aliases": ["lft", "liver function"],
    },
    {
        "code": "CHEM-AST",
        "name": "AST reagent",
        "tests_per_kit": 500,
        "volume_note": "R1: 4x35ml; R2: 2x18ml",
        "aliases": ["ast", "sgot", "aspartate amino"],
        "panel_aliases": ["lft", "liver function"],
    },
    {
        "code": "CHEM-ALP",
        "name": "ALP reagent",
        "tests_per_kit": 500,
        "volume_note": "R1: 4x35ml; R2: 2x18ml",
        "aliases": ["alp", "alkaline phosphatase"],
        "panel_aliases": ["lft", "liver function"],
    },
    {
        "code": "CHEM-GGT",
        "name": "GGT reagent",
        "tests_per_kit": 500,
        "volume_note": "R1: 4x35ml; R2: 2x18ml",
        "aliases": ["ggt", "gamma gt", "gamma glutamyl"],
        "panel_aliases": ["lft", "liver function"],
    },
    {
        "code": "CHEM-CHOL",
        "name": "Total cholesterol reagent",
        "tests_per_kit": 390,
        "volume_note": "4x40ml",
        "aliases": ["total cholesterol", "cholesterol"],
        "skip_if_name_has": ["hdl", "ldl"],
        "panel_aliases": ["lipid", "lipogram"],
    },
    {
        "code": "CHEM-TRIG",
        "name": "Triglyceride reagent",
        "tests_per_kit": 390,
        "volume_note": "4x40ml",
        "aliases": ["triglyceride", "trig"],
        "panel_aliases": ["lipid", "lipogram"],
    },
    {
        "code": "CHEM-HDL",
        "name": "HDL reagent",
        "tests_per_kit": 110,
        "volume_note": "R1: 1x40ml; R2: 1x14ml",
        "aliases": ["hdl"],
        "panel_aliases": ["lipid", "lipogram"],
    },
    {
        "code": "CHEM-LDL",
        "name": "LDL reagent",
        "tests_per_kit": 110,
        "volume_note": "R1: 1x40ml; R2: 1x14ml",
        "aliases": ["ldl"],
        "panel_aliases": ["lipid", "lipogram"],
    },
    {
        "code": "CHEM-URIC",
        "name": "Uric acid reagent",
        "tests_per_kit": 460,
        "volume_note": "R1: 4x40ml; R2: 2x20ml",
        "aliases": ["uric acid", "urate"],
    },
    {
        "code": "CHEM-FBC-DIL",
        "name": "FBC diluent",
        "tests_per_kit": None,
        "volume_note": "Diluent 20L",
        "unit": "L",
        "qty_consumed_per_test": 0,
        "aliases": ["fbc", "full blood count", "cbc", "complete blood count"],
        "link_only_to_panel": True,
    },
    {
        "code": "CHEM-FBC-LYSE",
        "name": "FBC lyse",
        "tests_per_kit": None,
        "volume_note": "Lyse 500ml",
        "unit": "ml",
        "qty_consumed_per_test": 0,
        "aliases": ["fbc", "full blood count", "cbc", "complete blood count"],
        "link_only_to_panel": True,
    },
    {
        "code": "CHEM-FBC-RINSE",
        "name": "FBC rinse",
        "tests_per_kit": None,
        "volume_note": "Rinse 20L",
        "unit": "L",
        "qty_consumed_per_test": 0,
        "aliases": ["fbc", "full blood count", "cbc", "complete blood count"],
        "link_only_to_panel": True,
    },
]


def kit_by_code(code: str) -> dict | None:
    for row in MEASURABLE_KITS:
        if row["code"] == code:
            return row
    return None


def should_skip_kit_for_test(row: dict, test_name: str, test_code: str) -> bool:
    blob = f"{_norm(test_name)} {_norm(test_code)}"
    for fragment in row.get("skip_if_name_has") or []:
        if _norm(fragment) and _norm(fragment) in blob:
            return True
    return False
