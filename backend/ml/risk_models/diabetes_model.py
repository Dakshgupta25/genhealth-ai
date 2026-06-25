"""
Diabetes risk prediction model for GenHealth AI.

Ensemble: XGBoost (0.6 weight) + PyTorch neural network (0.4 weight).
Uses SHAP for explainability.
"""

import logging
import os
import pickle
from typing import Any, Dict, List, Optional

import numpy as np

from ml.utils.confidence import (
    ensemble_probability, probability_to_risk_level, compute_model_confidence,
)

logger = logging.getLogger(__name__)

# ── Optional ML dependencies ──────────────────────────────────────────────────
try:
    import xgboost as xgb
    _XGB_AVAILABLE = True
except ImportError:
    _XGB_AVAILABLE = False
    logger.warning("xgboost not installed.")

try:
    import torch
    import torch.nn as nn
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False
    logger.warning("torch not installed.")

try:
    import shap
    _SHAP_AVAILABLE = True
except ImportError:
    _SHAP_AVAILABLE = False

try:
    from sklearn.preprocessing import StandardScaler
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False

# ─── Feature schema ───────────────────────────────────────────────────────────

DIABETES_FEATURES = [
    "age",
    "gender_male",
    "bmi",
    "latest_bmi",
    "latest_blood_sugar_fasting",
    "latest_hba1c",
    "has_diabetes_history",
    "diabetes_recurrence_count",
    "disease_count",
    "parent_diabetes",
    "grandparent_diabetes",
    "sibling_diabetes",
    "family_diabetes_count",
    "thyroid_med_count",       # Thyroid conditions correlate with T2DM
    "exercise_regularity",
    "diet_quality_score",
]

# Human-readable factor labels for each feature
FACTOR_LABELS: Dict[str, str] = {
    "age": "Age factor",
    "gender_male": "Gender (Male)",
    "bmi": "Body mass index",
    "latest_bmi": "Latest recorded BMI",
    "latest_blood_sugar_fasting": "Fasting blood sugar level",
    "latest_hba1c": "HbA1c (glycated hemoglobin)",
    "has_diabetes_history": "Personal history of diabetes",
    "diabetes_recurrence_count": "Number of diabetes medications in records",
    "disease_count": "Total number of distinct conditions",
    "parent_diabetes": "Parent has diabetes",
    "grandparent_diabetes": "Grandparent had diabetes",
    "sibling_diabetes": "Sibling has diabetes",
    "family_diabetes_count": "Total family members with diabetes",
    "thyroid_med_count": "Thyroid disease (associated risk factor)",
    "exercise_regularity": "Exercise regularity",
    "diet_quality_score": "Diet quality score",
}

FACTOR_SOURCE_MAP: Dict[str, str] = {
    "age": "demographic",
    "bmi": "clinical",
    "latest_bmi": "clinical",
    "latest_blood_sugar_fasting": "lab",
    "latest_hba1c": "lab",
    "has_diabetes_history": "medical_history",
    "diabetes_recurrence_count": "medical_history",
    "parent_diabetes": "family",
    "grandparent_diabetes": "family",
    "sibling_diabetes": "family",
    "family_diabetes_count": "family",
    "exercise_regularity": "lifestyle",
    "diet_quality_score": "lifestyle",
}

MODEL_STORE_DIR = os.path.join(os.path.dirname(__file__), "..", "models_store")


# ─── Neural Network ───────────────────────────────────────────────────────────

if _TORCH_AVAILABLE:
    class DiabetesNet(nn.Module):
        """
        3-hidden-layer feedforward network for diabetes risk prediction.

        Architecture:
            Input  → 64 (ReLU, BN, Dropout 0.3)
                   → 32 (ReLU, BN, Dropout 0.2)
                   → 16 (ReLU)
                   → 1  (Sigmoid)
        """

        def __init__(self, input_size: int = len(DIABETES_FEATURES)) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_size, 64),
                nn.ReLU(),
                nn.BatchNorm1d(64),
                nn.Dropout(0.3),
                nn.Linear(64, 32),
                nn.ReLU(),
                nn.BatchNorm1d(32),
                nn.Dropout(0.2),
                nn.Linear(32, 16),
                nn.ReLU(),
                nn.Linear(16, 1),
                nn.Sigmoid(),
            )

        def forward(self, x):
            return self.net(x)

        def predict_proba(self, x: np.ndarray) -> float:
            """Return scalar probability from a feature array."""
            self.eval()
            with torch.no_grad():
                tensor = torch.FloatTensor(x)
                return float(self.net(tensor).squeeze())
else:
    DiabetesNet = None


# ─── Main Model Class ─────────────────────────────────────────────────────────

class DiabetesRiskModel:
    """
    Ensemble diabetes risk predictor.

    Combines XGBoost (tabular gradient boosting) and a small neural net
    to predict the probability of developing Type 2 Diabetes.

    If model files are not found, falls back to a heuristic rule-based
    estimate to ensure the system always returns a result.

    Attributes:
        xgb_model:    Trained XGBClassifier or None.
        nn_model:     Trained DiabetesNet or None.
        scaler:       StandardScaler fitted on training data.
        feature_names: Ordered list of feature keys used during training.
    """

    XGB_PATH = os.path.join(MODEL_STORE_DIR, "diabetes_xgb.pkl")
    NN_PATH = os.path.join(MODEL_STORE_DIR, "diabetes_nn.pth")
    SCALER_PATH = os.path.join(MODEL_STORE_DIR, "diabetes_scaler.pkl")

    # Ensemble weights
    XGB_WEIGHT = 0.60
    NN_WEIGHT = 0.40

    def __init__(self) -> None:
        self.xgb_model: Optional[Any] = None
        self.nn_model: Optional[Any] = None
        self.scaler: Optional[Any] = None
        self.feature_names: List[str] = DIABETES_FEATURES
        self._loaded = False
        self._load_models()

    def __repr__(self) -> str:
        return (
            f"DiabetesRiskModel(loaded={self._loaded}, "
            f"xgb={self.xgb_model is not None}, "
            f"nn={self.nn_model is not None})"
        )

    def health_check(self) -> dict:
        """Return model component status."""
        return {
            "model": "DiabetesRiskModel",
            "loaded": self._loaded,
            "xgb_available": self.xgb_model is not None,
            "nn_available": self.nn_model is not None,
            "feature_count": len(self.feature_names),
        }

    # ─── Prediction ──────────────────────────────────────────────────────────

    def predict(self, features: Dict[str, float]) -> Dict:
        """
        Predict diabetes risk probability and generate contributing factors.

        Args:
            features: Feature dict from HealthFeatureEngineer.build_features().

        Returns:
            {
              "disease": "Type 2 Diabetes",
              "probability": float,
              "risk_level": "low" | "moderate" | "high",
              "contributing_factors": [...],
              "model_confidence": float,
              "xgb_probability": float,
              "nn_probability": float,
            }
        """
        x = self._extract_feature_vector(features)

        xgb_prob = self._predict_xgb(x)
        nn_prob = self._predict_nn(x)

        if xgb_prob is None and nn_prob is None:
            # Full fallback to heuristic
            xgb_prob = nn_prob = self._heuristic_estimate(features)

        elif xgb_prob is None:
            xgb_prob = nn_prob

        elif nn_prob is None:
            nn_prob = xgb_prob

        final_prob = ensemble_probability(xgb_prob, nn_prob, self.XGB_WEIGHT, self.NN_WEIGHT)
        risk_level = probability_to_risk_level(final_prob)
        model_conf = compute_model_confidence(xgb_prob, nn_prob)

        contributing = self.get_feature_importance(features, x)

        return {
            "disease": "Type 2 Diabetes",
            "icd10": "E11",
            "probability": round(final_prob, 4),
            "risk_level": risk_level,
            "contributing_factors": contributing,
            "model_confidence": model_conf,
            "xgb_probability": round(xgb_prob, 4),
            "nn_probability": round(nn_prob, 4),
        }

    def get_feature_importance(
        self,
        features: Dict[str, float],
        x: np.ndarray,
    ) -> List[Dict]:
        """
        Compute SHAP-based feature importance.

        Falls back to weight-based importance if SHAP is unavailable.

        Args:
            features: Feature dict.
            x:        Feature vector (shape [1, n_features]).

        Returns:
            Top 5 contributing factors sorted by absolute weight.
        """
        if _SHAP_AVAILABLE and self.xgb_model is not None:
            try:
                explainer = shap.TreeExplainer(self.xgb_model)
                shap_values = explainer.shap_values(x)
                shap_arr = shap_values[0] if isinstance(shap_values, list) else shap_values[0]

                factors = []
                for i, fname in enumerate(self.feature_names):
                    val = float(x[0, i]) if x.ndim == 2 else float(x[i])
                    shap_val = float(shap_arr[i])
                    if abs(shap_val) < 0.01:
                        continue
                    factors.append({
                        "factor": self._factor_label(fname, val, features),
                        "weight": round(abs(shap_val), 3),
                        "direction": "increases" if shap_val > 0 else "decreases",
                        "source": FACTOR_SOURCE_MAP.get(fname, "clinical"),
                    })

                factors.sort(key=lambda f: f["weight"], reverse=True)
                return factors[:5]
            except Exception as e:
                logger.debug("SHAP explanation failed: %s", e)

        # Fallback: use feature values scaled to [0,1] as proxy importance
        return self._heuristic_importance(features)

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _load_models(self) -> None:
        """Load XGBoost and neural network models from disk."""
        loaded_any = False

        if _XGB_AVAILABLE and os.path.exists(self.XGB_PATH):
            try:
                with open(self.XGB_PATH, "rb") as f:
                    self.xgb_model = pickle.load(f)
                logger.info("Diabetes XGB model loaded from %s.", self.XGB_PATH)
                loaded_any = True
            except Exception as e:
                logger.warning("Could not load XGB model: %s", e)

        if _TORCH_AVAILABLE and os.path.exists(self.NN_PATH):
            try:
                self.nn_model = DiabetesNet(input_size=len(self.feature_names))
                self.nn_model.load_state_dict(
                    torch.load(self.NN_PATH, map_location="cpu")
                )
                self.nn_model.eval()
                logger.info("Diabetes NN model loaded from %s.", self.NN_PATH)
                loaded_any = True
            except Exception as e:
                logger.warning("Could not load NN model: %s", e)

        if _SKLEARN_AVAILABLE and os.path.exists(self.SCALER_PATH):
            try:
                with open(self.SCALER_PATH, "rb") as f:
                    self.scaler = pickle.load(f)
            except Exception as e:
                logger.warning("Could not load scaler: %s", e)

        self._loaded = loaded_any
        if not loaded_any:
            logger.info(
                "No diabetes model files found. Using heuristic fallback. "
                "Run training/train_diabetes.py to generate models."
            )

    def _extract_feature_vector(self, features: Dict[str, float]) -> np.ndarray:
        """Extract ordered numpy array for the model."""
        vec = np.array(
            [features.get(k, 0.0) for k in self.feature_names],
            dtype=np.float32,
        ).reshape(1, -1)
        return vec

    def _predict_xgb(self, x: np.ndarray) -> Optional[float]:
        """Run XGBoost prediction. Returns None if model unavailable."""
        if self.xgb_model is None:
            return None
        try:
            prob = float(self.xgb_model.predict_proba(x)[0, 1])
            return prob
        except Exception as e:
            logger.debug("XGB prediction error: %s", e)
            return None

    def _predict_nn(self, x: np.ndarray) -> Optional[float]:
        """Run neural network prediction. Returns None if model unavailable."""
        if self.nn_model is None:
            return None
        try:
            x_scaled = self.scaler.transform(x) if self.scaler else x
            return self.nn_model.predict_proba(x_scaled)
        except Exception as e:
            logger.debug("NN prediction error: %s", e)
            return None

    def _heuristic_estimate(self, features: Dict[str, float]) -> float:
        """
        Rule-based diabetes risk estimate when ML models are unavailable.

        Based on known clinical risk factors with evidence-based weights.
        """
        score = 0.10  # Base risk

        age = features.get("age", 40.0)
        score += min(0.15, max(0.0, (age - 35) * 0.005))  # Risk increases with age

        fbs = features.get("latest_blood_sugar_fasting", 90.0)
        if fbs >= 126:
            score += 0.35
        elif fbs >= 100:
            score += 0.18

        hba1c = features.get("latest_hba1c", 5.4)
        if hba1c >= 6.5:
            score += 0.30
        elif hba1c >= 5.7:
            score += 0.15

        bmi = features.get("bmi", 23.5) or features.get("latest_bmi", 23.5)
        if bmi >= 30:
            score += 0.10
        elif bmi >= 25:
            score += 0.05

        score += features.get("parent_diabetes", 0) * 0.18
        score += features.get("grandparent_diabetes", 0) * 0.08
        score += min(0.12, features.get("family_diabetes_count", 0) * 0.04)

        if features.get("has_diabetes_history", 0):
            score += 0.25

        score -= features.get("exercise_regularity", 0.3) * 0.05
        score -= features.get("diet_quality_score", 0.5) * 0.04

        return min(0.98, max(0.02, score))

    def _heuristic_importance(self, features: Dict[str, float]) -> List[Dict]:
        """Generate proxy importance when SHAP is unavailable."""
        importance_weights = {
            "has_diabetes_history": 0.30,
            "latest_hba1c": 0.25,
            "latest_blood_sugar_fasting": 0.22,
            "parent_diabetes": 0.18,
            "grandparent_diabetes": 0.10,
            "bmi": 0.08,
            "exercise_regularity": 0.06,
            "family_diabetes_count": 0.05,
        }
        factors = []
        for fname, weight in importance_weights.items():
            val = features.get(fname, 0.0)
            if val == 0:
                continue
            factors.append({
                "factor": self._factor_label(fname, val, features),
                "weight": weight,
                "direction": "increases",
                "source": FACTOR_SOURCE_MAP.get(fname, "clinical"),
            })
        return sorted(factors, key=lambda f: f["weight"], reverse=True)[:5]

    @staticmethod
    def _factor_label(fname: str, val: float, features: Dict) -> str:
        """Generate a human-readable factor description."""
        base = FACTOR_LABELS.get(fname, fname.replace("_", " ").title())
        if fname == "latest_blood_sugar_fasting" and val:
            return f"Fasting blood sugar: {val:.0f} mg/dL"
        elif fname == "latest_hba1c" and val:
            return f"HbA1c: {val:.1f}%"
        elif fname == "bmi" or fname == "latest_bmi":
            return f"BMI: {val:.1f} kg/m²"
        elif fname == "age" and val:
            return f"Age: {int(val)} years"
        return base
