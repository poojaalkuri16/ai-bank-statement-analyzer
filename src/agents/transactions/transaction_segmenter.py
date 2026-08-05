"""
transaction_segmenter.py
========================
Orchestrates the transaction segmentation pipeline.

Pipeline (this module only — no field extraction occurs here)
--------------------------------------------------------------
  DocumentProfile.transaction_region_text   (clean region text)
           ↓
  Boilerplate strip          (_strip_boilerplate)
           ↓
  TransactionStartDetector   (discovers recurring anchor pattern)
           ↓
  TransactionBoundaryDetector (splits on anchor → raw blocks)
           ↓
  list[str]                  (ordered transaction blocks)

Design principles
-----------------
- No bank-specific logic.
- No hardcoded field names or column positions.
- No layout-specific strategies (table/block/same_line/mixed).
  The new anchor-based approach works uniformly across all layouts
  because it discovers the start pattern from the data rather than
  assuming it.
- Wrapped descriptions are handled automatically: continuation lines
  are part of the same block because they do not match the start
  pattern.
- Page breaks are handled by DocumentUnderstandingEngine (repeated
  headers removed before we receive the region text).

Backward compatibility
----------------------
The public segment(raw_text, profile) signature is preserved so all
existing callers (DocumentAgent, tests) continue to work unchanged.
"""
from __future__ import annotations

import re

from src.agents.transactions.transaction_start_detector import (
    TransactionStartDetector,
)
from src.agents.transactions.transaction_boundary_detector import (
    TransactionBoundaryDetector,
)
from src.schemas.document_profile import DocumentProfile


# ---------------------------------------------------------------------------
# Boilerplate suppression
# Lines matching this pattern are removed before segmentation so they
# never appear inside transaction blocks.
# ---------------------------------------------------------------------------

_BOILERPLATE_RE = re.compile(
    r"statement of account"
    r"|statement continued"
    r"|page \d+\s+of\s+\d+"
    r"|customer\s+name"
    r"|opening\s+balance"
    r"|closing\s+balance"
    r"|this is a (system|computer) generated"
    r"|generated statement"
    r"|authorised\s+signatory"
    r"|branch\s+name"
    r"|account\s+number"
    r"|ifsc\s*(?:code)?"
    r"|micr\s*(?:code)?"
    r"|swift\s*(?:code)?"
    r"|a/c\s*no"
    r"|acc(?:ount)?\s*no"
    r"|mobile\s*(?:no|number)"
    r"|email\s*(?:id|address)?"
    r"|nominee"
    r"|pan\s*(?:no|number|card)"
    r"|cif\s*(?:no|number)?"
    r"|rs\.\s*\d"
    r"|inr\s*\d"
    r"|date\s+description\s+debit"
    r"|date\s+description\s+credit"
    r"|date\s+particulars"
    r"|date\s+narration"
    r"|txn\s+date\s+value"
    # Standalone column-header words that leak from page-break headers.
    # These are checked as whole-line matches (no other content on the line).
    r"|^description$"
    r"|^particulars$"
    r"|^narration$"
    r"|^debit$"
    r"|^credit$"
    r"|^withdrawals?$"
    r"|^deposits?$"
    r"|^running\s+balance"
    r"|^balance$"
    r"|^date$",
    re.IGNORECASE | re.MULTILINE,
)


def _strip_boilerplate(text: str) -> str:
    """Remove every boilerplate line from *text*."""
    result = []
    for ln in text.splitlines():
        # Check against stripped line so ^ and $ anchors match correctly
        if not _BOILERPLATE_RE.search(ln.strip()):
            result.append(ln)
    return "\n".join(result)


# ---------------------------------------------------------------------------
# Segmenter
# ---------------------------------------------------------------------------

class TransactionSegmenter:
    """
    Splits a bank statement's transaction region into individual blocks.

    Each block contains the raw text for exactly one transaction.
    No parsing, extraction, or validation is performed here.
    """

    def __init__(self) -> None:
        self._start_detector    = TransactionStartDetector()
        self._boundary_detector = TransactionBoundaryDetector()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def segment(
        self,
        raw_text: str,
        profile: DocumentProfile,
    ) -> list[str]:
        """
        Segment the document into transaction blocks.

        Parameters
        ----------
        raw_text : full raw PDF text (used only as fallback when
                   profile.transaction_region_text is not set)
        profile  : populated DocumentProfile from DocumentUnderstandingEngine

        Returns
        -------
        Ordered list of transaction block strings.
        """
        # ── Step 1: obtain the clean transaction region text ──────────────
        #
        # DocumentUnderstandingEngine pre-slices the region and stores it
        # in profile.transaction_region_text.  Use it directly to avoid
        # any index-space mismatch.
        #
        # If not set (legacy path / unit tests with a bare DocumentProfile),
        # fall back to using the full raw text after stripping repeated
        # headers.

        if profile.transaction_region_text is not None:
            region_text = profile.transaction_region_text
        else:
            repeated    = profile.repeated_header_lines or set()
            region_lines = [
                ln for ln in raw_text.splitlines()
                if ln.strip() not in repeated
            ]
            region_text = "\n".join(region_lines)

        # ── Step 2: remove structural boilerplate lines ──────────────────
        clean = _strip_boilerplate(region_text)

        # ── Step 2b: strip any remaining repeated page-header lines ───────
        # These are lines the DocumentUnderstandingEngine identified as
        # page headers/footers.  They may survive into the region text if
        # they appear mid-document at page-break positions.
        # This step is generic — it uses the profile's own detected set,
        # not any bank-specific patterns.
        repeated = profile.repeated_header_lines or set()
        if repeated:
            clean = "\n".join(
                ln for ln in clean.splitlines()
                if ln.strip() not in repeated
            )

        # ── Step 3: discover the transaction start pattern ────────────────
        region_lines = [ln for ln in clean.splitlines() if ln.strip()]
        start_pattern = self._start_detector.detect(region_lines)

        # Store for debug output (accessed by DocumentAgent)
        self._last_start_pattern = start_pattern

        # ── Step 4: split on the pattern → transaction blocks ─────────────
        blocks = self._boundary_detector.split(clean, start_pattern)

        return blocks

    # ------------------------------------------------------------------
    # Debug helpers
    # ------------------------------------------------------------------

    @property
    def last_start_pattern(self):
        """The StartPattern used in the most recent segment() call."""
        return getattr(self, "_last_start_pattern", None)
