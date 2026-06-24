"""
Risk Analysis Pydantic schemas.

Request/response models for risk predictions, risk profiles, watchlists,
and family-level hereditary risk maps.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ContributingFactor(BaseModel):
    """A single factor that contributed to a risk prediction."""
    factor: str = Field(..., description="Human-readable description of the factor")
    weight: float = Field(..., ge=0.0, le=1.0, description="Relative weight (0–1)")
    source: str = Field(..., description="'family' | 'record' | 'demographic' | 'lifestyle'")
    detail: Optional[str] = None


class RiskPredictionOut(BaseModel):
    """Single disease risk prediction as returned in API responses."""
    id: uuid.UUID
    disease_name: str
    icd10_code: Optional[str] = None
    probability: float
    probability_pct: float
    risk_level: str                        # low | moderate | high
    contributing_factors: List[ContributingFactor] = Field(default_factory=list)
    top_factors: List[ContributingFactor] = Field(default_factory=list)
    model_version: Optional[str] = None
    generated_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


class RiskProfileOut(BaseModel):
    """Full risk profile for a user — all active predictions."""
    user_id: uuid.UUID
    overall_risk_level: str              # Derived from highest individual risk
    health_score: int = Field(..., ge=0, le=100)
    predictions: List[RiskPredictionOut]
    total_predictions: int
    high_risk_count: int
    moderate_risk_count: int
    low_risk_count: int
    last_updated: Optional[datetime] = None


class FamilyRiskNode(BaseModel):
    """Risk information for one family member (used in family risk map)."""
    family_member_id: uuid.UUID
    name: str
    relationship: str
    generation: int
    conditions: List[str] = Field(default_factory=list)
    risk_contributions: List[Dict[str, Any]] = Field(default_factory=list)


class FamilyRiskMapOut(BaseModel):
    """Family-level hereditary risk map for doctor/patient views."""
    user_id: uuid.UUID
    family_nodes: List[FamilyRiskNode]
    hereditary_diseases: List[str]
    user_predictions: List[RiskPredictionOut]


class WatchlistItem(BaseModel):
    """A single item in the disease watchlist."""
    disease_name: str
    icd10_code: Optional[str] = None
    probability: float
    probability_pct: float
    risk_level: str
    reason: str                          # Short explanation for why it's on the watchlist
    family_members_affected: List[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None


class WatchlistOut(BaseModel):
    """Watchlist of top flagged future risks for the user."""
    user_id: uuid.UUID
    items: List[WatchlistItem]
    total: int


class RiskGenerateIn(BaseModel):
    """
    Body for POST /risk/generate.

    Optionally specify which disease to re-run (omit for full refresh).
    """
    disease_name: Optional[str] = Field(
        None, description="Specific disease to re-predict. Leave empty for full refresh."
    )
    force: bool = Field(
        default=False,
        description="Force re-generation even if predictions are fresh (< 24h old).",
    )
