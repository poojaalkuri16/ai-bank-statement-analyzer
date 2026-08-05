"""
layout_analyzer.py
==================
Analyses the structure of a raw bank statement text and produces a
DocumentProfile describing the layout so downstream components know
how to segment and extract transactions.

Design principle
----------------
Detection is purely structural — it never uses bank names as signals
for layout decisions.  Bank name detection is kept for informational
purposes only (populating profile.bank_name) and has no effect on
layout routing.

Layout types
------------
table        Lines of the form:  Date  Description  Amount  Balance
             The date is alone on its own line OR at the start of a
             fixed-width row.

block        Key-value pairs:    Txn Date: …  Particulars: …  Amount: …

same_line    All fields on one line, tab- or space-separated.

mixed        Document contains both table and block patterns.

unknown      Could not detect a reliable structure; best-effort
             extraction will be attempted.
"""
import re

from src.agents.extraction.shared.date_parser import detect_date_formats
from src.schemas.document_profile import DocumentProfile


class LayoutAnalyzer:
    """
    Performs structural analysis of a financial document.

    Does NOT extract transactions; only produces a DocumentProfile.
    """

    # Bank name detection — informational only, no routing effect
    BANK_PATTERNS = {
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

    # -----------------------------------------------------------------------
    # Column header words that appear in table-layout statements.
    # Any two or more of these alongside DATE and BALANCE → table layout.
    # -----------------------------------------------------------------------
    _TABLE_DESCRIPTION_VARIANTS = frozenset([
        "DESCRIPTION",
        "PARTICULARS",
        "NARRATION",
        "DETAILS",
        "REMARKS",
        "TRANSACTION DETAILS",
        "TRANSACTION NARRATION",
    ])

    _TABLE_AMOUNT_VARIANTS = frozenset([
        "AMOUNT",
        "DEBIT",
        "CREDIT",
        "WITHDRAWAL",
        "WITHDRAWALS",
        "DEPOSIT",
        "DEPOSITS",
        "DR",
        "CR",
    ])

    # -----------------------------------------------------------------------
    # Label words found in key-value (block) layouts.
    # -----------------------------------------------------------------------
    _BLOCK_DATE_LABELS = frozenset([
        "TXN DATE",
        "TRANSACTION DATE",
        "VALUE DATE",
        "POSTING DATE",
        "DATE",
    ])

    _BLOCK_DESC_LABELS = frozenset([
        "PARTICULARS",
        "PARTICULAR",
        "DESCRIPTION",
        "NARRATION",
        "DETAILS",
        "REMARKS",
    ])

    def analyze(self, raw_text: str, page_count: int = 1) -> DocumentProfile:

        profile = DocumentProfile()
        profile.page_count = page_count
        upper = raw_text.upper()

        # ----------------------------------------------------------------
        # Bank name (informational only)
        # ----------------------------------------------------------------
        for bank, patterns in self.BANK_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, upper):
                    profile.bank_name = bank
                    break
            if profile.bank_name:
                break

        # ----------------------------------------------------------------
        # Document type
        # ----------------------------------------------------------------
        if "STATEMENT" in upper and "ACCOUNT" in upper:
            profile.document_type = "bank_statement"

        # ----------------------------------------------------------------
        # Table header detection
        # Must contain: DATE + BALANCE + at least one description variant
        #               OR DATE + BALANCE + at least one amount variant
        #
        # We check that the column headers appear as standalone words
        # (not embedded in key-value label lines like "Txn Date: ...").
        # A simple heuristic: if there are MORE colon-lines than non-colon
        # lines containing DATE, the document is likely block-style, not
        # table-style.
        # ----------------------------------------------------------------
        has_date_col    = bool(re.search(r"\bDATE\b", upper))
        has_balance_col = bool(re.search(r"\bBALANCE\b", upper))
        has_desc_col    = any(
            bool(re.search(r"\b" + re.escape(v) + r"\b", upper))
            for v in self._TABLE_DESCRIPTION_VARIANTS
        )
        has_amount_col  = any(
            bool(re.search(r"\b" + re.escape(v) + r"\b", upper))
            for v in self._TABLE_AMOUNT_VARIANTS
        )

        # Count lines that contain DATE as a label (e.g. "Date : ...")
        # vs. lines that contain DATE as a standalone column header token
        date_label_lines = sum(
            1 for ln in upper.splitlines()
            if re.search(r"\bDATE\s*:", ln)
        )
        date_column_lines = sum(
            1 for ln in upper.splitlines()
            if re.search(r"\bDATE\b", ln) and not re.search(r"\bDATE\s*:", ln)
        )

        # Only set table headers when DATE appears as a column name more
        # often than as a KV label — prevents KV blocks from being
        # misclassified as tables.
        if (
            has_date_col
            and has_balance_col
            and (has_desc_col or has_amount_col)
            and date_column_lines >= date_label_lines
        ):
            profile.has_table_headers = True

        # ----------------------------------------------------------------
        # Block / label-based detection
        # Must contain: a date label + a description label + AMOUNT
        # ----------------------------------------------------------------
        has_date_label = any(lbl in upper for lbl in self._BLOCK_DATE_LABELS)
        has_desc_label = any(lbl in upper for lbl in self._BLOCK_DESC_LABELS)
        has_amount_kw  = "AMOUNT" in upper

        if has_date_label and has_desc_label and has_amount_kw:
            profile.has_labeled_fields = True

        # ----------------------------------------------------------------
        # Same-line detection
        # A date immediately followed on the same line by non-date content
        # and a monetary value  →  same_line layout.
        # We look for: <date>  <non-numeric text>  <amount>  [<balance>]
        # ----------------------------------------------------------------
        _same_line_re = re.compile(
            r"\b\d{2}[/\-]\d{2}[/\-]\d{2,4}\b"   # date
            r".{3,60}"                              # description
            r"\b\d[\d,]*\.\d{2}\b",               # amount
        )
        profile.has_inline_dates = bool(_same_line_re.search(raw_text))

        # ----------------------------------------------------------------
        # Layout type
        # ----------------------------------------------------------------
        if profile.has_table_headers and profile.has_labeled_fields:
            profile.layout_type = "mixed"
        elif profile.has_table_headers:
            if profile.has_inline_dates:
                profile.layout_type = "same_line"
            else:
                profile.layout_type = "table"
        elif profile.has_labeled_fields:
            profile.layout_type = "block"
        elif profile.has_inline_dates:
            profile.layout_type = "same_line"
        else:
            profile.layout_type = "unknown"

        # ----------------------------------------------------------------
        # Running balance
        # ----------------------------------------------------------------
        if "BALANCE" in upper:
            profile.has_running_balance = True

        # ----------------------------------------------------------------
        # Currency
        # ----------------------------------------------------------------
        if "₹" in raw_text or "RS." in upper or "INR" in upper:
            profile.currency = "INR"

        # ----------------------------------------------------------------
        # Date formats — delegate to shared parser
        # ----------------------------------------------------------------
        profile.date_formats = detect_date_formats(raw_text)

        # ----------------------------------------------------------------
        # Amount style
        # ----------------------------------------------------------------
        has_dr       = bool(re.search(r"\bDR\b|\(DR\)", upper))
        has_cr       = bool(re.search(r"\bCR\b|\(CR\)", upper))
        has_negative = bool(re.search(r"-\s*\d", raw_text))

        if (has_dr or has_cr) and has_negative:
            profile.amount_style = "mixed"
        elif has_dr or has_cr:
            profile.amount_style = "inline_dr_cr"
        elif has_negative:
            profile.amount_style = "negative_numbers"
        else:
            profile.amount_style = "unknown"

        # ----------------------------------------------------------------
        # Multiline narrations
        # ----------------------------------------------------------------
        profile.multiline_descriptions = bool(
            re.search(r"\n[A-Z][A-Z\s/&\-]{3,}\n", upper)
        )

        # ----------------------------------------------------------------
        # Confidence score — does NOT penalise unknown banks
        # ----------------------------------------------------------------
        score = 0.0
        if profile.document_type:
            score += 0.25
        if profile.layout_type not in ("unknown", None):
            score += 0.25
        if profile.currency:
            score += 0.15
        if profile.date_formats:
            score += 0.20
        if profile.has_running_balance:
            score += 0.15

        profile.confidence = round(min(score, 1.0), 2)

        return profile
