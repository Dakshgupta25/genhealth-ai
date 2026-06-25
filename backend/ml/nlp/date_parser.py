"""
Date parsing and normalization for medical documents.

Handles the wide variety of date formats found in Indian medical records,
including ambiguous day-first formats, written month names, and relative
temporal references.
"""

import logging
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from ml.utils.medical_constants import FREQUENCY_MAP

logger = logging.getLogger(__name__)

try:
    from dateutil import parser as dateutil_parser
    from dateutil.relativedelta import relativedelta
    _DATEUTIL_AVAILABLE = True
except ImportError:
    logger.warning("python-dateutil not installed. Date parsing will be limited.")
    _DATEUTIL_AVAILABLE = False


# ─── Date Patterns ────────────────────────────────────────────────────────────

# Numeric date formats: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, YYYY-MM-DD
_NUMERIC_DATE_RE = re.compile(
    r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})\b"
    r"|\b(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})\b"
)

# Written date formats: "12 June 2025", "12th June 2025", "June 12, 2025"
_WRITTEN_DATE_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+(\d{4})\b"
    r"|"
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b",
    re.IGNORECASE,
)

# Relative date: "after 2 weeks", "in 3 months", "next 10 days"
_RELATIVE_DATE_RE = re.compile(
    r"\b(?:after|in|within|next)\s+(\d+)\s+(days?|weeks?|months?|years?)\b",
    re.IGNORECASE,
)

# Follow-up instruction: "F/U after 2 weeks", "Review on 15/07/2025"
_FOLLOW_UP_RE = re.compile(
    r"\b(?:follow[\s\-]?up|F/?U|review|revisit|come\s+back|next\s+visit)\s*"
    r"(?:after|on|in|@|:)?\s*"
    r"(?:(\d+)\s*(days?|weeks?|months?)|(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}))",
    re.IGNORECASE,
)

_MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


class MedicalDateParser:
    """
    Robust date parser for Indian medical prescriptions and lab reports.

    Handles:
    - DD/MM/YYYY, MM-DD-YYYY, YYYY-MM-DD (numeric)
    - "12 June 2025", "12th June 2025", "June 12, 2025" (written)
    - Relative: "after 2 weeks", "in 3 months"
    - Follow-up dates
    - Ambiguous year (e.g., "25" → 2025)
    """

    def __init__(self, reference_date: Optional[date] = None) -> None:
        """
        Args:
            reference_date: The date to resolve relative dates against.
                            Defaults to today.
        """
        self.reference_date = reference_date or date.today()

    def __repr__(self) -> str:
        return f"MedicalDateParser(reference_date={self.reference_date})"

    def health_check(self) -> dict:
        """Return status of the date parser."""
        return {
            "dateutil_available": _DATEUTIL_AVAILABLE,
            "reference_date": str(self.reference_date),
        }

    # ─── Public API ──────────────────────────────────────────────────────────

    def normalize_date(self, date_text: str) -> Optional[str]:
        """
        Convert any date text to ISO 8601 format (YYYY-MM-DD).

        Tries parsers in order of specificity:
        1. Written date (e.g., "12 June 2025")
        2. Numeric date (DD/MM/YYYY first, then MM/DD/YYYY)
        3. dateutil fallback (dayfirst=True for Indian format)

        Args:
            date_text: Raw date string from OCR/NLP.

        Returns:
            ISO 8601 date string (e.g., "2025-06-12"), or None if unparseable.
        """
        if not date_text:
            return None

        date_text = date_text.strip()

        # Try written format first (most unambiguous)
        result = self._parse_written_date(date_text)
        if result:
            return result.isoformat()

        # Try numeric format (DD/MM/YYYY preferred for Indian records)
        result = self._parse_numeric_date(date_text)
        if result:
            return result.isoformat()

        # Try dateutil as fallback
        if _DATEUTIL_AVAILABLE:
            try:
                parsed = dateutil_parser.parse(date_text, dayfirst=True, fuzzy=True)
                return parsed.date().isoformat()
            except (ValueError, OverflowError):
                pass

        logger.debug("Could not parse date: '%s'", date_text)
        return None

    def extract_all_dates(self, text: str) -> List[Dict]:
        """
        Extract all date strings from a body of text.

        Args:
            text: Input text from OCR.

        Returns:
            List of dicts: {text, start, end, normalized, confidence}
        """
        found: List[Dict] = []
        covered: List[Tuple[int, int]] = []

        # Find written dates
        for m in _WRITTEN_DATE_RE.finditer(text):
            span = m.span()
            if not _overlaps(span, covered):
                normalized = self.normalize_date(m.group(0))
                if normalized:
                    found.append({
                        "text": m.group(0),
                        "start": span[0],
                        "end": span[1],
                        "type": "DATE",
                        "normalized": normalized,
                        "confidence": 0.95,
                        "source": "rule",
                    })
                    covered.append(span)

        # Find numeric dates
        for m in _NUMERIC_DATE_RE.finditer(text):
            span = m.span()
            if not _overlaps(span, covered):
                normalized = self.normalize_date(m.group(0))
                if normalized:
                    found.append({
                        "text": m.group(0),
                        "start": span[0],
                        "end": span[1],
                        "type": "DATE",
                        "normalized": normalized,
                        "confidence": 0.85,
                        "source": "rule",
                    })
                    covered.append(span)

        return sorted(found, key=lambda x: x["start"])

    def extract_follow_up_date(self, text: str) -> Optional[str]:
        """
        Find a follow-up date instruction and return a resolved ISO date.

        Handles:
        - "Follow up after 2 weeks" → today + 14 days
        - "Review on 15/07/2025"   → "2025-07-15"
        - "F/U in 3 months"        → today + 3 months

        Args:
            text: OCR text from prescription.

        Returns:
            ISO 8601 date string or None.
        """
        for m in _FOLLOW_UP_RE.finditer(text):
            count_str = m.group(1)
            unit = m.group(2)
            explicit_date = m.group(3)

            if explicit_date:
                return self.normalize_date(explicit_date)

            if count_str and unit:
                count = int(count_str)
                unit_lower = unit.lower().rstrip("s")
                return self._resolve_relative(count, unit_lower)

        return None

    def resolve_relative_date(self, relative_text: str) -> Optional[str]:
        """
        Resolve a relative date expression to an ISO date.

        Args:
            relative_text: e.g., "after 2 weeks", "in 3 months"

        Returns:
            ISO 8601 date string or None.
        """
        m = _RELATIVE_DATE_RE.search(relative_text)
        if m:
            count = int(m.group(1))
            unit = m.group(2).lower().rstrip("s")
            return self._resolve_relative(count, unit)
        return None

    # ─── Private parsers ─────────────────────────────────────────────────────

    def _parse_written_date(self, text: str) -> Optional[date]:
        """Parse a written date like '12 June 2025' or 'June 12, 2025'."""
        m = _WRITTEN_DATE_RE.search(text)
        if not m:
            return None

        groups = m.groups()
        # Format 1: DD Month YYYY (groups 0-2)
        if groups[0] is not None:
            try:
                day = int(groups[0])
                month = _MONTH_MAP.get(groups[1].lower()[:3])
                year = self._normalize_year(int(groups[2]))
                if month:
                    return date(year, month, day)
            except (ValueError, TypeError):
                pass

        # Format 2: Month DD YYYY (groups 3-5)
        if groups[3] is not None:
            try:
                month = _MONTH_MAP.get(groups[3].lower()[:3])
                day = int(groups[4])
                year = self._normalize_year(int(groups[5]))
                if month:
                    return date(year, month, day)
            except (ValueError, TypeError):
                pass

        return None

    def _parse_numeric_date(self, text: str) -> Optional[date]:
        """
        Parse a numeric date (DD/MM/YYYY or YYYY-MM-DD).

        Prefers DD/MM/YYYY (Indian format). Tries YYYY-MM-DD for ISO dates.
        """
        m = _NUMERIC_DATE_RE.search(text)
        if not m:
            return None

        groups = m.groups()

        # Format: DD/MM/YYYY (groups 0-2)
        if groups[0] is not None:
            p1, p2, p3 = int(groups[0]), int(groups[1]), int(groups[2])

            # Detect ISO format (YYYY/MM/DD would have p1 > 31)
            if p1 > 31:
                # Likely YYYY/MM/DD
                return self._safe_date(p1, p2, p3)

            # Try DD/MM/YYYY
            year = self._normalize_year(p3)
            result = self._safe_date(year, p2, p1)
            if result:
                return result

            # Fallback: try MM/DD/YYYY
            return self._safe_date(year, p1, p2)

        # Format: YYYY/MM/DD (groups 3-5)
        if groups[3] is not None:
            year = int(groups[3])
            month = int(groups[4])
            day = int(groups[5])
            return self._safe_date(year, month, day)

        return None

    def _resolve_relative(self, count: int, unit: str) -> Optional[str]:
        """
        Compute a future date from today + (count × unit).

        Args:
            count: Number of units.
            unit:  'day', 'week', 'month', or 'year'.

        Returns:
            ISO date string.
        """
        if not _DATEUTIL_AVAILABLE:
            # Simple fallback using timedelta for days/weeks
            if unit == "day":
                return (self.reference_date + timedelta(days=count)).isoformat()
            elif unit == "week":
                return (self.reference_date + timedelta(weeks=count)).isoformat()
            return None

        delta_kwargs = {f"{unit}s": count}
        try:
            future = self.reference_date + relativedelta(**delta_kwargs)
            return future.isoformat()
        except Exception:
            return None

    def _normalize_year(self, year: int) -> int:
        """Expand 2-digit years: 00-49 → 2000-2049, 50-99 → 1950-1999."""
        if year < 100:
            return 2000 + year if year < 50 else 1900 + year
        return year

    def _safe_date(self, year: int, month: int, day: int) -> Optional[date]:
        """Construct a date, returning None on invalid values."""
        try:
            return date(year, month, day)
        except ValueError:
            return None


def _overlaps(span: Tuple[int, int], covered: List[Tuple[int, int]]) -> bool:
    """Return True if span overlaps with any covered span."""
    for s, e in covered:
        if span[0] < e and span[1] > s:
            return True
    return False


# ─── Module-level convenience functions ──────────────────────────────────────

_parser: Optional[MedicalDateParser] = None


def get_date_parser() -> MedicalDateParser:
    """Return (or create) the module-level MedicalDateParser singleton."""
    global _parser
    if _parser is None:
        _parser = MedicalDateParser()
    return _parser


def normalize_date(date_text: str) -> Optional[str]:
    """Convenience wrapper: normalize a single date string to ISO format."""
    return get_date_parser().normalize_date(date_text)


def extract_dates(text: str) -> List[Dict]:
    """Convenience wrapper: extract all dates from a text body."""
    return get_date_parser().extract_all_dates(text)
