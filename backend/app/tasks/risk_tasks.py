"""
Risk analysis background tasks for GenHealth AI.
Aggregates user clinical data, runs disease risk models, integrates generational heritability boost,
and persists results to SQL and MongoDB.
"""

import logging
import asyncio
from datetime import datetime
from uuid import UUID
from typing import Optional

from sqlalchemy import select, and_, update

from app.celery_app import celery_app
from app.config import get_settings
from app.database import get_session_maker, init_mongo, get_mongo_db
from app.models.user import User
from app.models.family import FamilyMember
from app.models.health_record import HealthRecord, ExtractedEntity
from app.models.risk_prediction import RiskPrediction

from ml.risk_models import get_risk_classifier
from ml.generational.pattern_detector import HereditaryPatternDetector

logger = logging.getLogger(__name__)
settings = get_settings()


def run_async(coro):
    """Run an async coroutine inside the synchronous Celery task thread."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


def ensure_db_connections():
    """Ensure database connection factories are initialized for the worker process."""
    try:
        get_mongo_db()
    except RuntimeError:
        init_mongo()


async def async_compute_user_risk(user_id: str, disease_name: Optional[str] = None, force: bool = False) -> bool:
    """Orchestrate clinical risk estimation and store results in PostgreSQL and MongoDB."""
    ensure_db_connections()
    user_uuid = UUID(user_id)

    async_session = get_session_maker()
    async with async_session() as session:
        # 1. Fetch user demographics
        user_res = await session.execute(select(User).where(User.id == user_uuid))
        user = user_res.scalar_one_or_none()
        if not user:
            logger.error("User %s not found.", user_id)
            return False

        # 2. Fetch family tree and conditions from family member health records
        family_res = await session.execute(
            select(FamilyMember)
            .where(FamilyMember.user_id == user_uuid)
        )
        family_members = list(family_res.scalars().all())

        # Compile family health history
        family_health_data = []
        for m in family_members:
            # Query disease entities for this family member
            entities_res = await session.execute(
                select(ExtractedEntity)
                .join(HealthRecord)
                .where(
                    and_(
                        HealthRecord.family_member_id == m.id,
                        ExtractedEntity.entity_type == "disease"
                    )
                )
            )
            conditions = [e.effective_value for e in entities_res.scalars().all()]
            family_health_data.append({
                "member_id": str(m.id),
                "relationship": m.relationship,
                "conditions": conditions
            })

        # 3. Detect generational heritability patterns and compute boost
        logger.info("Computing hereditary generational risk factors...")
        pattern_detector = HereditaryPatternDetector()
        patterns_result = pattern_detector.detect_patterns(
            user_id=user_id,
            family_members=family_members,
            family_health_data=family_health_data
        )
        generational_boost = patterns_result.get("hereditary_risk_boost", {})

        # 4. Fetch user's own health records and clinical entities
        records_res = await session.execute(
            select(HealthRecord)
            .where(
                and_(
                    HealthRecord.owner_id == user_uuid,
                    HealthRecord.family_member_id.is_(None)
                )
            )
        )
        records = list(records_res.scalars().all())
        record_ids = [r.id for r in records]

        entities = []
        if record_ids:
            entities_res = await session.execute(
                select(ExtractedEntity).where(ExtractedEntity.record_id.in_(record_ids))
            )
            entities = list(entities_res.scalars().all())

        # 5. Run ensemble disease classifiers
        logger.info("Running disease risk classifiers...")
        classifier = get_risk_classifier()
        profile = classifier.generate_full_risk_profile(
            user=user,
            records=records,
            entities=entities,
            family_members=family_members,
            generational_boost=generational_boost
        )

        predictions = profile.get("predictions", [])

        # Filter to a specific disease if requested
        if disease_name:
            predictions = [p for p in predictions if disease_name.lower() in p["disease"].lower()]

        # 6. Deactivate old predictions in PostgreSQL
        disease_names = [p["disease"] for p in predictions]
        if disease_names:
            await session.execute(
                update(RiskPrediction)
                .where(
                    and_(
                        RiskPrediction.user_id == user_uuid,
                        RiskPrediction.disease_name.in_(disease_names),
                        RiskPrediction.is_active == True
                    )
                )
                .values(is_active=False)
            )

        # 7. Insert new predictions to PostgreSQL
        for pred in predictions:
            db_pred = RiskPrediction(
                user_id=user_uuid,
                disease_name=pred["disease"],
                icd10_code=pred.get("icd10"),
                probability=pred["probability"],
                risk_level=pred["risk_level"],
                contributing_factors=pred.get("contributing_factors", []),
                model_version=pred.get("model_version", "1.0"),
                is_active=True,
            )
            session.add(db_pred)

        await session.commit()
        logger.info("Saved SQL risk predictions for user: %s", user_id)

        # 8. Store user composite profile in MongoDB
        logger.info("Archiving user risk profile to MongoDB...")
        mongo_db = get_mongo_db()
        await mongo_db["risk_profiles"].update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "health_score": profile["health_score"],
                    "health_grade": profile["health_grade"],
                    "watchlist": profile["watchlist"],
                    "feature_summary": profile["feature_summary"],
                    "model_versions": profile.get("model_versions", {}),
                    "updated_at": datetime.utcnow().isoformat()
                }
            },
            upsert=True
        )
        logger.info("Risk profile processing complete for user %s.", user_id)
        return True


async def async_refresh_all_risk_predictions() -> bool:
    """Iterate over all users in the platform and enqueue risk analysis tasks."""
    ensure_db_connections()
    async_session = get_session_maker()
    async with async_session() as session:
        result = await session.execute(select(User.id))
        user_ids = result.scalars().all()
        
        for uid in user_ids:
            compute_user_risk.delay(str(uid), force=True)
            
        logger.info("Triggered bulk risk prediction updates for %d users.", len(user_ids))
        return True


@celery_app.task(name="app.tasks.risk_tasks.compute_user_risk")
def compute_user_risk(user_id: str, disease_name: Optional[str] = None, force: bool = False) -> bool:
    """Celery task entry point to compute user risk profiles."""
    logger.info("Celery risk task triggered: user_id=%s, disease=%s", user_id, disease_name)
    return run_async(async_compute_user_risk(user_id, disease_name, force))


@celery_app.task(name="app.tasks.risk_tasks.refresh_all_risk_predictions")
def refresh_all_risk_predictions() -> bool:
    """Celery task entry point to refresh all user risk profiles periodically."""
    logger.info("Celery beat task triggered: refresh_all_risk_predictions")
    return run_async(async_refresh_all_risk_predictions())
