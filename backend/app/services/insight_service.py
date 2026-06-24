"""
Insight service.

Business logic for:
  - Health score computation (0–100) based on risk predictions and records
  - Disease frequency trend analysis
  - Personalised recommendation generation
  - AI health summary generation
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.health_record import ExtractedEntity, HealthRecord
from app.models.risk_prediction import RiskPrediction

logger = logging.getLogger(__name__)


# ─── Health Score ─────────────────────────────────────────────────────────────

# Maximum penalty per risk category
_RISK_PENALTIES = {"high": 20, "moderate": 10, "low": 3}
_BASE_SCORE = 100


async def compute_health_score(user_id: UUID, db: AsyncSession) -> int:
    """
    Compute a 0–100 health score for the user.

    Algorithm:
    1. Start from 100.
    2. Subtract penalty for each active risk prediction based on its level.
    3. Add a small bonus for recently verified records (engagement proxy).
    4. Clamp to [0, 100].

    Returns:
        Integer health score between 0 and 100.
    """
    # Fetch active risk predictions
    result = await db.execute(
        select(RiskPrediction.risk_level)
        .where(and_(RiskPrediction.user_id == user_id, RiskPrediction.is_active == True))
    )
    risk_levels = [row[0] for row in result.all()]

    score = _BASE_SCORE
    for level in risk_levels:
        score -= _RISK_PENALTIES.get(level, 0)

    # Small engagement bonus: up to +5 for verified records
    verified_count_result = await db.execute(
        select(func.count(HealthRecord.id)).where(
            and_(
                HealthRecord.owner_id == user_id,
                HealthRecord.is_verified_by_user == True,
            )
        )
    )
    verified_count = verified_count_result.scalar_one() or 0
    score += min(verified_count * 2, 5)

    return max(0, min(100, score))


# ─── Disease Trends ───────────────────────────────────────────────────────────

async def get_disease_trends(
    user_id: UUID, db: AsyncSession, months: int = 12
) -> List[Dict[str, Any]]:
    """
    Compute disease mention frequency over the past N months.

    Returns a list of dicts:
    [{"disease": "Hypothyroidism", "mentions": 3, "months": [...]}]
    """
    since = datetime.utcnow() - timedelta(days=months * 30)

    result = await db.execute(
        select(
            ExtractedEntity.entity_value,
            HealthRecord.record_date,
        )
        .join(HealthRecord, HealthRecord.id == ExtractedEntity.record_id)
        .where(
            and_(
                HealthRecord.owner_id == user_id,
                ExtractedEntity.entity_type == "disease",
                HealthRecord.record_date >= since,
            )
        )
        .order_by(HealthRecord.record_date)
    )
    rows = result.all()

    # Group by disease
    disease_data: Dict[str, List[str]] = defaultdict(list)
    for entity_value, record_date in rows:
        month_label = record_date.strftime("%b %Y") if record_date else "Unknown"
        disease_data[entity_value.strip().title()].append(month_label)

    trends = [
        {
            "disease": disease,
            "mentions": len(months_list),
            "months": sorted(set(months_list)),
        }
        for disease, months_list in disease_data.items()
    ]
    return sorted(trends, key=lambda t: t["mentions"], reverse=True)


# ─── Recommendations ──────────────────────────────────────────────────────────

# Recommendation templates keyed by (risk_level, disease_keyword)
_RECOMMENDATION_TEMPLATES = [
    {
        "match_diseases": ["diabetes", "type 2 diabetes"],
        "match_levels": ["high", "moderate"],
        "category": "diet",
        "priority": "urgent",
        "title": "Reduce refined sugar intake",
        "description": (
            "Cut refined carbohydrates by 30%. Replace with complex carbs: "
            "whole grains, lentils, and leafy vegetables."
        ),
        "action": "Set a daily dietary reminder.",
    },
    {
        "match_diseases": ["diabetes", "hypertension", "hypothyroidism"],
        "match_levels": ["high", "moderate", "low"],
        "category": "exercise",
        "priority": "recommended",
        "title": "30 min brisk walk daily",
        "description": (
            "Morning walks before breakfast improve insulin sensitivity, "
            "regulate blood pressure, and support thyroid metabolism."
        ),
        "action": "Set a morning walk reminder.",
    },
    {
        "match_diseases": ["diabetes", "type 2 diabetes"],
        "match_levels": ["high"],
        "category": "checkup",
        "priority": "urgent",
        "title": "Annual HbA1c blood test",
        "description": (
            "HbA1c measures average blood sugar over 3 months. "
            "Essential given high diabetes risk."
        ),
        "action": "Schedule a lab appointment.",
    },
    {
        "match_diseases": ["hypothyroidism", "thyroid"],
        "match_levels": ["high", "moderate"],
        "category": "diet",
        "priority": "recommended",
        "title": "Increase iodine-rich foods",
        "description": (
            "Include seafood, iodized salt, dairy, and eggs in your diet. "
            "Iodine supports thyroid hormone production."
        ),
        "action": "Update your meal plan.",
    },
    {
        "match_diseases": ["heart disease", "hypertension", "coronary"],
        "match_levels": ["high", "moderate"],
        "category": "checkup",
        "priority": "recommended",
        "title": "Annual cardiac screening",
        "description": (
            "ECG + lipid profile test annually. "
            "Recommended given cardiovascular family history."
        ),
        "action": "Book with a cardiologist.",
    },
    {
        "match_diseases": [],
        "match_levels": ["high", "moderate", "low"],
        "category": "sleep",
        "priority": "optional",
        "title": "8 hours consistent sleep",
        "description": (
            "Consistent sleep schedules regulate cortisol and insulin. "
            "Especially important for thyroid and metabolic health."
        ),
        "action": "Set a bedtime reminder.",
    },
]


async def get_recommendations(
    user_id: UUID, db: AsyncSession
) -> List[Dict[str, Any]]:
    """
    Generate personalised health recommendations based on active risk predictions.

    Matches recommendation templates against the user's active risk conditions
    and filters out duplicates. Returns recommendations sorted by priority.
    """
    result = await db.execute(
        select(RiskPrediction.disease_name, RiskPrediction.risk_level)
        .where(and_(RiskPrediction.user_id == user_id, RiskPrediction.is_active == True))
    )
    predictions = result.all()

    matched: List[Dict[str, Any]] = []
    seen_titles: set = set()

    for template in _RECOMMENDATION_TEMPLATES:
        # Check if any user disease matches the template diseases
        disease_match = (
            not template["match_diseases"]  # Universal template
            or any(
                any(keyword in pred[0].lower() for keyword in template["match_diseases"])
                for pred in predictions
                if pred[1] in template["match_levels"]
            )
        )

        if disease_match and template["title"] not in seen_titles:
            seen_titles.add(template["title"])
            matched.append(dict(template))

    # Sort: urgent first, then recommended, then optional
    priority_order = {"urgent": 0, "recommended": 1, "optional": 2}
    matched.sort(key=lambda r: priority_order.get(r["priority"], 3))
    return matched


# ─── AI Health Summary ────────────────────────────────────────────────────────

async def generate_health_summary(
    user_id: UUID, user_name: str, db: AsyncSession
) -> Dict[str, Any]:
    """
    Generate a structured AI health summary for a user.

    In production this would call an LLM API. For now, it produces a
    deterministic template-based summary using real data from the database.
    """
    score = await compute_health_score(user_id, db)
    trends = await get_disease_trends(user_id, db, months=6)

    result = await db.execute(
        select(RiskPrediction)
        .where(and_(RiskPrediction.user_id == user_id, RiskPrediction.is_active == True))
        .order_by(desc(RiskPrediction.probability))
        .limit(3)
    )
    top_risks = result.scalars().all()

    top_risk_names = [r.disease_name for r in top_risks]
    risk_clause = (
        ", ".join(top_risk_names[:-1]) + f" and {top_risk_names[-1]}"
        if len(top_risk_names) > 1
        else (top_risk_names[0] if top_risk_names else "no significant conditions")
    )

    summary_text = (
        f"Hello {user_name.split()[0]}! Your current health score is {score}/100. "
        f"Your primary areas to monitor are {risk_clause}. "
        "Stay on top of your annual checkups and follow your personalised plan."
    )

    return {
        "user_id": str(user_id),
        "health_score": score,
        "summary": summary_text,
        "top_risks": [r.disease_name for r in top_risks],
        "recent_conditions": [t["disease"] for t in trends[:3]],
        "generated_at": datetime.utcnow().isoformat(),
    }
