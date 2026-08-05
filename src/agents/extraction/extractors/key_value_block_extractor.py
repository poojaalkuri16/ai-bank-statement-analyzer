"""
key_value_block_extractor.py
=============================
Extracts a Transaction from a key-value style transaction block.

Handles multiple KV formats:

Format A — inline label+value:
    Txn Date: 16/05/2024
    Particulars: SPOTIFY PREMIUM
    Amount: 199.00 DR
    Balance: 45678.12

Format B — split label / value (label on one line, value on next):
    Txn Date
    : 2024-08-02
    : INDIAN OIL FUEL STATION
    Amount
    : -1,354.33 (Dr)
    Balance
    : ₹37,585.82

Format C — mixed (some inline, some split):
    Txn Date : 16/05/2024
    Particulars
    : SPOTIFY PREMIUM
    Amount : 199.00 DR

The extractor uses a field-state machine that tracks which field is
being collected.  KV value lines (starting with ":" or "- ") are
automatically attributed to the most recently started field.

Design
------
- No bank-specific logic.
- Handles any label wording that maps to date/description/amount/balance.
- Strips leading ":" or "-" prefixes from value lines before parsing.
- Never replaces a parse failure with zero.
"""
from __future__ import annotations

import re
from decimal import Decimal

from src.agents.extraction.shared.amount_normalizer import parse_amount
from src.agents.extraction.shared.date_parser import parse_date
from src.schemas.transaction import Transaction

# Credit keyword heuristic
_CREDIT_KEYWORDS = (
    "SALARY", "CREDIT", "REFUND", "INTEREST",
    "CASH DEPOSIT", "NEFT INWARD", "IMPS INWARD", "RTGS INWARD",
    "REVERSAL", "CASHBACK",
)

# Boilerplate guard — these lines must never become descriptions
_BOILERPLATE_RE = re.compile(
    r"statement of account|statement continued|page \d+ of \d+"
    r"|customer name|opening balance|closing balance"
    r"|this is a system generated|generated statement"
    r"|authorised signatory|branch name|account number"
    r"|ifsc|micr|swift",
    re.IGNORECASE,
)

# A KV value line starts with ":" or "-" (optionally with spaces)
_KV_VALUE_PREFIX = re.compile(r"^[ \t]*[:\-][ \t]*")

# ---------------------------------------------------------------------------
# Label → field-name mapping
# Maps every common label variant to a canonical field name.
# Checked longest-match first so "Txn Date" fires before "Date".
# ---------------------------------------------------------------------------
_LABEL_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^(?:Txn[ \t]+Date|Transaction[ \t]+Date|Value[ \t]+Date|Posting[ \t]+Date)[ \t]*[:\-]?$", re.IGNORECASE), "date"),
    (re.compile(r"^(?:Txn[ \t]+Date|Transaction[ \t]+Date|Value[ \t]+Date|Posting[ \t]+Date)[ \t]*[:\-][ \t]*(.+)$", re.IGNORECASE), "date"),
    (re.compile(r"^Date[ \t]*[:\-]?$", re.IGNORECASE), "date"),
    (re.compile(r"^Date[ \t]*[:\-][ \t]*(.+)$", re.IGNORECASE), "date"),
    (re.compile(r"^Particulars?[ \t]*[:\-]?$", re.IGNORECASE), "description"),
    (re.compile(r"^Particulars?[ \t]*[:\-][ \t]*(.+)$", re.IGNORECASE), "description"),
    (re.compile(r"^(?:Description|Narration|Remarks|Details|Merchant)[ \t]*[:\-]?$", re.IGNORECASE), "description"),
    (re.compile(r"^(?:Description|Narration|Remarks|Details|Merchant)[ \t]*[:\-][ \t]*(.+)$", re.IGNORECASE), "description"),
    (re.compile(r"^Amount[ \t]*[:\-]?$", re.IGNORECASE), "amount"),
    (re.compile(r"^Amount[ \t]*[:\-][ \t]*(.+)$", re.IGNORECASE), "amount"),
    (re.compile(r"^(?:Withdrawal|Deposit|Debit|Credit|Transaction[ \t]+Amount)[ \t]*[:\-]?$", re.IGNORECASE), "amount"),
    (re.compile(r"^(?:Withdrawal|Deposit|Debit|Credit|Transaction[ \t]+Amount)[ \t]*[:\-][ \t]*(.+)$", re.IGNORECASE), "amount"),
    (re.compile(r"^(?:Balance|Running[ \t]+Balance|Closing[ \t]+Balance|Available[ \t]+Balance)[ \t]*[:\-]?$", re.IGNORECASE), "balance"),
    (re.compile(r"^(?:Balance|Running[ \t]+Balance|Closing[ \t]+Balance|Available[ \t]+Balance)[ \t]*[:\-][ \t]*(.+)$", re.IGNORECASE), "balance"),
]


def _match_label(line: str) -> tuple[str | None, str]:
    """
    If *line* starts with a recognised field label, return
    (field_name, inline_value).  Otherwise return (None, "").

    inline_value is the text after the colon/dash on the same line,
    or "" when the label is bare (value expected on next line).
    """
    for pattern, field in _LABEL_MAP:
        m = pattern.match(line)
        if m:
            # Capture group 1 holds the inline value when present
            inline = m.group(1).strip() if m.lastindex and m.group(1) else ""
            return field, inline
    return None, ""


def _strip_kv_prefix(text: str) -> str:
    """Remove leading ': ' or '- ' prefix from a KV value line."""
    return _KV_VALUE_PREFIX.sub("", text).strip()


def _to_decimal(raw: str | None) -> tuple[Decimal | None, str | None]:
    """Convert *raw* to (positive Decimal, txn_type | None) via parse_amount."""
    if not raw:
        return None, None
    # Strip leading KV prefix if present
    cleaned = _strip_kv_prefix(raw).replace(",", "")
    return parse_amount(cleaned)


class KeyValueBlockExtractor:
    """
    Parses a key-value transaction block into a Transaction object.

    Works with both inline-value and split-label formats.
    Generalises to any KV layout without bank-specific assumptions.
    """

    def can_handle(self, block: str) -> bool:
        """
        True when the block contains at least one recognised field label
        AND either a date or monetary value that suggests it's a transaction.
        """
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        has_label   = False
        has_date    = False
        has_money   = False

        _money_re = re.compile(r"\b\d[\d,]*\.\d{2}\b")

        for ln in lines:
            field, _ = _match_label(ln)
            if field:
                has_label = True
                if field == "date":
                    has_date = True
            if parse_date(ln) or parse_date(_strip_kv_prefix(ln)):
                has_date = True
            if _money_re.search(ln):
                has_money = True

        return has_label and (has_date or has_money)

    def extract(self, block: str) -> Transaction:  # noqa: C901
        """
        Extract fields using a field-state-machine that attributes every
        value line to the most recently started field.
        """
        current_field: str | None = None

        date_val:      object = None
        desc_parts:    list[str] = []
        amount_raw:    str | None = None
        balance_raw:   str | None = None

        for raw_line in block.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()

            if not stripped:
                continue

            # Skip boilerplate lines
            if _BOILERPLATE_RE.search(stripped):
                continue

            # ── Try to match a field label ────────────────────────────────
            field, inline_value = _match_label(stripped)

            if field is not None:
                current_field = field

                if inline_value:
                    # Label and value on the same line
                    self._assign(
                        field, inline_value,
                        date_val=date_val,
                        desc_parts=desc_parts,
                        amount_raw=amount_raw,
                        balance_raw=balance_raw,
                    )
                    date_val, desc_parts, amount_raw, balance_raw = \
                        self._update(field, inline_value, date_val, desc_parts, amount_raw, balance_raw)
                continue

            # ── KV value line (starts with ":" or "-") ────────────────────
            if _KV_VALUE_PREFIX.match(line):
                value = _strip_kv_prefix(stripped)
                if current_field and value:
                    # Remember state BEFORE update for the balance-fallback check
                    amount_was_set_before = (amount_raw is not None)

                    date_val, desc_parts, amount_raw, balance_raw = \
                        self._update(current_field, value, date_val, desc_parts, amount_raw, balance_raw)

                    # After consuming a date value, switch to description
                    # collection so subsequent KV lines become description.
                    # Union Bank pattern:
                    #   Txn Date → : date_value → : description_value
                    if current_field == "date" and date_val is not None:
                        current_field = "description"

                    # When amount was ALREADY set before this line and the
                    # current field is still "amount", a subsequent KV money
                    # line is the balance (Balance label suppressed by
                    # boilerplate filter).
                    elif (
                        current_field == "amount"
                        and amount_was_set_before
                        and balance_raw is None
                    ):
                        from src.agents.extraction.shared.amount_normalizer import (
                            parse_amount as _pa,
                        )
                        _parsed, _ = _pa(value.replace(",", ""))
                        if _parsed is not None:
                            balance_raw = value
                continue

            # ── Plain continuation line ───────────────────────────────────
            # Could be a multi-line description or a value without a prefix.
            if current_field == "description":
                # Only add if it looks like a narration (not a number)
                if not _is_pure_money(stripped) and not _BOILERPLATE_RE.search(stripped):
                    desc_parts.append(stripped)
            elif current_field == "date" and date_val is None:
                d = parse_date(stripped)
                if d:
                    date_val = d
            elif current_field == "amount" and amount_raw is None:
                amount_raw = stripped
            elif current_field == "balance" and balance_raw is None:
                balance_raw = stripped

        # ── Build description ─────────────────────────────────────────────
        description = " ".join(p for p in desc_parts if p).strip()

        # ── Parse amount and balance ──────────────────────────────────────
        amount_val, txn_type = _to_decimal(amount_raw)
        balance_val, _       = _to_decimal(balance_raw)

        # ── Determine transaction type ────────────────────────────────────
        if txn_type is None:
            upper = (description or "").upper()
            txn_type = "CREDIT" if any(kw in upper for kw in _CREDIT_KEYWORDS) else "DEBIT"

        confidence = 0.9 if (date_val and description and amount_val) else \
                     0.6 if (date_val and amount_val) else 0.3

        return Transaction(
            transaction_date=date_val,
            description=description or "",
            amount=amount_val,
            balance=balance_val,
            transaction_type=txn_type,
            confidence=confidence,
            reasoning="Parsed using key-value block extractor.",
            source_text=block,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _update(
        field: str,
        value: str,
        date_val,
        desc_parts: list,
        amount_raw,
        balance_raw,
    ) -> tuple:
        """Apply *value* to *field*, returning updated state tuple."""
        if field == "date" and date_val is None:
            d = parse_date(value)
            if d:
                date_val = d
        elif field == "description":
            if value and not _is_pure_money(value) and not _BOILERPLATE_RE.search(value):
                desc_parts.append(value)
        elif field == "amount" and amount_raw is None:
            amount_raw = value
        elif field == "balance" and balance_raw is None:
            balance_raw = value
        return date_val, desc_parts, amount_raw, balance_raw

    @staticmethod
    def _assign(*args, **kwargs):
        pass  # compatibility shim — actual logic in _update


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_PURE_MONEY_RE = re.compile(
    r"^[-₹]?\s*\d[\d,]*\.?\d*"
    r"(?:\s*\(?\s*(?:DR|CR|Dr|Cr|Debit|Credit)\s*\)?)?\s*$",
    re.IGNORECASE,
)


def _is_pure_money(text: str) -> bool:
    """True when *text* is only a monetary value with no other content."""
    return bool(_PURE_MONEY_RE.match(text.strip()))
