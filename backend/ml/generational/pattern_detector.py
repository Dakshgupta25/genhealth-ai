"""
Hereditary disease pattern detection across family generations.

Computes weighted family risk scores based on relationship closeness
and known disease heritability coefficients.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


HEREDITARY_DISEASES: Dict[str, Dict] = {
    "type_2_diabetes": {
        "heritability": 0.72, "icd10_prefix": "E11",
        "display": "Type 2 Diabetes",
        "keywords": ["diabetes", "E10", "E11", "diabetic", "insulin"],
    },
    "hypertension": {
        "heritability": 0.54, "icd10_prefix": "I10",
        "display": "Hypertension",
        "keywords": ["hypertension", "I10", "high blood pressure"],
    },
    "hypothyroidism": {
        "heritability": 0.67, "icd10_prefix": "E03",
        "display": "Hypothyroidism",
        "keywords": ["hypothyroid", "E03", "hashimoto", "underactive thyroid"],
    },
    "hyperthyroidism": {
        "heritability": 0.79, "icd10_prefix": "E05",
        "display": "Hyperthyroidism",
        "keywords": ["hyperthyroid", "E05", "graves", "overactive thyroid"],
    },
    "coronary_artery_disease": {
        "heritability": 0.56, "icd10_prefix": "I25",
        "display": "Coronary Artery Disease",
        "keywords": ["coronary", "I25", "cad", "ischemic heart", "angina", "heart attack"],
    },
    "depression": {
        "heritability": 0.40, "icd10_prefix": "F32",
        "display": "Depression",
        "keywords": ["depression", "F32", "F33", "major depressive"],
    },
    "breast_cancer": {
        "heritability": 0.30, "icd10_prefix": "C50",
        "display": "Breast Cancer",
        "keywords": ["breast cancer", "C50", "brca"],
    },
    "colorectal_cancer": {
        "heritability": 0.35, "icd10_prefix": "C18",
        "display": "Colorectal Cancer",
        "keywords": ["colorectal", "colon cancer", "C18", "C19", "C20"],
    },
    "asthma": {
        "heritability": 0.65, "icd10_prefix": "J45",
        "display": "Asthma",
        "keywords": ["asthma", "J45", "bronchial asthma"],
    },
    "osteoporosis": {
        "heritability": 0.60, "icd10_prefix": "M80",
        "display": "Osteoporosis",
        "keywords": ["osteoporosis", "M80", "M81", "low bone density"],
    },
}

RELATIONSHIP_WEIGHTS: Dict[str, float] = {
    "parent": 2.0,
    "father": 2.0,
    "mother": 2.0,
    "sibling": 1.8,
    "brother": 1.8,
    "sister": 1.8,
    "child": 1.5,
    "son": 1.5,
    "daughter": 1.5,
    "grandparent": 1.0,
    "paternal_grandfather": 1.0,
    "paternal_grandmother": 1.0,
    "maternal_grandfather": 1.0,
    "maternal_grandmother": 1.0,
    "aunt_uncle": 0.5,
    "uncle": 0.5,
    "aunt": 0.5,
    "cousin": 0.25,
    "spouse": 0.1,
}

# Weighted score thresholds
HIGH_RISK_THRESHOLD = 1.5
MODERATE_RISK_THRESHOLD = 0.8

# Disease key → model disease key mapping (for boost injection)
DISEASE_TO_MODEL_KEY: Dict[str, str] = {
    "type_2_diabetes": "diabetes",
    "hypertension": "hypertension",
    "hypothyroidism": "thyroid",
    "hyperthyroidism": "thyroid",
    "coronary_artery_disease": "heart_disease",
}


class HereditaryPatternDetector:
    """
    Detects hereditary disease patterns in a user's family health data.

    For each known hereditary disease, computes a weighted family risk score
    based on how many relatives have the disease, weighted by relationship
    closeness and the disease's known heritability coefficient.
    """

    def __repr__(self) -> str:
        return (
            f"HereditaryPatternDetector("
            f"diseases={len(HEREDITARY_DISEASES)}, "
            f"relationship_types={len(RELATIONSHIP_WEIGHTS)})"
        )

    def health_check(self) -> dict:
        return {
            "hereditary_diseases_tracked": len(HEREDITARY_DISEASES),
            "relationship_types": len(RELATIONSHIP_WEIGHTS),
            "high_risk_threshold": HIGH_RISK_THRESHOLD,
            "moderate_risk_threshold": MODERATE_RISK_THRESHOLD,
        }

    def detect_patterns(
        self,
        user_id: str,
        family_members: List[Any],
        family_health_data: List[Dict],
    ) -> Dict:
        """
        Detect hereditary patterns for a user across all tracked diseases.

        Args:
            user_id:           The user's ID (for logging).
            family_members:    List of FamilyMember ORM objects.
            family_health_data: List of dicts: {member_id, relationship, conditions[]}

        Returns:
            {
              "patterns": [...],
              "hereditary_risk_boost": {...},
              "generation_map": {...},
            }
        """
        logger.info("Detecting hereditary patterns for user: %s", user_id)

        # Build member → conditions map
        member_conditions = self._build_member_conditions(family_health_data)

        # Build member → relationship map
        member_relationships = {
            str(m.id): (m.relationship or "unknown").lower()
            for m in family_members
        }

        patterns: List[Dict] = []
        hereditary_boost: Dict[str, float] = {}

        for disease_key, disease_info in HEREDITARY_DISEASES.items():
            affected = []
            weighted_score = 0.0

            for member in family_members:
                member_id = str(member.id)
                conditions = member_conditions.get(member_id, [])
                rel = member_relationships.get(member_id, "unknown")

                if self._member_has_disease(conditions, disease_info["keywords"]):
                    weight = self._get_relationship_weight(rel)
                    affected.append({
                        "name": member.name or "Family Member",
                        "relationship": rel.replace("_", " ").title(),
                        "weight": weight,
                    })
                    weighted_score += weight

            if not affected:
                continue

            # Apply heritability coefficient
            adjusted_score = weighted_score * disease_info["heritability"]

            # Determine risk flag
            if adjusted_score >= HIGH_RISK_THRESHOLD:
                risk_flag = "high"
            elif adjusted_score >= MODERATE_RISK_THRESHOLD:
                risk_flag = "moderate"
            else:
                risk_flag = "low"

            # Compute generation span (how many generations are affected)
            gen_map = self.build_generation_map(family_members)
            gens_affected = set()
            for m in family_members:
                if str(m.id) in [a.get("name") for a in affected]:
                    gens_affected.add(gen_map.get(str(m.id), 0))

            pattern = {
                "disease": disease_info["display"],
                "disease_key": disease_key,
                "icd10": disease_info["icd10_prefix"],
                "affected_members": affected,
                "affected_count": len(affected),
                "weighted_score": round(adjusted_score, 3),
                "raw_score": round(weighted_score, 3),
                "heritability": disease_info["heritability"],
                "risk_flag": risk_flag,
                "generation_span": max(1, len(gens_affected)),
            }
            patterns.append(pattern)

            # Compute risk boost for the ML models
            model_key = DISEASE_TO_MODEL_KEY.get(disease_key)
            if model_key and risk_flag in ("high", "moderate"):
                # Boost = heritability × normalized_score × 0.20 (cap at 0.25)
                boost = min(0.25, disease_info["heritability"] * adjusted_score * 0.08)
                hereditary_boost[model_key] = max(
                    hereditary_boost.get(model_key, 0.0), boost
                )

        # Sort patterns by weighted score (highest first)
        patterns.sort(key=lambda p: p["weighted_score"], reverse=True)

        logger.info(
            "Hereditary pattern detection complete: %d patterns found, %d boosts applied.",
            len(patterns), len(hereditary_boost),
        )

        return {
            "patterns": patterns,
            "hereditary_risk_boost": hereditary_boost,
            "generation_map": self.build_generation_map(family_members),
        }

    def build_generation_map(self, family_members: List[Any]) -> Dict[str, int]:
        """
        Map each family member to a generation number relative to the user.

        Convention:
        - Generation -2: Grandparents
        - Generation -1: Parents
        - Generation  0: User (not in family_members)
        - Generation +1: Children
        - Generation +2: Grandchildren

        Args:
            family_members: List of FamilyMember ORM objects.

        Returns:
            Dict mapping member_id → generation number.
        """
        gen_map: Dict[str, int] = {}
        for member in family_members:
            rel = (member.relationship or "").lower().replace(" ", "_")
            gen = self._relationship_to_generation(rel)
            gen_map[str(member.id)] = gen
        return gen_map

    def get_shared_risk_summary(self, patterns: List[Dict]) -> List[Dict]:
        """
        Summarize patterns into a user-facing shared risk overview.

        Args:
            patterns: From detect_patterns()["patterns"].

        Returns:
            Simplified list for frontend display.
        """
        return [
            {
                "disease": p["disease"],
                "risk_flag": p["risk_flag"],
                "affected_count": p["affected_count"],
                "heritability_pct": f"{int(p['heritability'] * 100)}%",
                "top_relative": p["affected_members"][0]["relationship"] if p["affected_members"] else "",
            }
            for p in patterns
            if p["risk_flag"] in ("high", "moderate")
        ]

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _build_member_conditions(
        self, family_health_data: List[Dict]
    ) -> Dict[str, List[str]]:
        """Build member_id → conditions list from family health data."""
        member_conditions: Dict[str, List[str]] = {}
        for record in family_health_data:
            member_id = str(record.get("member_id", ""))
            conditions = record.get("conditions", [])
            if member_id:
                member_conditions.setdefault(member_id, []).extend(
                    c.lower() for c in conditions
                )
        return member_conditions

    @staticmethod
    def _member_has_disease(conditions: List[str], keywords: List[str]) -> bool:
        """Return True if any condition matches any keyword."""
        for condition in conditions:
            for kw in keywords:
                if kw.lower() in condition:
                    return True
        return False

    @staticmethod
    def _get_relationship_weight(relationship: str) -> float:
        """Return the relationship weight for a given relationship string."""
        rel_clean = relationship.lower().strip().replace(" ", "_")
        # Try exact match first
        if rel_clean in RELATIONSHIP_WEIGHTS:
            return RELATIONSHIP_WEIGHTS[rel_clean]
        # Try partial match
        for key, weight in RELATIONSHIP_WEIGHTS.items():
            if key in rel_clean or rel_clean in key:
                return weight
        return 0.25  # Default: distant relative

    @staticmethod
    def _relationship_to_generation(rel: str) -> int:
        """Map relationship string to generation number."""
        if any(kw in rel for kw in ("grandfather", "grandmother", "grandparent")):
            return -2
        if any(kw in rel for kw in ("father", "mother", "parent")):
            return -1
        if any(kw in rel for kw in ("son", "daughter", "child")):
            return 1
        if any(kw in rel for kw in ("grandson", "granddaughter", "grandchild")):
            return 2
        if any(kw in rel for kw in ("brother", "sister", "sibling")):
            return 0
        if any(kw in rel for kw in ("uncle", "aunt")):
            return -1
        return 0  # Same generation assumption


# ─── Module-level singleton ───────────────────────────────────────────────────

_detector: Optional[HereditaryPatternDetector] = None


def get_pattern_detector() -> HereditaryPatternDetector:
    """Return (or create) the module-level HereditaryPatternDetector singleton."""
    global _detector
    if _detector is None:
        _detector = HereditaryPatternDetector()
    return _detector
