"""
Risk classifier — orchestrates all disease models → unified risk profile.

Provides a single entry point for computing a user's complete health risk
across diabetes, hypertension, thyroid disorder, and cardiovascular disease.
"""

import logging
from typing import Any, Dict, List, Optional

from ml.risk_models.diabetes_model import DiabetesRiskModel
from ml.risk_models.hypertension_model import HypertensionRiskModel
from ml.risk_models.thyroid_model import ThyroidRiskModel
from ml.risk_models.heart_model import HeartRiskModel
from ml.risk_models.feature_engineer import HealthFeatureEngineer

logger = logging.getLogger(__name__)

# Health score weights for each disease (must sum to 100)
DISEASE_WEIGHTS = {
    "heart_disease": 30,
    "diabetes": 25,
    "hypertension": 25,
    "thyroid": 20,
}

# Watchlist threshold (include disease if probability > this)
WATCHLIST_THRESHOLD = 0.40


class RiskClassifier:
    """
    Orchestrates all disease risk models to produce a unified risk profile.

    Attributes:
        models:           Dict of disease name → risk model instance.
        feature_engineer: HealthFeatureEngineer for building feature vectors.
    """

    def __init__(self) -> None:
        logger.info("Initializing RiskClassifier...")
        self.models = {
            "diabetes": DiabetesRiskModel(),
            "hypertension": HypertensionRiskModel(),
            "thyroid": ThyroidRiskModel(),
            "heart_disease": HeartRiskModel(),
        }
        self.feature_engineer = HealthFeatureEngineer()
        logger.info("RiskClassifier ready. Models: %s", list(self.models.keys()))

    def __repr__(self) -> str:
        return f"RiskClassifier(models={list(self.models.keys())})"

    def health_check(self) -> dict:
        """Return status of all component models."""
        return {
            "classifier": "ready",
            "models": {name: model.health_check() for name, model in self.models.items()},
            "feature_engineer": self.feature_engineer.health_check(),
        }

    # ─── Main public API ──────────────────────────────────────────────────────

    def generate_full_risk_profile(
        self,
        user: Any,
        records: List[Any],
        entities: List[Any],
        family_members: List[Any],
        family_records: Optional[List[Any]] = None,
        generational_boost: Optional[Dict[str, float]] = None,
    ) -> Dict:
        """
        Generate a complete risk profile for a user.

        Steps:
        1. Build feature vector from user records + family data.
        2. Run all disease models.
        3. Apply generational risk boost (from pattern_detector).
        4. Compute composite health score.
        5. Generate watchlist (diseases > 40% probability).

        Args:
            user:              User ORM object.
            records:           User's HealthRecord list.
            entities:          User's ExtractedEntity list.
            family_members:    User's FamilyMember list.
            family_records:    Family entities (for family feature computation).
            generational_boost: Optional {disease_key: boost_probability} from HereditaryPatternDetector.

        Returns:
            Complete risk profile dict.
        """
        logger.info("Generating risk profile for user: %s", getattr(user, "id", "unknown"))

        # Step 1: Build feature vector
        features = self.feature_engineer.build_features(
            user=user,
            records=records,
            entities=entities,
            family_members=family_members,
            family_records=family_records or [],
        )

        # Step 2: Run all models
        predictions = self._run_all_models(features)

        # Step 3: Apply generational boost
        if generational_boost:
            predictions = self._apply_generational_boost(predictions, generational_boost)

        # Step 4: Compute health score
        health_score = self.compute_health_score(predictions)

        # Step 5: Watchlist
        watchlist = self.generate_watchlist(predictions)

        # Step 6: Assemble profile
        profile = {
            "health_score": health_score,
            "health_grade": self._score_to_grade(health_score),
            "predictions": list(predictions.values()),
            "watchlist": watchlist,
            "feature_summary": self._feature_summary(features),
            "model_versions": {
                name: "v1.0" for name in self.models
            },
        }

        logger.info(
            "Risk profile complete. Health score=%d, Watchlist=%d diseases.",
            health_score, len(watchlist),
        )
        return profile

    def generate_from_features(self, features: Dict[str, float]) -> Dict:
        """
        Generate risk profile from a pre-built feature dict.

        Useful for testing or when feature engineering runs separately.

        Args:
            features: Feature dict from HealthFeatureEngineer.

        Returns:
            Complete risk profile dict.
        """
        predictions = self._run_all_models(features)
        health_score = self.compute_health_score(predictions)
        watchlist = self.generate_watchlist(predictions)
        return {
            "health_score": health_score,
            "health_grade": self._score_to_grade(health_score),
            "predictions": list(predictions.values()),
            "watchlist": watchlist,
        }

    # ─── Component methods ────────────────────────────────────────────────────

    def _run_all_models(self, features: Dict[str, float]) -> Dict[str, Dict]:
        """Run all 4 disease models and collect predictions."""
        predictions = {}
        for disease_key, model in self.models.items():
            try:
                result = model.predict(features)
                predictions[disease_key] = result
                logger.debug(
                    "Model '%s': probability=%.3f, risk=%s",
                    disease_key, result["probability"], result["risk_level"],
                )
            except Exception as exc:
                logger.error("Model '%s' failed: %s", disease_key, exc)
                predictions[disease_key] = {
                    "disease": disease_key.replace("_", " ").title(),
                    "probability": 0.0,
                    "risk_level": "low",
                    "contributing_factors": [],
                    "model_confidence": 0.0,
                }
        return predictions

    def _apply_generational_boost(
        self,
        predictions: Dict[str, Dict],
        boost: Dict[str, float],
    ) -> Dict[str, Dict]:
        """
        Add hereditary risk boost to prediction probabilities.

        Caps the final probability at 0.95 to avoid overconfidence.

        Args:
            predictions:  Dict of disease predictions from models.
            boost:        Dict of disease_key → boost_probability.

        Returns:
            Updated predictions dict.
        """
        for disease_key, boost_val in boost.items():
            if disease_key in predictions and boost_val > 0:
                original = predictions[disease_key]["probability"]
                boosted = min(0.95, original + boost_val)
                predictions[disease_key]["probability"] = round(boosted, 4)
                predictions[disease_key]["risk_level"] = _prob_to_level(boosted)
                predictions[disease_key]["generational_boost_applied"] = round(boost_val, 4)
                logger.debug(
                    "Generational boost applied to '%s': %.3f → %.3f.",
                    disease_key, original, boosted,
                )
        return predictions

    def compute_health_score(self, predictions: Dict[str, Dict]) -> int:
        """
        Compute an overall health score (0–100, higher = healthier).

        Formula:
            score = 100 - Σ(probability_i × weight_i)

        Where weights are: heart=30, diabetes=25, hypertension=25, thyroid=20.

        Args:
            predictions: Dict of disease_key → prediction dict.

        Returns:
            Integer health score clamped to [0, 100].
        """
        deduction = 0.0
        for disease_key, weight in DISEASE_WEIGHTS.items():
            prob = predictions.get(disease_key, {}).get("probability", 0.0)
            deduction += prob * weight

        score = 100.0 - deduction
        return max(0, min(100, round(score)))

    def generate_watchlist(self, predictions: Dict[str, Dict]) -> List[Dict]:
        """
        Return diseases with predicted probability > 40%, sorted by probability.

        Args:
            predictions: Disease prediction dict.

        Returns:
            Sorted list of watchlist entries.
        """
        watchlist = []
        for disease_key, pred in predictions.items():
            prob = pred.get("probability", 0.0)
            if prob >= WATCHLIST_THRESHOLD:
                watchlist.append({
                    "disease": pred.get("disease", disease_key.replace("_", " ").title()),
                    "icd10": pred.get("icd10", ""),
                    "probability": prob,
                    "risk_level": pred.get("risk_level", "moderate"),
                    "top_factor": (pred.get("contributing_factors") or [{}])[0].get("factor", ""),
                })

        return sorted(watchlist, key=lambda x: x["probability"], reverse=True)

    # ─── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _score_to_grade(score: int) -> str:
        """Convert numeric health score to letter grade."""
        if score >= 85: return "A"
        elif score >= 70: return "B"
        elif score >= 55: return "C"
        elif score >= 40: return "D"
        return "F"

    @staticmethod
    def _feature_summary(features: Dict[str, float]) -> Dict:
        """Extract key feature values for the profile summary."""
        return {
            "age": features.get("age"),
            "bmi": features.get("bmi") or features.get("latest_bmi"),
            "blood_sugar_fasting": features.get("latest_blood_sugar_fasting"),
            "hba1c": features.get("latest_hba1c"),
            "tsh": features.get("latest_tsh"),
            "systolic_bp": features.get("latest_systolic_bp"),
            "cholesterol": features.get("latest_cholesterol"),
        }


def _prob_to_level(prob: float) -> str:
    if prob >= 0.60: return "high"
    elif prob >= 0.30: return "moderate"
    return "low"


# ─── Module-level singleton ───────────────────────────────────────────────────

_classifier: Optional[RiskClassifier] = None


def get_risk_classifier() -> RiskClassifier:
    """Return (or create) the module-level RiskClassifier singleton."""
    global _classifier
    if _classifier is None:
        _classifier = RiskClassifier()
    return _classifier
