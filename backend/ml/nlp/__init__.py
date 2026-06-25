"""
NLP package for GenHealth AI.

Provides medical entity extraction, normalization, and date parsing.
"""

from ml.nlp.entity_extractor import MedicalEntityExtractor, get_entity_extractor
from ml.nlp.normalizer import MedicalNormalizer, get_normalizer
from ml.nlp.date_parser import MedicalDateParser, get_date_parser, normalize_date, extract_dates
from ml.nlp.medical_vocab import PATTERNS, find_drugs_in_text, find_diseases_in_text

__all__ = [
    "MedicalEntityExtractor",
    "get_entity_extractor",
    "MedicalNormalizer",
    "get_normalizer",
    "MedicalDateParser",
    "get_date_parser",
    "normalize_date",
    "extract_dates",
    "PATTERNS",
    "find_drugs_in_text",
    "find_diseases_in_text",
]
