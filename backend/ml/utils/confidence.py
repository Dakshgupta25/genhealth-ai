"""
Confidence scoring utilities for GenHealth AI ML pipeline.

Provides:
  - Calibrated confidence aggregation across OCR engines
  - Entity-level confidence scoring
  - Model ensemble confidence computation
  - Confidence-to-risk-level mapping
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─── OCR Confidence ───────────────────────────────────────────────────────────

def aggregate_ocr_confidence(
    tesseract_words: List[Dict[str, Any]],
    easyocr_words: List[Dict[str, Any]],
    iou_threshold: float = 0.5,
) -> float:
    """
    Compute an overall document-level OCR confidence score.

    Uses a weighted average of per-word confidences from both engines.
    Words with higher confidence are weighted more.

    Args:
        tesseract_words: List of {text, confidence (0-100)} dicts.
        easyocr_words:   List of {text, confidence (0-1)} dicts.
        iou_threshold:   Minimum IOU to consider two words as matching.

    Returns:
        Overall confidence float in [0.0, 1.0].
    """
    if not tesseract_words and not easyocr_words:
        return 0.0

    confidences: List[float] = []

    # Normalize tesseract confidence from 0-100 to 0-1
    for word in tesseract_words:
        conf = word.get("confidence", 0)
        if conf >= 0:  # Tesseract returns -1 for uncertain words
            confidences.append(conf / 100.0)

    for word in easyocr_words:
        conf = word.get("confidence", 0.0)
        confidences.append(float(conf))

    if not confidences:
        return 0.0

    # Weighted mean — higher confidence words count more
    weighted_sum = sum(c ** 2 for c in confidences)  # Square to emphasize high-confidence words
    weight_total = sum(c for c in confidences)
    if weight_total == 0:
        return 0.0

    return min(1.0, weighted_sum / weight_total)


def word_confidence_to_quality(confidence: float) -> str:
    """
    Map OCR confidence to a human-readable quality label.

    Args:
        confidence: Float in [0.0, 1.0].

    Returns:
        'excellent' | 'good' | 'fair' | 'poor'
    """
    if confidence >= 0.90:
        return "excellent"
    elif confidence >= 0.75:
        return "good"
    elif confidence >= 0.55:
        return "fair"
    return "poor"


# ─── Entity Confidence ────────────────────────────────────────────────────────

def compute_entity_confidence(
    rule_confidence: Optional[float],
    ml_confidence: Optional[float],
    has_normalization_match: bool = False,
) -> float:
    """
    Compute a final entity confidence score combining rule-based and ML signals.

    Heuristics:
    - If both signals present: 0.4 * rule + 0.6 * ml (ML trusted more)
    - If only ML: ml * 0.95 (slight penalty for lack of rule confirmation)
    - If only rule: rule * 0.85 (penalty for no ML confirmation)
    - Normalization match adds +0.05 bonus (capped at 1.0)

    Args:
        rule_confidence: Confidence from rule-based extractor (0-1) or None.
        ml_confidence:   Confidence from ML NER model (0-1) or None.
        has_normalization_match: True if entity was successfully mapped to ICD-10/ATC.

    Returns:
        Combined confidence float in [0.0, 1.0].
    """
    if rule_confidence is not None and ml_confidence is not None:
        combined = 0.4 * rule_confidence + 0.6 * ml_confidence
    elif ml_confidence is not None:
        combined = ml_confidence * 0.95
    elif rule_confidence is not None:
        combined = rule_confidence * 0.85
    else:
        combined = 0.5  # Unknown — default to medium

    if has_normalization_match:
        combined = min(1.0, combined + 0.05)

    return round(combined, 3)


def filter_entities_by_confidence(
    entities: List[Dict[str, Any]],
    min_confidence: float = 0.65,
) -> List[Dict[str, Any]]:
    """
    Filter out entities below the confidence threshold.

    Args:
        entities:       List of entity dicts with a 'confidence' key.
        min_confidence: Minimum acceptable confidence (default 0.65).

    Returns:
        Filtered list of entities.
    """
    return [e for e in entities if e.get("confidence", 0.0) >= min_confidence]


# ─── Model Ensemble Confidence ────────────────────────────────────────────────

def ensemble_probability(
    xgb_prob: float,
    nn_prob: float,
    xgb_weight: float = 0.6,
    nn_weight: float = 0.4,
) -> float:
    """
    Compute weighted ensemble probability from XGBoost and Neural Net.

    Args:
        xgb_prob:   XGBoost model probability in [0.0, 1.0].
        nn_prob:    Neural network probability in [0.0, 1.0].
        xgb_weight: Weight for XGBoost (default 0.6).
        nn_weight:  Weight for neural net (default 0.4).

    Returns:
        Ensemble probability in [0.0, 1.0].
    """
    assert abs(xgb_weight + nn_weight - 1.0) < 1e-6, "Weights must sum to 1.0"
    return round(xgb_weight * xgb_prob + nn_weight * nn_prob, 4)


def probability_to_risk_level(
    probability: float,
    low_threshold: float = 0.30,
    high_threshold: float = 0.60,
) -> str:
    """
    Convert a probability to a risk level string.

    Args:
        probability:    Float in [0.0, 1.0].
        low_threshold:  Below this → 'low'.
        high_threshold: Above this → 'high'.

    Returns:
        'low' | 'moderate' | 'high'
    """
    if probability >= high_threshold:
        return "high"
    elif probability >= low_threshold:
        return "moderate"
    return "low"


def compute_model_confidence(
    xgb_prob: float,
    nn_prob: float,
) -> float:
    """
    Estimate how confident the model is in its own prediction.

    Agreement between the two models → higher confidence.
    Uses 1 - normalized disagreement.

    Args:
        xgb_prob: XGBoost predicted probability.
        nn_prob:  Neural network predicted probability.

    Returns:
        Model confidence float in [0.0, 1.0].
    """
    disagreement = abs(xgb_prob - nn_prob)
    # Max possible disagreement is 1.0, penalize heavily above 0.2
    confidence = 1.0 - (disagreement * 1.5)
    return max(0.30, min(1.0, round(confidence, 3)))


# ─── Calibration ─────────────────────────────────────────────────────────────

def platt_scale(raw_score: float, a: float = 1.0, b: float = 0.0) -> float:
    """
    Apply Platt scaling to calibrate raw model scores to probabilities.

    f(x) = 1 / (1 + exp(A*x + B))

    Default A=1, B=0 is the identity sigmoid (no calibration).

    Args:
        raw_score: Raw model output score.
        a:         Platt A parameter (fit on validation set).
        b:         Platt B parameter (fit on validation set).

    Returns:
        Calibrated probability in (0, 1).
    """
    try:
        return 1.0 / (1.0 + math.exp(a * raw_score + b))
    except OverflowError:
        return 0.0 if raw_score > 0 else 1.0


def confidence_label(score: float) -> str:
    """Return a human-readable label for a confidence score."""
    if score >= 0.90:
        return "Very High"
    elif score >= 0.75:
        return "High"
    elif score >= 0.55:
        return "Moderate"
    elif score >= 0.35:
        return "Low"
    return "Very Low"
