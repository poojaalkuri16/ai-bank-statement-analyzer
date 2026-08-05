"""
date_parser.py
==============
Centralised date parsing for the extraction engine.

All extractors import from here so date format support is added in
exactly one place.

Supported formats
-----------------
  DD/MM/YYYY      01/05/2024
  DD-MM-YYYY      01-05-2024
  YYYY-MM-DD      2024-05-01
  DD/MM/YY        01/05/24
  DD-MM-YY        01-05-24
  DD MMM YYYY     01 May 2024   (case-insensitive month abbreviation)
  DD MMM YY       01 May 24
  MMM DD YYYY     May 01 2024
  MM/DD/YYYY      05/01/2024    (US style — tried last to avoid ambiguity)

Design note
-----------
All patterns are tried in order of specificity: 4-digit year formats
before 2-digit, named-month before numeric, unambiguous before
ambiguous.  When a date is ambiguous (e.g. 01/05/24 could be
DD/MM/YY or MM/DD/YY) we prefer the DD/MM/YY interpretation because
Indian bank statements are always DD/MM format.
"""
from __future__ import annotations

import re
from datetime import date, datetime


# ---------------------------------------------------------------------------
# Month name lookup (English abbreviations and full names)
# ---------------------------------------------------------------------------

_MONTH_NAMES: dict[str, int] = {
    "jan": 1,  "january": 1,
    "feb": 2,  "february": 2,
    "mar": 3,  "march": 3,
    "apr": 4,  "april": 4,
    "may": 5,
    "jun": 6,  "june": 6,
    "jul": 7,  "july": 7,
    "aug": 8,  "august": 8,
    "sep": 9,  "september": 9,  "sept": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_MONTH_RE = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"

# ---------------------------------------------------------------------------
# Date pattern table
# (format_key, regex, parse_function)
# ---------------------------------------------------------------------------

def _parse_dmy4(m: re.Match) -> date | None:
    """DD/MM/YYYY or DD-MM-YYYY"""
    try:
        return date(int(m.group("y")), int(m.group("mo")), int(m.group("d")))
    except ValueError:
        return None


def _parse_ymd(m: re.Match) -> date | None:
    """YYYY-MM-DD"""
    try:
        return date(int(m.group("y")), int(m.group("mo")), int(m.group("d")))
    except ValueError:
        return None


def _parse_dmy2(m: re.Match) -> date | None:
    """DD/MM/YY or DD-MM-YY — 2-digit year, pivot at 2000"""
    try:
        yy = int(m.group("y"))
        yyyy = 2000 + yy if yy <= 99 else yy
        return date(yyyy, int(m.group("mo")), int(m.group("d")))
    except ValueError:
        return None


def _parse_named_month(m: re.Match) -> date | None:
    """DD MMM YYYY or DD MMM YY"""
    try:
        mon = _MONTH_NAMES.get(m.group("mon").lower())
        if mon is None:
            return None
        yy = int(m.group("y"))
        yyyy = 2000 + yy if yy < 100 else yy
        return date(yyyy, mon, int(m.group("d")))
    except ValueError:
        return None


def _parse_named_month_us(m: re.Match) -> date | None:
    """MMM DD YYYY"""
    try:
        mon = _MONTH_NAMES.get(m.group("mon").lower())
        if mon is None:
            return None
        return date(int(m.group("y")), mon, int(m.group("d")))
    except ValueError:
        return None


_DATE_PATTERNS: list[tuple[str, re.Pattern, object]] = [
    # 4-digit year, unambiguous formats first
    (
        "DD/MM/YYYY",
        re.compile(r"\b(?P<d>\d{2})/(?P<mo>\d{2})/(?P<y>\d{4})\b"),
        _parse_dmy4,
    ),
    (
        "DD-MM-YYYY",
        re.compile(r"\b(?P<d>\d{2})-(?P<mo>\d{2})-(?P<y>\d{4})\b"),
        _parse_dmy4,
    ),
    (
        "YYYY-MM-DD",
        re.compile(r"\b(?P<y>\d{4})-(?P<mo>\d{2})-(?P<d>\d{2})\b"),
        _parse_ymd,
    ),
    # Named month — unambiguous
    (
        "DD MMM YYYY",
        re.compile(
            r"\b(?P<d>\d{1,2})\s+(?P<mon>" + _MONTH_RE + r")\s+(?P<y>\d{4})\b",
            re.IGNORECASE,
        ),
        _parse_named_month,
    ),
    (
        "MMM DD YYYY",
        re.compile(
            r"\b(?P<mon>" + _MONTH_RE + r")\s+(?P<d>\d{1,2}),?\s+(?P<y>\d{4})\b",
            re.IGNORECASE,
        ),
        _parse_named_month_us,
    ),
    # Named month with 2-digit year
    (
        "DD MMM YY",
        re.compile(
            r"\b(?P<d>\d{1,2})\s+(?P<mon>" + _MONTH_RE + r")\s+(?P<y>\d{2})\b",
            re.IGNORECASE,
        ),
        _parse_named_month,
    ),
    # 2-digit year — try after named-month to avoid false positives
    (
        "DD/MM/YY",
        re.compile(r"\b(?P<d>\d{2})/(?P<mo>\d{2})/(?P<y>\d{2})\b"),
        _parse_dmy2,
    ),
    (
        "DD-MM-YY",
        re.compile(r"\b(?P<d>\d{2})-(?P<mo>\d{2})-(?P<y>\d{2})\b"),
        _parse_dmy2,
    ),
]

# Flat list of (pattern, parser) for fast scanning
_PATTERNS_ONLY: list[tuple[re.Pattern, object]] = [
    (pat, fn) for _, pat, fn in _DATE_PATTERNS
]

# Format keys that LayoutAnalyzer can reference
DATE_FORMAT_KEYS: list[str] = [fmt for fmt, _, _ in _DATE_PATTERNS]


def parse_date(text: str) -> date | None:
    """
    Try every supported date pattern against *text*.
    Return the first successfully parsed date, or None.
    """
    for pattern, fn in _PATTERNS_ONLY:
        m = pattern.search(text)
        if m:
            result = fn(m)
            if result is not None:
                return result
    return None


def extract_date_from_line(line: str) -> date | None:
    """
    Return the first valid date found anywhere in *line*, or None.
    Alias for parse_date — kept for clarity at call sites.
    """
    return parse_date(line)


def is_date_line(line: str) -> bool:
    """
    Return True when *line* consists entirely (or almost entirely) of a
    date string with no other meaningful content.
    """
    stripped = line.strip()
    for pattern, fn in _PATTERNS_ONLY:
        m = pattern.fullmatch(stripped)
        if m and fn(m) is not None:
            return True
    # Also accept lines where the date is the only non-whitespace content
    for pattern, fn in _PATTERNS_ONLY:
        m = pattern.search(stripped)
        if m:
            remainder = stripped[: m.start()].strip() + stripped[m.end() :].strip()
            if not remainder:
                return True
    return False


def detect_date_formats(text: str) -> list[str]:
    """
    Return a list of format keys whose patterns appear anywhere in *text*.
    Used by LayoutAnalyzer to populate DocumentProfile.date_formats.
    """
    found = []
    for fmt, pattern, fn in _DATE_PATTERNS:
        if pattern.search(text):
            found.append(fmt)
    return found
