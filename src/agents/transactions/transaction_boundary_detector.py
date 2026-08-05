"""
transaction_boundary_detector.py
==================================
Uses a StartPattern to split a clean region-text string into an
ordered list of raw transaction blocks.

Design
------
The algorithm is intentionally simple:

    For each non-empty line in the region:
        If the line matches pattern.is_start → flush the current block,
                                               start a new one.
        Otherwise → append to the current block.

This single rule correctly handles:
    - wrapped descriptions  (continuation lines are part of the same block)
    - multi-line narrations (never split mid-transaction)
    - 3-column tables       (debit / credit / balance all in one block)
    - key-value blocks      (all label lines stay together)
    - same-line records     (each line is its own block because each
                             line IS a full anchor)
    - blank lines between transactions (skipped)
    - page breaks           (headers already removed before this stage)

The algorithm does NOT:
    - look for amounts to decide boundaries
    - look at column positions
    - count lines
    - hardcode any field names

Post-filtering
--------------
After splitting, blocks that contain no monetary value are discarded
(they are artefacts — e.g. residual header lines that slipped through
boilerplate removal).
"""
from __future__ import annotations

import re

from src.agents.transactions.transaction_start_detector import StartPattern


_MONEY_RE = re.compile(r"\b\d[\d,]*\.\d{2}\b")


class TransactionBoundaryDetector:
    """
    Splits a region text into transaction blocks using a StartPattern.
    """

    def split(
        self,
        region_text: str,
        pattern: StartPattern,
    ) -> list[str]:
        """
        Split *region_text* into transaction blocks.

        Parameters
        ----------
        region_text : the cleaned transaction region (no headers, no footers)
        pattern     : the detected start pattern from TransactionStartDetector

        Returns
        -------
        Ordered list of raw transaction block strings.  Each string
        contains all text belonging to exactly one transaction.
        """
        blocks:  list[str]  = []
        current: list[str]  = []

        for raw_line in region_text.splitlines():
            line = raw_line.rstrip()   # preserve leading whitespace (indent)

            # Skip completely blank lines — they carry no information
            if not line.strip():
                continue

            if pattern.is_start(line):
                # Flush the previous block before starting a new one
                self._flush(current, blocks)
                current = [line]
            else:
                current.append(line)

        # Flush the final block
        self._flush(current, blocks)

        # Post-filter: discard blocks with no monetary value
        # (residual header/footer lines that bypassed boilerplate removal)
        filtered = [b for b in blocks if _MONEY_RE.search(b)]

        return filtered

    @staticmethod
    def _flush(current: list[str], blocks: list[str]) -> None:
        """Append the current accumulated lines as one block if non-empty."""
        text = "\n".join(current).strip()
        if text:
            blocks.append(text)
