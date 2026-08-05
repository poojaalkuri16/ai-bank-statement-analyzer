"""
transaction_normalizer.py
=========================
Cleans and standardises extracted Transaction objects before
validation and categorization.

Responsibilities
----------------
1. Uppercase and collapse whitespace in description.
2. Infer transaction_type from description keywords when the extractor
   could not determine it from the amount format (no DR/CR suffix,
   no column-position information).

This is the correct place for type inference because it runs after
every extraction path (TableRowExtractor, KeyValueBlockExtractor,
SameLineExtractor, SemanticExtractor) and before validation.

Rules
-----
- If transaction_type is already set (DEBIT or CREDIT), leave it.
- If transaction_type is None, apply keyword inference:
    CREDIT keywords → CREDIT
    anything else   → DEBIT   (conservative default)
- Never modify amount, balance, or date.
"""
import re
import re as _re

from src.schemas.transaction import Transaction


_CREDIT_KEYWORDS = (
    "SALARY",
    "CREDIT",
    "REFUND",
    "INTEREST",
    "CASH DEPOSIT",
    "NEFT INWARD",
    "IMPS INWARD",
    "RTGS INWARD",
    "REVERSAL",
    "CASHBACK",
)

_MULTIPLE_SPACES = re.compile(r"\s+")


class TransactionNormalizer:
    """
    Normalises a Transaction after field extraction.
    """

    def normalize(self, transaction: Transaction) -> Transaction:

        # ── 1. Description: uppercase + collapse whitespace ──────────────
        if transaction.description:
            description = transaction.description.upper()
            description = _MULTIPLE_SPACES.sub(" ", description).strip()
            # Collapse "X/ Y" → "X/Y" for payment references like UPI/LANDLORD
            # that may have been joined from wrapped lines with a space after /
            description = _re.sub(r"/\s+", "/", description)
            transaction.description = description

        # ── 2. Transaction type inference ────────────────────────────────
        if transaction.transaction_type not in ("DEBIT", "CREDIT"):
            upper_desc = (transaction.description or "").upper()
            if any(kw in upper_desc for kw in _CREDIT_KEYWORDS):
                transaction.transaction_type = "CREDIT"
            else:
                transaction.transaction_type = "DEBIT"

        return transaction
