"""
Medical vocabulary and terminology lookups for the NLP pipeline.

Provides:
  - Compiled regex patterns for medical entity types
  - Drug name sets for fast O(1) lookup
  - Disease keyword sets with ICD-10 mapping
  - Frequency and dosage pattern matchers
"""

import re
from typing import Dict, FrozenSet, List, Optional, Pattern, Set, Tuple

from ml.utils.medical_constants import (
    ATC_LOOKUP, BRAND_TO_GENERIC, ICD10_LOOKUP,
    DOCTOR_TITLE_PATTERNS, HOSPITAL_KEYWORDS, FREQUENCY_MAP,
)


# ─── Drug Vocabulary ──────────────────────────────────────────────────────────

# All known drug generic names (set for O(1) lookup)
DRUG_GENERIC_NAMES: FrozenSet[str] = frozenset(ATC_LOOKUP.keys())

# All known brand names (set for O(1) lookup)
DRUG_BRAND_NAMES: FrozenSet[str] = frozenset(BRAND_TO_GENERIC.keys())

# Union of all drug names (generic + brand)
ALL_DRUG_NAMES: FrozenSet[str] = DRUG_GENERIC_NAMES | DRUG_BRAND_NAMES


# ─── Disease Vocabulary ───────────────────────────────────────────────────────

# All known disease display names (lowercase)
DISEASE_NAMES: FrozenSet[str] = frozenset(ICD10_LOOKUP.keys())

# Disease keywords (fragments that appear in disease names for partial matching)
DISEASE_KEYWORDS: FrozenSet[str] = frozenset({
    "diabetes", "hypertension", "thyroid", "hypothyroid", "hyperthyroid",
    "cardiac", "coronary", "angina", "infarct", "stroke", "arrhythmia",
    "asthma", "copd", "pneumonia", "tuberculosis",
    "hepatitis", "cirrhosis", "fatty liver",
    "epilepsy", "migraine", "parkinson", "alzheimer", "dementia",
    "depression", "anxiety", "bipolar", "schizophrenia",
    "arthritis", "osteoporosis", "fibromyalgia",
    "kidney", "renal", "nephritis", "nephrotic",
    "cancer", "tumor", "malignant", "carcinoma",
    "anemia", "anaemia", "thalassemia",
    "gout", "uric acid", "hyperlipidemia", "cholesterol",
    "obesity", "overweight",
    "pcos", "polycystic",
    "cataract", "glaucoma", "retinopathy",
    "eczema", "psoriasis", "dermatitis",
    "dengue", "malaria", "typhoid",
})


# ─── Compiled Regex Patterns ─────────────────────────────────────────────────

class MedicalPatterns:
    """
    Centralized collection of compiled medical regex patterns.

    All patterns are compiled once at class instantiation time for efficiency.
    """

    # Dosage: e.g., "500mg", "2.5mcg", "10 IU", "100 ml"
    DOSAGE = re.compile(
        r"\b(\d+\.?\d*)\s*(mg|mcg|ml|IU|units?|g|kg|mmol|µg|μg|ug|mEq|mg/ml)\b",
        re.IGNORECASE,
    )

    # Frequency: e.g., "OD", "BD", "TDS", "once daily", "twice a day"
    FREQUENCY = re.compile(
        r"\b(once\s+daily|twice\s+daily|thrice\s+daily|three\s+times\s+daily|"
        r"four\s+times\s+daily|once\s+weekly|once\s+monthly|"
        r"od|bd|tds|tid|qid|sos|prn|hs|ac|pc|stat|daily|weekly|monthly|"
        r"at\s+bedtime|before\s+meals?|after\s+meals?|as\s+needed)\b",
        re.IGNORECASE,
    )

    # Duration: e.g., "for 7 days", "× 10 days", "x 2 weeks"
    DURATION = re.compile(
        r"(?:for|×|x|X)\s*(\d+)\s*(days?|weeks?|months?|years?)",
        re.IGNORECASE,
    )

    # Date: various Indian/International formats
    DATE = re.compile(
        r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})\b"
        r"|\b(\d{1,2})(?:st|nd|rd|th)?\s+"
        r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+(\d{4})\b",
        re.IGNORECASE,
    )

    # Lab values: e.g., "HbA1c: 7.2%", "TSH: 4.5 mIU/L", "FBS- 118 mg/dL"
    LAB_VALUE = re.compile(
        r"\b(HbA1c|Hb|TSH|T3|T4|FBS|PPBS|RBS|LDL|HDL|TG|TC|"
        r"Hgb|Hematocrit|Platelets|WBC|RBC|Creatinine|eGFR|"
        r"Uric\s+Acid|Vitamin\s+[DB]\d*|Ferritin|SGOT|SGPT|"
        r"Bilirubin|Sodium|Potassium|Cholesterol|Triglycerides|INR|PT)\s*"
        r"[:\-=]?\s*(\d+\.?\d*)\s*"
        r"(mg/dL|mmol/L|mIU/L|µg/dL|ng/mL|g/dL|%|IU/L|pg/mL|mEq/L)?",
        re.IGNORECASE,
    )

    # Blood pressure: e.g., "BP: 130/80", "120/80 mmHg"
    BLOOD_PRESSURE = re.compile(
        r"\b(?:BP|Blood\s+Pressure)\s*[:\-=]?\s*(\d{2,3})\s*/\s*(\d{2,3})\s*(?:mmHg)?",
        re.IGNORECASE,
    )

    # Follow-up date: e.g., "Follow up after 2 weeks", "Review on 15/07/2025"
    FOLLOW_UP = re.compile(
        r"(?:follow[\s\-]?up|review|revisit|next\s+visit|come\s+back)\s*"
        r"(?:after|on|in|@)?\s*"
        r"(?:(\d+)\s*(days?|weeks?|months?)|(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}))",
        re.IGNORECASE,
    )

    # Allergy: e.g., "Allergic to Penicillin", "NKDA"
    ALLERGY = re.compile(
        r"(?:allerg(?:ic|y)\s+to|contraindicated|NKDA|no\s+known\s+drug\s+allergy)"
        r"\s*:?\s*([A-Za-z\s,]+)?",
        re.IGNORECASE,
    )

    # Tablet/capsule count: e.g., "Tab Amoxicillin", "Cap Omeprazole", "Syrup"
    MEDICINE_PREFIX = re.compile(
        r"\b(Tab\.?|Tablet|Cap\.?|Capsule|Syrup|Inj\.?|Injection|"
        r"Drops?|Cream|Gel|Oint(?:ment)?|Inhaler|Patch|Spray)\s+",
        re.IGNORECASE,
    )

    # Doctor prefix patterns (compiled from constants)
    DOCTOR = re.compile(
        "|".join(DOCTOR_TITLE_PATTERNS),
        re.IGNORECASE,
    )

    # Hospital keywords (compiled for fast scanning)
    HOSPITAL = re.compile(
        r"(?:[A-Z][a-zA-Z\s]+)?\b(?:" +
        "|".join(re.escape(kw) for kw in HOSPITAL_KEYWORDS) +
        r")\b",
        re.IGNORECASE,
    )

    # Diagnosis section header: e.g., "Diagnosis:", "Dx:", "Impression:"
    DIAGNOSIS_HEADER = re.compile(
        r"^(?:Diagnosis|Dx|Impression|Clinical\s+Diagnosis|Assessment)\s*:?\s*",
        re.IGNORECASE | re.MULTILINE,
    )

    # Prescription header: e.g., "Rx:", "Medicines:", "Treatment:"
    RX_HEADER = re.compile(
        r"^(?:Rx|R/|Treatment|Prescription|Medicines?)\s*:?\s*",
        re.IGNORECASE | re.MULTILINE,
    )


# Module-level singleton
PATTERNS = MedicalPatterns()


def find_drugs_in_text(text: str) -> List[Dict]:
    """
    Find drug names in text using vocabulary matching.

    Performs case-insensitive substring matching against both generic
    and brand name dictionaries.

    Args:
        text: Input text from OCR.

    Returns:
        List of dicts: {text, start, end, type, normalized, atc_code, generic_name}
    """
    text_lower = text.lower()
    found: List[Dict] = []
    covered_spans: List[Tuple[int, int]] = []  # To avoid duplicate matches

    # Try longest names first (to prefer "metformin hydrochloride" over "metformin")
    sorted_names = sorted(ALL_DRUG_NAMES, key=len, reverse=True)

    for drug_name in sorted_names:
        idx = 0
        while True:
            pos = text_lower.find(drug_name, idx)
            if pos == -1:
                break

            end = pos + len(drug_name)

            # Check word boundaries
            pre_ok = (pos == 0 or not text_lower[pos - 1].isalpha())
            post_ok = (end == len(text_lower) or not text_lower[end].isalpha())

            if pre_ok and post_ok:
                # Check if span is already covered
                if not _overlaps_any(pos, end, covered_spans):
                    covered_spans.append((pos, end))

                    # Resolve generic name
                    if drug_name in BRAND_TO_GENERIC:
                        generic = BRAND_TO_GENERIC[drug_name]
                        atc = ATC_LOOKUP.get(generic, {}).get("atc_code", "")
                        drug_class = ATC_LOOKUP.get(generic, {}).get("drug_class", "")
                    else:
                        generic = drug_name
                        atc = ATC_LOOKUP.get(drug_name, {}).get("atc_code", "")
                        drug_class = ATC_LOOKUP.get(drug_name, {}).get("drug_class", "")

                    found.append({
                        "text": text[pos:end],
                        "start": pos,
                        "end": end,
                        "type": "MEDICINE",
                        "normalized": generic.title(),
                        "atc_code": atc,
                        "drug_class": drug_class,
                        "source": "vocab",
                        "confidence": 0.90,
                    })
            idx = pos + 1

    return found


def find_diseases_in_text(text: str) -> List[Dict]:
    """
    Find disease names in text using ICD-10 vocabulary matching.

    Args:
        text: Input text from OCR.

    Returns:
        List of dicts: {text, start, end, type, normalized, icd10_code}
    """
    text_lower = text.lower()
    found: List[Dict] = []
    covered_spans: List[Tuple[int, int]] = []

    sorted_diseases = sorted(DISEASE_NAMES, key=len, reverse=True)

    for disease in sorted_diseases:
        idx = 0
        while True:
            pos = text_lower.find(disease, idx)
            if pos == -1:
                break
            end = pos + len(disease)
            pre_ok = pos == 0 or not text_lower[pos - 1].isalpha()
            post_ok = end == len(text_lower) or not text_lower[end].isalpha()

            if pre_ok and post_ok and not _overlaps_any(pos, end, covered_spans):
                covered_spans.append((pos, end))
                found.append({
                    "text": text[pos:end],
                    "start": pos,
                    "end": end,
                    "type": "DISEASE",
                    "normalized": disease.title(),
                    "icd10_code": ICD10_LOOKUP.get(disease, ""),
                    "source": "vocab",
                    "confidence": 0.88,
                })
            idx = pos + 1

    return found


def _overlaps_any(start: int, end: int, spans: List[Tuple[int, int]]) -> bool:
    """Return True if (start, end) overlaps with any span in the list."""
    for s, e in spans:
        if start < e and end > s:
            return True
    return False
