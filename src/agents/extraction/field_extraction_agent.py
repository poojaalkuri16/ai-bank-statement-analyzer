"""
field_extraction_agent.py
=========================
Routes each transaction block to the most appropriate parser and
returns a normalised Transaction object.

Parser registry
---------------
Parsers are tried in priority order.  Each parser exposes a
``can_handle(block: str) -> bool`` probe; the first parser that
accepts the block is used.

Priority
  1. TableRowExtractor    — canonical 4-line block (date / desc / amt / bal)
  2. KeyValueBlockExtractor — labelled key-value block (Txn Date: …)
  3. SameLineExtractor    — single-line record (date + desc + amt [+ bal])
  4. SemanticExtractor    — generic fallback using individual field extractors

Extending
---------
To add support for a new layout, create a new extractor class with
``can_handle()`` and ``extract()`` methods and add it to the PARSERS
list in ``FieldExtractionAgent.__init__``.  No other code needs to
change.
"""
from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from src.agents.extraction.extractors.amount_extractor import AmountExtractor
from src.agents.extraction.extractors.balance_extractor import BalanceExtractor
from src.agents.extraction.extractors.date_extractor import DateExtractor
from src.agents.extraction.extractors.description_extractor import (
    DescriptionExtractor,
)
from src.agents.extraction.extractors.key_value_block_extractor import (
    KeyValueBlockExtractor,
)
from src.agents.extraction.extractors.same_line_extractor import (
    SameLineExtractor,
)
from src.agents.extraction.extractors.table_row_extractor import (
    TableRowExtractor,
)
from decimal import Decimal
from src.agents.normalization.transaction_normalizer import TransactionNormalizer
from src.schemas.transaction import Transaction


# ---------------------------------------------------------------------------
# Parser interface
# ---------------------------------------------------------------------------

@runtime_checkable
class TransactionParser(Protocol):
    """
    Structural protocol every parser must satisfy.

    can_handle(block) — True when this parser can reliably extract
                        fields from *block*.
    extract(block)    — Return a Transaction (may have None fields
                        if parsing is partial).
    """

    def can_handle(self, block: str) -> bool: ...
    def extract(self, block: str) -> Transaction: ...


# ---------------------------------------------------------------------------
# Semantic fallback extractor (wraps the individual field extractors)
# ---------------------------------------------------------------------------

class SemanticExtractor:
    """
    Generic fallback that assembles a Transaction from the outputs of
    the individual DateExtractor, DescriptionExtractor, AmountExtractor,
    and BalanceExtractor.

    Accepts any block (can_handle always returns True) and is used last.
    """

    def __init__(self) -> None:
        self._date        = DateExtractor()
        self._description = DescriptionExtractor()
        self._amount      = AmountExtractor()
        self._balance     = BalanceExtractor()

    def can_handle(self, block: str) -> bool:  # noqa: ARG002
        return True  # always accepts as the final fallback

    def extract(self, block: str, last_balance: Decimal | None = None) -> Transaction:
        date_r = self._date.extract(block)
        desc_r = self._description.extract(block)

        # Retrieve candidates directly from detector
        amt_candidates = self._amount.detector.detect(block)
        bal_candidates = self._balance.detector.detect(block)

        best_amt = None
        best_bal = None
        txn_type = None
        reasoning_addition = ""

        if last_balance is not None:
            for amt_c in amt_candidates:
                for bal_c in bal_candidates:
                    # Avoid matching a candidate with itself at the same line with same value
                    if amt_c.line_number == bal_c.line_number and amt_c.value == bal_c.value:
                        continue
                    if abs(bal_c.value - last_balance) == abs(amt_c.value):
                        best_amt = amt_c
                        best_bal = bal_c
                        best_amt.confidence = 1.0
                        best_bal.confidence = 1.0
                        txn_type = "CREDIT" if bal_c.value >= last_balance else "DEBIT"
                        reasoning_addition = f"Derived amount {amt_c.value} and balance {bal_c.value} from balance difference check (last balance: {last_balance})."
                        break
                if best_amt is not None:
                    break

        if best_amt is not None and best_bal is not None:
            amt_val = best_amt.value
            bal_val = best_bal.value
            amt_reasoning = f"Matched via running balance difference: {best_amt.raw_text}"
            bal_reasoning = f"Matched via running balance difference: {best_bal.raw_text}"
            confidence = min(date_r.confidence, desc_r.confidence, 1.0)
        else:
            # Fall back to standard individual extraction
            amt_r  = self._amount.extract(block)
            bal_r  = self._balance.extract(block)
            amt_val = amt_r.value
            bal_val = bal_r.value
            amt_reasoning = amt_r.reasoning
            bal_reasoning = bal_r.reasoning
            confidence = min(
                date_r.confidence,
                desc_r.confidence,
                amt_r.confidence,
                bal_r.confidence,
            )

        return Transaction(
            transaction_date=date_r.value,
            description=desc_r.value or "",
            amount=amt_val,
            balance=bal_val,
            transaction_type=txn_type,
            confidence=confidence,
            reasoning="\n".join(filter(None, [
                date_r.reasoning,
                desc_r.reasoning,
                amt_reasoning,
                bal_reasoning,
                reasoning_addition,
            ])),
        )


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

class FieldExtractionAgent:
    """
    Routes each transaction block to the correct parser via a priority-
    ordered registry.

    All parsers produce the same Transaction schema so downstream code
    never needs to know which parser was used.
    """

    def __init__(self) -> None:

        self.normalizer = TransactionNormalizer()
        self.last_balance: Decimal | None = None

        # Ordered list of parsers — first match wins
        self._parsers: list[TransactionParser] = [
            TableRowExtractor(),
            KeyValueBlockExtractor(),
            SameLineExtractor(),
            SemanticExtractor(),   # must be last (always accepts)
        ]

    def reset(self) -> None:
        """Reset running state for a new document run."""
        self.last_balance = None

    def register_parser(
        self,
        parser: TransactionParser,
        priority: int = 0,
    ) -> None:
        """
        Insert *parser* at *priority* position in the registry.
        Lower index = higher priority.  The SemanticExtractor fallback
        is always kept last regardless of priority.

        Parameters
        ----------
        parser   : any object satisfying the TransactionParser protocol
        priority : insertion position (0 = highest priority)
        """
        # Keep SemanticExtractor last
        fallback = self._parsers.pop()
        self._parsers.insert(priority, parser)
        self._parsers.append(fallback)

    def extract(self, transaction_block: str) -> Transaction:
        """
        Extract and normalise a Transaction from *transaction_block*.

        Tries each registered parser in order; uses the first one whose
        can_handle() returns True.
        """
        for parser in self._parsers:
            if parser.can_handle(transaction_block):
                if isinstance(parser, SemanticExtractor):
                    txn = parser.extract(transaction_block, last_balance=self.last_balance)
                else:
                    txn = parser.extract(transaction_block)
                
                normalized = self.normalizer.normalize(txn)
                
                # Correct transaction type based on running balance change if both are available
                if self.last_balance is not None and normalized.balance is not None:
                    diff = normalized.balance - self.last_balance
                    if diff > 0:
                        normalized.transaction_type = "CREDIT"
                    elif diff < 0:
                        normalized.transaction_type = "DEBIT"
                
                if normalized.balance is not None:
                    self.last_balance = normalized.balance
                return normalized

        # Should never reach here (SemanticExtractor always accepts)
        raise RuntimeError(
            "No parser could handle block:\n"
            f"{transaction_block!r}"
        )
