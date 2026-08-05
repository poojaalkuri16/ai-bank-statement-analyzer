"""
formatters.py
=============
Shared presentation utilities for the QA layer.

Contents
--------
fmt_inr(amount)          — Indian rupee formatting with lakh/crore separators
fmt_date(d)              — "09 May 2024" style date string
normalize_merchant(desc) — maps raw transaction descriptions to clean names
                           (re-exported from src.utils.merchant_normalizer
                            to avoid circular imports between analytics and QA)
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

# Re-export from the shared utilities module so callers only need one import
from src.utils.merchant_normalizer import normalize_merchant  # noqa: F401


# ---------------------------------------------------------------------------
# Indian Rupee formatter
# ---------------------------------------------------------------------------

def fmt_inr(amount: Decimal | int | float | None) -> str:
    """
    Format *amount* as an Indian rupee string with proper separators.

    Indian numbering groups the last three digits, then groups of two:
        1234567.89  →  ₹12,34,567.89
           85743.56  →  ₹85,743.56
              825.42  →  ₹825.42

    Returns "₹0" when amount is None or zero.
    """
    if amount is None:
        return "₹0"

    d = Decimal(str(amount))

    # Separate integer and fractional parts
    sign, digits_tuple, exponent = d.as_tuple()
    is_negative = sign != 0

    # Rebuild as plain string with 2 decimal places
    formatted_plain = f"{abs(d):.2f}"
    integer_part, frac_part = formatted_plain.split(".")

    # Apply Indian grouping to integer part
    int_str = _apply_indian_grouping(integer_part)

    # Drop trailing ".00" only when the fraction is exactly zero
    if frac_part == "00":
        result = f"₹{int_str}"
    else:
        # Strip unnecessary trailing zero from single-decimal amounts
        result = f"₹{int_str}.{frac_part}"

    if is_negative:
        result = "-" + result

    return result


def _apply_indian_grouping(integer_str: str) -> str:
    """
    Insert commas using Indian numbering convention.

    Examples:
        "85743"    → "85,743"
        "1234567"  → "12,34,567"
        "100"      → "100"
    """
    n = len(integer_str)
    if n <= 3:
        return integer_str

    # Last 3 digits form the first group
    last_three = integer_str[-3:]
    rest = integer_str[:-3]

    # Remaining digits in groups of 2 from right
    groups = []
    while len(rest) > 2:
        groups.append(rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.append(rest)

    groups.reverse()
    return ",".join(groups) + "," + last_three


# ---------------------------------------------------------------------------
# Date formatter
# ---------------------------------------------------------------------------

_MONTHS = (
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def fmt_date(d: date | None) -> str:
    """
    Return a human-readable date string.

    Examples:
        date(2024, 5, 9)  →  "09 May 2024"
        None              →  "Unknown Date"
    """
    if d is None:
        return "Unknown Date"
    return f"{d.day:02d} {_MONTHS[d.month]} {d.year}"


