from dataclasses import dataclass, field
from decimal import Decimal

from src.agents.analytics.analytics_agent import AnalyticsAgent
from src.agents.analytics.insights import FinancialInsights
from src.agents.qa.intent_detector import DetectedIntent, Intent
from src.agents.qa.transaction_query_engine import TransactionQueryEngine
from src.schemas.financial_report import FinancialReport
from src.schemas.transaction import Transaction


# ---------------------------------------------------------------------------
# Dispatch result value object
# ---------------------------------------------------------------------------

@dataclass
class DispatchResult:
    """
    Carries the raw result of a dispatched query so ResponseFormatter can
    render it without knowing anything about how it was computed.
    """

    intent: str

    # Scalar results
    amount: Decimal | None = None
    text: str | None = None

    # Primary transaction list
    transactions: list[Transaction] | None = None

    # Merchant refund / credit transactions (for context-aware responses).
    # Populated alongside MERCHANT_SPEND / MERCHANT_LIST when credits exist
    # from the same merchant (e.g. Amazon refund).
    refund_transactions: list[Transaction] = field(default_factory=list)

    # Named scalar bundle used by the financial summary renderer.
    # Keys: "income", "expense", "balance", "transaction_count"
    summary_amounts: dict[str, Decimal] = field(default_factory=dict)

    # Single-transaction list used by the financial summary renderer
    # to show the largest single expense.
    extra_transactions: list[Transaction] = field(default_factory=list)

    # Structured results
    category: str | None = None
    merchant: str | None = None
    category_amount_pairs: list[tuple[str, Decimal]] | None = None

    # Extended fields for new intents
    count: int | None = None
    payment_method: str | None = None
    percentage: Decimal | None = None
    balance_amount: Decimal | None = None


class QueryDispatcher:
    """
    Executes a DetectedIntent against a FinancialReport and returns a
    DispatchResult.

    Rules
    -----
    - All aggregate calculations are delegated to AnalyticsAgent.
    - Transaction filtering is delegated to TransactionQueryEngine.
    - String formatting is never done here — that is ResponseFormatter's job.
    """

    def __init__(self) -> None:
        self._analytics = AnalyticsAgent()
        self._insights  = FinancialInsights()
        self._engine    = TransactionQueryEngine()

    def dispatch(
        self,
        detected: DetectedIntent,
        report: FinancialReport,
    ) -> DispatchResult:

        txns   = report.transactions
        intent = detected.intent

        # ------------------------------------------------------------------
        # Balance variants
        # ------------------------------------------------------------------
        if intent == Intent.OPENING_BALANCE:
            return DispatchResult(
                intent=intent,
                amount=self._analytics.opening_balance(txns),
            )

        if intent == Intent.CLOSING_BALANCE:
            return DispatchResult(
                intent=intent,
                amount=self._analytics.closing_balance(txns),
            )

        if intent == Intent.HIGHEST_BALANCE:
            txn = self._analytics.highest_balance(txns)
            return DispatchResult(
                intent=intent,
                transactions=[txn] if txn else [],
                balance_amount=txn.balance if txn else None,
            )

        if intent == Intent.LOWEST_BALANCE:
            txn = self._analytics.lowest_balance(txns)
            return DispatchResult(
                intent=intent,
                transactions=[txn] if txn else [],
                balance_amount=txn.balance if txn else None,
            )

        if intent == Intent.BALANCE:
            return DispatchResult(
                intent=intent,
                amount=self._get_closing_balance(txns),
            )

        # ------------------------------------------------------------------
        # Largest credit / debit
        # ------------------------------------------------------------------
        if intent == Intent.LARGEST_CREDIT:
            txn = self._analytics.highest_income(txns)
            return DispatchResult(
                intent=intent,
                transactions=[txn] if txn else [],
            )

        if intent == Intent.LARGEST_DEBIT:
            txn = self._analytics.highest_expense(txns)
            return DispatchResult(
                intent=intent,
                transactions=[txn] if txn else [],
            )

        # ------------------------------------------------------------------
        # Transaction counts
        # ------------------------------------------------------------------
        if intent == Intent.TRANSACTION_COUNT:
            return DispatchResult(
                intent=intent,
                count=len(txns),
            )

        if intent == Intent.DEBIT_COUNT:
            debits = self._engine.debits(txns)
            return DispatchResult(
                intent=intent,
                count=len(debits),
            )

        if intent == Intent.CREDIT_COUNT:
            credits = self._engine.credits(txns)
            return DispatchResult(
                intent=intent,
                count=len(credits),
            )

        # ------------------------------------------------------------------
        # Date filtering
        # ------------------------------------------------------------------
        if intent == Intent.DATE_FILTER:
            filtered = self._apply_date_filter(detected, txns)
            return DispatchResult(
                intent=intent,
                transactions=filtered,
            )

        # ------------------------------------------------------------------
        # Amount filtering
        # ------------------------------------------------------------------
        if intent == Intent.AMOUNT_FILTER:
            if detected.amount_direction == "above" and detected.amount_threshold:
                filtered = self._engine.above_amount(
                    txns, detected.amount_threshold,
                )
            elif detected.amount_direction == "below" and detected.amount_threshold:
                filtered = self._engine.below_amount(
                    txns, detected.amount_threshold,
                )
            else:
                filtered = []
            return DispatchResult(
                intent=intent,
                transactions=filtered,
                text=detected.amount_direction,
                amount=Decimal(str(detected.amount_threshold)) if detected.amount_threshold else None,
            )

        # ------------------------------------------------------------------
        # First / Last transaction
        # ------------------------------------------------------------------
        if intent == Intent.FIRST_TRANSACTION:
            return DispatchResult(
                intent=intent,
                transactions=[txns[0]] if txns else [],
            )

        if intent == Intent.LAST_TRANSACTION:
            return DispatchResult(
                intent=intent,
                transactions=[txns[-1]] if txns else [],
            )

        # ------------------------------------------------------------------
        # Biggest transactions (top 5 by amount)
        # ------------------------------------------------------------------
        if intent == Intent.BIGGEST_TRANSACTIONS:
            sorted_txns = sorted(
                txns,
                key=lambda t: t.amount or Decimal("0"),
                reverse=True,
            )[:5]
            return DispatchResult(
                intent=intent,
                transactions=sorted_txns,
            )

        # ------------------------------------------------------------------
        # Merchant frequency
        # ------------------------------------------------------------------
        if intent == Intent.MERCHANT_FREQUENCY:
            matches = self._engine.search_description(
                txns, detected.merchant or "",
            )
            return DispatchResult(
                intent=intent,
                merchant=detected.merchant,
                count=len(matches),
                transactions=matches,
            )

        # ------------------------------------------------------------------
        # Payment method
        # ------------------------------------------------------------------
        if intent == Intent.PAYMENT_METHOD:
            method = detected.payment_method or ""
            matches = self._engine.by_payment_method(txns, method)
            # Compute total for debit transactions
            debit_matches = [t for t in matches if _is_debit(t)]
            total = sum(
                (t.amount for t in debit_matches if t.amount is not None),
                Decimal("0"),
            ) if debit_matches else None
            return DispatchResult(
                intent=intent,
                payment_method=method,
                transactions=matches,
                count=len(matches),
                amount=total,
            )

        # ------------------------------------------------------------------
        # Category percentage
        # ------------------------------------------------------------------
        if intent == Intent.CATEGORY_PERCENTAGE:
            if detected.category:
                percentages = self._analytics.spending_percentages(txns)
                pct = percentages.get(detected.category, Decimal("0"))
                return DispatchResult(
                    intent=intent,
                    category=detected.category,
                    percentage=pct,
                )
            # No specific category — show all percentages
            return DispatchResult(
                intent=intent,
                text=self._analytics.spending_distribution(txns),
            )

        # ------------------------------------------------------------------
        # Recommendations
        # ------------------------------------------------------------------
        if intent == Intent.RECOMMENDATIONS:
            return DispatchResult(
                intent=intent,
                text=self._analytics.generate_recommendations(txns),
            )

        # ------------------------------------------------------------------
        # Financial habits
        # ------------------------------------------------------------------
        if intent == Intent.FINANCIAL_HABITS:
            return DispatchResult(
                intent=intent,
                text=self._analytics.financial_habits_summary(txns),
            )

        # ------------------------------------------------------------------
        # Merchant frequency ranking (by count, not amount)
        # ------------------------------------------------------------------
        if intent == Intent.MERCHANT_FREQUENCY_RANKING:
            return DispatchResult(
                intent=intent,
                category_amount_pairs=self._analytics.merchant_frequency(txns),
            )

        # ------------------------------------------------------------------
        # Balance threshold — "did balance exceed X?"
        # ------------------------------------------------------------------
        if intent == Intent.BALANCE_THRESHOLD:
            threshold = detected.amount_threshold or 0
            direction = detected.amount_direction or "above"
            txns_with_balance = [t for t in txns if t.balance is not None]

            if not txns_with_balance:
                return DispatchResult(
                    intent=intent,
                    text="No balance information available.",
                    amount=Decimal(str(threshold)),
                )

            if direction == "above":
                highest = max(txns_with_balance, key=lambda t: t.balance)
                exceeded = highest.balance >= threshold
                return DispatchResult(
                    intent=intent,
                    text="yes" if exceeded else "no",
                    amount=Decimal(str(threshold)),
                    transactions=[highest],
                    balance_amount=highest.balance,
                )
            else:  # below
                lowest = min(txns_with_balance, key=lambda t: t.balance)
                went_below = lowest.balance <= threshold
                return DispatchResult(
                    intent=intent,
                    text="yes" if went_below else "no",
                    amount=Decimal(str(threshold)),
                    transactions=[lowest],
                    balance_amount=lowest.balance,
                )

        # ------------------------------------------------------------------
        # Balance after transaction
        # ------------------------------------------------------------------
        if intent == Intent.BALANCE_AFTER:
            q_lower = detected.raw.lower()
            # Find the referenced transaction
            target_txn = None

            # Check for common references
            if "salary" in q_lower:
                for t in txns:
                    if (t.category or "").lower() == "salary":
                        target_txn = t
                        break
            elif "largest debit" in q_lower or "biggest debit" in q_lower:
                target_txn = self._analytics.highest_expense(txns)
            elif "largest credit" in q_lower or "biggest credit" in q_lower:
                target_txn = self._analytics.highest_income(txns)
            elif "refund" in q_lower:
                for t in txns:
                    if (t.category or "").lower() == "refund" or "refund" in (t.description or "").lower():
                        target_txn = t
                        break
            else:
                # Try to find by merchant name or description keyword
                for t in txns:
                    desc = (t.description or "").lower()
                    # Extract key words from the query after "balance after"
                    if "balance after" in q_lower:
                        after_part = q_lower.split("balance after")[-1].strip()
                        # Remove common words
                        after_part = after_part.replace("my", "").replace("the", "").strip()
                        if after_part and after_part in desc:
                            target_txn = t
                            break

            if target_txn and target_txn.balance is not None:
                return DispatchResult(
                    intent=intent,
                    transactions=[target_txn],
                    balance_amount=target_txn.balance,
                )
            return DispatchResult(intent=intent)

        # ------------------------------------------------------------------
        # Aggregate analytics
        # ------------------------------------------------------------------
        if intent == Intent.TOTAL_SPEND:
            return DispatchResult(
                intent=intent,
                amount=self._analytics.total_expense(txns),
            )

        if intent == Intent.TOTAL_INCOME:
            return DispatchResult(
                intent=intent,
                amount=self._analytics.total_income(txns),
            )

        if intent == Intent.NET_CASH_FLOW:
            return DispatchResult(
                intent=intent,
                amount=self._analytics.net_cash_flow(txns),
            )

        if intent == Intent.LARGEST_EXPENSE:
            txn = self._analytics.highest_expense(txns)
            return DispatchResult(
                intent=intent,
                transactions=[txn] if txn else [],
            )

        # ------------------------------------------------------------------
        # Category-scoped
        # ------------------------------------------------------------------
        if intent == Intent.CATEGORY_NOT_FOUND:
            return DispatchResult(
                intent=intent,
                category=detected.category,
            )

        if intent == Intent.CATEGORY_SPEND:
            amount = self._analytics.category_total(txns, detected.category)
            # For "Rent" category, also search by description keyword
            # since pre-categorised transactions may have wrong category
            if (detected.category or "").lower() == "rent" and amount == 0:
                amount = sum(
                    (t.amount for t in txns
                     if _is_debit(t)
                     and any(kw in (t.description or "").lower()
                             for kw in ("rent", "landlord", "rentpay"))),
                    Decimal("0"),
                )
            return DispatchResult(
                intent=intent,
                amount=amount,
                category=detected.category,
            )

        if intent == Intent.CATEGORY_LIST:
            filtered = self._engine.by_category(txns, detected.category)
            # For "Refund" category, also match by description keyword
            # since pre-categorised transactions may have wrong category
            if (detected.category or "").lower() == "refund" and not filtered:
                filtered = [
                    t for t in txns
                    if "refund" in (t.description or "").lower()
                ]
            # For "Rent" category, also match by description keyword
            if (detected.category or "").lower() == "rent" and not filtered:
                filtered = [
                    t for t in txns
                    if any(kw in (t.description or "").lower()
                           for kw in ("rent", "landlord", "rentpay"))
                ]
            return DispatchResult(
                intent=intent,
                transactions=filtered,
                category=detected.category,
            )

        # ------------------------------------------------------------------
        # Merchant-scoped
        # ------------------------------------------------------------------
        if intent == Intent.MERCHANT_SPEND:
            matches = self._engine.search_description(txns, detected.merchant)
            debits  = [t for t in matches if _is_debit(t)]
            credits = [t for t in matches if _is_credit(t)]
            total   = sum((t.amount for t in debits), Decimal("0"))
            return DispatchResult(
                intent=intent,
                amount=total,
                merchant=detected.merchant,
                refund_transactions=credits,
            )

        if intent == Intent.MERCHANT_LIST:
            matches = self._engine.search_description(txns, detected.merchant)
            credits = [t for t in matches if _is_credit(t)]
            return DispatchResult(
                intent=intent,
                transactions=matches,
                merchant=detected.merchant,
                refund_transactions=credits,
            )

        # ------------------------------------------------------------------
        # Analytics intelligence
        # ------------------------------------------------------------------
        if intent == Intent.SPENDING_SUMMARY:
            return DispatchResult(
                intent=intent,
                category_amount_pairs=sorted(
                    self._analytics.category_totals(txns).items(),
                    key=lambda item: item[1],
                    reverse=True,
                ),
                amount=self._analytics.total_expense(txns),
            )

        if intent == Intent.TOP_MERCHANTS:
            return DispatchResult(
                intent=intent,
                category_amount_pairs=self._analytics.top_merchants(txns),
            )

        if intent == Intent.RECURRING:
            return DispatchResult(
                intent=intent,
                text=self._analytics.recurring_summary(txns),
            )

        if intent == Intent.SPENDING_DIST:
            return DispatchResult(
                intent=intent,
                text=self._analytics.spending_distribution(txns),
            )

        if intent == Intent.BUDGET_HEALTH:
            return DispatchResult(
                intent=intent,
                text=self._analytics.budget_health(txns),
            )

        if intent == Intent.LARGEST_CATEGORY:
            result = self._analytics.largest_spending_category(txns)
            if result is None:
                return DispatchResult(intent=intent)
            cat, amount = result
            return DispatchResult(intent=intent, category=cat, amount=amount)

        if intent == Intent.FINANCIAL_INSIGHTS:
            # Gather everything the rich summary needs in one pass.
            income  = self._analytics.total_income(txns)
            expense = self._analytics.total_expense(txns)
            balance = self._get_closing_balance(txns)
            largest = self._analytics.highest_expense(txns)
            top_cat = self._analytics.largest_spending_category(txns)
            dist    = sorted(
                self._analytics.category_totals(txns).items(),
                key=lambda item: item[1],
                reverse=True,
            )
            return DispatchResult(
                intent=intent,
                summary_amounts={
                    "income":            income,
                    "expense":           expense,
                    "balance":           balance or Decimal("0"),
                    "transaction_count": Decimal(str(len(txns))),
                },
                extra_transactions=[largest] if largest else [],
                category_amount_pairs=dist,
                category=top_cat[0] if top_cat else None,
                amount=top_cat[1]   if top_cat else None,
            )

        # ------------------------------------------------------------------
        # Refund total — prioritize category, fallback to description
        # ------------------------------------------------------------------
        if intent == Intent.REFUND_TOTAL:
            # First try to find by category
            refund_txns = [
                t for t in txns
                if _is_credit(t)
                and (t.category or "").lower() == "refund"
            ]
            # If no category matches, fall back to description keyword
            if not refund_txns:
                refund_txns = [
                    t for t in txns
                    if _is_credit(t)
                    and "refund" in (t.description or "").lower()
                ]
            total = sum(
                (t.amount for t in refund_txns),
                Decimal("0"),
            )
            return DispatchResult(
                intent=intent,
                amount=total,
                transactions=refund_txns,
            )

        # ------------------------------------------------------------------
        # Unknown fallback
        # ------------------------------------------------------------------
        return DispatchResult(intent=Intent.UNKNOWN)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_closing_balance(
        transactions: list[Transaction],
    ) -> Decimal | None:
        for txn in reversed(transactions):
            if txn.balance is not None:
                return txn.balance
        return None

    def _apply_date_filter(
        self,
        detected: DetectedIntent,
        txns: list[Transaction],
    ) -> list[Transaction]:
        ft = detected.date_filter_type
        if ft == "on":
            return self._engine.by_date_on(txns, detected.date_from or "")
        if ft == "between":
            return self._engine.by_date_between(
                txns, detected.date_from or "", detected.date_to or "",
            )
        if ft == "after":
            return self._engine.by_date_after(txns, detected.date_from or "")
        if ft == "before":
            return self._engine.by_date_before(txns, detected.date_from or "")
        return []


# ---------------------------------------------------------------------------
# Module-level helpers (pure functions, no state)
# ---------------------------------------------------------------------------

def _is_debit(txn: Transaction) -> bool:
    return (txn.transaction_type or "").upper() == "DEBIT"


def _is_credit(txn: Transaction) -> bool:
    return (txn.transaction_type or "").upper() == "CREDIT"
