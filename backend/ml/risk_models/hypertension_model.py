"""
Hypertension risk prediction model for GenHealth AI.

Ensemble: XGBoost (0.6) + PyTorch HypertensionNet (0.4).
Key features: age, gender, BP readings, family history, salt/stress signals.
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

try:
    import xgboost as xgb
    _XGB_AVAILABLE = True
except ImportError:
    _XGB_AVAILABLE = False

try:
    import torch
    import torch.nn as nn
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

try:
    import shap
    _SHAP_AVAILABLE = True
except ImportError:
    _SHAP_AVAILABLE = False

MODEL_STORE_DIR = os.path.join(os.path.dirname(__file__), "..", "models_store")

HYPERTENSION_FEATURES = [
    "age",
    "gender_male",
    "bmi",
    "latest_bmi",
    "latest_systolic_bp",
    "latest_diastolic_bp",
    "has_hypertension_history",
    "hypertension_recurrence_count",
    "has_diabetes_history",
    "latest_blood_sugar_fasting",
    "latest_cholesterol",
    "latest_creatinine",
    "parent_hypertension",
    "grandparent_hypertension",
    "family_hypertension_count",
    "exercise_regularity",
    "diet_quality_score",
    "disease_count",
]

FACTOR_LABELS: Dict[str, str] = {
    "age": "Age factor",
    "gender_male": "Gender (Male)",
    "bmi": "Body mass index",
    "latest_bmi": "Latest recorded BMI",
    "latest_systolic_bp": "Systolic blood pressure",
    "latest_diastolic_bp": "Diastolic blood pressure",
    "has_hypertension_history": "Personal history of hypertension",
    "hypertension_recurrence_count": "BP medications in records",
    "has_diabetes_history": "Diabetes (comorbidity)",
    "latest_blood_sugar_fasting": "Fasting blood sugar",
    "latest_cholesterol": "Total cholesterol",
    "latest_creatinine": "Creatinine (kidney function)",
    "parent_hypertension": "Parent has hypertension",
    "grandparent_hypertension": "Grandparent had hypertension",
    "family_hypertension_count": "Family members with hypertension",
    "exercise_regularity": "Exercise regularity",
    "diet_quality_score": "Diet quality (low salt intake)",
}

FACTOR_SOURCE_MAP: Dict[str, str] = {
    "age": "demographic",
    "bmi": "clinical", "latest_bmi": "clinical",
    "latest_systolic_bp": "lab", "latest_diastolic_bp": "lab",
    "has_hypertension_history": "medical_history",
    "parent_hypertension": "family", "grandparent_hypertension": "family",
    "family_hypertension_count": "family",
    "exercise_regularity": "lifestyle", "diet_quality_score": "lifestyle",
}


if _TORCH_AVAILABLE:
    class HypertensionNet(nn.Module):
        def __init__(self, input_size: int = len(HYPERTENSION_FEATURES)) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_size, 64), nn.ReLU(), nn.BatchNorm1d(64), nn.Dropout(0.3),
                nn.Linear(64, 32), nn.ReLU(), nn.BatchNorm1d(32), nn.Dropout(0.2),
                nn.Linear(32, 16), nn.ReLU(),
                nn.Linear(16, 1), nn.Sigmoid(),
            )

        def forward(self, x):
            return self.net(x)

        def predict_proba(self, x: np.ndarray) -> float:
            self.eval()
            with torch.no_grad():
                return float(self.net(torch.FloatTensor(x)).squeeze())
else:
    HypertensionNet = None


class HypertensionRiskModel:
    """Ensemble hypertension risk predictor."""

    XGB_PATH = os.path.join(MODEL_STORE_DIR, "hypertension_xgb.pkl")
    NN_PATH = os.path.join(MODEL_STORE_DIR, "hypertension_nn.pth")
    SCALER_PATH = os.path.join(MODEL_STORE_DIR, "hypertension_scaler.pkl")
    XGB_WEIGHT, NN_WEIGHT = 0.60, 0.40

    def __init__(self) -> None:
        self.xgb_model: Optional[Any] = None
        self.nn_model: Optional[Any] = None
        self.scaler: Optional[Any] = None
        self.feature_names = HYPERTENSION_FEATURES
        self._loaded = False
        self._load_models()

    def __repr__(self) -> str:
        return f"HypertensionRiskModel(loaded={self._loaded})"

    def health_check(self) -> dict:
        return {"model": "HypertensionRiskModel", "loaded": self._loaded,
                "feature_count": len(self.feature_names)}

    def predict(self, features: Dict[str, float]) -> Dict:
        x = self._vec(features)
        xgb_p = self._xgb(x)
        nn_p = self._nn(x)
        if xgb_p is None and nn_p is None:
            xgb_p = nn_p = self._heuristic(features)
        xgb_p = xgb_p or nn_p
        nn_p = nn_p or xgb_p
        prob = ensemble_probability(xgb_p, nn_p, self.XGB_WEIGHT, self.NN_WEIGHT)
        return {
            "disease": "Hypertension",
            "icd10": "I10",
            "probability": round(prob, 4),
            "risk_level": probability_to_risk_level(prob),
            "contributing_factors": self._importance(features),
            "model_confidence": compute_model_confidence(xgb_p, nn_p),
            "xgb_probability": round(xgb_p, 4),
            "nn_probability": round(nn_p, 4),
        }

    def _heuristic(self, features: Dict[str, float]) -> float:
        score = 0.08
        age = features.get("age", 40.0)
        score += min(0.12, max(0.0, (age - 40) * 0.004))
        sbp = features.get("latest_systolic_bp", 118.0)
        if sbp >= 140: score += 0.30
        elif sbp >= 130: score += 0.15
        elif sbp >= 120: score += 0.05
        dbp = features.get("latest_diastolic_bp", 76.0)
        if dbp >= 90: score += 0.15
        bmi = features.get("bmi", 23.5) or features.get("latest_bmi", 23.5)
        if bmi >= 30: score += 0.08
        score += features.get("parent_hypertension", 0) * 0.15
        score += features.get("grandparent_hypertension", 0) * 0.07
        if features.get("has_hypertension_history", 0): score += 0.25
        if features.get("has_diabetes_history", 0): score += 0.06
        score -= features.get("exercise_regularity", 0.3) * 0.06
        score -= features.get("diet_quality_score", 0.5) * 0.05  # Salt intake proxy
        return min(0.98, max(0.02, score))

    def _importance(self, features: Dict) -> List[Dict]:
        items = [
            ("has_hypertension_history", 0.28),
            ("latest_systolic_bp", 0.24),
            ("parent_hypertension", 0.16),
            ("bmi", 0.10),
            ("age", 0.08),
            ("diet_quality_score", 0.06),
        ]
        out = []
        for fname, weight in items:
            val = features.get(fname, 0.0)
            if val == 0: continue
            label = FACTOR_LABELS.get(fname, fname.replace("_", " ").title())
            if fname == "latest_systolic_bp" and val:
                label = f"Systolic BP: {val:.0f} mmHg"
            out.append({"factor": label, "weight": weight,
                        "direction": "increases",
                        "source": FACTOR_SOURCE_MAP.get(fname, "clinical")})
        return out[:5]

    def _vec(self, features: Dict) -> np.ndarray:
        return np.array([features.get(k, 0.0) for k in self.feature_names],
                        dtype=np.float32).reshape(1, -1)

    def _xgb(self, x: np.ndarray) -> Optional[float]:
        if self.xgb_model is None: return None
        try: return float(self.xgb_model.predict_proba(x)[0, 1])
        except Exception: return None

    def _nn(self, x: np.ndarray) -> Optional[float]:
        if self.nn_model is None: return None
        try:
            xs = self.scaler.transform(x) if self.scaler else x
            return self.nn_model.predict_proba(xs)
        except Exception: return None

    def _load_models(self) -> None:
        loaded = False
        if _XGB_AVAILABLE and os.path.exists(self.XGB_PATH):
            try:
                with open(self.XGB_PATH, "rb") as f:
                    self.xgb_model = pickle.load(f)
                loaded = True
            except Exception as e:
                logger.warning("Hypertension XGB load failed: %s", e)
        if _TORCH_AVAILABLE and HypertensionNet and os.path.exists(self.NN_PATH):
            try:
                self.nn_model = HypertensionNet(len(self.feature_names))
                self.nn_model.load_state_dict(torch.load(self.NN_PATH, map_location="cpu"))
                self.nn_model.eval()
                loaded = True
            except Exception as e:
                logger.warning("Hypertension NN load failed: %s", e)
        self._loaded = loaded
