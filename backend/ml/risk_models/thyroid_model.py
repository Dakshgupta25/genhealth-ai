"""
Thyroid disorder risk prediction model for GenHealth AI.

Key insight: female gender has 3× higher thyroid risk.
Features: gender, family history, TSH levels, iodine intake region.
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

THYROID_FEATURES = [
    "age",
    "gender_male",            # Female (0) has 3× higher risk
    "latest_tsh",
    "has_thyroid_history",
    "thyroid_med_count",
    "parent_thyroid",
    "family_thyroid_count",
    "has_diabetes_history",   # Autoimmune correlation
    "disease_count",
    "exercise_regularity",
]

FACTOR_LABELS: Dict[str, str] = {
    "age": "Age factor",
    "gender_male": "Gender (Female has 3× higher risk)",
    "latest_tsh": "TSH level",
    "has_thyroid_history": "Personal history of thyroid disorder",
    "thyroid_med_count": "Thyroid medications in records",
    "parent_thyroid": "Parent has thyroid disorder",
    "family_thyroid_count": "Family members with thyroid disorder",
    "has_diabetes_history": "Diabetes (autoimmune association)",
    "exercise_regularity": "Exercise regularity",
}

FACTOR_SOURCE_MAP: Dict[str, str] = {
    "gender_male": "demographic", "age": "demographic",
    "latest_tsh": "lab",
    "has_thyroid_history": "medical_history",
    "parent_thyroid": "family", "family_thyroid_count": "family",
    "exercise_regularity": "lifestyle",
}


if _TORCH_AVAILABLE:
    class ThyroidNet(nn.Module):
        def __init__(self, input_size: int = len(THYROID_FEATURES)) -> None:
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
    ThyroidNet = None


class ThyroidRiskModel:
    """Thyroid disorder risk predictor."""

    XGB_PATH = os.path.join(MODEL_STORE_DIR, "thyroid_xgb.pkl")
    NN_PATH = os.path.join(MODEL_STORE_DIR, "thyroid_nn.pth")
    SCALER_PATH = os.path.join(MODEL_STORE_DIR, "thyroid_scaler.pkl")
    XGB_WEIGHT, NN_WEIGHT = 0.60, 0.40

    def __init__(self) -> None:
        self.xgb_model: Optional[Any] = None
        self.nn_model: Optional[Any] = None
        self.scaler: Optional[Any] = None
        self.feature_names = THYROID_FEATURES
        self._loaded = False
        self._load_models()

    def __repr__(self) -> str:
        return f"ThyroidRiskModel(loaded={self._loaded})"

    def health_check(self) -> dict:
        return {"model": "ThyroidRiskModel", "loaded": self._loaded,
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
            "disease": "Thyroid Disorder",
            "icd10": "E03.9",
            "probability": round(prob, 4),
            "risk_level": probability_to_risk_level(prob),
            "contributing_factors": self._importance(features),
            "model_confidence": compute_model_confidence(xgb_p, nn_p),
            "xgb_probability": round(xgb_p, 4),
            "nn_probability": round(nn_p, 4),
        }

    def _heuristic(self, features: Dict[str, float]) -> float:
        score = 0.06
        # Female gender: 3× multiplier applied as additive boost
        if not features.get("gender_male", 0):
            score += 0.12  # Female base uplift

        tsh = features.get("latest_tsh", 2.2)
        if tsh > 4.0: score += 0.20    # Hypothyroidism signal
        elif tsh < 0.4: score += 0.15  # Hyperthyroidism signal
        elif tsh > 2.5: score += 0.05  # Borderline

        if features.get("has_thyroid_history", 0): score += 0.28
        score += features.get("parent_thyroid", 0) * 0.14
        score += min(0.10, features.get("family_thyroid_count", 0) * 0.05)
        if features.get("has_diabetes_history", 0): score += 0.05  # Autoimmune

        return min(0.98, max(0.02, score))

    def _importance(self, features: Dict) -> List[Dict]:
        items = [
            ("has_thyroid_history", 0.30),
            ("latest_tsh", 0.25),
            ("gender_male", 0.20),
            ("parent_thyroid", 0.15),
            ("family_thyroid_count", 0.08),
        ]
        out = []
        for fname, weight in items:
            val = features.get(fname, 0.0)
            label = FACTOR_LABELS.get(fname, fname.replace("_", " ").title())
            if fname == "latest_tsh" and val:
                label = f"TSH: {val:.2f} mIU/L"
            if fname == "gender_male":
                if val == 0:  # Female
                    out.append({"factor": "Female gender (3× higher thyroid risk)", "weight": weight,
                                "direction": "increases", "source": "demographic"})
                continue
            if val == 0: continue
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
        if _TORCH_AVAILABLE and ThyroidNet and os.path.exists(self.NN_PATH):
            try:
                self.nn_model = ThyroidNet(len(self.feature_names))
                self.nn_model.load_state_dict(torch.load(self.NN_PATH, map_location="cpu"))
                self.nn_model.eval()
                loaded = True
            except Exception: pass
        self._loaded = loaded
