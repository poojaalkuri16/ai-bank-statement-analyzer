"""
table_row_extractor.py
======================
Extracts a Transaction from a structured table-row block.

Supported block shapes
----------------------
4-line (debit-only or credit-only column):
    01/05/2024
    UPI/LANDLORD/RENTPAY
    24,950.89              ← amount (debit)
    57,499.11              ← balance

5-line (separate debit and credit columns):
    11/05/2024
    SB INTEREST CREDIT
    0                      ← debit column (empty → 0)
    582.30                 ← credit column
    32,469.20              ← balance

In the 5-line form the non-zero column determines the transaction type
directly.  When both are non-zero (which should not happen in a valid
statement) the larger value is treated as the amount.

Amount normalization
--------------------
parse_amount() converts all common representations to a non-negative
Decimal and infers the transaction type from DR/CR suffixes.

Type inference precedence
-------------------------
1. DR/CR suffix on the amount line
2. Column position (debit column vs. credit column, 5-line form)
3. CREDIT_KEYWORDS in the description
"""
from __future__ import annotations

import re
from decimal import Decimal

from src.agents.extraction.shared.amount_normalizer import parse_amount
from src.agents.extraction.shared.date_parser import parse_date
from src.schemas.transaction import Transaction

# Money token — accepts plain number, DR/CR suffix, currency prefix, negative
_MONEY_TOKEN_RE = re.compile(
    r"^[-₹]?\s*\d[\d,]*\.\d{2}"
    r"(?:\s*\(?\s*(?:DR|CR|Dr|Cr|Debit|Credit)\s*\)?)?$",
    re.IGNORECASE,
)

# Zero is a valid empty-column placeholder in 3-column statements
_ZERO_RE = re.compile(r"^0+\.?0*$")


def _is_money_or_zero(text: str) -> bool:
    """True when *text* is a monetary value OR the zero placeholder."""
    stripped = text.strip()
    return bool(_MONEY_TOKEN_RE.match(stripped)) or bool(_ZERO_RE.match(stripped))


def _to_decimal(raw: str) -> tuple[Decimal | None, str | None]:
    """
    Convert *raw* to (positive_decimal, txn_type | None).

    Uses parse_amount exclusively — never falls back to bare Decimal()
    because that would accept account numbers and reference numbers as
    monetary values.
    """
    cleaned = raw.replace(",", "").strip()
    if not cleaned:
        return None, None
    return parse_amount(cleaned)


class TableRowExtractor:
    """
    Parses 4-line and 5-line table-row transaction blocks into a
    Transaction object.
    """

    CREDIT_KEYWORDS = (
        "SALARY",
        "CREDIT",
        "REFUND",
        "INTEREST",
        "CASH DEPOSIT",
        "NEFT INWARD",
        "IMPS INWARD",
        "RTGS INWARD",
    )

    def can_handle(self, block: str) -> bool:
        """
        True when the block is a recognised table-row layout.

        4-line: date / desc / amount / balance-or-other
          - lines[0] must be a date
          - lines[2] must be a monetary value (the transaction amount)
          - lines[3] may be anything — parsed as balance if it looks like
            money, otherwise balance=None (e.g. when lines[3] is an
            account number or reference)

        5-line: date / desc / debit / credit / balance
          - lines[2] and lines[3] are the debit and credit columns (may be 0)
          - lines[4] must be a monetary value (the running balance)
        """
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]

        if len(lines) < 4:
            return False

        if parse_date(lines[0]) is None:
            return False

        # 5-line: try first — all three money lines must be valid
        if len(lines) >= 5 and _is_money_or_zero(lines[4]):
            if _is_money_or_zero(lines[2]) and _is_money_or_zero(lines[3]):
                return True

        # 4-line: only the amount column (lines[2]) must be a valid money value
        return _is_money_or_zero(lines[2])

    def extract(self, transaction_block: str) -> Transaction:
        """
        Extract all fields from a 4-line or 5-line table-row block.
        """
        lines = [
            line.strip()
            for line in transaction_block.splitlines()
            if line.strip()
        ]

        if len(lines) < 4:
            raise ValueError(
                f"Table row block needs ≥4 non-empty lines, got {len(lines)}:\n"
                f"{transaction_block}"
            )

        # ----------------------------------------------------------------
        # Date
        # ----------------------------------------------------------------
        transaction_date = parse_date(lines[0])
        if transaction_date is None:
            raise ValueError(f"Could not parse date from: {lines[0]!r}")

        # ----------------------------------------------------------------
        # Description
        # ----------------------------------------------------------------
        description = lines[1]

        # ----------------------------------------------------------------
        # Determine layout shape and extract amount / balance
        # ----------------------------------------------------------------
        if len(lines) >= 5 and _is_money_or_zero(lines[4]):
            # 5-line layout: date / desc / debit / credit / balance
            amount, transaction_type = self._extract_5col(
                lines[2], lines[3], lines[4], description
            )
            balance_val, _ = _to_decimal(lines[4])
        else:
            # 4-line layout: date / desc / amount / balance-or-other
            amount, transaction_type = self._extract_4col(
                lines[2], description
            )
            # lines[3] is only used as balance when it parses as money;
            # account numbers and reference numbers are left as None.
            raw_bal = lines[3].replace(",", "").strip()
            balance_val, _ = parse_amount(raw_bal)
            # balance stays None if lines[3] is not a monetary value

        return Transaction(
            transaction_date=transaction_date,
            description=description,
            amount=amount,
            balance=balance_val,
            transaction_type=transaction_type,
            confidence=1.0,
            reasoning="Parsed using structured table-row block.",
            source_text=transaction_block,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_4col(
        self,
        amount_line: str,
        description: str,
    ) -> tuple[Decimal, str]:
        """
        4-column layout: amount is on lines[2], type from DR/CR or keywords.
        """
        amount, txn_type = _to_decimal(amount_line)
        if amount is None:
            amount = Decimal("0")

        if txn_type is None:
            txn_type = self._type_from_description(description)

        return amount, txn_type

    def _extract_5col(
        self,
        debit_line: str,
        credit_line: str,
        balance_line: str,   # noqa: ARG002  (unused — balance parsed by caller)
        description: str,
    ) -> tuple[Decimal, str]:
        """
        5-column layout: debit and credit are separate columns.

        Rules:
          - If debit > 0 and credit == 0 → DEBIT,  amount = debit
          - If credit > 0 and debit == 0 → CREDIT, amount = credit
          - If both > 0 (rare, data issue) → take the larger as amount;
            infer type from DR/CR suffix or description
          - If both == 0 → amount = 0, type from description
        """
        debit_val,  debit_type  = _to_decimal(debit_line)
        credit_val, credit_type = _to_decimal(credit_line)

        debit_val  = debit_val  or Decimal("0")
        credit_val = credit_val or Decimal("0")

        if debit_val > 0 and credit_val == 0:
            # Explicit DEBIT column
            txn_type = debit_type or "DEBIT"
            return debit_val, txn_type

        if credit_val > 0 and debit_val == 0:
            # Explicit CREDIT column
            txn_type = credit_type or "CREDIT"
            return credit_val, txn_type

        if debit_val > 0 and credit_val > 0:
            # Both columns filled — prefer the one with an explicit type marker,
            # otherwise take the larger value and infer from description
            if debit_type == "DEBIT":
                return debit_val, "DEBIT"
            if credit_type == "CREDIT":
                return credit_val, "CREDIT"
            if debit_val >= credit_val:
                return debit_val, self._type_from_description(description)
            return credit_val, self._type_from_description(description)

        # Both zero
        return Decimal("0"), self._type_from_description(description)

    def _type_from_description(self, description: str) -> str:
        upper = description.upper()
        return "CREDIT" if any(kw in upper for kw in self.CREDIT_KEYWORDS) else "DEBIT"
