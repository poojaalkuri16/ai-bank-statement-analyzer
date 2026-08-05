"""
transaction_start_detector.py
==============================
Discovers the recurring anchor pattern that marks the START of each
transaction in a bank statement region.

The detector scores every candidate pattern by counting how many lines
match AND are confirmed by a nearby monetary value.  The highest-scoring
candidate is used.  No bank names or hardcoded layouts are required.

Supported anchor types
----------------------
kv_date_inline  "Txn Date: 2024-08-02"          — label+value on same line
kv_date_bare    "Txn Date"                       — label alone (value next line)
date_label      "Date: 02/08/2024"               — generic date label
date_only       "01/05/2024"                     — bare date on its own line
date_start      "01/05/2024  UPI PAYMENT 1000.00" — date starts a same-line record
serial_number   "1. PAYMENT"                      — sequence number
txn_id          "TXN001", "REF/2024/001"          — transaction reference
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from src.agents.extraction.shared.date_parser import (
    extract_date_from_line,
    is_date_line,
)


# ---------------------------------------------------------------------------
_MONEY_RE      = re.compile(r"\b\d[\d,]*\.\d{2}\b")
_DATE_RANGE_RE = re.compile(r"\b(?:to|thru|through|till|until)\b", re.IGNORECASE)
_KV_VALUE_RE   = re.compile(r"^[ \t]*[:\-][ \t]*\S")


# ---------------------------------------------------------------------------
# StartPattern
# ---------------------------------------------------------------------------

@dataclass
class StartPattern:
    kind:        str
    is_start:    Callable[[str], bool]
    description: str

    def __str__(self) -> str:
        return f"{self.kind}: {self.description}"


# ---------------------------------------------------------------------------
# Individual anchor testers
# ---------------------------------------------------------------------------

_KV_DATE_INLINE_RE = re.compile(
    r"^[ \t]*(?:Txn[ \t]+Date|Transaction[ \t]+Date"
    r"|Value[ \t]+Date|Posting[ \t]+Date)[ \t]*[:\-][ \t]*\S",
    re.IGNORECASE,
)

_KV_DATE_BARE_RE = re.compile(
    r"^[ \t]*(?:Txn[ \t]+Date|Transaction[ \t]+Date"
    r"|Value[ \t]+Date|Posting[ \t]+Date)[ \t]*$",
    re.IGNORECASE,
)

_PLAIN_DATE_LABEL_RE = re.compile(
    r"^[ \t]*Date[ \t]*[:\-][ \t]*\S",
    re.IGNORECASE,
)

_SERIAL_RE = re.compile(r"^(?:S(?:r)?\.?\s*No\.?\s*)?\d{1,4}[.)]\s+\S")

_TXN_ID_RE = re.compile(
    r"^(?:TXN|TRN|REF|NEFT|IMPS|UPI|RTGS)[/\-\s]*\d",
    re.IGNORECASE,
)


def _is_kv_date_inline(line: str) -> bool:
    return bool(_KV_DATE_INLINE_RE.match(line))


def _is_kv_date_bare(line: str) -> bool:
    """
    True when the line is a bare KV date label with no value.
    e.g. "Txn Date" — value appears on the next line as ": 2024-08-02"
    """
    return bool(_KV_DATE_BARE_RE.match(line))


def _is_plain_date_label(line: str) -> bool:
    return bool(_PLAIN_DATE_LABEL_RE.match(line))


def _is_date_only(line: str) -> bool:
    """True when the entire line is a single date — no other content."""
    stripped = line.strip()
    if _DATE_RANGE_RE.search(stripped):   # reject date ranges
        return False
    return is_date_line(stripped)


def _is_date_start(line: str) -> bool:
    """
    True when a line STARTS with a date and has additional content
    (handles same-line records: "01/05/2024  PAYMENT  1000.00  9000.00").

    Explicitly rejects:
    - date-range lines  ("01/05/2024 to 31/05/2024")
    - bare date lines   (those are handled by _is_date_only)
    """
    stripped = line.strip()
    if _DATE_RANGE_RE.search(stripped):
        return False
    if is_date_line(stripped):     # bare date → let date_only handle it
        return False
    return extract_date_from_line(stripped) is not None


def _is_serial(line: str) -> bool:
    return bool(_SERIAL_RE.match(line.strip()))


def _is_txn_id(line: str) -> bool:
    return bool(_TXN_ID_RE.match(line.strip()))


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class TransactionStartDetector:
    """
    Scores every candidate anchor pattern against the region lines and
    returns the one that most reliably marks transaction starts.
    """

    _CANDIDATES: list[tuple[str, Callable, str]] = [
        ("kv_date_inline",  _is_kv_date_inline,  "Txn Date: <value> on same line"),
        ("kv_date_bare",    _is_kv_date_bare,     "Txn Date label alone (value on next line)"),
        ("date_label",      _is_plain_date_label, "Date: label at line start"),
        ("date_only",       _is_date_only,        "Bare date on its own line"),
        ("date_start",      _is_date_start,       "Date at start of same-line record"),
        ("serial_number",   _is_serial,           "Serial / sequence number"),
        ("txn_id",          _is_txn_id,           "Transaction / reference ID"),
    ]

    def detect(self, region_lines: list[str]) -> StartPattern:
        """
        Return the highest-scoring StartPattern for *region_lines*.

        Scoring: a line scores +1 when it matches the candidate AND
        a monetary value appears on the same line or within the next 6.
        """
        non_empty = [ln for ln in region_lines if ln.strip()]

        best_kind  = "date_start"
        best_fn    = _is_date_start
        best_desc  = "Date at start of line (fallback)"
        best_score = 0

        for kind, test_fn, description in self._CANDIDATES:
            score = self._score_candidate(non_empty, test_fn)
            if score > best_score:
                best_score = score
                best_fn    = test_fn
                best_desc  = description
                best_kind  = kind

        return StartPattern(kind=best_kind, is_start=best_fn, description=best_desc)

    @staticmethod
    def _score_candidate(lines: list[str], test_fn: Callable) -> int:
        score = 0
        for i, line in enumerate(lines):
            if not test_fn(line):
                continue
            if _MONEY_RE.search(line):      # same-line money (same-line records)
                score += 1
                continue
            window = lines[i + 1 : min(i + 7, len(lines))]
            if any(_MONEY_RE.search(wl) for wl in window):
                score += 1
        return score
