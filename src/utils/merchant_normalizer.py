"""
merchant_normalizer.py
======================
Maps raw transaction descriptions to canonical merchant display names.

This module lives in src/utils/ so it can be imported by both the
analytics layer and the QA presentation layer without creating a
circular import.

Rules
-----
- Patterns are matched longest-first so "bajaj finserv" takes
  precedence over the shorter "bajaj".
- If no pattern matches, the description is returned title-cased.
"""
from __future__ import annotations

# Maps lowercase substrings found in raw descriptions → clean display names.
# Sorted longest-key-first at module load time.
_MERCHANT_PATTERNS: list[tuple[str, str]] = sorted(
    [
        ("upi/swiggy",          "Swiggy"),
        ("swiggy",              "Swiggy"),
        ("zomato",              "Zomato"),
        ("flipkart",            "Flipkart"),
        ("amazon",              "Amazon"),
        ("reliance fresh",      "Reliance Fresh"),
        ("bigbasket",           "BigBasket"),
        ("dmart",               "DMart"),
        ("medplus",             "MedPlus"),
        ("apollo",              "Apollo Pharmacy"),
        ("bescom",              "BESCOM"),
        ("makemytrip",          "MakeMyTrip"),
        ("google play",         "Google Play"),
        ("netflix",             "Netflix"),
        ("spotify",             "Spotify"),
        ("hotstar",             "Hotstar"),
        ("bajaj finserv",       "Bajaj Finserv"),
        ("bajaj",               "Bajaj Finserv"),
        ("indian oil",          "Indian Oil"),
        ("hpcl",                "HPCL"),
        ("bpcl",                "BPCL"),
        ("rahul sharma",        "Rahul Sharma"),
        ("infotech solutions",  "Infotech Solutions"),
        ("lic",                 "LIC"),
        ("lifestyle",           "Lifestyle"),
        ("upi/landlord",        "Landlord (Rent)"),
        ("landlord",            "Landlord (Rent)"),
        ("salary credit",       "Salary Credit"),
        ("salary",              "Salary"),
        ("atm cash",            "ATM Withdrawal"),
        ("atm",                 "ATM Withdrawal"),
    ],
    key=lambda pair: len(pair[0]),
    reverse=True,   # longest first
)


def normalize_merchant(description: str) -> str:
    """
    Return a clean merchant display name for *description*, or the
    original description (title-cased) if no pattern matches.

    Examples
    --------
    "UPI/SWIGGY/ORDERPAY"                       → "Swiggy"
    "FLIPKART ONLINE PAYMENT"                   → "Flipkart"
    "EMI - CONSUMER DURABLE LOAN BAJAJ FINSERV" → "Bajaj Finserv"
    "SALARY CREDIT - INFOTECH SOLUTIONS"        → "Infotech Solutions"
    "UNKNOWN VENDOR XYZ"                        → "Unknown Vendor Xyz"
    """
    lower = description.lower()
    for pattern, name in _MERCHANT_PATTERNS:
        if pattern in lower:
            return name
    return description.title()
