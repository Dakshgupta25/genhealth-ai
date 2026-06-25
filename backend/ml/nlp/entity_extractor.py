"""
Medical Named Entity Recognition (NER) for GenHealth AI.

Combines:
- Rule-based: regex + vocabulary matching (fast, high-precision for structured patterns)
- ML-based: ClinicalBERT transformer NER (handles complex/novel expressions)

Falls back gracefully when transformer models are unavailable.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from ml.nlp.medical_vocab import (
    PATTERNS, find_drugs_in_text, find_diseases_in_text,
)
from ml.nlp.date_parser import get_date_parser
from ml.nlp.normalizer import get_normalizer, MedicalNormalizer
from ml.utils.confidence import compute_entity_confidence, filter_entities_by_confidence

logger = logging.getLogger(__name__)

# ── Optional transformer dependency ──────────────────────────────────────────
_TRANSFORMERS_AVAILABLE = False
_NER_PIPELINE = None

try:
    from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
    _TRANSFORMERS_AVAILABLE = True
    logger.info("Transformers available. ClinicalBERT NER will be used.")
except ImportError:
    logger.warning(
        "transformers not installed. ML-based NER unavailable. "
        "Using rule-based extraction only."
    )


# ─── Entity Type Registry ─────────────────────────────────────────────────────

ENTITY_TYPES: Dict[str, Dict] = {
    "DISEASE": {"color": "#EF4444", "icon": "🔴"},
    "MEDICINE": {"color": "#3B82F6", "icon": "💊"},
    "DOSAGE": {"color": "#8B5CF6", "icon": "⚖️"},
    "FREQUENCY": {"color": "#EC4899", "icon": "🔁"},
    "DURATION": {"color": "#10B981", "icon": "⏳"},
    "DOCTOR": {"color": "#8B5CF6", "icon": "👨‍⚕️"},
    "HOSPITAL": {"color": "#6366F1", "icon": "🏥"},
    "DATE": {"color": "#64748B", "icon": "📅"},
    "TEST": {"color": "#F59E0B", "icon": "🧪"},
    "TEST_RESULT": {"color": "#F59E0B", "icon": "📊"},
    "BLOOD_PRESSURE": {"color": "#EF4444", "icon": "💉"},
    "LAB_VALUE": {"color": "#F59E0B", "icon": "🔬"},
    "ALLERGY": {"color": "#F97316", "icon": "⚠️"},
}

# ClinicalBERT label → our entity type mapping
_BERT_LABEL_MAP: Dict[str, str] = {
    "B-DISEASE": "DISEASE",
    "I-DISEASE": "DISEASE",
    "B-CHEMICAL": "MEDICINE",
    "I-CHEMICAL": "MEDICINE",
    "B-DNA": "TEST",
    "B-PROTEIN": "TEST_RESULT",
    "B-CELL_TYPE": "TEST",
    "B-CELL_LINE": "TEST",
    # blaze999/Medical-NER labels
    "B-Drug": "MEDICINE",
    "I-Drug": "MEDICINE",
    "B-Disease_disorder": "DISEASE",
    "I-Disease_disorder": "DISEASE",
    "B-Diagnostic_procedure": "TEST",
    "I-Diagnostic_procedure": "TEST",
    "B-Lab_value": "LAB_VALUE",
    "I-Lab_value": "LAB_VALUE",
    "B-Dosage": "DOSAGE",
    "I-Dosage": "DOSAGE",
    "B-Frequency": "FREQUENCY",
    "I-Frequency": "FREQUENCY",
    "B-Duration": "DURATION",
    "I-Duration": "DURATION",
}

# Model to use for NER (falls back gracefully)
_CLINICAL_NER_MODEL = "blaze999/Medical-NER"
_CLINICAL_NER_FALLBACK = "samrawal/bert-base-uncased_clinical-ner"


class MedicalEntityExtractor:
    """
    Hybrid medical NER system combining rule-based and transformer-based extraction.

    For each text input:
    1. Rule-based extractor runs fast pattern matching → high precision.
    2. ML extractor runs ClinicalBERT on the same text → high recall.
    3. Results are merged: ML preferred for high-confidence spans, rules for others.
    4. All entities are normalized via MedicalNormalizer.

    Attributes:
        min_confidence:  Minimum entity confidence to include in results.
        use_ml:          Whether to use the transformer model.
        normalizer:      MedicalNormalizer instance.
        date_parser:     MedicalDateParser instance.
    """

    def __init__(
        self,
        min_confidence: float = 0.60,
        use_ml: bool = True,
        model_name: str = _CLINICAL_NER_MODEL,
    ) -> None:
        self.min_confidence = min_confidence
        self.use_ml = use_ml and _TRANSFORMERS_AVAILABLE
        self.model_name = model_name
        self.normalizer: MedicalNormalizer = get_normalizer()
        self.date_parser = get_date_parser()
        self._pipeline: Optional[Any] = None  # Lazy-initialized

        logger.info(
            "MedicalEntityExtractor initialized. use_ml=%s, min_confidence=%.2f.",
            self.use_ml, self.min_confidence,
        )

    def __repr__(self) -> str:
        return (
            f"MedicalEntityExtractor(use_ml={self.use_ml}, "
            f"model='{self.model_name}', min_confidence={self.min_confidence})"
        )

    def health_check(self) -> dict:
        """Return extractor component status."""
        return {
            "transformers_available": _TRANSFORMERS_AVAILABLE,
            "ml_enabled": self.use_ml,
            "model": self.model_name,
            "pipeline_loaded": self._pipeline is not None,
            "min_confidence": self.min_confidence,
        }

    # ─── Public API ──────────────────────────────────────────────────────────

    def extract(self, text: str) -> Dict:
        """
        Extract and normalize all medical entities from text.

        Args:
            text: OCR-extracted or raw medical text.

        Returns:
            {
              "entities": [...],         # All entities merged + normalized
              "medicines": [...],        # MEDICINE entities only
              "diseases": [...],         # DISEASE entities only
              "dates": [...],            # DATE entities
              "doctors": [...],          # DOCTOR entities
              "hospitals": [...],        # HOSPITAL entities
              "lab_values": [...],       # LAB_VALUE entities
              "structured_summary": {...}# Structured prescription breakdown
            }
        """
        if not text or not text.strip():
            return self._empty_result()

        # Step 1: Rule-based extraction
        rule_entities = self._rule_based_extract(text)

        # Step 2: ML extraction (if enabled)
        ml_entities = self._ml_based_extract(text) if self.use_ml else []

        # Step 3: Merge
        merged = self._merge_and_deduplicate(rule_entities, ml_entities)

        # Step 4: Filter by confidence
        filtered = filter_entities_by_confidence(merged, self.min_confidence)

        # Step 5: Normalize all entities
        normalized = self.normalizer.normalize_entities(filtered)

        # Step 6: Organize into typed sub-lists
        result = self._organize_results(normalized, text)

        # Step 7: Build structured prescription
        result["structured_summary"] = self.extract_structured_prescription(normalized)

        return result

    # ─── Rule-based extraction ────────────────────────────────────────────────

    def _rule_based_extract(self, text: str) -> List[Dict]:
        """
        Extract entities using regex patterns and vocabulary matching.

        Covers: drugs, diseases, dosages, frequencies, durations, dates,
                lab values, blood pressure, doctors, hospitals, allergies.
        """
        entities: List[Dict] = []

        # Drugs (vocab matching — highest precision)
        entities.extend(find_drugs_in_text(text))

        # Diseases (vocab matching)
        entities.extend(find_diseases_in_text(text))

        # Dosages
        for m in PATTERNS.DOSAGE.finditer(text):
            entities.append({
                "text": m.group(0),
                "start": m.start(),
                "end": m.end(),
                "type": "DOSAGE",
                "normalized": m.group(0).upper(),
                "confidence": 0.95,
                "source": "rule",
            })

        # Frequencies
        for m in PATTERNS.FREQUENCY.finditer(text):
            freq_text = m.group(0)
            entities.append({
                "text": freq_text,
                "start": m.start(),
                "end": m.end(),
                "type": "FREQUENCY",
                "normalized": self.normalizer.normalize_frequency(freq_text),
                "confidence": 0.92,
                "source": "rule",
            })

        # Durations
        for m in PATTERNS.DURATION.finditer(text):
            entities.append({
                "text": m.group(0),
                "start": m.start(),
                "end": m.end(),
                "type": "DURATION",
                "normalized": m.group(0).strip(),
                "confidence": 0.90,
                "source": "rule",
            })

        # Dates
        date_entities = self.date_parser.extract_all_dates(text)
        entities.extend(date_entities)

        # Lab values
        for m in PATTERNS.LAB_VALUE.finditer(text):
            entities.append({
                "text": m.group(0),
                "start": m.start(),
                "end": m.end(),
                "type": "LAB_VALUE",
                "normalized": m.group(0).strip(),
                "lab_name": m.group(1),
                "lab_numeric_value": _safe_float(m.group(2)),
                "lab_unit": m.group(3) or "",
                "confidence": 0.93,
                "source": "rule",
            })

        # Blood pressure
        for m in PATTERNS.BLOOD_PRESSURE.finditer(text):
            entities.append({
                "text": m.group(0),
                "start": m.start(),
                "end": m.end(),
                "type": "BLOOD_PRESSURE",
                "normalized": f"{m.group(1)}/{m.group(2)} mmHg",
                "systolic": int(m.group(1)),
                "diastolic": int(m.group(2)),
                "confidence": 0.95,
                "source": "rule",
            })

        # Doctors
        for m in PATTERNS.DOCTOR.finditer(text):
            entities.append({
                "text": m.group(0),
                "start": m.start(),
                "end": m.end(),
                "type": "DOCTOR",
                "normalized": m.group(0).strip(),
                "confidence": 0.85,
                "source": "rule",
            })

        # Hospitals
        for m in PATTERNS.HOSPITAL.finditer(text):
            entities.append({
                "text": m.group(0),
                "start": m.start(),
                "end": m.end(),
                "type": "HOSPITAL",
                "normalized": m.group(0).strip().title(),
                "confidence": 0.75,
                "source": "rule",
            })

        # Allergies
        for m in PATTERNS.ALLERGY.finditer(text):
            entities.append({
                "text": m.group(0),
                "start": m.start(),
                "end": m.end(),
                "type": "ALLERGY",
                "normalized": m.group(1).strip() if m.group(1) else "NKDA",
                "confidence": 0.88,
                "source": "rule",
            })

        return entities

    # ─── ML-based extraction ──────────────────────────────────────────────────

    def _ml_based_extract(self, text: str) -> List[Dict]:
        """
        Run ClinicalBERT NER pipeline on the input text.

        Aggregates subword tokens back to full word-level entities.
        Filters results below confidence threshold.

        Args:
            text: Input medical text.

        Returns:
            List of entity dicts from the transformer model.
        """
        if not _TRANSFORMERS_AVAILABLE:
            return []

        # Lazy-load the pipeline
        if self._pipeline is None:
            self._pipeline = self._load_ner_pipeline()
            if self._pipeline is None:
                return []

        try:
            # Truncate to model max (512 tokens)
            raw_results = self._pipeline(
                text[:2000],
                aggregation_strategy="simple",
            )
        except Exception as exc:
            logger.error("ClinicalBERT NER failed: %s", exc)
            return []

        entities: List[Dict] = []
        for result in raw_results:
            label = result.get("entity_group", result.get("entity", ""))
            our_type = _BERT_LABEL_MAP.get(label)
            if not our_type:
                continue

            confidence = float(result.get("score", 0.0))
            if confidence < 0.70:
                continue

            start = result.get("start", 0)
            end = result.get("end", 0)
            word = result.get("word", text[start:end]).strip()

            if not word or len(word) < 2:
                continue

            entities.append({
                "text": word,
                "start": start,
                "end": end,
                "type": our_type,
                "normalized": word.title(),
                "confidence": confidence,
                "source": "ml",
            })

        return entities

    def _load_ner_pipeline(self):
        """
        Load the ClinicalBERT NER pipeline.

        Tries the primary model first, falls back to secondary.
        Returns None if both fail.
        """
        for model_name in [self.model_name, _CLINICAL_NER_FALLBACK]:
            try:
                logger.info("Loading NER model: %s (this may take ~60s).", model_name)
                ner = pipeline(
                    "ner",
                    model=model_name,
                    tokenizer=model_name,
                    aggregation_strategy="simple",
                    device=-1,  # CPU
                )
                logger.info("NER model loaded: %s.", model_name)
                return ner
            except Exception as exc:
                logger.warning("Could not load model '%s': %s", model_name, exc)

        logger.error("All NER models failed to load. Falling back to rule-only extraction.")
        self.use_ml = False
        return None

    # ─── Merge ────────────────────────────────────────────────────────────────

    def _merge_and_deduplicate(
        self, rule_entities: List[Dict], ml_entities: List[Dict]
    ) -> List[Dict]:
        """
        Merge rule and ML entity lists, resolving conflicts.

        Conflict resolution for overlapping spans:
        - If ML confidence > 0.85 → prefer ML
        - Otherwise → prefer rule-based

        Args:
            rule_entities: Entities from rule-based extractor.
            ml_entities:   Entities from ML model.

        Returns:
            Merged, deduplicated entity list sorted by start position.
        """
        if not ml_entities:
            return rule_entities
        if not rule_entities:
            return ml_entities

        merged: List[Dict] = []
        used_ml_indices = set()

        for rule_ent in rule_entities:
            r_start, r_end = rule_ent["start"], rule_ent["end"]
            conflicting_ml_idx = None
            best_overlap = 0.0

            for i, ml_ent in enumerate(ml_entities):
                if i in used_ml_indices:
                    continue
                m_start, m_end = ml_ent["start"], ml_ent["end"]
                overlap = _span_overlap_ratio(r_start, r_end, m_start, m_end)
                if overlap > best_overlap:
                    best_overlap = overlap
                    conflicting_ml_idx = i

            if conflicting_ml_idx is not None and best_overlap > 0.3:
                ml_ent = ml_entities[conflicting_ml_idx]
                used_ml_indices.add(conflicting_ml_idx)
                # Prefer ML if high confidence, else prefer rule
                if ml_ent["confidence"] > 0.85:
                    entity = {**ml_ent}
                    entity["confidence"] = compute_entity_confidence(
                        rule_entities[rule_entities.index(rule_ent)]["confidence"],
                        ml_ent["confidence"],
                    )
                    merged.append(entity)
                else:
                    merged.append(rule_ent)
            else:
                merged.append(rule_ent)

        # Add unmatched ML entities
        for i, ml_ent in enumerate(ml_entities):
            if i not in used_ml_indices:
                merged.append({**ml_ent, "confidence": ml_ent["confidence"] * 0.85})

        return sorted(merged, key=lambda e: e["start"])

    # ─── Structured extraction ────────────────────────────────────────────────

    def extract_structured_prescription(self, entities: List[Dict]) -> Dict:
        """
        Build a structured prescription dict from the flat entity list.

        Groups MEDICINE + adjacent DOSAGE + FREQUENCY + DURATION into
        medication entries.

        Args:
            entities: Normalized entity list.

        Returns:
            Structured prescription dict.
        """
        medicines_raw = [e for e in entities if e["type"] == "MEDICINE"]
        diseases = [e.get("normalized", e["text"]) for e in entities if e["type"] == "DISEASE"]
        dates = [e.get("normalized") for e in entities if e["type"] == "DATE" and e.get("normalized")]
        doctors = [e.get("normalized", e["text"]) for e in entities if e["type"] == "DOCTOR"]
        hospitals = [e.get("normalized", e["text"]) for e in entities if e["type"] == "HOSPITAL"]
        dosages = [e for e in entities if e["type"] == "DOSAGE"]
        frequencies = [e for e in entities if e["type"] == "FREQUENCY"]
        durations = [e for e in entities if e["type"] == "DURATION"]
        allergies = [e.get("normalized", e["text"]) for e in entities if e["type"] == "ALLERGY"]
        lab_values = [
            {
                "name": e.get("lab_name", e["text"]),
                "value": e.get("lab_numeric_value"),
                "unit": e.get("lab_unit", ""),
            }
            for e in entities if e["type"] == "LAB_VALUE"
        ]

        # Associate dosage/frequency/duration with nearby medicine
        medications = []
        for med in medicines_raw:
            med_end = med["end"]
            # Find the nearest dosage after this medicine (within 100 chars)
            nearby_dosage = _find_nearest(dosages, med_end, window=100)
            nearby_freq = _find_nearest(frequencies, med_end, window=150)
            nearby_dur = _find_nearest(durations, med_end, window=200)

            medications.append({
                "name": med.get("normalized", med["text"]),
                "brand": med.get("text"),
                "atc_code": med.get("atc_code", ""),
                "drug_class": med.get("drug_class", ""),
                "dosage": nearby_dosage.get("text", "") if nearby_dosage else "",
                "frequency": nearby_freq.get("normalized", nearby_freq.get("text", "")) if nearby_freq else "",
                "duration": nearby_dur.get("text", "") if nearby_dur else "",
                "confidence": med.get("confidence", 0.0),
            })

        follow_up = self.date_parser.extract_follow_up_date(
            " ".join(e["text"] for e in entities)
        )

        return {
            "conditions": list(set(diseases)),
            "medications": medications,
            "doctor": {
                "name": doctors[0] if doctors else "",
                "hospital": hospitals[0] if hospitals else "",
                "all_hospitals": hospitals,
            },
            "dates": dates,
            "lab_values": lab_values,
            "allergies": allergies,
            "follow_up": follow_up,
        }

    # ─── Organization ─────────────────────────────────────────────────────────

    def _organize_results(self, entities: List[Dict], original_text: str) -> Dict:
        """Group entities by type into the final result structure."""
        by_type: Dict[str, List[Dict]] = {t: [] for t in ENTITY_TYPES}
        for entity in entities:
            t = entity.get("type", "")
            if t in by_type:
                by_type[t].append(entity)

        return {
            "entities": entities,
            "medicines": by_type["MEDICINE"],
            "diseases": by_type["DISEASE"],
            "dates": by_type["DATE"],
            "doctors": by_type["DOCTOR"],
            "hospitals": by_type["HOSPITAL"],
            "lab_values": by_type["LAB_VALUE"],
            "dosages": by_type["DOSAGE"],
            "frequencies": by_type["FREQUENCY"],
            "allergies": by_type["ALLERGY"],
            "blood_pressure": by_type["BLOOD_PRESSURE"],
        }

    @staticmethod
    def _empty_result() -> Dict:
        return {
            "entities": [],
            "medicines": [],
            "diseases": [],
            "dates": [],
            "doctors": [],
            "hospitals": [],
            "lab_values": [],
            "dosages": [],
            "frequencies": [],
            "allergies": [],
            "blood_pressure": [],
            "structured_summary": {
                "conditions": [], "medications": [],
                "doctor": {"name": "", "hospital": ""},
                "dates": [], "lab_values": [],
                "allergies": [], "follow_up": None,
            },
        }


# ─── Private helpers ──────────────────────────────────────────────────────────

def _span_overlap_ratio(a_start: int, a_end: int, b_start: int, b_end: int) -> float:
    """Compute overlap ratio of two character spans."""
    overlap = max(0, min(a_end, b_end) - max(a_start, b_start))
    if overlap == 0:
        return 0.0
    shorter = min(a_end - a_start, b_end - b_start)
    return overlap / shorter if shorter > 0 else 0.0


def _safe_float(value: Optional[str]) -> Optional[float]:
    """Safely parse a string to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _find_nearest(
    entities: List[Dict], after_pos: int, window: int = 150
) -> Optional[Dict]:
    """Find the nearest entity starting after `after_pos` within `window` chars."""
    candidates = [
        e for e in entities
        if e["start"] >= after_pos and (e["start"] - after_pos) <= window
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda e: e["start"])


# ─── Module-level singleton ───────────────────────────────────────────────────

_extractor: Optional[MedicalEntityExtractor] = None


def get_entity_extractor(
    min_confidence: float = 0.60,
    use_ml: bool = True,
) -> MedicalEntityExtractor:
    """Return (or create) the module-level MedicalEntityExtractor singleton."""
    global _extractor
    if _extractor is None:
        _extractor = MedicalEntityExtractor(
            min_confidence=min_confidence,
            use_ml=use_ml,
        )
    return _extractor
