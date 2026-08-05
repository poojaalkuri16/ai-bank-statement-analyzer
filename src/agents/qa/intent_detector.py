from __future__ import annotations

import re as _re
from dataclasses import dataclass

from src.agents.qa.fuzzy_matcher import FuzzyMatcher


# ---------------------------------------------------------------------------
# Intent constants
# ---------------------------------------------------------------------------

class Intent:
    """Enumeration of all recognised intents."""

    # Analytics — aggregate numbers
    TOTAL_SPEND          = "TOTAL_SPEND"
    TOTAL_INCOME         = "TOTAL_INCOME"
    NET_CASH_FLOW        = "NET_CASH_FLOW"
    BALANCE              = "BALANCE"
    OPENING_BALANCE      = "OPENING_BALANCE"
    CLOSING_BALANCE      = "CLOSING_BALANCE"
    HIGHEST_BALANCE      = "HIGHEST_BALANCE"
    LOWEST_BALANCE       = "LOWEST_BALANCE"
    LARGEST_EXPENSE      = "LARGEST_EXPENSE"
    LARGEST_CREDIT       = "LARGEST_CREDIT"
    LARGEST_DEBIT        = "LARGEST_DEBIT"

    # Counts
    TRANSACTION_COUNT    = "TRANSACTION_COUNT"
    DEBIT_COUNT          = "DEBIT_COUNT"
    CREDIT_COUNT         = "CREDIT_COUNT"

    # Filtering
    DATE_FILTER          = "DATE_FILTER"
    AMOUNT_FILTER        = "AMOUNT_FILTER"

    # Positional
    FIRST_TRANSACTION    = "FIRST_TRANSACTION"
    LAST_TRANSACTION     = "LAST_TRANSACTION"
    BIGGEST_TRANSACTIONS = "BIGGEST_TRANSACTIONS"

    # Merchant frequency
    MERCHANT_FREQUENCY   = "MERCHANT_FREQUENCY"

    # Payment method
    PAYMENT_METHOD       = "PAYMENT_METHOD"

    # Percentage analytics
    CATEGORY_PERCENTAGE  = "CATEGORY_PERCENTAGE"

    # Recommendations
    RECOMMENDATIONS      = "RECOMMENDATIONS"

    # Balance threshold query
    BALANCE_THRESHOLD    = "BALANCE_THRESHOLD"

    # Balance after transaction
    BALANCE_AFTER        = "BALANCE_AFTER"

    # Financial habits summary
    FINANCIAL_HABITS     = "FINANCIAL_HABITS"

    # Merchant frequency ranking (by count, not amount)
    MERCHANT_FREQUENCY_RANKING = "MERCHANT_FREQUENCY_RANKING"

    # Category-scoped
    CATEGORY_SPEND       = "CATEGORY_SPEND"
    CATEGORY_LIST        = "CATEGORY_LIST"
    CATEGORY_NOT_FOUND   = "CATEGORY_NOT_FOUND"

    # Merchant-scoped
    MERCHANT_SPEND       = "MERCHANT_SPEND"
    MERCHANT_LIST        = "MERCHANT_LIST"

    # Analytics intelligence
    SPENDING_SUMMARY     = "SPENDING_SUMMARY"
    TOP_MERCHANTS        = "TOP_MERCHANTS"
    RECURRING            = "RECURRING"
    SPENDING_DIST        = "SPENDING_DIST"
    BUDGET_HEALTH        = "BUDGET_HEALTH"
    LARGEST_CATEGORY     = "LARGEST_CATEGORY"
    FINANCIAL_INSIGHTS   = "FINANCIAL_INSIGHTS"

    # Fallback
    UNKNOWN              = "UNKNOWN"

    # Refund-specific
    REFUND_TOTAL         = "REFUND_TOTAL"


# ---------------------------------------------------------------------------
# Detected-intent value object
# ---------------------------------------------------------------------------

@dataclass
class DetectedIntent:
    intent: str
    category: str | None = None
    merchant: str | None = None
    raw: str = ""
    fuzzy_corrected: bool = False   # True when the match came from fuzzy
    # Filtering parameters
    amount_threshold: float | None = None
    amount_direction: str | None = None  # "above" or "below"
    date_from: str | None = None
    date_to: str | None = None
    date_filter_type: str | None = None  # "on", "between", "after", "before"
    payment_method: str | None = None


# ---------------------------------------------------------------------------
# Canonical category alias table
# ---------------------------------------------------------------------------

CATEGORY_ALIASES: dict[str, list[str]] = {
    "Food": [
        "food",
        "food delivery",
        "dining",
        "restaurant",
        "restaurants",
        "swiggy",
        "zomato",
        "meal",
        "breakfast",
        "lunch",
        "dinner",
        "cafe",
        "coffee",
        "pizza",
        "burger",
        "dominos",
        "kfc",
        "mcdonald",
    ],
    "Groceries": [
        "groceries",
        "grocery",
        "reliance fresh",
        "bigbasket",
        "big basket",
        "dmart",
        "supermarket",
        "more supermarket",
        "spar",
        "star bazaar",
    ],
    "Fuel": [
        "fuel",
        "fuel station",
        "petrol",
        "diesel",
        "indian oil",
        "hpcl",
        "bpcl",
        "shell",
    ],
    "Shopping": [
        "shopping",
        "shop",
        "purchase",
        "amazon",
        "flipkart",
        "myntra",
        "ajio",
        "meesho",
        "lifestyle",
    ],
    "Healthcare": [
        "healthcare",
        "health",
        "medical",
        "medicine",
        "medicines",
        "medplus",
        "apollo",
        "pharmacy",
        "hospital",
        "clinic",
    ],
    "Insurance": [
        "insurance",
        "lic",
        "premium",
    ],
    "Bills": [
        "bills",
        "bill",
        "electricity",
        "bescom",
        "water",
        "internet",
        "broadband",
        "wifi",
        "mobile bill",
        "mobile",
        "recharge",
        "gas",
    ],
    "Travel": [
        "travel",
        "trip",
        "flight",
        "makemytrip",
        "uber",
        "ola",
        "rapido",
        "hotel",
        "air",
        "irctc",
        "railway",
        "train",
    ],
    "EMI": [
        "emi",
        "loan",
        "installment",
        "instalment",
        "bajaj",
        "bajaj finserv",
        "consumer durable",
    ],
    "Entertainment": [
        "entertainment",
        "google play",
        "netflix",
        "spotify",
        "prime video",
        "hotstar",
        "zee5",
        "sony liv",
        "bookmyshow",
        "movie",
        "movies",
        "cinema",
        "digital",
        "streaming",
    ],
    "Cash Withdrawal": [
        "cash withdrawal",
        "cash",
        "atm",
        "withdrawal",
        "cash wd",
    ],
    "Interest": [
        "interest",
        "interest credit",
        "sb interest",
    ],
    "Refund": [
        "refund",
        "returned",
        "amazon return",
        "return",
    ],
    "Rent": [
        "rent",
        "house rent",
        "rental",
        "landlord",
        "rentpay",
    ],
    "Salary": [
        "salary",
        "salary credit",
        "payroll",
        "salary payment",
        "paycheck",
    ],
    "Transfer": [
        "transfer",
        "transfers",
        "upi",
        "imps",
        "neft",
        "rtgs",
        "fund transfer",
        "bank transfer",
        "upi transfer",
    ],
    "Others": [
        "others",
        "other",
        "miscellaneous",
        "misc",
        "uncategorized",
    ],
}

# Canonical category names as a lowercased frozenset for fast lookup
_CANONICAL_NAMES: frozenset[str] = frozenset(
    name.lower() for name in CATEGORY_ALIASES
)

# Pre-sort aliases within every category: longest first
_SORTED_ALIASES: dict[str, list[str]] = {
    cat: sorted(aliases, key=len, reverse=True)
    for cat, aliases in CATEGORY_ALIASES.items()
}

# ---------------------------------------------------------------------------
# Known merchants
# ---------------------------------------------------------------------------

KNOWN_MERCHANTS: dict[str, str] = {
    # Food delivery
    "swiggy":            "Swiggy",
    "zomato":            "Zomato",
    # E-commerce
    "amazon":            "Amazon",
    "flipkart":          "Flipkart",
    "myntra":            "Myntra",
    "ajio":              "Ajio",
    "meesho":            "Meesho",
    "lifestyle":         "Lifestyle",
    # Grocery
    "reliance fresh":    "Reliance Fresh",
    "bigbasket":         "BigBasket",
    "big basket":        "BigBasket",
    "dmart":             "DMart",
    # Healthcare
    "medplus":           "MedPlus",
    "apollo":            "Apollo Pharmacy",
    # Utilities
    "bescom":            "BESCOM",
    # Travel
    "makemytrip":        "MakeMyTrip",
    "uber":              "Uber",
    "ola":               "Ola",
    "irctc":             "IRCTC",
    # Finance / EMI
    "bajaj finserv":     "Bajaj Finserv",
    "bajaj":             "Bajaj Finserv",
    # Entertainment
    "google play":       "Google Play",
    "google pay":        "Google Play",
    "netflix":           "Netflix",
    "spotify":           "Spotify",
    "hotstar":           "Hotstar",
    # Fuel
    "indian oil":        "Indian Oil",
    "hpcl":              "HPCL",
    "bpcl":              "BPCL",
    # People / transfers
    "rahul sharma":      "Rahul Sharma",
    # Employers
    "infotech":          "Infotech Solutions",
    # Insurance
    "lic":               "LIC",
}

_SORTED_MERCHANT_KEYS: list[str] = sorted(KNOWN_MERCHANTS, key=len, reverse=True)

# ---------------------------------------------------------------------------
# Intent-cue phrase sets
# ---------------------------------------------------------------------------

_SPEND_PHRASES: frozenset[str] = frozenset([
    "how much did i spend",
    "how much have i spent",
    "spending on",
    "spent on",
    "spending",
    "expenses",
    "expense on",
    "total",
    "what are my expenses",
    "total debits",
    "money spent",
    "total spend",
    "total spent",
    "total debit",
])

_SHOW_PREFIXES: frozenset[str] = frozenset([
    "show",
    "find",
    "list",
    "search",
    "display",
    "get",
])

# When "on X" is present but X resolves to nothing, block TOTAL_SPEND
_ON_ENTITY_RE = _re.compile(r"\bon\s+\w")

# ---------------------------------------------------------------------------
# Analytics phrase sets  (centralised so they're easy to extend)
# ---------------------------------------------------------------------------

_SPENDING_SUMMARY_PHRASES: frozenset[str] = frozenset([
    "spending summary",
    "category summary",
    "expense summary",
    "spending breakdown",
    "expense breakdown",
    "where did i spend",
    "where did my money go",
    "show all categories",
    "all categories",
    "break down my expenses",
    "where is my money going",
    "category breakdown",
    "show categories",
    "my spending",
    "summarize my spending",
    "summarise my spending",
    "spending overview",
    "expense overview",
    "how am i spending",
])

_TOP_MERCHANTS_PHRASES: frozenset[str] = frozenset([
    "top merchants",
    "top merchant",
    "highest spending merchants",
    "biggest merchants",
    "merchant summary",
    "who received the most money",
    "merchant breakdown",
    "where did the most money go",
    "biggest payees",
])

_RECURRING_PHRASES: frozenset[str] = frozenset([
    "recurring",
    "repeated payments",
    "subscriptions",
    "monthly payments",
    "regular payments",
    "recurring payments",
    "recurring subscriptions",
    "recurring bills",
    "standing orders",
])

_SPENDING_DIST_PHRASES: frozenset[str] = frozenset([
    "spending distribution",
    "category percentages",
    "spending percentages",
    "expense distribution",
    "expense percentages",
    "spending by percentage",
])

_BUDGET_HEALTH_PHRASES: frozenset[str] = frozenset([
    "budget health",
    "financial health",
    "am i overspending",
    "did i overspend",
    "overspending",
    "how are my finances",
    "savings rate",
    "budget analysis",
    "how am i doing financially",
    "am i saving",
    "did i save",
    "did i save money",
    "cash flow health",
    "spending health",
])

_LARGEST_CATEGORY_PHRASES: frozenset[str] = frozenset([
    "largest spending category",
    "highest spending category",
    "biggest spending category",
    "top spending category",
    "which category did i spend the most on",
    "largest category",
    "largest expense category",
    "top category",
    "most spent category",
    "where did i spend the most",
    "which category has the highest spending",
    "highest category",
])

_FINANCIAL_INSIGHTS_PHRASES: frozenset[str] = frozenset([
    "financial insights",
    "financial summary",
    "summarize my finances",
    "summarise my finances",
    "summary of my finances",
    "analyze my spending",
    "analyse my spending",
    "analyze my finances",
    "analyse my finances",
    "what do you notice",
    "insights",
    "give me a summary",
    "overall summary",
    "summarize my statement",
    "statement summary",
    "statement analysis",
])

_REFUND_PHRASES: frozenset[str] = frozenset([
    "how much refund",
    "total refund",
    "refunds received",
    "refund received",
    "how much did i receive as refund",
    "how much refund did i receive",
    "refund total",
    "refund amount",
    "did i receive refund",
    "did i get refund",
    "did i get any refund",
    "show refunds",
    "refund summary",
    "any refund",
    "my refund",
    "my refunds",
])

# Phrases that mean "show me total income / credits"
_TOTAL_INCOME_PHRASES: frozenset[str] = frozenset([
    "total income",
    "how much did i receive",
    "how much income",
    "total credits",
    "total credit",
    "money received",
    "money deposited",
    "credits received",
    "deposits",
    "how much was credited",
    "total salary",
    "what is my income",
])

# ---------------------------------------------------------------------------
# Salary / Interest question patterns
# ---------------------------------------------------------------------------

_SALARY_QUESTION_PHRASES: frozenset[str] = frozenset([
    "did i receive salary",
    "did i get salary",
    "salary received",
    "how much salary",
    "salary earned",
    "my salary",
    "salary amount",
    "salary credit",
    "show salary",
    "show me salary",
    "salary income",
])

_INTEREST_QUESTION_PHRASES: frozenset[str] = frozenset([
    "did i receive interest",
    "did i receive any interest",
    "did i get interest",
    "did i get any interest",
    "interest received",
    "interest earned",
    "how much interest",
    "how much interest did i earn",
    "my interest",
    "interest amount",
    "interest credit",
    "interest credits",
    "show interest",
    "show me interest",
    "interest income",
])

# ---------------------------------------------------------------------------
# Transaction count phrases
# ---------------------------------------------------------------------------

_TRANSACTION_COUNT_PHRASES: frozenset[str] = frozenset([
    "how many transactions",
    "number of transactions",
    "transaction count",
    "total transactions",
    "count of transactions",
    "how many transaction",
])

_DEBIT_COUNT_PHRASES: frozenset[str] = frozenset([
    "how many debits",
    "how many debit",
    "number of debits",
    "debit count",
    "total debits count",
    "count of debits",
])

_CREDIT_COUNT_PHRASES: frozenset[str] = frozenset([
    "how many credits",
    "how many credit",
    "number of credits",
    "credit count",
    "total credits count",
    "count of credits",
])

# ---------------------------------------------------------------------------
# Positional transaction phrases
# ---------------------------------------------------------------------------

_FIRST_TRANSACTION_PHRASES: frozenset[str] = frozenset([
    "first transaction",
    "earliest transaction",
    "beginning of statement",
    "beginning of the statement",
    "start of statement",
    "start of the statement",
    "first entry",
    "earliest entry",
])

_LAST_TRANSACTION_PHRASES: frozenset[str] = frozenset([
    "last transaction",
    "most recent transaction",
    "end of statement",
    "end of the statement",
    "latest transaction",
    "last entry",
    "most recent entry",
])

_BIGGEST_TXNS_PHRASES: frozenset[str] = frozenset([
    "biggest transactions",
    "largest transactions",
    "highest value transactions",
    "big transactions",
    "top transactions",
    "largest amount transactions",
])

# ---------------------------------------------------------------------------
# Payment method detection
# ---------------------------------------------------------------------------

_PAYMENT_METHODS: dict[str, list[str]] = {
    "UPI":             ["upi"],
    "NEFT":            ["neft"],
    "IMPS":            ["imps"],
    "RTGS":            ["rtgs"],
    "ATM":             ["atm", "atm withdrawal"],
    "POS":             ["pos"],
    "Cash Withdrawal": ["cash withdrawal", "cash withdraw", "cash", "atm withdrawal", "atm"],
    "Transfer":        ["transfer", "fund transfer", "bank transfer"],
}

_PAYMENT_METHOD_PHRASES: frozenset[str] = frozenset([
    "payment method",
    "payment mode",
    "how did i pay",
    "transactions via",
    "transactions using",
    "through upi",
    "through neft",
    "through imps",
    "through rtgs",
    "via upi",
    "via neft",
    "via imps",
    "via rtgs",
])

# ---------------------------------------------------------------------------
# Percentage analytics phrases
# ---------------------------------------------------------------------------

_PERCENTAGE_TRIGGER_RE = _re.compile(
    r"(?:what\s+percentage|percentage\s+(?:of|spent|on)|"
    r"how\s+much\s+percent|%\s*(?:of|spent|on))"
)

# ---------------------------------------------------------------------------
# Recommendations phrases
# ---------------------------------------------------------------------------

_RECOMMENDATIONS_PHRASES: frozenset[str] = frozenset([
    "recommendations",
    "recommend",
    "suggestions",
    "suggest",
    "tips",
    "advice",
    "how can i save",
    "how to save",
    "save money",
    "save more money",
    "what can i do to save",
    "reduce spending",
    "cut expenses",
    "spending tips",
    "financial advice",
    "financial tips",
    "budget tips",
    "budget advice",
    "saving tips",
    "improve my finances",
    "improve my spending",
    "how do i reduce spending",
    "any financial advice",
])

# ---------------------------------------------------------------------------
# Balance threshold phrases — "did balance exceed X?"
# ---------------------------------------------------------------------------

_BALANCE_THRESHOLD_RE = _re.compile(
    r"(?:did|has|have)\s+(?:my\s+)?balance\s+"
    r"(?:ever\s+)?(?:exceed|go\s+(?:above|beyond|over)|cross|reach|hit)\s+"
    r"[₹]?\s*(\d+(?:,\d{2,3})*(?:\.\d{1,2})?(?:\s*(?:lakh|crore|k))?)",
    _re.IGNORECASE,
)

_BALANCE_BELOW_RE = _re.compile(
    r"(?:did|has|have)\s+(?:my\s+)?balance\s+"
    r"(?:ever\s+)?(?:go\s+below|drop\s+(?:below|under)|fall\s+below)\s+"
    r"[₹]?\s*(\d+(?:,\d{2,3})*(?:\.\d{1,2})?(?:\s*(?:lakh|crore|k))?)",
    _re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Balance after transaction phrases
# ---------------------------------------------------------------------------

_BALANCE_AFTER_PHRASES: frozenset[str] = frozenset([
    "balance after",
    "balance after my",
    "balance after the",
    "what was my balance after",
    "balance after my",
    "balance following",
])

# ---------------------------------------------------------------------------
# Financial habits phrases
# ---------------------------------------------------------------------------

_FINANCIAL_HABITS_PHRASES: frozenset[str] = frozenset([
    "financial habits",
    "my financial habits",
    "summarize my financial habits",
    "summarise my financial habits",
    "how are my financial habits",
    "analyze my financial habits",
    "analyse my financial habits",
    "what are my financial habits",
    "financial behavior",
    "financial behaviour",
])

# ---------------------------------------------------------------------------
# Merchant frequency ranking phrases (by count, not amount)
# ---------------------------------------------------------------------------

_MERCHANT_FREQUENCY_RANKING_PHRASES: frozenset[str] = frozenset([
    "most frequent merchants",
    "frequent merchants",
    "merchants used most often",
    "merchants i use most",
    "most used merchants",
    "merchant frequency",
    "frequency of merchants",
    "how often do i use merchants",
    "which merchants appear most frequently",
    "which merchants do i use most often",
    "most visited merchants",
    "merchants that appear most",
    "merchants appearing frequently",
])

# ---------------------------------------------------------------------------
# Amount extraction regex — ₹5000, 5000 rupees, rs 5000, etc.
# ---------------------------------------------------------------------------

_AMOUNT_RE = _re.compile(
    r"(?:[₹]|rs\.?|rupees?)\s*"
    r"(\d+(?:,\d{2,3})*(?:\.\d{1,2})?)"
    r"|"
    r"(\d+(?:,\d{2,3})*(?:\.\d{1,2})?)\b",
    _re.IGNORECASE,
)

_ABOVE_PHRASES: frozenset[str] = frozenset([
    "above", "greater than", "more than", "over", "exceeding", "higher than",
])

_BELOW_PHRASES: frozenset[str] = frozenset([
    "below", "less than", "under", "lesser than", "lower than",
])

# ---------------------------------------------------------------------------
# Date extraction patterns
# ---------------------------------------------------------------------------

_DATE_ON_RE = _re.compile(
    r"(?:transactions?\s+)?on\s+(\d{1,2})\s+"
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s*"
    r"(\d{4})?",
    _re.IGNORECASE,
)

_DATE_BETWEEN_RE = _re.compile(
    r"between\s+(\d{1,2})\s+"
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"(?:\s+\d{4})?\s+and\s+(\d{1,2})\s+"
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)",
    _re.IGNORECASE,
)

_DATE_AFTER_RE = _re.compile(
    r"after\s+(\d{1,2})\s+"
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"(?:\s+\d{4})?",
    _re.IGNORECASE,
)

_DATE_BEFORE_RE = _re.compile(
    r"before\s+(\d{1,2})\s+"
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"(?:\s+\d{4})?",
    _re.IGNORECASE,
)


class IntentDetector:
    """
    Detects the intent (and optional category / merchant slot) from a
    normalised question string.

    Detection order
    ---------------
    1.  Empty / blank                 → UNKNOWN
    2.  Balance keywords              → BALANCE
    3.  Canonical category name check → CATEGORY_SPEND / CATEGORY_LIST
    4.  Merchant keyword check        → MERCHANT_SPEND / MERCHANT_LIST
    5.  Alias-based category check    → CATEGORY_SPEND / CATEGORY_LIST
    6.  Analytics intelligence        → SPENDING_SUMMARY / TOP_MERCHANTS / …
    7.  Aggregate analytics           → TOTAL_SPEND / TOTAL_INCOME / …
    8.  Fuzzy match                   → routes as category or merchant
    9.  UNKNOWN fallback
    """

    def __init__(self) -> None:
        self._fuzzy = FuzzyMatcher(CATEGORY_ALIASES, KNOWN_MERCHANTS)

    def detect(self, normalised: str) -> DetectedIntent:
        q = normalised.strip()

        if not q:
            return DetectedIntent(intent=Intent.UNKNOWN, raw=q)

        # ------------------------------------------------------------------
        # 0. Follow-up detection — pronouns referencing previous context
        #    (handled at QAAgent level, not here)
        # ------------------------------------------------------------------

        # ------------------------------------------------------------------
        # 1. Balance variants — specific before generic
        # ------------------------------------------------------------------
        if any(p in q for p in (
            "opening balance", "beginning balance", "start balance",
            "initial balance",
        )):
            return DetectedIntent(intent=Intent.OPENING_BALANCE, raw=q)

        if any(p in q for p in (
            "closing balance", "end balance", "final balance",
        )):
            return DetectedIntent(intent=Intent.CLOSING_BALANCE, raw=q)

        if any(p in q for p in (
            "highest balance", "maximum balance", "peak balance",
            "max balance",
        )):
            return DetectedIntent(intent=Intent.HIGHEST_BALANCE, raw=q)

        if any(p in q for p in (
            "lowest balance", "minimum balance", "min balance",
        )):
            return DetectedIntent(intent=Intent.LOWEST_BALANCE, raw=q)

        # Balance threshold — "did balance exceed X?" — before generic balance
        m = _BALANCE_THRESHOLD_RE.search(q)
        if m:
            threshold_str = m.group(1).replace(",", "")
            if "lakh" in q.lower():
                threshold = float(threshold_str) * 100000
            elif "crore" in q.lower():
                threshold = float(threshold_str) * 10000000
            elif threshold_str.lower().endswith("k"):
                threshold = float(threshold_str[:-1]) * 1000
            else:
                threshold = float(threshold_str)
            return DetectedIntent(
                intent=Intent.BALANCE_THRESHOLD,
                raw=q,
                amount_threshold=threshold,
                amount_direction="above",
            )

        m = _BALANCE_BELOW_RE.search(q)
        if m:
            threshold_str = m.group(1).replace(",", "")
            if "lakh" in q.lower():
                threshold = float(threshold_str) * 100000
            elif "crore" in q.lower():
                threshold = float(threshold_str) * 10000000
            elif threshold_str.lower().endswith("k"):
                threshold = float(threshold_str[:-1]) * 1000
            else:
                threshold = float(threshold_str)
            return DetectedIntent(
                intent=Intent.BALANCE_THRESHOLD,
                raw=q,
                amount_threshold=threshold,
                amount_direction="below",
            )

        # Balance after transaction — before generic balance
        if any(p in q for p in _BALANCE_AFTER_PHRASES):
            return DetectedIntent(intent=Intent.BALANCE_AFTER, raw=q)

        # Generic balance → closing / current balance
        if any(p in q for p in (
            "balance", "account balance", "current balance",
            "what is my balance", "available balance",
            "what is my account balance",
        )):
            return DetectedIntent(intent=Intent.BALANCE, raw=q)

        # ------------------------------------------------------------------
        # Determine intent cues once
        # ------------------------------------------------------------------
        is_spend_cue = self._is_spend_cue(q)
        is_show_cue  = self._is_show_cue(q)

        # ------------------------------------------------------------------
        # 1b. Refund total — before category matching
        # ------------------------------------------------------------------
        if any(p in q for p in _REFUND_PHRASES):
            return DetectedIntent(intent=Intent.REFUND_TOTAL, raw=q)

        # ------------------------------------------------------------------
        # 1c. Total income — before category matching so "income" or
        #     "salary received" doesn't route to CATEGORY_SPEND(Salary)
        # ------------------------------------------------------------------
        if any(p in q for p in _TOTAL_INCOME_PHRASES):
            return DetectedIntent(intent=Intent.TOTAL_INCOME, raw=q)

        # ------------------------------------------------------------------
        # 1d. Salary question patterns — route to CATEGORY_LIST(Salary)
        # ------------------------------------------------------------------
        if any(p in q for p in _SALARY_QUESTION_PHRASES):
            return DetectedIntent(
                intent=Intent.CATEGORY_LIST,
                category="Salary",
                raw=q,
            )

        # ------------------------------------------------------------------
        # 1e. Interest question patterns — route to CATEGORY_LIST(Interest)
        # ------------------------------------------------------------------
        if any(p in q for p in _INTEREST_QUESTION_PHRASES):
            return DetectedIntent(
                intent=Intent.CATEGORY_LIST,
                category="Interest",
                raw=q,
            )

        # ------------------------------------------------------------------
        # 1f. Transaction counts — before category matching
        # ------------------------------------------------------------------
        if any(p in q for p in _DEBIT_COUNT_PHRASES):
            return DetectedIntent(intent=Intent.DEBIT_COUNT, raw=q)

        if any(p in q for p in _CREDIT_COUNT_PHRASES):
            return DetectedIntent(intent=Intent.CREDIT_COUNT, raw=q)

        if any(p in q for p in _TRANSACTION_COUNT_PHRASES):
            return DetectedIntent(intent=Intent.TRANSACTION_COUNT, raw=q)

        # ------------------------------------------------------------------
        # 1g. Recommendations — before category matching
        # ------------------------------------------------------------------
        if any(p in q for p in _RECOMMENDATIONS_PHRASES):
            return DetectedIntent(intent=Intent.RECOMMENDATIONS, raw=q)

        # ------------------------------------------------------------------
        # 1h. Financial habits — before category matching
        # ------------------------------------------------------------------
        if any(p in q for p in _FINANCIAL_HABITS_PHRASES):
            return DetectedIntent(intent=Intent.FINANCIAL_HABITS, raw=q)

        # ------------------------------------------------------------------
        # 1i. Merchant frequency ranking (by count, not amount)
        # ------------------------------------------------------------------
        if any(p in q for p in _MERCHANT_FREQUENCY_RANKING_PHRASES):
            return DetectedIntent(intent=Intent.MERCHANT_FREQUENCY_RANKING, raw=q)

        # ------------------------------------------------------------------
        # 1h. Percentage analytics — before category matching
        # ------------------------------------------------------------------
        if _PERCENTAGE_TRIGGER_RE.search(q):
            # Try to find a category in the question
            pct_category = (
                self._find_canonical_category(q)
                or self._find_alias_category(q)
            )
            return DetectedIntent(
                intent=Intent.CATEGORY_PERCENTAGE,
                category=pct_category,
                raw=q,
            )

        # ------------------------------------------------------------------
        # 2. Canonical category name check — runs before merchant matching
        # ------------------------------------------------------------------
        canonical_category = self._find_canonical_category(q)

        if canonical_category is not None:
            if is_spend_cue:
                return DetectedIntent(
                    intent=Intent.CATEGORY_SPEND,
                    category=canonical_category,
                    raw=q,
                )
            if is_show_cue:
                return DetectedIntent(
                    intent=Intent.CATEGORY_LIST,
                    category=canonical_category,
                    raw=q,
                )

        # ------------------------------------------------------------------
        # 3. Merchant keyword check (exact)
        # ------------------------------------------------------------------
        merchant_name, merchant_key = self._find_merchant(q)

        if merchant_name is not None:
            # Merchant frequency: "how many X transactions"
            if any(p in q for p in (
                "how many", "how many times", "number of",
                "count", "frequency",
            )):
                return DetectedIntent(
                    intent=Intent.MERCHANT_FREQUENCY,
                    merchant=merchant_name,
                    raw=q,
                )
            if is_spend_cue:
                return DetectedIntent(
                    intent=Intent.MERCHANT_SPEND,
                    merchant=merchant_name,
                    raw=q,
                )
            if is_show_cue:
                return DetectedIntent(
                    intent=Intent.MERCHANT_LIST,
                    merchant=merchant_name,
                    raw=q,
                )

        # ------------------------------------------------------------------
        # 4. Alias-based category check (exact)
        #     Skip payment-method keywords that are also category aliases
        #     (e.g. "upi", "neft") — those should route to PAYMENT_METHOD.
        # ------------------------------------------------------------------
        alias_category = self._find_alias_category(q)

        if alias_category is not None:
            # Check if a payment method keyword triggered the alias match
            _pay_keywords = {"upi", "imps", "neft", "rtgs", "atm", "pos"}
            _alias_hit = None
            for _cat, _aliases in _SORTED_ALIASES.items():
                for _a in _aliases:
                    if _a in q:
                        _alias_hit = _a
                        break
                if _alias_hit:
                    break
            if _alias_hit and _alias_hit in _pay_keywords:
                # Route to payment method instead
                payment = self._detect_payment_method(q)
                if payment:
                    return DetectedIntent(
                        intent=Intent.PAYMENT_METHOD,
                        raw=q,
                        payment_method=payment,
                    )

            if is_spend_cue:
                return DetectedIntent(
                    intent=Intent.CATEGORY_SPEND,
                    category=alias_category,
                    raw=q,
                )
            if is_show_cue:
                return DetectedIntent(
                    intent=Intent.CATEGORY_LIST,
                    category=alias_category,
                    raw=q,
                )

        # ------------------------------------------------------------------
        # 5. Analytics intelligence — phrase matching
        # ------------------------------------------------------------------
        if any(p in q for p in _LARGEST_CATEGORY_PHRASES):
            return DetectedIntent(intent=Intent.LARGEST_CATEGORY, raw=q)

        if any(p in q for p in _SPENDING_SUMMARY_PHRASES):
            return DetectedIntent(intent=Intent.SPENDING_SUMMARY, raw=q)

        if any(p in q for p in _TOP_MERCHANTS_PHRASES):
            return DetectedIntent(intent=Intent.TOP_MERCHANTS, raw=q)

        if any(p in q for p in _RECURRING_PHRASES):
            return DetectedIntent(intent=Intent.RECURRING, raw=q)

        if any(p in q for p in _SPENDING_DIST_PHRASES):
            return DetectedIntent(intent=Intent.SPENDING_DIST, raw=q)

        if any(p in q for p in _BUDGET_HEALTH_PHRASES):
            return DetectedIntent(intent=Intent.BUDGET_HEALTH, raw=q)

        if any(p in q for p in _FINANCIAL_INSIGHTS_PHRASES):
            return DetectedIntent(intent=Intent.FINANCIAL_INSIGHTS, raw=q)

        # ------------------------------------------------------------------
        # 5b. Amount filtering — "transactions above/below ₹X"
        # ------------------------------------------------------------------
        amount_result = self._detect_amount_filter(q)
        if amount_result is not None:
            direction, threshold = amount_result
            return DetectedIntent(
                intent=Intent.AMOUNT_FILTER,
                raw=q,
                amount_direction=direction,
                amount_threshold=threshold,
            )

        # ------------------------------------------------------------------
        # 5c. Date filtering — "transactions on/between/after/before"
        # ------------------------------------------------------------------
        date_result = self._detect_date_filter(q)
        if date_result is not None:
            return DetectedIntent(
                intent=Intent.DATE_FILTER,
                raw=q,
                date_filter_type=date_result[0],
                date_from=date_result[1],
                date_to=date_result[2],
            )

        # ------------------------------------------------------------------
        # 5d. First / Last transaction
        # ------------------------------------------------------------------
        if any(p in q for p in _FIRST_TRANSACTION_PHRASES):
            return DetectedIntent(intent=Intent.FIRST_TRANSACTION, raw=q)

        if any(p in q for p in _LAST_TRANSACTION_PHRASES):
            return DetectedIntent(intent=Intent.LAST_TRANSACTION, raw=q)

        # ------------------------------------------------------------------
        # 5e. Biggest transactions
        # ------------------------------------------------------------------
        if any(p in q for p in _BIGGEST_TXNS_PHRASES):
            return DetectedIntent(intent=Intent.BIGGEST_TRANSACTIONS, raw=q)

        # ------------------------------------------------------------------
        # 6. Aggregate analytics
        #    Blocked when "on X" is present — means user asked about a
        #    specific entity, not the grand total.
        # ------------------------------------------------------------------
        has_on_clause = bool(_ON_ENTITY_RE.search(q))

        if not has_on_clause and (
            any(p in q for p in (
                "total expense", "total expenses",
                "how much did i spend",
                "what are my expenses",
                "total debits", "total debit",
                "money spent", "total spend", "total spent",
            )) or q in ("spent", "expenses", "spending")
        ):
            return DetectedIntent(intent=Intent.TOTAL_SPEND, raw=q)

        if any(p in q for p in (
            "total income", "how much did i receive",
        )) or q == "income":
            return DetectedIntent(intent=Intent.TOTAL_INCOME, raw=q)

        if any(p in q for p in (
            "cash flow", "net cash flow", "net flow",
        )):
            return DetectedIntent(intent=Intent.NET_CASH_FLOW, raw=q)

        # ------------------------------------------------------------------
        # Largest debit / credit — before LARGEST_EXPENSE
        # ------------------------------------------------------------------
        if any(p in q for p in (
            "largest credit", "biggest credit", "highest credit",
            "largest income", "biggest income", "highest income",
        )):
            return DetectedIntent(intent=Intent.LARGEST_CREDIT, raw=q)

        if any(p in q for p in (
            "largest debit", "biggest debit", "highest debit",
            "largest expense", "highest expense", "biggest expense",
            "biggest payment", "largest payment", "highest payment",
            "largest outgoing", "biggest outgoing",
        )):
            return DetectedIntent(intent=Intent.LARGEST_DEBIT, raw=q)

        # Keep backward compat for existing LARGEST_EXPENSE detection
        if any(p in q for p in (
            "largest expense", "highest expense", "biggest expense",
        )):
            return DetectedIntent(intent=Intent.LARGEST_EXPENSE, raw=q)

        # ------------------------------------------------------------------
        # 6b. Payment method detection — after aggregate analytics
        #     to avoid "cash flow" → Cash Withdrawal false positives.
        # ------------------------------------------------------------------
        payment = self._detect_payment_method(q)
        if payment is not None:
            return DetectedIntent(
                intent=Intent.PAYMENT_METHOD,
                raw=q,
                payment_method=payment,
            )

        # ------------------------------------------------------------------
        # 7. Fuzzy match — catches typos after all exact paths have failed
        # ------------------------------------------------------------------
        if is_spend_cue or is_show_cue:
            fuzzy = self._fuzzy.match(q)
            if fuzzy is not None:
                if fuzzy.kind == "category":
                    intent = (
                        Intent.CATEGORY_SPEND if is_spend_cue
                        else Intent.CATEGORY_LIST
                    )
                    return DetectedIntent(
                        intent=intent,
                        category=fuzzy.display_name,
                        raw=q,
                        fuzzy_corrected=True,
                    )
                else:  # merchant
                    intent = (
                        Intent.MERCHANT_SPEND if is_spend_cue
                        else Intent.MERCHANT_LIST
                    )
                    return DetectedIntent(
                        intent=intent,
                        merchant=fuzzy.display_name,
                        raw=q,
                        fuzzy_corrected=True,
                    )

        # ------------------------------------------------------------------
        # 8. Unknown fallback
        # ------------------------------------------------------------------
        return DetectedIntent(intent=Intent.UNKNOWN, raw=q)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_spend_cue(q: str) -> bool:
        return any(p in q for p in _SPEND_PHRASES)

    @staticmethod
    def _is_show_cue(q: str) -> bool:
        for prefix in _SHOW_PREFIXES:
            if q == prefix:
                return True
            if q.startswith(prefix + " "):
                return True
            if (" " + prefix + " ") in q:
                return True
        return False

    @staticmethod
    def _find_canonical_category(q: str) -> str | None:
        for name in sorted(_CANONICAL_NAMES, key=len, reverse=True):
            if name in q:
                for display_name in CATEGORY_ALIASES:
                    if display_name.lower() == name:
                        return display_name
        return None

    @staticmethod
    def _find_alias_category(q: str) -> str | None:
        for category, aliases in _SORTED_ALIASES.items():
            for alias in aliases:
                if alias in q:
                    return category
        return None

    @staticmethod
    def _find_merchant(q: str) -> tuple[str | None, str | None]:
        for keyword in _SORTED_MERCHANT_KEYS:
            if keyword in _CANONICAL_NAMES:
                continue
            if keyword in q:
                return KNOWN_MERCHANTS[keyword], keyword
        return None, None

    @staticmethod
    def _detect_payment_method(q: str) -> str | None:
        """Return canonical payment method name if detected."""
        # Check explicit trigger phrases first
        if not any(p in q for p in _PAYMENT_METHOD_PHRASES):
            # Also check for "transactions via/through X" patterns
            for method, keywords in _PAYMENT_METHODS.items():
                for kw in keywords:
                    if kw in q:
                        return method
            return None
        # Trigger phrase found — find which method
        for method, keywords in _PAYMENT_METHODS.items():
            for kw in keywords:
                if kw in q:
                    return method
        return None

    @staticmethod
    def _detect_amount_filter(
        q: str,
    ) -> tuple[str, float] | None:
        """Return (direction, threshold) if amount filter detected."""
        direction = None
        if any(p in q for p in _ABOVE_PHRASES):
            direction = "above"
        elif any(p in q for p in _BELOW_PHRASES):
            direction = "below"
        if direction is None:
            return None

        # Extract the amount value
        m = _AMOUNT_RE.search(q)
        if m is None:
            return None
        # Pick whichever group matched (2 alternatives)
        raw = (m.group(1) or m.group(2) or "").replace(",", "")
        if not raw:
            return None
        try:
            threshold = float(raw)
        except ValueError:
            return None
        if threshold <= 0:
            return None
        return direction, threshold

    @staticmethod
    def _detect_date_filter(
        q: str,
    ) -> tuple[str, str, str | None] | None:
        """Return (filter_type, date_from, date_to) if date filter detected."""
        # Between
        m = _DATE_BETWEEN_RE.search(q)
        if m:
            d1 = f"{int(m.group(1)):02d} {_normalise_month(m.group(2))}"
            d2 = f"{int(m.group(3)):02d} {_normalise_month(m.group(4))}"
            return "between", d1, d2

        # After
        m = _DATE_AFTER_RE.search(q)
        if m:
            d = f"{int(m.group(1)):02d} {_normalise_month(m.group(2))}"
            return "after", d, None

        # Before
        m = _DATE_BEFORE_RE.search(q)
        if m:
            d = f"{int(m.group(1)):02d} {_normalise_month(m.group(2))}"
            return "before", d, None

        # On
        m = _DATE_ON_RE.search(q)
        if m:
            d = f"{int(m.group(1)):02d} {_normalise_month(m.group(2))}"
            return "on", d, None

        return None


def _normalise_month(raw: str) -> str:
    """Return 3-letter month abbreviation from any month string."""
    _MONTH_MAP = {
        "january": "Jan", "jan": "Jan",
        "february": "Feb", "feb": "Feb",
        "march": "Mar", "mar": "Mar",
        "april": "Apr", "apr": "Apr",
        "may": "May",
        "june": "Jun", "jun": "Jun",
        "july": "Jul", "jul": "Jul",
        "august": "Aug", "aug": "Aug",
        "september": "Sep", "sep": "Sep",
        "october": "Oct", "oct": "Oct",
        "november": "Nov", "nov": "Nov",
        "december": "Dec", "dec": "Dec",
    }
    return _MONTH_MAP.get(raw.lower(), raw[:3].title())
