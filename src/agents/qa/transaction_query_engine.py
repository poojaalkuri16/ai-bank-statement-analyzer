from collections.abc import Iterable
from datetime import date

from src.schemas.transaction import Transaction


# Month abbreviation → number mapping
_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_date_str(date_str: str) -> date | None:
    """Parse 'DD Mon' or 'DD Mon YYYY' to a date object."""
    parts = date_str.strip().split()
    if len(parts) < 2:
        return None
    try:
        day = int(parts[0])
        month = _MONTH_MAP.get(parts[1].lower()[:3])
        if month is None:
            return None
        year = int(parts[2]) if len(parts) > 2 else 2024
        return date(year, month, day)
    except (ValueError, IndexError):
        return None


class TransactionQueryEngine:
    """
    Provides reusable transaction filtering and search operations.
    """

    def all_transactions(
        self,
        transactions: Iterable[Transaction],
    ) -> list[Transaction]:
        return list(transactions)

    def credits(
        self,
        transactions: Iterable[Transaction],
    ) -> list[Transaction]:
        return [
            txn
            for txn in transactions
            if (txn.transaction_type or "").upper() == "CREDIT"
        ]

    def debits(
        self,
        transactions: Iterable[Transaction],
    ) -> list[Transaction]:
        return [
            txn
            for txn in transactions
            if (txn.transaction_type or "").upper() == "DEBIT"
        ]

    def above_amount(
        self,
        transactions: Iterable[Transaction],
        amount: float,
    ) -> list[Transaction]:
        return [
            txn
            for txn in transactions
            if txn.amount is not None
            and float(txn.amount) > amount
        ]

    def below_amount(
        self,
        transactions: Iterable[Transaction],
        amount: float,
    ) -> list[Transaction]:
        return [
            txn
            for txn in transactions
            if txn.amount is not None
            and float(txn.amount) < amount
        ]

    def between_amounts(
        self,
        transactions: Iterable[Transaction],
        minimum: float,
        maximum: float,
    ) -> list[Transaction]:
        return [
            txn
            for txn in transactions
            if txn.amount is not None
            and minimum <= float(txn.amount) <= maximum
        ]

    def search_description(
        self,
        transactions: Iterable[Transaction],
        keyword: str,
    ) -> list[Transaction]:
        """
        Searches transaction descriptions using keyword matching.
        A transaction matches only if every keyword is present.
        """

        words = [
            word.lower()
            for word in keyword.split()
            if word.strip()
        ]

        if not words:
            return []

        matches: list[Transaction] = []

        for txn in transactions:

            if not txn.description:
                continue

            description = txn.description.lower()

            if all(word in description for word in words):
                matches.append(txn)

        return matches

    def by_category(
        self,
        transactions: Iterable[Transaction],
        category: str,
    ) -> list[Transaction]:
        """
        Returns transactions belonging to a category.
        """

        category = category.lower()

        return [
            txn
            for txn in transactions
            if txn.category
            and txn.category.lower() == category
        ]

    def by_date_on(
        self,
        transactions: Iterable[Transaction],
        date_str: str,
    ) -> list[Transaction]:
        """Return transactions on a specific date."""
        target = _parse_date_str(date_str)
        if target is None:
            return []
        return [
            t for t in transactions
            if t.transaction_date is not None
            and t.transaction_date.day == target.day
            and t.transaction_date.month == target.month
        ]

    def by_date_between(
        self,
        transactions: Iterable[Transaction],
        from_str: str,
        to_str: str,
    ) -> list[Transaction]:
        """Return transactions between two dates (inclusive)."""
        d_from = _parse_date_str(from_str)
        d_to   = _parse_date_str(to_str)
        if d_from is None or d_to is None:
            return []
        return [
            t for t in transactions
            if t.transaction_date is not None
            and d_from <= t.transaction_date <= d_to
        ]

    def by_date_after(
        self,
        transactions: Iterable[Transaction],
        date_str: str,
    ) -> list[Transaction]:
        """Return transactions after a date."""
        target = _parse_date_str(date_str)
        if target is None:
            return []
        return [
            t for t in transactions
            if t.transaction_date is not None
            and t.transaction_date > target
        ]

    def by_date_before(
        self,
        transactions: Iterable[Transaction],
        date_str: str,
    ) -> list[Transaction]:
        """Return transactions before a date."""
        target = _parse_date_str(date_str)
        if target is None:
            return []
        return [
            t for t in transactions
            if t.transaction_date is not None
            and t.transaction_date < target
        ]

    def by_payment_method(
        self,
        transactions: Iterable[Transaction],
        method: str,
    ) -> list[Transaction]:
        """
        Return transactions matching a payment method.

        Matches against the transaction mode field AND the description
        (since many bank statements embed the payment method in the
        narration, e.g. "UPI/SWIGGY/ORDERPAY").

        For POS, uses word-boundary matching to avoid false positives
        like "POSTPAID" matching "POS".

        Resolves canonical payment method names (e.g. "Cash Withdrawal")
        to their individual keywords so that description matching works
        for every variant, not just the canonical name.
        """
        from src.agents.qa.intent_detector import _PAYMENT_METHODS

        method_upper = method.upper()

        # Build the set of uppercase keywords to match against.
        # If the caller passed a canonical name (e.g. "Cash Withdrawal"),
        # resolve it to its keyword list.  Otherwise treat the method
        # string itself as a single keyword.
        keywords_upper: list[str] = []
        for canonical, kws in _PAYMENT_METHODS.items():
            if canonical.upper() == method_upper:
                keywords_upper = [kw.upper() for kw in kws]
                break
        if not keywords_upper:
            keywords_upper = [method_upper]

        result: list[Transaction] = []
        for txn in transactions:
            # Check mode field
            if txn.mode and txn.mode.upper() == method_upper:
                result.append(txn)
                continue
            # Check description for any payment method keyword
            desc = (txn.description or "").upper()

            # Special handling for POS to avoid "POSTPAID" false positive
            if method_upper == "POS":
                # Match "POS " at start, " POS " in middle, or at end
                if (desc.startswith("POS ") or
                    " POS " in desc or
                    desc.endswith(" POS")):
                    result.append(txn)
            else:
                if any(kw in desc for kw in keywords_upper):
                    result.append(txn)
        return result