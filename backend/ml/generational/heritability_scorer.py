"""
Heritability scorer for GenHealth AI.

Computes the heritability-adjusted risk contribution of family disease
history, using established genetic epidemiology coefficients.
"""

import logging
from typing import Dict, List, Optional, Tuple

from ml.generational.pattern_detector import (
    HEREDITARY_DISEASES, RELATIONSHIP_WEIGHTS,
    HIGH_RISK_THRESHOLD, MODERATE_RISK_THRESHOLD,
)

logger = logging.getLogger(__name__)


class HeritabilityScorer:
    """
    Computes hereditary risk weights and scores for disease risk models.

    Scores represent the additional probability of disease development
    given known family history, adjusted by:
    - Relationship closeness (parent > grandparent > aunt/uncle)
    - Known heritability coefficient of the disease
    - Number of affected family members

    The output is a risk boost [0.0, 0.25] suitable for adding to
    the base ML model probability.
    """

    # Maximum boost any single disease can receive (prevents overcorrection)
    MAX_BOOST = 0.25

    def __repr__(self) -> str:
        return f"HeritabilityScorer(max_boost={self.MAX_BOOST})"

    def health_check(self) -> dict:
        return {
            "heritability_scorer": "ready",
            "max_boost": self.MAX_BOOST,
            "diseases_supported": len(HEREDITARY_DISEASES),
        }

    def compute_disease_boost(
        self,
        disease_key: str,
        affected_relatives: List[Dict],
    ) -> float:
        """
        Compute the hereditary risk boost for a single disease.

        Formula:
            raw_score = Σ(relationship_weight for each affected relative)
            adjusted_score = raw_score × heritability_coefficient
            boost = min(MAX_BOOST, adjusted_score × scaling_factor)

        Args:
            disease_key:       Disease identifier (e.g., 'type_2_diabetes').
            affected_relatives: List of {relationship: str} dicts.

        Returns:
            Float boost in [0.0, MAX_BOOST].
        """
        disease_info = HEREDITARY_DISEASES.get(disease_key)
        if not disease_info or not affected_relatives:
            return 0.0

        heritability = disease_info["heritability"]
        raw_score = sum(
            self._relationship_weight(r.get("relationship", "unknown"))
            for r in affected_relatives
        )
        adjusted_score = raw_score * heritability

        # Scale to [0, MAX_BOOST]: a score of 3.0 → ~0.20 boost
        boost = min(self.MAX_BOOST, adjusted_score * 0.08)
        logger.debug(
            "Disease '%s': raw=%.2f, adjusted=%.2f, boost=%.3f.",
            disease_key, raw_score, adjusted_score, boost,
        )
        return round(boost, 4)

    def compute_all_boosts(
        self, patterns: List[Dict]
    ) -> Dict[str, float]:
        """
        Compute hereditary boosts for all detected patterns.

        Args:
            patterns: From HereditaryPatternDetector.detect_patterns()["patterns"].

        Returns:
            Dict mapping model disease key → boost float.
        """
        from ml.generational.pattern_detector import DISEASE_TO_MODEL_KEY

        boosts: Dict[str, float] = {}
        for pattern in patterns:
            disease_key = pattern.get("disease_key", "")
            model_key = DISEASE_TO_MODEL_KEY.get(disease_key)
            if not model_key:
                continue

            boost = self.compute_disease_boost(
                disease_key, pattern.get("affected_members", [])
            )
            # Use max boost if multiple diseases map to same model key (e.g., both thyroid types)
            boosts[model_key] = max(boosts.get(model_key, 0.0), boost)

        return boosts

    def heritability_risk_summary(
        self, patterns: List[Dict]
    ) -> List[Dict]:
        """
        Generate a user-facing heritability risk summary.

        Args:
            patterns: From HereditaryPatternDetector.detect_patterns()["patterns"].

        Returns:
            List of dicts suitable for frontend display.
        """
        summaries = []
        for pattern in patterns:
            weighted_score = pattern.get("weighted_score", 0.0)
            heritability = pattern.get("heritability", 0.5)
            risk_flag = pattern.get("risk_flag", "low")

            if risk_flag == "low":
                continue  # Only include moderate and high risks

            summaries.append({
                "disease": pattern["disease"],
                "heritability_pct": f"{int(heritability * 100)}%",
                "affected_family_members": pattern.get("affected_count", 0),
                "risk_flag": risk_flag,
                "weighted_score": weighted_score,
                "interpretation": self._interpret_score(weighted_score, heritability),
            })

        return sorted(summaries, key=lambda s: s["weighted_score"], reverse=True)

    def dominant_risk_factors(
        self, patterns: List[Dict], top_n: int = 3
    ) -> List[Tuple[str, str, float]]:
        """
        Return the top N dominant hereditary risk factors.

        Args:
            patterns: Detected hereditary patterns.
            top_n:    Maximum number of factors to return.

        Returns:
            List of (disease_display, risk_flag, weighted_score) tuples.
        """
        scored = [
            (p["disease"], p["risk_flag"], p["weighted_score"])
            for p in patterns
            if p["risk_flag"] in ("high", "moderate")
        ]
        return sorted(scored, key=lambda x: x[2], reverse=True)[:top_n]

    # ─── Private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _relationship_weight(relationship: str) -> float:
        """Return the weight for a given relationship string."""
        rel_clean = relationship.lower().strip().replace(" ", "_")
        if rel_clean in RELATIONSHIP_WEIGHTS:
            return RELATIONSHIP_WEIGHTS[rel_clean]
        for key, weight in RELATIONSHIP_WEIGHTS.items():
            if key in rel_clean:
                return weight
        return 0.25

    @staticmethod
    def _interpret_score(weighted_score: float, heritability: float) -> str:
        """Return a natural language interpretation of the heritability score."""
        if weighted_score >= HIGH_RISK_THRESHOLD * 1.5:
            return (
                f"Strong family history across multiple generations. "
                f"This condition has {int(heritability * 100)}% heritability. "
                f"Regular screening is strongly recommended."
            )
        elif weighted_score >= HIGH_RISK_THRESHOLD:
            return (
                f"Significant family history detected. "
                f"With {int(heritability * 100)}% heritability, "
                f"early detection and prevention are important."
            )
        return (
            f"Moderate family history detected. "
            f"This condition has {int(heritability * 100)}% heritability. "
            f"Maintain awareness and schedule routine checkups."
        )
