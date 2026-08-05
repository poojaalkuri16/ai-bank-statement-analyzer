"""
document_understanding_engine.py
=================================
Analyses the raw text of a bank statement and produces a
DocumentProfile describing its structure.

Design principles
-----------------
- Never uses bank names to make routing decisions.
- No hardcoded column names, field labels, or PDF layouts.
- Every decision is based on structural analysis of the document itself.
- Warns explicitly when the transaction region cannot be detected with
  confidence rather than silently degrading.

Pipeline
--------
1.  Detect repeated page headers/footers by POSITIONAL analysis
    (lines that appear at the TOP of every page-chunk), not frequency.
2.  Strip those headers/footers from the clean line list.
3.  Detect the transaction region using structural signals.
4.  Extract the region text and store it in DocumentProfile.
5.  Classify the layout from the region text.
6.  Populate all remaining profile fields.
"""
from __future__ import annotations

import re
import warnings
from collections import Counter

from src.agents.extraction.shared.date_parser import (
    detect_date_formats,
    extract_date_from_line,
    is_date_line,
)
from src.schemas.document_profile import DocumentProfile


# ---------------------------------------------------------------------------
# Structural signal sets — used for layout classification and region
# detection.  These are GENERIC column-header words present in many
# different bank statement formats; they are not bank-specific.
# ---------------------------------------------------------------------------

_TABLE_DESC_VARIANTS: frozenset[str] = frozenset([
    "DESCRIPTION", "PARTICULARS", "NARRATION",
    "DETAILS", "REMARKS",
])

_TABLE_AMOUNT_VARIANTS: frozenset[str] = frozenset([
    "AMOUNT", "DEBIT", "CREDIT",
    "WITHDRAWAL", "WITHDRAWALS", "DEPOSIT", "DEPOSITS",
    "DR", "CR",
])

_BLOCK_DATE_LABELS: frozenset[str] = frozenset([
    "TXN DATE", "TRANSACTION DATE", "VALUE DATE", "POSTING DATE", "DATE",
])

_BLOCK_DESC_LABELS: frozenset[str] = frozenset([
    "PARTICULARS", "PARTICULAR", "DESCRIPTION", "NARRATION", "DETAILS",
])

# Lines whose content strongly signals the END of the transaction region
_REGION_END_SIGNALS = re.compile(
    r"closing\s+balance"
    r"|total\s+debit"
    r"|total\s+credit"
    r"|net\s+balance"
    r"|summary\s+of\s+transactions"
    r"|transaction\s+summary"
    r"|disclaimer"
    r"|this\s+is\s+a\s+(?:computer|system)\s+generated"
    r"|authorised\s+signatory"
    r"|for\s+any\s+queries",
    re.IGNORECASE,
)

# A date range line like "01/05/2024 to 31/05/2024" — NOT a transaction start
_DATE_RANGE_RE = re.compile(
    r"\b(?:to|thru|through|till|until)\b", re.IGNORECASE
)

# Monetary value with a decimal point
_MONEY_RE = re.compile(r"\b\d[\d,]*\.\d{2}\b")

# A KV value line — starts with ": " or "- " (optionally indented)
_KV_VALUE_RE = re.compile(r"^[ \t]*[:\-][ \t]*\S")

# Inline same-line layout signal
_SAME_LINE_RE = re.compile(
    r"\b\d{2}[/\-]\d{2}[/\-]\d{2,4}\b.{3,60}\b\d[\d,]*\.\d{2}\b"
)

# How many lines from the top of each page-chunk to consider as the
# potential header zone.
_HEADER_ZONE_LINES = 8

# Bank name patterns — for informational annotation only.
# Never used for routing decisions.
_BANK_PATTERNS: dict[str, list[str]] = {
    "State Bank of India":  [r"STATE\s+BANK\s+OF\s+INDIA", r"\bSBI\b"],
    "Canara Bank":          [r"CANARA\s+BANK"],
    "Union Bank of India":  [r"UNION\s+BANK\s+OF\s+INDIA"],
    "ICICI Bank":           [r"ICICI\s+BANK"],
    "HDFC Bank":            [r"HDFC\s+BANK"],
    "Axis Bank":            [r"AXIS\s+BANK"],
    "Kotak Mahindra Bank":  [r"KOTAK"],
    "Punjab National Bank": [r"PUNJAB\s+NATIONAL\s+BANK", r"\bPNB\b"],
    "Bank of Baroda":       [r"BANK\s+OF\s+BARODA", r"\bBOB\b"],
    "Indian Bank":          [r"INDIAN\s+BANK"],
    "Bank of India":        [r"BANK\s+OF\s+INDIA"],
    "Yes Bank":             [r"YES\s+BANK"],
    "IndusInd Bank":        [r"INDUSIND"],
    "Federal Bank":         [r"FEDERAL\s+BANK"],
    "South Indian Bank":    [r"SOUTH\s+INDIAN\s+BANK"],
}


class DocumentUnderstandingEngine:
    """
    Structural analysis engine for bank statement text.

    Produces a DocumentProfile with:
    - transaction_region_text : clean text of the transaction section only
    - repeated_header_lines   : suppressed page-header strings
    - layout_type             : structural classification
    - date_formats, currency, amount_style, confidence
    """

    def analyze(self, raw_text: str, page_count: int = 1) -> DocumentProfile:

        profile            = DocumentProfile()
        profile.page_count = page_count

        all_lines = raw_text.splitlines()

        # ── Step 1: detect positional page headers/footers ────────────────
        profile.repeated_header_lines = self._detect_page_headers(
            all_lines, page_count
        )

        # ── Step 2: build clean line list ─────────────────────────────────
        clean_lines = [
            ln for ln in all_lines
            if ln.strip() not in profile.repeated_header_lines
        ]
        clean_text = "\n".join(clean_lines)
        upper      = clean_text.upper()

        # ── Step 3: bank name (informational only) ─────────────────────────
        profile.bank_name = self._detect_bank_name(upper)

        # ── Step 4: document type ──────────────────────────────────────────
        if "STATEMENT" in upper and "ACCOUNT" in upper:
            profile.document_type = "bank_statement"

        # ── Step 5: transaction region detection ───────────────────────────
        start_idx, end_idx, method = self._detect_transaction_region(clean_lines)

        if start_idx is None:
            warnings.warn(
                "DocumentUnderstandingEngine: transaction region could not "
                "be detected with confidence. The full document will be used "
                "as a fallback — segmentation quality may be reduced.\n"
                "Hint: ensure the document contains recognisable transaction "
                "anchors (date lines, 'Txn Date:' labels, column headers).",
                stacklevel=2,
            )

        profile.transaction_region_start = start_idx
        profile.transaction_region_end   = end_idx

        # ── Step 6: extract region text ───────────────────────────────────
        if start_idx is not None:
            region_lines = clean_lines[
                start_idx : (end_idx + 1 if end_idx is not None else None)
            ]
        else:
            region_lines = clean_lines   # fallback only — warned above

        region_text  = "\n".join(region_lines)
        region_upper = region_text.upper()

        # Store pre-sliced region so segmenter uses it directly
        profile.transaction_region_text = region_text

        # ── Step 7: layout classification ─────────────────────────────────
        profile.layout_type        = self._classify_layout(region_text, region_upper)
        profile.has_table_headers  = self._has_table_headers(region_upper)
        profile.has_labeled_fields = self._has_labeled_fields(region_upper)
        profile.has_inline_dates   = bool(_SAME_LINE_RE.search(region_text))

        # ── Step 8: metadata ───────────────────────────────────────────────
        profile.date_formats           = detect_date_formats(clean_text)
        profile.currency               = self._detect_currency(clean_text, upper)
        profile.amount_style           = self._detect_amount_style(
            region_upper, region_text
        )
        profile.has_running_balance    = "BALANCE" in region_upper
        profile.multiline_descriptions = bool(
            re.search(r"\n[A-Z][A-Z\s/&\-]{3,}\n", region_upper)
        )

        # ── Step 9: confidence ─────────────────────────────────────────────
        profile.confidence = self._score_confidence(profile)

        return profile

    # -----------------------------------------------------------------------
    # Step 1 — Positional page-header detection
    # -----------------------------------------------------------------------

    def _detect_page_headers(
        self,
        all_lines: list[str],
        page_count: int,
    ) -> set:
        """
        Identify recurring page headers and footers using POSITIONAL
        analysis rather than global frequency.

        A page header/footer is a line that appears in the header zone
        (top _HEADER_ZONE_LINES non-empty lines) of EVERY page-chunk.

        This correctly handles:
        - "ICICI BANK" appearing at the top of every page → suppressed
        - "UPI/BESCOM/ELECBILL" appearing twice in the body → NOT suppressed

        For single-page documents we use conservative boilerplate patterns
        only (no frequency analysis).

        Additional structural boilerplate is always removed regardless of
        page count.
        """
        stripped  = [ln.strip() for ln in all_lines]
        non_empty = [ln for ln in stripped if ln]

        suppressed: set[str] = set()

        # ── Always-suppress structural boilerplate ────────────────────────
        # These lines are definitionally not transactions regardless of
        # how many times they appear or where.
        _structural = re.compile(
            r"^statement of account$"
            r"|^statement of transactions$"
            r"|^statement continued$"
            r"|^account statement$"
            r"|^transaction details$"
            r"|^page \d+\s+of\s+\d+$"
            r"|^running balance"
            r"|^opening balance"
            r"|^closing balance"
            r"|^this is a (?:system|computer) generated"
            r"|^authorised signatory"
            r"|^for any queries",
            re.IGNORECASE,
        )
        for ln in non_empty:
            if _structural.match(ln):
                suppressed.add(ln)

        # ── Positional detection for multi-page documents ─────────────────
        if page_count >= 2:
            # Strategy: find positions where structural boilerplate lines
            # appear in the text (page breaks, "Statement of Account", etc.).
            # Lines that appear in a small window AROUND those positions
            # and are not transaction data are page headers/footers.
            #
            # This is more robust than equal-size chunking because it
            # finds actual page-break positions rather than assuming them.

            # Step A: find indices of structural anchor lines
            _structural_anchor = re.compile(
                r"^statement of account"
                r"|^page \d+\s+of\s+\d+"
                r"|^running balance"
                r"|^this is a (?:system|computer) generated",
                re.IGNORECASE,
            )
            anchor_indices = [
                i for i, ln in enumerate(non_empty)
                if _structural_anchor.match(ln)
            ]

            # Step B: collect lines within _HEADER_ZONE_LINES of each anchor
            candidate_lines: set[str] = set()
            for idx in anchor_indices:
                start = max(0, idx - _HEADER_ZONE_LINES)
                end   = min(len(non_empty), idx + _HEADER_ZONE_LINES + 1)
                for ln in non_empty[start:end]:
                    candidate_lines.add(ln)

            # Also collect the top _HEADER_ZONE_LINES lines of the document
            # (the document header is always at the very top)
            for ln in non_empty[:_HEADER_ZONE_LINES]:
                candidate_lines.add(ln)

            # Step C: a candidate becomes a header if it:
            # - is not transaction data (date, money, KV value/label)
            # - appears at least twice in the whole document
            #   (a true page header repeats; one-off content doesn't)
            line_counts = Counter(non_empty)
            for line in candidate_lines:
                if self._is_transaction_data(line):
                    continue
                if line_counts[line] >= 2:
                    suppressed.add(line)
                elif len(anchor_indices) == 0 and line_counts[line] == 1:
                    # Single-page-break document: accept once-occurring lines
                    # near structural anchors
                    suppressed.add(line)

        return suppressed

    @staticmethod
    def _is_transaction_data(line: str) -> bool:
        """
        True when *line* is likely transaction data that must never be
        suppressed, regardless of how often or where it appears.

        A line is transaction data when it:
        - contains a monetary value (with decimal point), OR
        - is a pure date line, OR
        - starts with a KV value marker (": " or "- "), OR
        - is a bare KV field LABEL (Txn Date, Particulars, Amount, etc.), OR
        - looks like a transaction narration/description (UPI/, NEFT, ATM,
          merchant names, etc.) — these are never page headers.
        """
        if _MONEY_RE.search(line):
            return True
        if is_date_line(line.strip()):
            return True
        if _KV_VALUE_RE.match(line):
            return True
        # KV field label lines — appear once per transaction in block layouts
        _kv_label = re.compile(
            r"^[ \t]*(?:Txn[ \t]+Date|Transaction[ \t]+Date|Value[ \t]+Date"
            r"|Posting[ \t]+Date|Date|Particulars?|Amount|Balance"
            r"|Narration|Description|Details|Remarks)[ \t]*$",
            re.IGNORECASE,
        )
        if _kv_label.match(line):
            return True
        # Transaction narration patterns — payment references, merchant names.
        # These lines appear in the body of the statement and are never headers.
        # We check for common payment method prefixes and mixed case/slash
        # patterns that are characteristic of transaction descriptions.
        # Also protect any ALL-CAPS text line that looks like a merchant name
        # (contains at least 2 words of capital letters).
        _narration = re.compile(
            r"^(?:UPI|NEFT|IMPS|RTGS|ATM|POS|ECS|ACH|NACH)[/\s\-]"
            r"|^(?:SALARY|REFUND|INTEREST|CASHBACK|TRANSFER)\s"
            r"|/",   # any line containing "/" is likely a payment ref
            re.IGNORECASE,
        )
        if _narration.match(line.strip()):
            return True
        # Protect lines that are clearly merchant/narration descriptions:
        # all-uppercase words with spaces (e.g. "MAKEMYTRIP FLIGHT BOOKING",
        # "REDBUS TICKET BOOKING").  These are never page headers.
        _merchant_desc = re.compile(r"^[A-Z][A-Z\s\-/&]{5,}$")
        if _merchant_desc.match(line.strip()):
            return True
        return False

    # -----------------------------------------------------------------------
    # Step 5 — Transaction region detection
    # -----------------------------------------------------------------------

    def _detect_transaction_region(
        self,
        clean_lines: list[str],
    ) -> tuple[int | None, int | None, str]:
        """
        Locate the line-index range of the transaction history section.

        Heuristics (tried in priority order)
        ─────────────────────────────────────
        H1. Table column-header row containing DATE + a description/amount
            variant on the same line.  Transactions start on the next line.

        H2. KV date label (inline): "Txn Date: 2024-08-02" on one line.

        H3. KV date label (split-line): "Txn Date" alone on a line,
            followed by a ": value" line.

        H4. First bare date-only line (not a date range) that has a
            monetary value within the next 6 lines.

        End detection
        ─────────────
        E1. A line matching REGION_END_SIGNALS after the start.
        E2. Last line in the document containing a date or money value.
        """
        start_idx: int | None = None
        end_idx:   int | None = None
        method:    str        = "none"

        upper_lines = [ln.upper() for ln in clean_lines]

        # ── H1: table column-header row ───────────────────────────────────
        for i, ln_up in enumerate(upper_lines):
            if (
                "DATE" in ln_up
                and any(v in ln_up for v in _TABLE_DESC_VARIANTS | _TABLE_AMOUNT_VARIANTS)
                and ":" not in ln_up
                and not _KV_VALUE_RE.match(clean_lines[i])
            ):
                if i + 1 < len(clean_lines):
                    start_idx = i + 1
                    method    = "H1:table_header"
                break

        # ── H2: KV date label inline ──────────────────────────────────────
        if start_idx is None:
            _kv_inline = re.compile(
                r"^[ \t]*(?:Txn[ \t]+Date|Transaction[ \t]+Date"
                r"|Value[ \t]+Date|Posting[ \t]+Date)[ \t]*[:\-][ \t]*\S",
                re.IGNORECASE,
            )
            for i, ln in enumerate(clean_lines):
                if _kv_inline.match(ln):
                    start_idx = i
                    method    = "H2:kv_date_inline"
                    break

        # ── H3: KV date label split-line ──────────────────────────────────
        if start_idx is None:
            _kv_bare = re.compile(
                r"^[ \t]*(?:Txn[ \t]+Date|Transaction[ \t]+Date"
                r"|Value[ \t]+Date|Posting[ \t]+Date)[ \t]*$",
                re.IGNORECASE,
            )
            for i, ln in enumerate(clean_lines[:-1]):
                if _kv_bare.match(ln):
                    for j in range(i + 1, min(i + 4, len(clean_lines))):
                        if clean_lines[j].strip():
                            if _KV_VALUE_RE.match(clean_lines[j]):
                                start_idx = i
                                method    = "H3:kv_date_split"
                            break
                if start_idx is not None:
                    break

        # ── H4: first bare date followed by money ─────────────────────────
        if start_idx is None:
            for i, ln in enumerate(clean_lines):
                s = ln.strip()
                if not is_date_line(s):
                    continue
                if _DATE_RANGE_RE.search(s):   # reject "01/05 to 31/05"
                    continue
                window = clean_lines[i : min(i + 6, len(clean_lines))]
                if any(_MONEY_RE.search(wl) for wl in window):
                    start_idx = i
                    method    = "H4:first_date_with_money"
                    break

        if start_idx is None:
            return None, None, "none"

        # ── Find end ──────────────────────────────────────────────────────
        for i in range(start_idx + 1, len(clean_lines)):
            if _REGION_END_SIGNALS.search(clean_lines[i]):
                end_idx = i - 1
                break

        if end_idx is None:
            last = start_idx
            for i in range(start_idx, len(clean_lines)):
                if (extract_date_from_line(clean_lines[i].strip())
                        or _MONEY_RE.search(clean_lines[i])):
                    last = i
            end_idx = last

        return start_idx, end_idx, method

    # -----------------------------------------------------------------------
    # Step 7 — Layout classification
    # -----------------------------------------------------------------------

    def _classify_layout(self, region_text: str, region_upper: str) -> str:
        has_table = self._has_table_headers(region_upper)
        has_block = self._has_labeled_fields(region_upper)

        date_only_count   = 0
        date_inline_count = 0

        for ln in region_text.splitlines():
            s = ln.strip()
            if not s:
                continue
            if is_date_line(s) and not _DATE_RANGE_RE.search(s):
                date_only_count += 1
            elif extract_date_from_line(s) and _MONEY_RE.search(s):
                date_inline_count += 1

        if has_table and has_block:
            return "mixed"
        if has_table:
            return "same_line" if date_inline_count > date_only_count else "table"
        if has_block:
            return "block"
        if date_inline_count > 0:
            return "same_line"
        if date_only_count > 0:
            return "table"
        return "unknown"

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _has_table_headers(self, region_upper: str) -> bool:
        has_date    = bool(re.search(r"\bDATE\b", region_upper))
        has_balance = bool(re.search(r"\bBALANCE\b", region_upper))
        has_desc    = any(
            bool(re.search(r"\b" + re.escape(v) + r"\b", region_upper))
            for v in _TABLE_DESC_VARIANTS
        )
        has_amt = any(
            bool(re.search(r"\b" + re.escape(v) + r"\b", region_upper))
            for v in _TABLE_AMOUNT_VARIANTS
        )
        if not (has_date and has_balance and (has_desc or has_amt)):
            return False
        date_label = sum(
            1 for ln in region_upper.splitlines()
            if re.search(r"\bDATE\s*:", ln)
        )
        date_col = sum(
            1 for ln in region_upper.splitlines()
            if re.search(r"\bDATE\b", ln) and not re.search(r"\bDATE\s*:", ln)
        )
        return date_col >= date_label

    def _has_labeled_fields(self, region_upper: str) -> bool:
        has_date_lbl = any(lbl in region_upper for lbl in _BLOCK_DATE_LABELS)
        has_desc_lbl = any(lbl in region_upper for lbl in _BLOCK_DESC_LABELS)
        return has_date_lbl and has_desc_lbl and "AMOUNT" in region_upper

    @staticmethod
    def _detect_bank_name(upper: str) -> str | None:
        for bank, patterns in _BANK_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, upper):
                    return bank
        return None

    @staticmethod
    def _detect_currency(raw_text: str, upper: str) -> str | None:
        if "₹" in raw_text or "RS." in upper or "INR" in upper:
            return "INR"
        if "$" in raw_text or "USD" in upper:
            return "USD"
        if "£" in raw_text or "GBP" in upper:
            return "GBP"
        return None

    @staticmethod
    def _detect_amount_style(region_upper: str, region_text: str) -> str:
        has_dr       = bool(re.search(r"\bDR\b|\(DR\)", region_upper))
        has_cr       = bool(re.search(r"\bCR\b|\(CR\)", region_upper))
        has_negative = bool(re.search(r"-\s*\d", region_text))
        if (has_dr or has_cr) and has_negative:
            return "mixed"
        if has_dr or has_cr:
            return "inline_dr_cr"
        if has_negative:
            return "negative_numbers"
        return "plain"

    @staticmethod
    def _score_confidence(profile: DocumentProfile) -> float:
        score = 0.0
        if profile.document_type:
            score += 0.20
        if profile.transaction_region_start is not None:
            score += 0.30
        if profile.layout_type not in ("unknown", None):
            score += 0.20
        if profile.currency:
            score += 0.15
        if profile.date_formats:
            score += 0.15
        return round(min(score, 1.0), 2)
