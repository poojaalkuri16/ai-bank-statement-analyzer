"""
amount_normalizer.py
====================
Converts raw amount strings from bank statements into a canonical
(positive Decimal, transaction_type) pair.

Bank statements use many conventions for debits and credits:

    -1354.33          negative number  → (1354.33, DEBIT)
    1354.33 DR        inline suffix    → (1354.33, DEBIT)
    1354.33 (Dr)      parenthesised    → (1354.33, DEBIT)
    ₹1354.33 (Dr)     with currency    → (1354.33, DEBIT)
    1354.33 Debit     word suffix      → (1354.33, DEBIT)
    78096.46 (Cr)     parenthesised    → (78096.46, CREDIT)
    599.60 CR         inline suffix    → (599.60, CREDIT)
    599.60 Credit     word suffix      → (599.60, CREDIT)

Rejection rules
---------------
A monetary value in a bank statement ALWAYS contains a decimal point
(paise / paisa component).  Strings without a decimal point are treated
as identifiers — account numbers, reference numbers, phone numbers,
IFSC codes, etc. — and are rejected.

The only exception is the literal "0" (and variants like "0.0"),
which is used as an empty-column placeholder in 3-column statements
(Debit | Credit | Balance) and is accepted explicitly.

Examples of values that must be rejected:
    38491027561000   → account number  → (None, None)
    1800425380       → phone number    → (None, None)
    SBIN0011452      → IFSC code       → (None, None)
    100              → bare integer    → (None, None)

Examples of values that must be accepted:
    1354.33          → (1354.33, None)
    1354.33 DR       → (1354.33, DEBIT)
    0                → (0,       None)   ← column placeholder only
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


_DR_RE = re.compile(
    r"\b(?:DR|DEBIT)\b|\(DR\)|\(Dr\)",
    re.IGNORECASE,
)
_CR_RE = re.compile(
    r"\b(?:CR|CREDIT)\b|\(CR\)|\(Cr\)",
    re.IGNORECASE,
)

# Strips currency symbols, commas and whitespace before numeric parsing
_STRIP_RE = re.compile(r"[₹,\s]")

# Matches an optional sign followed by a numeric body that MUST contain
# a decimal point.  This deliberately rejects bare integers.
_MONETARY_RE = re.compile(r"^(-?)(\d[\d]*\.\d+)$")

# The zero placeholder used in 3-column statements
_ZERO_RE = re.compile(r"^0+\.?0*$")


def parse_amount(raw: str) -> tuple[Decimal | None, str | None]:
    """
    Parse *raw* into (positive_decimal, transaction_type).

    Returns (None, None) if *raw* cannot be recognised as a monetary value.

    transaction_type is "DEBIT", "CREDIT", or None.
    When None the caller must infer the type from other context
    (column position, description keywords, etc.).
    """
    text = raw.strip()
    if not text:
        return None, None

    has_dr = bool(_DR_RE.search(text))
    has_cr = bool(_CR_RE.search(text))

    # Strip currency symbol, commas, and whitespace
    clean = _STRIP_RE.sub("", text)
    # Remove parentheses and any remaining alphabetic suffix/prefix
    clean = re.sub(r"[()a-zA-Z₹]", "", clean).strip()

    if not clean:
        return None, None

    # Accept the zero placeholder explicitly before the decimal-point check
    if _ZERO_RE.match(clean):
        txn_type = None
        if has_dr:
            txn_type = "DEBIT"
        elif has_cr:
            txn_type = "CREDIT"
        return Decimal("0"), txn_type

    # Require a decimal point — rejects account numbers, phone numbers, etc.
    if "." not in clean:
        return None, None

    m = _MONETARY_RE.match(clean)
    if not m:
        return None, None

    is_negative = m.group(1) == "-"
    numeric_str = m.group(1) + m.group(2)

    try:
        value = Decimal(numeric_str)
    except InvalidOperation:
        return None, None

    positive_value = abs(value)

    if has_dr or is_negative:
        txn_type = "DEBIT"
    elif has_cr:
        txn_type = "CREDIT"
    else:
        txn_type = None

    return positive_value, txn_type
