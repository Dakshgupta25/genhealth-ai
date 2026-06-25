"""
Cardiovascular / Heart disease risk prediction model for GenHealth AI.

Key features: age (strongest predictor), family heart history, cholesterol,
BP, diabetes status, smoking signals from medicine records.
"""

import logging
import os
import pickle
from typing import Any, Dict, List, Optional

import numpy as np

from ml.utils.confidence import ensemble_probability, probability_to_risk_level, compute_model_confidence

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

MODEL_STORE_DIR = os.path.join(os.path.dirname(__file__), "..", "models_store")

HEART_FEATURES = [
    "age",
    "gender_male",
    "bmi",
    "latest_bmi",
    "latest_systolic_bp",
    "latest_diastolic_bp",
    "latest_cholesterol",
    "latest_ldl",
    "latest_hdl",
    "latest_triglycerides",
    "has_heart_history",
    "heart_med_count",
    "has_diabetes_history",
    "has_hypertension_history",
    "hypertension_recurrence_count",
    "latest_blood_sugar_fasting",
    "grandparent_heart_disease",
    "parent_heart_disease",
    "family_heart_count",
    "exercise_regularity",
    "diet_quality_score",
]

FACTOR_LABELS: Dict[str, str] = {
    "age": "Age factor",
    "gender_male": "Gender (Male has higher early-onset risk)",
    "bmi": "Body mass index",
    "latest_systolic_bp": "Systolic blood pressure",
    "latest_cholesterol": "Total cholesterol",
    "latest_ldl": "LDL (bad) cholesterol",
    "latest_hdl": "HDL (good) cholesterol — protective",
    "latest_triglycerides": "Triglycerides",
    "has_heart_history": "Personal history of heart disease",
    "heart_med_count": "Cardiac medications in records",
    "has_diabetes_history": "Diabetes (major cardiac risk factor)",
    "has_hypertension_history": "Hypertension (major cardiac risk factor)",
    "grandparent_heart_disease": "Grandparent had heart disease",
    "parent_heart_disease": "Parent had heart disease",
    "family_heart_count": "Family members with heart disease",
    "exercise_regularity": "Exercise regularity",
    "diet_quality_score": "Diet quality score",
}

FACTOR_SOURCE_MAP: Dict[str, str] = {
    "age": "demographic", "gender_male": "demographic",
    "bmi": "clinical", "latest_bmi": "clinical",
    "latest_systolic_bp": "lab", "latest_cholesterol": "lab",
    "latest_ldl": "lab", "latest_hdl": "lab",
    "has_heart_history": "medical_history",
    "has_diabetes_history": "medical_history",
    "has_hypertension_history": "medical_history",
    "parent_heart_disease": "family", "grandparent_heart_disease": "family",
    "family_heart_count": "family",
    "exercise_regularity": "lifestyle", "diet_quality_score": "lifestyle",
}


if _TORCH_AVAILABLE:
    class HeartNet(nn.Module):
        def __init__(self, input_size: int = len(HEART_FEATURES)) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_size, 64), nn.ReLU(), nn.BatchNorm1d(64), nn.Dropout(0.3),
                nn.Linear(64, 32), nn.ReLU(), nn.BatchNorm1d(32), nn.Dropout(0.2),
                nn.Linear(32, 16), nn.ReLU(),
                nn.Linear(16, 1), nn.Sigmoid(),
            )

        def forward(self, x): return self.net(x)

        def predict_proba(self, x: np.ndarray) -> float:
            self.eval()
            with torch.no_grad():
                return float(self.net(torch.FloatTensor(x)).squeeze())
else:
    HeartNet = None


class HeartRiskModel:
    """Cardiovascular disease risk predictor."""

    XGB_PATH = os.path.join(MODEL_STORE_DIR, "heart_xgb.pkl")
    NN_PATH = os.path.join(MODEL_STORE_DIR, "heart_nn.pth")
    SCALER_PATH = os.path.join(MODEL_STORE_DIR, "heart_scaler.pkl")
    XGB_WEIGHT, NN_WEIGHT = 0.60, 0.40

    def __init__(self) -> None:
        self.xgb_model: Optional[Any] = None
        self.nn_model: Optional[Any] = None
        self.scaler: Optional[Any] = None
        self.feature_names = HEART_FEATURES
        self._loaded = False
        self._load_models()

    def __repr__(self) -> str:
        return f"HeartRiskModel(loaded={self._loaded})"

    def health_check(self) -> dict:
        return {"model": "HeartRiskModel", "loaded": self._loaded,
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
            "disease": "Cardiovascular Disease",
            "icd10": "I25.1",
            "probability": round(prob, 4),
            "risk_level": probability_to_risk_level(prob),
            "contributing_factors": self._importance(features),
            "model_confidence": compute_model_confidence(xgb_p, nn_p),
            "xgb_probability": round(xgb_p, 4),
            "nn_probability": round(nn_p, 4),
        }

    def _heuristic(self, features: Dict[str, float]) -> float:
        """Framingham-inspired heuristic heart risk estimate."""
        score = 0.05
        age = features.get("age", 40.0)

        # Age is the strongest predictor
        if age >= 65: score += 0.20
        elif age >= 55: score += 0.12
        elif age >= 45: score += 0.06
        elif age >= 35: score += 0.02

        # Male gender for early-onset
        if features.get("gender_male", 0):
            score += 0.04

        # Cholesterol
        chol = features.get("latest_cholesterol", 185.0)
        if chol >= 240: score += 0.12
        elif chol >= 200: score += 0.06

        ldl = features.get("latest_ldl", 110.0)
        if ldl >= 160: score += 0.10
        elif ldl >= 130: score += 0.05

        hdl = features.get("latest_hdl", 48.0)
        if hdl < 40: score += 0.08      # Low HDL = higher risk
        elif hdl >= 60: score -= 0.04   # High HDL = protective

        # BP
        sbp = features.get("latest_systolic_bp", 118.0)
        if sbp >= 140: score += 0.10
        elif sbp >= 130: score += 0.05

        # Comorbidities (major multipliers)
        if features.get("has_diabetes_history", 0): score += 0.12
        if features.get("has_hypertension_history", 0): score += 0.08
        if features.get("has_heart_history", 0): score += 0.25

        # Family history
        score += features.get("parent_heart_disease", 0) * 0.15
        score += features.get("grandparent_heart_disease", 0) * 0.08
        score += min(0.10, features.get("family_heart_count", 0) * 0.04)

        # Lifestyle
        score -= features.get("exercise_regularity", 0.3) * 0.08
        score -= features.get("diet_quality_score", 0.5) * 0.05

        return min(0.98, max(0.02, score))

    def _importance(self, features: Dict) -> List[Dict]:
        items = [
            ("has_heart_history", 0.30),
            ("age", 0.22),
            ("latest_cholesterol", 0.18),
            ("has_diabetes_history", 0.15),
            ("parent_heart_disease", 0.12),
            ("has_hypertension_history", 0.10),
        ]
        out = []
        for fname, weight in items:
            val = features.get(fname, 0.0)
            if val == 0: continue
            label = FACTOR_LABELS.get(fname, fname.replace("_", " ").title())
            if fname == "latest_cholesterol" and val:
                label = f"Cholesterol: {val:.0f} mg/dL"
            elif fname == "age" and val:
                label = f"Age: {int(val)} years"
            out.append({"factor": label, "weight": weight, "direction": "increases",
                        "source": FACTOR_SOURCE_MAP.get(fname, "clinical")})
        return out[:5]

    def _vec(self, f: Dict) -> np.ndarray:
        return np.array([f.get(k, 0.0) for k in self.feature_names], dtype=np.float32).reshape(1, -1)

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
            except Exception: pass
        if _TORCH_AVAILABLE and HeartNet and os.path.exists(self.NN_PATH):
            try:
                self.nn_model = HeartNet(len(self.feature_names))
                self.nn_model.load_state_dict(torch.load(self.NN_PATH, map_location="cpu"))
                self.nn_model.eval()
                loaded = True
            except Exception: pass
        self._loaded = loaded
