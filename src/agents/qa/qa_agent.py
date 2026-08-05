from src.agents.qa.intent_detector import (
    IntentDetector,
    CATEGORY_ALIASES,
    _PAYMENT_METHODS,
)
from src.agents.qa.query_dispatcher import QueryDispatcher
from src.agents.qa.question_normalizer import QuestionNormalizer
from src.agents.qa.response_formatter import ResponseFormatter
from src.agents.qa.formatters import fmt_date, fmt_inr, normalize_merchant
from src.schemas.financial_report import FinancialReport
from src.schemas.transaction import Transaction


# ---------------------------------------------------------------------------
# Entity keywords — when present in a follow-up-like question, the query
# references a specific entity and must be resolved via intent detection,
# NOT conversation memory.
# ---------------------------------------------------------------------------

_ENTITY_KEYWORDS: frozenset[str] = frozenset(
    # Category names (lowercased)
    (name.lower() for name in CATEGORY_ALIASES)
) | frozenset(
    # Category aliases — only unambiguous ones
    [
        "salary", "refund", "rent", "interest", "emi",
        "landlord", "payroll", "rentpay", "rental",
    ]
    # Payment method names and keywords
    + [m.lower() for m in _PAYMENT_METHODS]
    + [kw for kws in _PAYMENT_METHODS.values() for kw in kws]
    # Common transaction type references
    + ["rtgs", "neft", "imps", "atm", "pos", "upi", "cash", "credit", "debit"]
)


# Phrases that indicate a follow-up to a previous answer
_FOLLOWUP_PHRASES = (
    "when did it happen",
    "when was it",
    "when did this happen",
    "who was it",
    "who was it paid to",
    "who was it to",
    "who did i pay",
    "who paid me",
    "who sent it",
    "who sent me",
    "what category",
    "what category was it",
    "what was my balance",
    "balance after that",
    "balance after",
    "explain that transaction",
    "explain it",
    "tell me more",
    "more details",
    "details about it",
    "what was the amount",
    "how much was it",
    "what was the date",
    "what was the merchant",
    "when did i receive it",
    "when did i get it",
    "when was it received",
    "when was it credited",
)


class QAAgent:
    """
    Answers user questions about a FinancialReport.

    Pipeline
    --------
    raw question
        → QuestionNormalizer   (clean / lowercase)
        → IntentDetector       (what does the user want + slots)
        → QueryDispatcher      (compute the answer via analytics / query engine)
        → ResponseFormatter    (render to human-readable string)

    Conversation Memory
    -------------------
    The last discussed transaction is remembered so follow-up questions
    like "when did it happen?" or "what category?" can be resolved.
    """

    def __init__(self) -> None:
        self._normalizer  = QuestionNormalizer()
        self._detector    = IntentDetector()
        self._dispatcher  = QueryDispatcher()
        self._formatter   = ResponseFormatter()
        self._last_txn: Transaction | None = None

    def answer(
        self,
        report: FinancialReport,
        question: str,
    ) -> str:
        """
        Return a natural-language answer to *question* using *report*.

        Public API is identical to the previous implementation:
            str  →  str
        """

        if not question or not question.strip():
            return "Please ask a question."

        normalised = self._normalizer.normalize(question)

        # Check for follow-up questions referencing previous context.
        # Skip when the question references a specific entity (category,
        # payment method, merchant) — those must be resolved via intent
        # detection, not conversation memory.
        if (
            self._is_followup(normalised)
            and self._last_txn is not None
            and not self._has_entity_reference(normalised)
        ):
            followup = self._handle_followup(normalised)
            if followup:
                return followup

        detected   = self._detector.detect(normalised)
        result     = self._dispatcher.dispatch(detected, report)

        # Remember transaction for follow-up conversation
        if result.transactions:
            self._last_txn = result.transactions[0]
        elif result.extra_transactions:
            self._last_txn = result.extra_transactions[0]

        return self._formatter.format(result)

    def clear_memory(self) -> None:
        """Clear conversation memory."""
        self._last_txn = None

    @staticmethod
    def _is_followup(normalised: str) -> bool:
        """Check if the question is a follow-up to a previous answer."""
        q = normalised.strip()
        return any(p in q for p in _FOLLOWUP_PHRASES)

    @staticmethod
    def _has_entity_reference(normalised: str) -> bool:
        """Return True when the question references a specific entity
        (category, payment method, or transaction type) and should
        therefore be resolved via intent detection rather than
        conversation memory."""
        q = normalised.strip()
        return any(kw in q for kw in _ENTITY_KEYWORDS)

    def _handle_followup(self, normalised: str) -> str | None:
        """Resolve a follow-up question using the remembered transaction."""
        txn = self._last_txn
        if txn is None:
            return None

        q = normalised.strip()
        merchant = normalize_merchant(txn.description or "")

        if any(p in q for p in (
            "when did it happen", "when was it",
            "when did this happen", "what was the date",
            "when did i receive it", "when did i get it",
            "when was it received", "when was it credited",
        )):
            return (
                f"That transaction happened on "
                f"{fmt_date(txn.transaction_date)}."
            )

        if any(p in q for p in (
            "who was it", "who was it paid to",
            "who was it to", "who did i pay",
            "who paid me", "who sent it", "who sent me",
            "what was the merchant",
        )):
            return (
                f"It was paid to {merchant}."
            )

        if any(p in q for p in (
            "what category", "what category was it",
        )):
            cat = txn.category or "Uncategorized"
            return (
                f"That transaction was categorised as {cat}."
            )

        if any(p in q for p in (
            "what was my balance", "balance after that", "balance after",
        )):
            if txn.balance is not None:
                return (
                    f"Your balance after that transaction was "
                    f"{fmt_inr(txn.balance)}."
                )
            return "No balance information available for that transaction."

        if any(p in q for p in (
            "what was the amount", "how much was it",
        )):
            return (
                f"The amount was {fmt_inr(txn.amount)}."
            )

        if any(p in q for p in (
            "explain that transaction", "explain it",
            "tell me more", "more details", "details about it",
        )):
            txn_type = (txn.transaction_type or "Unknown").upper()
            return (
                f"Transaction Details\n\n"
                f"Date        : {fmt_date(txn.transaction_date)}\n"
                f"Description : {txn.description or 'Unknown'}\n"
                f"Merchant    : {merchant}\n"
                f"Amount      : {fmt_inr(txn.amount)}\n"
                f"Type        : {txn_type}\n"
                f"Category    : {txn.category or 'Uncategorized'}"
                + (
                    f"\nBalance     : {fmt_inr(txn.balance)}"
                    if txn.balance is not None else ""
                )
            )

        return None
