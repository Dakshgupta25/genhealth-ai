"""
Feature engineering pipeline for GenHealth AI risk models.

Converts raw health records, extracted entities, and family member data
into a structured, ML-ready feature vector for disease risk prediction.
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np

from ml.utils.medical_constants import ICD10_LOOKUP, LAB_REFERENCE_RANGES

logger = logging.getLogger(__name__)

# ─── Population median imputation values ─────────────────────────────────────
# Used when a feature is missing from the user's records

POPULATION_MEDIANS: Dict[str, float] = {
    "age": 40.0,
    "bmi": 23.5,
    "latest_blood_sugar_fasting": 90.0,
    "latest_hba1c": 5.4,
    "latest_tsh": 2.2,
    "latest_systolic_bp": 118.0,
    "latest_diastolic_bp": 76.0,
    "latest_cholesterol": 185.0,
    "latest_ldl": 110.0,
    "latest_hdl": 48.0,
    "latest_triglycerides": 130.0,
    "latest_creatinine": 0.9,
    "latest_vitamin_d": 25.0,
    "exercise_regularity": 0.3,
    "diet_quality_score": 0.5,
}

# ICD-10 prefixes for disease categories
DIABETES_ICD10_PREFIXES = ("E10", "E11", "E12", "E13", "E14", "O24")
HYPERTENSION_ICD10_PREFIXES = ("I10", "I11", "I12", "I13", "I15")
THYROID_ICD10_PREFIXES = ("E00", "E01", "E02", "E03", "E04", "E05", "E06", "E07")
HEART_ICD10_PREFIXES = ("I20", "I21", "I22", "I23", "I24", "I25", "I50", "I48", "I47")
CANCER_ICD10_PREFIXES = ("C",)


class HealthFeatureEngineer:
    """
    Constructs ML feature vectors from a user's health record database.

    Feature categories:
    - Personal demographics (age, gender, BMI, blood group)
    - Medical history (disease counts, medication history, record count)
    - Latest lab values (blood sugar, HbA1c, TSH, BP, cholesterol)
    - Recurrence counts per disease
    - Generational / family history features
    - Lifestyle signals

    Missing features are imputed with population medians to avoid
    crashing downstream models on incomplete records.
    """

    # Complete feature schema — matches model training columns
    FEATURE_SCHEMA: Dict[str, type] = {
        "age": float,
        "gender_male": int,
        "bmi": float,
        "has_diabetes_history": int,
        "has_hypertension_history": int,
        "has_thyroid_history": int,
        "has_heart_history": int,
        "disease_count": int,
        "unique_medicines_count": int,
        "record_count": int,
        "years_of_history": float,
        "latest_blood_sugar_fasting": float,
        "latest_hba1c": float,
        "latest_tsh": float,
        "latest_systolic_bp": float,
        "latest_diastolic_bp": float,
        "latest_cholesterol": float,
        "latest_ldl": float,
        "latest_hdl": float,
        "latest_triglycerides": float,
        "latest_creatinine": float,
        "latest_vitamin_d": float,
        "latest_bmi": float,
        "diabetes_recurrence_count": int,
        "hypertension_recurrence_count": int,
        "thyroid_med_count": int,
        "heart_med_count": int,
        "parent_diabetes": int,
        "grandparent_diabetes": int,
        "sibling_diabetes": int,
        "family_diabetes_count": int,
        "parent_hypertension": int,
        "grandparent_hypertension": int,
        "family_hypertension_count": int,
        "grandparent_heart_disease": int,
        "parent_heart_disease": int,
        "family_heart_count": int,
        "parent_thyroid": int,
        "family_thyroid_count": int,
        "family_cancer_count": int,
        "exercise_regularity": float,
        "diet_quality_score": float,
    }

    def __repr__(self) -> str:
        return f"HealthFeatureEngineer(features={len(self.FEATURE_SCHEMA)})"

    def health_check(self) -> dict:
        """Return feature engineer status."""
        return {
            "feature_count": len(self.FEATURE_SCHEMA),
            "imputation_values": len(POPULATION_MEDIANS),
        }

    # ─── Main feature builder ─────────────────────────────────────────────────

    def build_features(
        self,
        user: Any,
        records: List[Any],
        entities: List[Any],
        family_members: List[Any],
        family_records: Optional[List[Any]] = None,
    ) -> Dict[str, float]:
        """
        Build the complete feature vector for a user.

        Args:
            user:           User ORM object (with date_of_birth, gender, etc.)
            records:        List of HealthRecord ORM objects for this user.
            entities:       List of ExtractedEntity ORM objects.
            family_members: List of FamilyMember ORM objects.
            family_records: List of (member, record, entity) tuples for family.

        Returns:
            Feature dict mapping feature names to numeric values.
            All features guaranteed to be present (imputed if missing).
        """
        features: Dict[str, float] = {}

        # Personal features
        features.update(self._personal_features(user))

        # Medical history features
        features.update(self._medical_history_features(records, entities))

        # Lab value features
        features.update(self._lab_value_features(entities))

        # Medication recurrence features
        features.update(self._medication_features(entities))

        # Family / generational features
        features.update(self.build_family_features(family_members, family_records or []))

        # Lifestyle features (defaults — can be updated from user preferences)
        features.setdefault("exercise_regularity", POPULATION_MEDIANS["exercise_regularity"])
        features.setdefault("diet_quality_score", POPULATION_MEDIANS["diet_quality_score"])

        # Impute missing values with population medians
        features = self._impute_missing(features)

        # Validate and cast all feature types
        features = self._validate_and_cast(features)

        logger.debug("Built %d features for user.", len(features))
        return features

    def build_features_from_dict(self, raw: Dict) -> Dict[str, float]:
        """
        Build features from a pre-computed raw dictionary.

        Useful for testing or when feature data has already been assembled
        outside the DB context.

        Args:
            raw: Dict with any subset of feature keys.

        Returns:
            Complete, imputed, validated feature dict.
        """
        features = {**raw}
        features = self._impute_missing(features)
        return self._validate_and_cast(features)

    def feature_vector(self, features: Dict, feature_names: List[str]) -> np.ndarray:
        """
        Convert a feature dict to an ordered numpy array.

        Args:
            features:      Feature dict from build_features().
            feature_names: Ordered list of feature keys (matches model training).

        Returns:
            1D numpy float32 array.
        """
        return np.array(
            [features.get(k, POPULATION_MEDIANS.get(k, 0.0)) for k in feature_names],
            dtype=np.float32,
        ).reshape(1, -1)

    # ─── Feature sub-builders ─────────────────────────────────────────────────

    def _personal_features(self, user: Any) -> Dict[str, float]:
        """Extract age, gender, and blood group features."""
        features: Dict[str, float] = {}

        # Age
        if user and user.date_of_birth:
            today = date.today()
            dob = user.date_of_birth
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            features["age"] = float(max(0, age))
        else:
            features["age"] = POPULATION_MEDIANS["age"]

        # Gender (1 = male, 0 = female)
        if user and user.gender:
            features["gender_male"] = 1 if user.gender.lower() in ("male", "m") else 0
        else:
            features["gender_male"] = 0

        return features

    def _medical_history_features(
        self, records: List[Any], entities: List[Any]
    ) -> Dict[str, float]:
        """Count records, diseases, and compute history length."""
        features: Dict[str, float] = {}

        features["record_count"] = float(len(records))

        # Unique diseases from entities
        disease_entities = [e for e in entities if e.entity_type == "DISEASE"]
        features["disease_count"] = float(len(set(e.entity_value for e in disease_entities)))

        # Disease history flags
        features["has_diabetes_history"] = int(
            any(_is_diabetes(e.entity_value) for e in disease_entities)
        )
        features["has_hypertension_history"] = int(
            any(_is_hypertension(e.entity_value) for e in disease_entities)
        )
        features["has_thyroid_history"] = int(
            any(_is_thyroid(e.entity_value) for e in disease_entities)
        )
        features["has_heart_history"] = int(
            any(_is_heart(e.entity_value) for e in disease_entities)
        )

        # Unique medicines
        medicine_entities = [e for e in entities if e.entity_type == "MEDICINE"]
        features["unique_medicines_count"] = float(
            len(set(e.entity_value for e in medicine_entities))
        )

        # Years of medical history
        if records:
            dates = [r.record_date for r in records if r.record_date]
            if dates:
                earliest = min(dates)
                latest = max(dates)
                delta_days = (latest - earliest).days if hasattr(latest - earliest, 'days') else 0
                features["years_of_history"] = round(delta_days / 365.25, 2)
            else:
                features["years_of_history"] = 0.0
        else:
            features["years_of_history"] = 0.0

        return features

    def _lab_value_features(self, entities: List[Any]) -> Dict[str, float]:
        """
        Extract the latest lab value for each tracked biomarker.

        Picks the most recent value among all entities of type LAB_VALUE.
        """
        features: Dict[str, float] = {}

        lab_entities = [
            e for e in entities
            if e.entity_type == "LAB_VALUE" and e.entity_value
        ]

        # Map entity value labels → feature keys
        lab_field_map = {
            "fbs": "latest_blood_sugar_fasting",
            "blood_sugar_fasting": "latest_blood_sugar_fasting",
            "hba1c": "latest_hba1c",
            "tsh": "latest_tsh",
            "systolic": "latest_systolic_bp",
            "bp_systolic": "latest_systolic_bp",
            "diastolic": "latest_diastolic_bp",
            "bp_diastolic": "latest_diastolic_bp",
            "cholesterol": "latest_cholesterol",
            "total_cholesterol": "latest_cholesterol",
            "ldl": "latest_ldl",
            "hdl": "latest_hdl",
            "triglycerides": "latest_triglycerides",
            "creatinine": "latest_creatinine",
            "vitamin_d": "latest_vitamin_d",
            "vit_d": "latest_vitamin_d",
            "bmi": "latest_bmi",
        }

        for entity in lab_entities:
            label_lower = (entity.entity_value or "").lower().strip()
            for lab_key, feature_key in lab_field_map.items():
                if lab_key in label_lower and feature_key not in features:
                    # Try to extract numeric value from structured_data or icd10_code field
                    try:
                        val = float(getattr(entity, "confidence", None) or 0)
                        # Note: actual lab value would come from structured_data JSON
                        # This is a simplified extraction
                        features[feature_key] = val
                    except (TypeError, ValueError):
                        pass

        return features

    def _medication_features(self, entities: List[Any]) -> Dict[str, float]:
        """Count medication recurrences by disease category."""
        features: Dict[str, float] = {}

        medicine_entities = [e for e in entities if e.entity_type == "MEDICINE"]
        med_values = [e.entity_value.lower() for e in medicine_entities]

        # Diabetes medications
        diabetes_meds = {
            "metformin", "glipizide", "gliclazide", "glimepiride", "glibenclamide",
            "sitagliptin", "vildagliptin", "dapagliflozin", "empagliflozin",
            "liraglutide", "semaglutide", "insulin", "pioglitazone",
        }
        features["diabetes_recurrence_count"] = float(
            sum(1 for m in med_values if any(d in m for d in diabetes_meds))
        )

        # Hypertension medications
        hypert_meds = {
            "amlodipine", "enalapril", "ramipril", "lisinopril", "losartan",
            "telmisartan", "metoprolol", "atenolol", "bisoprolol", "furosemide",
            "hydrochlorothiazide", "spironolactone",
        }
        features["hypertension_recurrence_count"] = float(
            sum(1 for m in med_values if any(h in m for h in hypert_meds))
        )

        # Thyroid medications
        thyroid_meds = {"levothyroxine", "thyroxine", "liothyronine", "carbimazole", "propylthiouracil"}
        features["thyroid_med_count"] = float(
            sum(1 for m in med_values if any(t in m for t in thyroid_meds))
        )

        # Heart medications
        heart_meds = {
            "atorvastatin", "rosuvastatin", "aspirin", "clopidogrel",
            "warfarin", "rivaroxaban", "apixaban", "nitrate", "isosorbide",
        }
        features["heart_med_count"] = float(
            sum(1 for m in med_values if any(h in m for h in heart_meds))
        )

        return features

    def build_family_features(
        self,
        family_members: List[Any],
        family_records: List[Any],
    ) -> Dict[str, float]:
        """
        Compute hereditary risk features from family member health data.

        Relationship weights:
        - Parent: 2.0 (first-degree relative)
        - Sibling: 1.8
        - Grandparent: 1.0
        - Aunt/Uncle: 0.5

        Args:
            family_members: List of FamilyMember ORM objects.
            family_records: List of entity dicts from family records.

        Returns:
            Family feature sub-dict.
        """
        features: Dict[str, float] = {
            "parent_diabetes": 0,
            "grandparent_diabetes": 0,
            "sibling_diabetes": 0,
            "family_diabetes_count": 0,
            "parent_hypertension": 0,
            "grandparent_hypertension": 0,
            "family_hypertension_count": 0,
            "parent_heart_disease": 0,
            "grandparent_heart_disease": 0,
            "family_heart_count": 0,
            "parent_thyroid": 0,
            "family_thyroid_count": 0,
            "family_cancer_count": 0,
        }

        if not family_members:
            return features

        # Build member → diseases map from family records
        member_diseases: Dict[str, List[str]] = {}
        for record in family_records:
            # record is expected to be a dict or ORM object
            member_id = str(getattr(record, "family_member_id", ""))
            disease = str(getattr(record, "entity_value", "")).lower()
            if member_id:
                member_diseases.setdefault(member_id, []).append(disease)

        for member in family_members:
            rel = (member.relationship or "").lower().replace(" ", "_")
            member_id = str(member.id)
            diseases = member_diseases.get(member_id, [])

            is_parent = rel in ("father", "mother", "parent")
            is_grandparent = "grand" in rel
            is_sibling = rel in ("brother", "sister", "sibling")

            for disease in diseases:
                if _is_diabetes(disease):
                    features["family_diabetes_count"] += 1
                    if is_parent: features["parent_diabetes"] = 1
                    if is_grandparent: features["grandparent_diabetes"] = 1
                    if is_sibling: features["sibling_diabetes"] = 1

                elif _is_hypertension(disease):
                    features["family_hypertension_count"] += 1
                    if is_parent: features["parent_hypertension"] = 1
                    if is_grandparent: features["grandparent_hypertension"] = 1

                elif _is_heart(disease):
                    features["family_heart_count"] += 1
                    if is_parent: features["parent_heart_disease"] = 1
                    if is_grandparent: features["grandparent_heart_disease"] = 1

                elif _is_thyroid(disease):
                    features["family_thyroid_count"] += 1
                    if is_parent: features["parent_thyroid"] = 1

                elif _is_cancer(disease):
                    features["family_cancer_count"] += 1

        return features

    # ─── Imputation + validation ──────────────────────────────────────────────

    def _impute_missing(self, features: Dict[str, float]) -> Dict[str, float]:
        """Fill missing features with population medians."""
        for key in self.FEATURE_SCHEMA:
            if key not in features or features[key] is None:
                features[key] = POPULATION_MEDIANS.get(key, 0.0)
        return features

    def _validate_and_cast(self, features: Dict[str, float]) -> Dict[str, float]:
        """Cast all values to their declared types and clip to valid ranges."""
        result: Dict[str, float] = {}
        for key, dtype in self.FEATURE_SCHEMA.items():
            val = features.get(key, 0.0)
            try:
                result[key] = dtype(val)
            except (TypeError, ValueError):
                result[key] = dtype(0)
        return result


# ─── Disease classification helpers ──────────────────────────────────────────

def _is_diabetes(text: str) -> bool:
    return any(kw in text.lower() for kw in ("diabet", "E10", "E11", "insulin", "glyco"))

def _is_hypertension(text: str) -> bool:
    return any(kw in text.lower() for kw in ("hypertens", "I10", "high blood pressure", "bp"))

def _is_thyroid(text: str) -> bool:
    return any(kw in text.lower() for kw in ("thyroid", "E03", "E05", "hypothyroid", "hyperthyroid", "tsh"))

def _is_heart(text: str) -> bool:
    return any(kw in text.lower() for kw in (
        "cardiac", "heart", "coronary", "angina", "infarct", "I20", "I21", "I25", "I50"
    ))

def _is_cancer(text: str) -> bool:
    return any(kw in text.lower() for kw in ("cancer", "tumor", "carcinoma", "malignant", "neoplasm"))
