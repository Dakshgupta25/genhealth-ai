"""
Medical entity normalization — maps extracted entities to standard medical codes.

Provides:
  - Disease → ICD-10 code (exact match, fuzzy match, prefix match)
  - Drug → ATC code + generic name (exact, brand-to-generic, fuzzy)
  - Date → ISO 8601 (delegates to date_parser)
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz, process as rfuzz_process
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:
    logger.warning("rapidfuzz not installed. Fuzzy matching will be unavailable.")
    _RAPIDFUZZ_AVAILABLE = False

from ml.utils.medical_constants import (
    ICD10_LOOKUP, ICD10_REVERSE,
    ATC_LOOKUP, BRAND_TO_GENERIC,
    FREQUENCY_MAP,
)
from ml.nlp.date_parser import normalize_date


class MedicalNormalizer:
    """
    Maps free-text medical entities to standardized codes.

    Uses a cascade:
    1. Exact match (O(1) dict lookup)
    2. Brand-name-to-generic resolution
    3. Fuzzy match via rapidfuzz (threshold ≥ 85%)
    4. Prefix match for ICD-10 categories

    All results include a confidence score reflecting the match method.
    """

    FUZZY_THRESHOLD = 85   # Minimum similarity score for fuzzy match (0-100)
    FUZZY_LIMIT = 3        # Max candidates to evaluate per query

    def __init__(self) -> None:
        # Build lowercased ICD-10 key list for fuzzy matching
        self._icd10_keys: List[str] = list(ICD10_LOOKUP.keys())
        # Build lowercased ATC key list
        self._atc_keys: List[str] = list(ATC_LOOKUP.keys())
        logger.info(
            "MedicalNormalizer initialized: %d ICD-10 entries, %d ATC entries.",
            len(self._icd10_keys), len(self._atc_keys),
        )

    def __repr__(self) -> str:
        return (
            f"MedicalNormalizer("
            f"icd10_entries={len(self._icd10_keys)}, "
            f"atc_entries={len(self._atc_keys)}, "
            f"rapidfuzz={_RAPIDFUZZ_AVAILABLE})"
        )

    def health_check(self) -> dict:
        """Return normalization system status."""
        return {
            "icd10_entries": len(self._icd10_keys),
            "atc_entries": len(self._atc_keys),
            "brand_entries": len(BRAND_TO_GENERIC),
            "rapidfuzz_available": _RAPIDFUZZ_AVAILABLE,
            "fuzzy_threshold": self.FUZZY_THRESHOLD,
        }

    # ─── Disease normalization ────────────────────────────────────────────────

    def normalize_disease(self, disease_text: str) -> Dict:
        """
        Map a free-text disease name to an ICD-10 code.

        Cascade:
        1. Exact match (lowercase).
        2. Fuzzy match via rapidfuzz (threshold 85).
        3. Prefix match (look for ICD-10 prefix substring).

        Args:
            disease_text: Raw extracted disease string.

        Returns:
            {
              "display": str,          # Normalized display name
              "icd10_code": str,       # ICD-10 code or empty string
              "confidence": float,     # Match confidence 0.0–1.0
              "match_method": str,     # "exact" | "fuzzy" | "prefix" | "none"
            }
        """
        if not disease_text:
            return self._disease_result("", "", 0.0, "none")

        query = disease_text.strip().lower()

        # 1. Exact match
        if query in ICD10_LOOKUP:
            code = ICD10_LOOKUP[query]
            return self._disease_result(query.title(), code, 1.0, "exact")

        # 2. Fuzzy match
        if _RAPIDFUZZ_AVAILABLE:
            best = rfuzz_process.extractOne(
                query, self._icd10_keys,
                scorer=fuzz.WRatio,
                score_cutoff=self.FUZZY_THRESHOLD,
            )
            if best:
                matched_key, score, _ = best
                code = ICD10_LOOKUP[matched_key]
                confidence = score / 100.0
                return self._disease_result(matched_key.title(), code, confidence, "fuzzy")

        # 3. Keyword prefix scan
        for key in self._icd10_keys:
            if query in key or key in query:
                code = ICD10_LOOKUP[key]
                return self._disease_result(key.title(), code, 0.70, "prefix")

        return self._disease_result(disease_text.title(), "", 0.40, "none")

    # ─── Medicine normalization ───────────────────────────────────────────────

    def normalize_medicine(self, medicine_text: str) -> Dict:
        """
        Map a drug name to its ATC code, generic name, and drug class.

        Cascade:
        1. Exact generic-name match.
        2. Brand-to-generic lookup.
        3. Fuzzy match on generic names.

        Args:
            medicine_text: Raw extracted drug name.

        Returns:
            {
              "brand_name": str,
              "generic_name": str,
              "atc_code": str,
              "drug_class": str,
              "confidence": float,
              "match_method": str,
            }
        """
        if not medicine_text:
            return self._drug_result(medicine_text, "", "", "", 0.0, "none")

        query = medicine_text.strip().lower()

        # 1. Exact generic match
        if query in ATC_LOOKUP:
            entry = ATC_LOOKUP[query]
            return self._drug_result(
                medicine_text, entry["generic_name"],
                entry["atc_code"], entry["drug_class"],
                1.0, "exact",
            )

        # 2. Brand name → generic
        if query in BRAND_TO_GENERIC:
            generic = BRAND_TO_GENERIC[query]
            entry = ATC_LOOKUP.get(generic, {})
            return self._drug_result(
                medicine_text, entry.get("generic_name", generic.title()),
                entry.get("atc_code", ""), entry.get("drug_class", ""),
                0.95, "brand",
            )

        # 3. Fuzzy generic match
        if _RAPIDFUZZ_AVAILABLE:
            best = rfuzz_process.extractOne(
                query, self._atc_keys,
                scorer=fuzz.WRatio,
                score_cutoff=self.FUZZY_THRESHOLD,
            )
            if best:
                matched_key, score, _ = best
                entry = ATC_LOOKUP[matched_key]
                return self._drug_result(
                    medicine_text, entry["generic_name"],
                    entry["atc_code"], entry["drug_class"],
                    score / 100.0, "fuzzy",
                )

        # 4. No match
        return self._drug_result(medicine_text, medicine_text.title(), "", "", 0.40, "none")

    # ─── Date normalization ───────────────────────────────────────────────────

    def normalize_date(self, date_text: str) -> str:
        """
        Convert any date format to ISO 8601 (YYYY-MM-DD).

        Delegates to the MedicalDateParser module.

        Args:
            date_text: Raw date string.

        Returns:
            ISO date string or empty string if unparseable.
        """
        return normalize_date(date_text) or ""

    # ─── Frequency normalization ──────────────────────────────────────────────

    def normalize_frequency(self, freq_text: str) -> str:
        """
        Standardize a dosing frequency abbreviation to a readable string.

        Args:
            freq_text: e.g., "bd", "TDS", "once daily"

        Returns:
            Standardized string, e.g., "Twice daily".
        """
        query = freq_text.strip().lower()
        return FREQUENCY_MAP.get(query, freq_text.title())

    # ─── Batch normalization ──────────────────────────────────────────────────

    def normalize_entity(self, entity: Dict) -> Dict:
        """
        Normalize a single extracted entity dict in place.

        Dispatches to normalize_disease, normalize_medicine, or normalize_date
        based on entity type.

        Args:
            entity: Entity dict with keys: text, type, ...

        Returns:
            Entity dict with normalization fields added.
        """
        entity_type = entity.get("type", "")
        text = entity.get("text", "")

        if entity_type == "DISEASE":
            result = self.normalize_disease(text)
            entity.update({
                "normalized": result["display"],
                "icd10_code": result["icd10_code"],
                "normalization_confidence": result["confidence"],
                "normalization_method": result["match_method"],
            })

        elif entity_type == "MEDICINE":
            result = self.normalize_medicine(text)
            entity.update({
                "normalized": result["generic_name"],
                "atc_code": result["atc_code"],
                "drug_class": result["drug_class"],
                "normalization_confidence": result["confidence"],
                "normalization_method": result["match_method"],
            })

        elif entity_type == "DATE":
            iso_date = self.normalize_date(text)
            entity.update({
                "normalized": iso_date,
                "normalization_confidence": 0.95 if iso_date else 0.0,
                "normalization_method": "dateparser",
            })

        elif entity_type == "FREQUENCY":
            entity.update({
                "normalized": self.normalize_frequency(text),
                "normalization_confidence": 0.90,
                "normalization_method": "lookup",
            })

        return entity

    def normalize_entities(self, entities: List[Dict]) -> List[Dict]:
        """
        Normalize a list of entities in place.

        Args:
            entities: List of entity dicts.

        Returns:
            List with normalization fields added to each entity.
        """
        return [self.normalize_entity(e) for e in entities]

    # ─── Private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _disease_result(
        display: str, code: str, confidence: float, method: str
    ) -> Dict:
        return {
            "display": display,
            "icd10_code": code,
            "confidence": round(confidence, 3),
            "match_method": method,
        }

    @staticmethod
    def _drug_result(
        brand: str, generic: str, atc: str,
        drug_class: str, confidence: float, method: str,
    ) -> Dict:
        return {
            "brand_name": brand,
            "generic_name": generic,
            "atc_code": atc,
            "drug_class": drug_class,
            "confidence": round(confidence, 3),
            "match_method": method,
        }


# ─── Module-level singleton ───────────────────────────────────────────────────

_normalizer: Optional[MedicalNormalizer] = None


def get_normalizer() -> MedicalNormalizer:
    """Return (or create) the module-level MedicalNormalizer singleton."""
    global _normalizer
    if _normalizer is None:
        _normalizer = MedicalNormalizer()
    return _normalizer
