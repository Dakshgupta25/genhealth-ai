"""
NLP Entity Extraction stub.

In Part 2, this module will implement:
  - Medical NER using BioBERT / scispaCy
  - ICD-10 disease code mapping (via WHO API or local lookup)
  - ATC medicine code mapping
  - Dosage and frequency pattern extraction
  - Date normalization

Current stub: returns mock entity extraction.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def extract_entities(text: str) -> List[Dict[str, Any]]:
    """
    Extract medical entities from OCR-processed text.

    Detects: diseases (→ ICD-10), medicines (→ ATC), dosages, doctors,
    hospitals, dates, test results, symptoms, and allergies.

    Args:
        text: Raw OCR-extracted text.

    Returns:
        List of entity dicts:
        [{"type": "disease", "value": "Hypothyroidism", "confidence": 0.92,
          "icd10_code": "E03.9", "start": 45, "end": 59}, ...]
    """
    logger.info("NLP entity extraction called (stub). Implement in Part 2.")
    # TODO (Part 2): Replace with BioBERT / scispaCy NER pipeline
    return []


def map_icd10(disease_name: str) -> str:
    """
    Map a disease name string to its ICD-10 code.

    Args:
        disease_name: Plain-text disease name.

    Returns:
        ICD-10 code string (e.g., 'E03.9') or empty string if not found.
    """
    # TODO (Part 2): Implement with WHO ICD API or local lookup table
    STUB_MAP = {
        "hypothyroidism": "E03.9",
        "type 2 diabetes": "E11",
        "hypertension": "I10",
        "coronary artery disease": "I25.1",
    }
    return STUB_MAP.get(disease_name.lower().strip(), "")


def map_atc(medicine_name: str) -> str:
    """
    Map a medicine name to its ATC classification code.

    Args:
        medicine_name: Plain-text medicine name.

    Returns:
        ATC code string (e.g., 'H03AA01') or empty string if not found.
    """
    # TODO (Part 2): Implement with WHO ATC database
    STUB_MAP = {
        "levothyroxine": "H03AA01",
        "metformin": "A10BA02",
        "amlodipine": "C08CA01",
    }
    return STUB_MAP.get(medicine_name.lower().strip(), "")
