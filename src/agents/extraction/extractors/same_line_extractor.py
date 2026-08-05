"""
same_line_extractor.py
======================
Extracts a Transaction from a single-line transaction record.

Many bank statements (especially older fixed-width exports and CSV-
derived PDFs) place all fields for one transaction on a single line,
separated by whitespace or tabs:

    01/05/2024  UPI/LANDLORD/RENTPAY  24,950.89  57,499.11
    14 May 2024  SWIGGY ORDER  1,353.06 DR  78,590.80 CR

Field inference strategy
------------------------
1.  Date  — the first token (or group of tokens) that parses as a date.
2.  Amounts — all monetary values on the line, collected in order.
3.  Balance — the last monetary value (rightmost).
4.  Amount  — the second-to-last monetary value.
             When only one value is found, it is treated as the amount
             and balance is left as None.
5.  Description — everything between the date and the first monetary
             value that is not purely numeric.
6.  Transaction type — inferred from DR/CR suffix on the amount token,
             then from description keywords.

This extractor intentionally avoids any positional assumptions.  It
works by semantic token roles, not column positions.
"""
from __future__ import annotations

import re
from decimal import Decimal

from src.agents.extraction.shared.amount_normalizer import parse_amount
from src.agents.extraction.shared.date_parser import parse_date
from src.schemas.transaction import Transaction

# Credit-keyword heuristic (same list used in other extractors)
_CREDIT_KEYWORDS = (
    "SALARY", "CREDIT", "REFUND", "INTEREST",
    "CASH DEPOSIT", "NEFT INWARD", "IMPS INWARD", "RTGS INWARD",
)

# Monetary token pattern (liberal — accepts DR/CR suffix)
_MONEY_TOKEN_RE = re.compile(
    r"[-₹]?\s*\d[\d,]*\.\d{2}"
    r"(?:\s*\(?\s*(?:DR|CR|Dr|Cr|Debit|Credit)\s*\)?)?",
    re.IGNORECASE,
)

# Boilerplate guard
_BOILERPLATE_RE = re.compile(
    r"statement of account|page \d+ of \d+|opening balance|closing balance"
    r"|customer name|system generated",
    re.IGNORECASE,
)


class SameLineExtractor:
    """
    Extracts a Transaction from a single-line record.

    Works with any line that begins with (or contains) a recognisable date
    followed by description text and at least one monetary value.
    """

    def can_handle(self, block: str) -> bool:
        """
        True when *block* is a single non-empty line containing both a
        date and at least one monetary value.
        """
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if len(lines) != 1:
            return False
        line = lines[0]
        if _BOILERPLATE_RE.search(line):
            return False
        has_date  = parse_date(line) is not None
        has_money = bool(_MONEY_TOKEN_RE.search(line))
        return has_date and has_money

    def extract(self, block: str) -> Transaction:
        line = block.strip()

        # ------------------------------------------------------------------
        # Tokenise the line
        # ------------------------------------------------------------------
        tokens = line.split()

        # ------------------------------------------------------------------
        # 1. Find the date — try 1-token first, then wider spans as fallback
        #    for named-month dates like "01 May 2024" (3 tokens).
        #    Use the narrowest successful match to leave as much text as
        #    possible for the description.
        # ------------------------------------------------------------------
        date_val   = None
        date_end   = 0

        for width in (1, 2, 3):
            if width > len(tokens):
                continue
            candidate = " ".join(tokens[:width])
            d = parse_date(candidate)
            if d is not None:
                # Only accept wider widths if the narrow one failed
                if date_val is None or width == 1:
                    date_val = d
                    date_end = width
                break

        # ------------------------------------------------------------------
        # 2. Find all monetary tokens and their positions
        # ------------------------------------------------------------------
        money_positions: list[tuple[int, str]] = []  # (token_index, raw_text)

        for idx, tok in enumerate(tokens):
            if _MONEY_TOKEN_RE.fullmatch(tok.strip()):
                money_positions.append((idx, tok))

        # ------------------------------------------------------------------
        # 3. Build description from tokens between date and first money token
        # ------------------------------------------------------------------
        if money_positions:
            first_money_idx = money_positions[0][0]
        else:
            first_money_idx = len(tokens)

        desc_tokens = [
            t for t in tokens[date_end:first_money_idx]
            if not _MONEY_TOKEN_RE.fullmatch(t.strip())
        ]
        description = " ".join(desc_tokens).strip()

        # ------------------------------------------------------------------
        # 4. Amount and balance
        # ------------------------------------------------------------------
        amount_raw  = None
        balance_raw = None
        txn_type    = None

        if len(money_positions) >= 2:
            # Second-to-last = amount, last = balance
            amount_raw  = money_positions[-2][1]
            balance_raw = money_positions[-1][1]
        elif len(money_positions) == 1:
            amount_raw = money_positions[0][1]

        amount_val = None
        balance_val = None

        if amount_raw:
            amount_val, txn_type = parse_amount(amount_raw)
            if amount_val is None:
                amount_val = _force_positive(amount_raw)

        if balance_raw:
            balance_val, _ = parse_amount(balance_raw)
            if balance_val is None:
                balance_val = _force_positive(balance_raw)

        # ------------------------------------------------------------------
        # 5. Transaction type
        # ------------------------------------------------------------------
        if txn_type is None and description:
            upper = description.upper()
            txn_type = "CREDIT" if any(
                kw in upper for kw in _CREDIT_KEYWORDS
            ) else "DEBIT"

        confidence = 0.9 if (date_val and description and amount_val) else 0.5

        return Transaction(
            transaction_date=date_val,
            description=description or "",
            amount=amount_val,
            balance=balance_val,
            transaction_type=txn_type or "DEBIT",
            confidence=confidence,
            reasoning="Parsed using same-line extractor.",
            source_text=block,
        )


def _force_positive(raw: str) -> Decimal | None:
    """
    Intentionally not used.

    This function was removed because it accepted bare integers (account
    numbers, reference numbers, etc.) as monetary values.  parse_amount()
    is the only path for amount parsing — it requires a decimal point.
    """
    return None
