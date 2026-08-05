"""
transaction_validator.py
========================
Validates extracted Transaction objects before they enter analytics.

Every transaction must have:
  - A valid date
  - A non-empty description
  - A non-negative amount > 0  (zero is rejected unless explicitly
    produced by the source, but since we never replace parse failures
    with zero, any zero here is suspicious)
  - A transaction type (DEBIT or CREDIT)

Optional:
  - balance

Invalid transactions are logged with a structured reason and skipped.
Valid transactions are returned unchanged.
"""
from __future__ import annotations

import logging

from src.schemas.transaction import Transaction

logger = logging.getLogger(__name__)


class TransactionValidator:
    """
    Filters a list of Transaction objects, keeping only those that
    pass every required-field check.

    Usage
    -----
    validator = TransactionValidator()
    good, skipped = validator.validate_all(raw_transactions)
    """

    def validate(self, txn: Transaction) -> tuple[bool, str]:
        """
        Return (True, "") when *txn* passes all checks.
        Return (False, reason) when a required field is missing.
        """
        if txn.transaction_date is None:
            return False, "missing transaction_date"

        if not (txn.description or "").strip():
            return False, "missing description"

        if txn.amount is None:
            return False, "missing amount"

        if txn.amount < 0:
            # Should never happen after amount normalisation, but guard anyway
            return False, f"negative amount: {txn.amount}"

        if txn.amount == 0:
            # Zero only appears when a parse attempt produced no real value.
            # Genuinely zero-value transactions do not appear in bank statements.
            return False, "amount is zero (likely a parse failure or empty column)"

        if txn.transaction_type not in ("DEBIT", "CREDIT"):
            return False, (
                f"invalid transaction_type: {txn.transaction_type!r} "
                f"(expected DEBIT or CREDIT)"
            )

        return True, ""

    def validate_all(
        self,
        transactions: list[Transaction],
    ) -> tuple[list[Transaction], list[dict]]:
        """
        Validate every transaction.

        Returns
        -------
        valid   : list of transactions that passed validation
        skipped : list of dicts describing each rejected transaction
        """
        valid: list[Transaction] = []
        skipped: list[dict] = []

        for txn in transactions:
            ok, reason = self.validate(txn)

            if ok:
                valid.append(txn)
            else:
                record = {
                    "reason":      reason,
                    "date":        str(txn.transaction_date),
                    "description": (txn.description or "")[:60],
                    "amount":      str(txn.amount),
                    "type":        txn.transaction_type,
                }
                skipped.append(record)
                logger.warning(
                    "Transaction rejected — %s | %s | %s | %s",
                    reason,
                    record["date"],
                    record["description"],
                    record["amount"],
                )

        if skipped:
            logger.info(
                "Validation complete: %d accepted, %d rejected.",
                len(valid),
                len(skipped),
            )

        return valid, skipped
