"""
RiskPrediction ORM model.

Stores AI-generated disease risk predictions for a user, including the
contributing factors and their weights. Predictions are re-generated
periodically or when new health records are uploaded.
"""

import uuid
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from sqlalchemy import (
    UUID,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


# Risk level thresholds
RISK_LOW_THRESHOLD = 0.30        # < 30%
RISK_MODERATE_THRESHOLD = 0.60   # 30% – 60%
# > 60% = High


def compute_risk_level(probability: float) -> str:
    """
    Classify a probability score into a risk level label.

    Args:
        probability: Float between 0.0 and 1.0.

    Returns:
        'low' | 'moderate' | 'high'
    """
    if probability < RISK_LOW_THRESHOLD:
        return "low"
    elif probability < RISK_MODERATE_THRESHOLD:
        return "moderate"
    return "high"


class RiskPrediction(Base):
    """
    AI-generated disease risk prediction for a user.

    Each row represents the current probability that the user will develop
    a specific disease, based on their personal health records, family history,
    and demographic data.

    contributing_factors is a JSONB array:
    [
      {"factor": "Family history (father)", "weight": 0.45, "source": "family"},
      {"factor": "Personal TSH elevation", "weight": 0.30, "source": "record"},
      {"factor": "Age group", "weight": 0.10, "source": "demographic"}
    ]
    """

    __tablename__ = "risk_predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    disease_name = Column(String(255), nullable=False)
    icd10_code = Column(String(20), nullable=True)

    probability = Column(Float, nullable=False)     # 0.0 – 1.0
    risk_level = Column(String(20), nullable=False) # low | moderate | high

    # Explainability: what drove this prediction
    contributing_factors = Column(JSONB, nullable=True, default=list)

    # Model metadata
    model_version = Column(String(20), nullable=True)
    generated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Only one active prediction per disease per user
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # ─── Relationships ─────────────────────────────────────────────────
    user: "User" = relationship("User", back_populates="risk_predictions")

    def __repr__(self) -> str:
        return (
            f"<RiskPrediction user={self.user_id} "
            f"disease={self.disease_name!r} prob={self.probability:.0%}>"
        )

    @property
    def probability_pct(self) -> float:
        """Probability as a percentage rounded to 1 decimal place."""
        return round(self.probability * 100, 1)

    @property
    def top_factors(self) -> List[Dict[str, Any]]:
        """Return contributing factors sorted by weight descending."""
        if not self.contributing_factors:
            return []
        return sorted(
            self.contributing_factors,
            key=lambda f: f.get("weight", 0),
            reverse=True,
        )
