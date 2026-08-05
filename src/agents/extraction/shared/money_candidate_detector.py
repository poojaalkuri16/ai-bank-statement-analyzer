"""
money_candidate_detector.py
===========================
Detects monetary values inside a transaction block.

Does NOT determine what each value represents — that is the job of
AmountExtractor and BalanceExtractor.

Date-fragment exclusion
-----------------------
Date strings like "01/05/2024" contain digit sequences that look
like money candidates.  Without exclusion, the component numbers
("01", "05", "2024") end up as candidates and corrupt amount
extraction when no labelled lines are present.

Fix: any line that contains a recognisable date pattern is skipped
entirely.  Numbers on the same line as a date are not money values.

Mixed-line exclusion
--------------------
Lines that contain both significant text (letters) and a bare integer
(no decimal point) are description lines with embedded reference
numbers — e.g. "UPI REF 12345678" or "TXN ID 987654321".
Such lines are skipped so that reference numbers never become amount
candidates.  A money line contains only the numeric value (plus
optional currency symbol or DR/CR marker) and nothing else.
"""
import re
from decimal import Decimal

from src.agents.extraction.shared.date_parser import extract_date_from_line
from src.schemas.extraction_candidate import ExtractionCandidate

# A line is a pure-money line when it consists solely of an optional
# currency prefix, digits/commas, an optional decimal part, and an
# optional DR/CR suffix — with no unrelated alphabetic text.
_PURE_MONEY_LINE_RE = re.compile(
    r"^\s*[-₹]?\s*\d[\d,]*(?:\.\d+)?"
    r"(?:\s*\(?\s*(?:DR|CR|Dr|Cr|Debit|Credit)\s*\)?)?\s*$",
    re.IGNORECASE,
)

# The original money-value pattern — used on lines already confirmed to
# be pure-money.
_MONEY_PATTERN = re.compile(r"[-₹]?\s*\d[\d,]*\.?\d*")


class MoneyCandidateDetector:
    """
    Detects monetary values inside a transaction block, skipping:

    1. Lines that contain a recognisable date (date-fragment exclusion).
    2. Lines that mix text with a bare integer (reference-number exclusion).

    Only lines that look like pure monetary values are scanned.
    """

    MONEY_PATTERN = _MONEY_PATTERN   # kept for backward compatibility

    def detect(
        self,
        transaction_block: str,
    ) -> list[ExtractionCandidate]:

        candidates = []

        for line_number, line in enumerate(
            transaction_block.splitlines(),
            start=1,
        ):
            stripped = line.strip()

            # 1. Skip date lines entirely
            if extract_date_from_line(stripped):
                continue

            # 2. Skip lines that are not pure-money lines
            #    (text mixed with integers = reference numbers in descriptions)
            if not _PURE_MONEY_LINE_RE.match(stripped):
                continue

            for match in _MONEY_PATTERN.finditer(line):

                raw = match.group().strip()

                cleaned = (
                    raw.replace("₹", "")
                    .replace(",", "")
                    .strip()
                )

                if cleaned in ("", "-", "."):
                    continue

                try:
                    value = Decimal(cleaned)
                except Exception:
                    continue

                candidates.append(
                    ExtractionCandidate(
                        value=value,
                        raw_text=raw,
                        line_number=line_number,
                    )
                )

        return candidates
