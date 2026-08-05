from decimal import Decimal

from src.agents.qa.formatters import fmt_date, fmt_inr, normalize_merchant
from src.agents.qa.intent_detector import Intent
from src.agents.qa.query_dispatcher import DispatchResult
from src.agents.qa.transaction_formatter import TransactionFormatter


class ResponseFormatter:
    """
    Converts a DispatchResult into a polished, human-readable string.

    Responsibilities
    ----------------
    - Render every intent into natural-language output with proper Indian
      rupee formatting, readable dates, and clean merchant names.
    - Delegate transaction list rendering to TransactionFormatter.
    - Never perform computation — only presentation.

    Formatting conventions
    ----------------------
    - Amounts use fmt_inr()  →  ₹85,743.56
    - Dates use fmt_date()   →  09 May 2024
    - Merchant names are normalised via normalize_merchant()
    - Numbered lists for multi-item responses (spending summary, merchants)
    - Existing header strings are preserved exactly so downstream tests pass
    """

    def __init__(self) -> None:
        self._txn_fmt = TransactionFormatter()

    def format(self, result: DispatchResult) -> str:  # noqa: A003
        intent = result.intent

        # ------------------------------------------------------------------
        # Balance variants
        # ------------------------------------------------------------------
        if intent == Intent.OPENING_BALANCE:
            if result.amount is None:
                return "No opening balance information found."
            return (
                f"Your opening balance is "
                f"{fmt_inr(result.amount)}."
            )

        if intent == Intent.CLOSING_BALANCE:
            if result.amount is None:
                return "No closing balance information found."
            return (
                f"Your closing balance is "
                f"{fmt_inr(result.amount)}."
            )

        if intent == Intent.HIGHEST_BALANCE:
            if not result.transactions:
                return "No balance information found."
            txn = result.transactions[0]
            return (
                f"Your highest balance was "
                f"{fmt_inr(txn.balance)}.\n\n"
                f"Date        : {fmt_date(txn.transaction_date)}\n"
                f"Transaction : {txn.description or 'Unknown'}\n"
                f"Amount      : {fmt_inr(txn.amount)}"
            )

        if intent == Intent.LOWEST_BALANCE:
            if not result.transactions:
                return "No balance information found."
            txn = result.transactions[0]
            return (
                f"Your lowest balance was "
                f"{fmt_inr(txn.balance)}.\n\n"
                f"Date        : {fmt_date(txn.transaction_date)}\n"
                f"Transaction : {txn.description or 'Unknown'}\n"
                f"Amount      : {fmt_inr(txn.amount)}"
            )

        if intent == Intent.BALANCE:
            if result.amount is None:
                return "No balance information found."
            return (
                f"Your current account balance is "
                f"{fmt_inr(result.amount)}."
            )

        # ------------------------------------------------------------------
        # Largest credit / debit
        # ------------------------------------------------------------------
        if intent == Intent.LARGEST_CREDIT:
            if not result.transactions:
                return "No credit transactions found."
            txn = result.transactions[0]
            merchant = normalize_merchant(txn.description or "")
            return (
                f"Your largest credit:\n\n"
                f"Date      : {fmt_date(txn.transaction_date)}\n"
                f"Merchant  : {merchant}\n"
                f"Amount    : {fmt_inr(txn.amount)}\n"
                f"Category  : {txn.category or 'Uncategorized'}"
            )

        if intent == Intent.LARGEST_DEBIT:
            if not result.transactions:
                return "No debit transactions found."
            txn = result.transactions[0]
            merchant = normalize_merchant(txn.description or "")
            return (
                f"Your largest debit:\n\n"
                f"Date      : {fmt_date(txn.transaction_date)}\n"
                f"Merchant  : {merchant}\n"
                f"Amount    : {fmt_inr(txn.amount)}\n"
                f"Category  : {txn.category or 'Uncategorized'}"
                + (
                    f"\nBalance   : {fmt_inr(txn.balance)}"
                    if txn.balance is not None else ""
                )
            )

        # ------------------------------------------------------------------
        # Aggregate analytics
        # ------------------------------------------------------------------
        if intent == Intent.TOTAL_SPEND:
            return (
                f"You spent {fmt_inr(result.amount)} "
                f"during this statement period."
            )

        if intent == Intent.TOTAL_INCOME:
            return (
                f"Your total income is {fmt_inr(result.amount)}."
            )

        if intent == Intent.NET_CASH_FLOW:
            return (
                f"Your net cash flow is {fmt_inr(result.amount)}."
            )

        if intent == Intent.LARGEST_EXPENSE:
            if not result.transactions:
                return "No expense transactions found."
            txn = result.transactions[0]
            merchant = normalize_merchant(txn.description or "")
            return (
                f"Your largest single expense:\n\n"
                f"Date      : {fmt_date(txn.transaction_date)}\n"
                f"Merchant  : {merchant}\n"
                f"Amount    : {fmt_inr(txn.amount)}\n"
                f"Category  : {txn.category or 'Uncategorized'}"
                + (
                    f"\nBalance   : {fmt_inr(txn.balance)}"
                    if txn.balance is not None else ""
                )
            )

        # ------------------------------------------------------------------
        # Transaction counts
        # ------------------------------------------------------------------
        if intent == Intent.TRANSACTION_COUNT:
            return (
                f"There are {result.count} transactions "
                f"in this statement."
            )

        if intent == Intent.DEBIT_COUNT:
            return (
                f"There are {result.count} debit transactions "
                f"in this statement."
            )

        if intent == Intent.CREDIT_COUNT:
            return (
                f"There are {result.count} credit transactions "
                f"in this statement."
            )

        # ------------------------------------------------------------------
        # Date filtering
        # ------------------------------------------------------------------
        if intent == Intent.DATE_FILTER:
            if not result.transactions:
                return "No transactions found for the specified date range."
            header = "Transactions matching your date filter:\n\n"
            return header + self._txn_fmt.format(result.transactions)

        # ------------------------------------------------------------------
        # Amount filtering
        # ------------------------------------------------------------------
        if intent == Intent.AMOUNT_FILTER:
            if not result.transactions:
                direction = result.text or "specified"
                threshold = result.amount or 0
                return (
                    f"No transactions found {direction} "
                    f"{fmt_inr(threshold)}."
                )
            direction = result.text or "matching"
            threshold = result.amount or 0
            header = (
                f"Transactions {direction} {fmt_inr(threshold)}:\n\n"
            )
            return header + self._txn_fmt.format(result.transactions)

        # ------------------------------------------------------------------
        # First / Last transaction
        # ------------------------------------------------------------------
        if intent == Intent.FIRST_TRANSACTION:
            if not result.transactions:
                return "No transactions found."
            txn = result.transactions[0]
            merchant = normalize_merchant(txn.description or "")
            return (
                f"First transaction in the statement:\n\n"
                f"Date      : {fmt_date(txn.transaction_date)}\n"
                f"Merchant  : {merchant}\n"
                f"Amount    : {fmt_inr(txn.amount)}\n"
                f"Type      : {(txn.transaction_type or 'Unknown').upper()}"
                + (
                    f"\nBalance   : {fmt_inr(txn.balance)}"
                    if txn.balance is not None else ""
                )
            )

        if intent == Intent.LAST_TRANSACTION:
            if not result.transactions:
                return "No transactions found."
            txn = result.transactions[0]
            merchant = normalize_merchant(txn.description or "")
            return (
                f"Last transaction in the statement:\n\n"
                f"Date      : {fmt_date(txn.transaction_date)}\n"
                f"Merchant  : {merchant}\n"
                f"Amount    : {fmt_inr(txn.amount)}\n"
                f"Type      : {(txn.transaction_type or 'Unknown').upper()}"
                + (
                    f"\nBalance   : {fmt_inr(txn.balance)}"
                    if txn.balance is not None else ""
                )
            )

        # ------------------------------------------------------------------
        # Biggest transactions
        # ------------------------------------------------------------------
        if intent == Intent.BIGGEST_TRANSACTIONS:
            if not result.transactions:
                return "No transactions found."
            return (
                "Your biggest transactions:\n\n"
                + self._txn_fmt.format(result.transactions)
            )

        # ------------------------------------------------------------------
        # Merchant frequency
        # ------------------------------------------------------------------
        if intent == Intent.MERCHANT_FREQUENCY:
            merchant = result.merchant or "this merchant"
            count = result.count or 0
            if count == 0:
                return (
                    f"No transactions found for {merchant} "
                    f"in this statement."
                )
            return (
                f"You had {count} transaction(s) with {merchant} "
                f"during this statement period."
            )

        # ------------------------------------------------------------------
        # Payment method
        # ------------------------------------------------------------------
        if intent == Intent.PAYMENT_METHOD:
            method = result.payment_method or "this method"
            count = result.count or 0
            if count == 0:
                return (
                    f"No transactions found via {method} "
                    f"in this statement."
                )
            # For cash withdrawals, show total and count
            if method.lower() == "cash withdrawal" and result.amount is not None:
                return (
                    f"Total cash withdrawn: {fmt_inr(result.amount)} "
                    f"({count} withdrawal(s))\n\n"
                    + self._txn_fmt.format(result.transactions)
                )
            # For other payment methods, show total if available
            if result.amount is not None and result.amount > 0:
                return (
                    f"Total spent via {method}: {fmt_inr(result.amount)} "
                    f"({count} transaction(s))\n\n"
                    + self._txn_fmt.format(result.transactions)
                )
            header = (
                f"Transactions via {method} ({count} found):\n\n"
            )
            return header + self._txn_fmt.format(result.transactions)

        # ------------------------------------------------------------------
        # Category percentage
        # ------------------------------------------------------------------
        if intent == Intent.CATEGORY_PERCENTAGE:
            if result.category and result.percentage is not None:
                return (
                    f"{result.category} accounts for "
                    f"{result.percentage:.1f}% of your total spending."
                )
            if result.text:
                return (
                    "Spending Distribution\n\n" + result.text
                )
            return "No spending data found."

        # ------------------------------------------------------------------
        # Recommendations
        # ------------------------------------------------------------------
        if intent == Intent.RECOMMENDATIONS:
            return (
                "Financial Recommendations\n\n"
                + (result.text or "No recommendations available.")
            )

        # ------------------------------------------------------------------
        # Financial habits
        # ------------------------------------------------------------------
        if intent == Intent.FINANCIAL_HABITS:
            return result.text or "No financial data available."

        # ------------------------------------------------------------------
        # Merchant frequency ranking
        # ------------------------------------------------------------------
        if intent == Intent.MERCHANT_FREQUENCY_RANKING:
            pairs = result.category_amount_pairs
            if not pairs:
                return "No merchant frequency data found."

            lines: list[str] = ["Most Frequent Merchants\n"]
            for i, (merchant, count) in enumerate(pairs, start=1):
                cnt = int(count)
                lines.append(f"{i}. {merchant} — {cnt} transaction(s)")

            return "\n".join(lines)

        # ------------------------------------------------------------------
        # Balance threshold
        # ------------------------------------------------------------------
        if intent == Intent.BALANCE_THRESHOLD:
            threshold = result.amount or 0
            direction = "exceeded" if (result.text == "yes") else "did not exceed"
            if result.text == "no" and result.transactions:
                # For "below" queries, adjust the wording
                direction = "did not go below" if result.amount else "did not exceed"

            if not result.transactions:
                return result.text or "No balance data available."

            txn = result.transactions[0]
            if result.text == "yes":
                return (
                    f"Yes, your balance {direction} {fmt_inr(threshold)}.\n\n"
                    f"Highest balance : {fmt_inr(txn.balance)}\n"
                    f"Date            : {fmt_date(txn.transaction_date)}\n"
                    f"Transaction     : {txn.description or 'Unknown'}"
                )
            else:
                # Determine if it was an "above" or "below" query
                if result.balance_amount is not None:
                    if result.balance_amount >= threshold:
                        return (
                            f"No, your balance never went below {fmt_inr(threshold)}.\n\n"
                            f"Lowest balance  : {fmt_inr(txn.balance)}\n"
                            f"Date            : {fmt_date(txn.transaction_date)}\n"
                            f"Transaction     : {txn.description or 'Unknown'}"
                        )
                    else:
                        return (
                            f"No, your balance never exceeded {fmt_inr(threshold)}.\n\n"
                            f"Highest balance : {fmt_inr(txn.balance)}\n"
                            f"Date            : {fmt_date(txn.transaction_date)}\n"
                            f"Transaction     : {txn.description or 'Unknown'}"
                        )
                return (
                    f"No, your balance {direction} {fmt_inr(threshold)}."
                )

        # ------------------------------------------------------------------
        # Balance after transaction
        # ------------------------------------------------------------------
        if intent == Intent.BALANCE_AFTER:
            if not result.transactions or result.balance_amount is None:
                return "Could not find the referenced transaction or balance information."
            txn = result.transactions[0]
            from src.agents.qa.formatters import normalize_merchant as nm
            merchant = nm(txn.description or "")
            return (
                f"Your balance after {merchant} was {fmt_inr(result.balance_amount)}.\n\n"
                f"Date      : {fmt_date(txn.transaction_date)}\n"
                f"Amount    : {fmt_inr(txn.amount)}\n"
                f"Category  : {txn.category or 'Uncategorized'}"
            )

        # ------------------------------------------------------------------
        # Category-scoped
        # ------------------------------------------------------------------
        if intent == Intent.CATEGORY_NOT_FOUND:
            label = result.category or "that category"
            return f"No matching category found for \"{label}\"."

        if intent == Intent.CATEGORY_SPEND:
            category = result.category or "this category"
            if result.amount is not None and result.amount == 0:
                return (
                    f"No transactions were found under "
                    f"the {category} category."
                )
            return (
                f"You spent {fmt_inr(result.amount)} on {category} "
                f"during this statement period."
            )

        if intent == Intent.CATEGORY_LIST:
            if not result.transactions:
                category = result.category or "that category"
                return (
                    f"No transactions were found under "
                    f"the {category} category."
                )
            return self._txn_fmt.format(result.transactions)

        # ------------------------------------------------------------------
        # Merchant-scoped
        # ------------------------------------------------------------------
        if intent == Intent.MERCHANT_SPEND:
            return self._format_merchant_spend(result)

        if intent == Intent.MERCHANT_LIST:
            return self._format_merchant_list(result)

        # ------------------------------------------------------------------
        # Analytics intelligence
        # ------------------------------------------------------------------
        if intent == Intent.SPENDING_SUMMARY:
            return self._format_spending_summary(result)

        if intent == Intent.TOP_MERCHANTS:
            return self._format_top_merchants(result)

        if intent == Intent.RECURRING:
            return (
                "Recurring Transactions\n\n"
                + (result.text or "No recurring transactions detected.")
            )

        if intent == Intent.SPENDING_DIST:
            return (
                "Spending Distribution\n\n"
                + (result.text or "No spending data found.")
            )

        if intent == Intent.BUDGET_HEALTH:
            return result.text or "No budget data found."

        if intent == Intent.LARGEST_CATEGORY:
            return self._format_largest_category(result)

        if intent == Intent.FINANCIAL_INSIGHTS:
            return self._format_financial_summary(result)

        # ------------------------------------------------------------------
        # Refund total
        # ------------------------------------------------------------------
        if intent == Intent.REFUND_TOTAL:
            amount = result.amount or Decimal("0")
            if amount == 0:
                return (
                    "No refund transactions were found "
                    "in this statement."
                )
            return (
                f"You received {fmt_inr(amount)} in refunds "
                f"during this statement period."
            )

        # ------------------------------------------------------------------
        # Unknown / unrecognised question
        # ------------------------------------------------------------------
        if result.merchant:
            return (
                f"I couldn't find any spending for \"{result.merchant}\" "
                f"in this statement."
            )
        if result.category:
            return (
                f"No transactions were found under "
                f"the {result.category} category."
            )
        return (
            "I couldn't find anything matching that question. "
            "Try asking about your balance, total spending, "
            "or a specific category."
        )

    # ------------------------------------------------------------------
    # Private renderers
    # ------------------------------------------------------------------

    def _format_spending_summary(self, result: DispatchResult) -> str:
        """
        Numbered category breakdown with top-3 concentration note.

        Keeps the 'Category-wise Spending Summary' header exactly so
        existing tests continue to pass.
        """
        pairs = result.category_amount_pairs
        if not pairs:
            return "Category-wise Spending Summary\n\nNo spending found."

        lines: list[str] = ["Category-wise Spending Summary\n"]
        for i, (category, amount) in enumerate(pairs, start=1):
            lines.append(f"{i}. {category} — {fmt_inr(amount)}")

        # Top-3 concentration note when total is available
        total = result.amount
        if total and total > 0 and len(pairs) >= 3:
            top3 = sum(amt for _, amt in pairs[:3])
            pct  = (top3 * Decimal("100")) / total
            lines.append(
                f"\nYour top 3 categories account for "
                f"{pct:.0f}% of total expenses."
            )

        return "\n".join(lines)

    def _format_top_merchants(self, result: DispatchResult) -> str:
        """
        Numbered merchant list with normalised names.

        Keeps the 'Top Spending Merchants' header exactly.
        """
        pairs = result.category_amount_pairs
        if not pairs:
            return "No merchant data found."

        lines: list[str] = ["Top Spending Merchants\n"]
        for i, (raw_desc, amount) in enumerate(pairs, start=1):
            clean = normalize_merchant(raw_desc)
            lines.append(f"{i}. {clean}\n   {fmt_inr(amount)}")

        return "\n\n".join(lines[:1]) + "\n".join(lines[1:])

    def _format_largest_category(self, result: DispatchResult) -> str:
        """
        Conversational 'where you spent the most' response.

        Keeps the 'Largest Spending Category' header exactly.
        """
        if result.category is None:
            return "No spending data found."
        return (
            "Largest Spending Category\n\n"
            f"You spent the most on {result.category}.\n\n"
            f"Amount: {fmt_inr(result.amount)}\n\n"
            "This is your highest expense category "
            "during the statement period."
        )

    def _format_financial_summary(self, result: DispatchResult) -> str:
        """
        Rich financial summary — 8-10 lines covering all key metrics.
        """
        sa = result.summary_amounts
        if not sa:
            return "No financial data available."

        income   = sa.get("income",   Decimal("0"))
        expense  = sa.get("expense",  Decimal("0"))
        balance  = sa.get("balance",  Decimal("0"))
        txn_cnt  = int(sa.get("transaction_count", 0))

        lines: list[str] = ["Financial Summary\n"]
        lines.append(f"Total Income    : {fmt_inr(income)}")
        lines.append(f"Total Expenses  : {fmt_inr(expense)}")
        lines.append(f"Current Balance : {fmt_inr(balance)}")
        lines.append(f"Transactions    : {txn_cnt}")

        if result.category and result.amount:
            lines.append(
                f"Top Category    : {result.category} "
                f"({fmt_inr(result.amount)})"
            )

        if result.extra_transactions:
            txn = result.extra_transactions[0]
            merchant = normalize_merchant(txn.description or "")
            lines.append(
                f"Largest Expense : {fmt_inr(txn.amount)} — {merchant} "
                f"on {fmt_date(txn.transaction_date)}"
            )

        if result.category_amount_pairs:
            top_pairs = result.category_amount_pairs[:3]
            dist_parts = ", ".join(
                f"{cat} {fmt_inr(amt)}"
                for cat, amt in top_pairs
            )
            lines.append(f"Top 3 Spend     : {dist_parts}")

        # Savings note
        if income > 0:
            savings = income - expense
            if savings >= 0:
                rate = (savings * Decimal("100")) / income
                lines.append(
                    f"Savings Rate    : {rate:.1f}% "
                    f"({fmt_inr(savings)} saved)"
                )
            else:
                over = abs(savings)
                lines.append(
                    f"Note            : Expenses exceeded income "
                    f"by {fmt_inr(over)} this period."
                )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Merchant spend / list helpers
    # ------------------------------------------------------------------

    def _format_merchant_spend(self, result: DispatchResult) -> str:
        """
        Three cases:
          a) Debit spend > 0              → "You spent ₹X on Y."
          b) No debits, credits exist     → context-aware refund notice
          c) No activity at all           → specific not-found message
        """
        merchant = result.merchant or "this merchant"
        amount   = result.amount or Decimal("0")

        # (a) Normal spend
        if amount > 0:
            return (
                f"You spent {fmt_inr(amount)} on {merchant} "
                f"during this statement period."
            )

        # (b) No debits but credits/refunds exist
        if result.refund_transactions:
            refund_total = sum(
                t.amount for t in result.refund_transactions
                if t.amount is not None
            )
            # Pick the article "an" before vowel sounds
            article = "an" if merchant[:1].lower() in "aeiou" else "a"
            txn     = result.refund_transactions[0]
            date_str = fmt_date(txn.transaction_date)

            return (
                f"No {merchant} purchases were found.\n\n"
                f"However, {article} {merchant} refund of "
                f"{fmt_inr(refund_total)} was detected on {date_str}."
            )

        # (c) Nothing at all
        return (
            f"I couldn't find any spending for \"{merchant}\" "
            f"in this statement."
        )

    def _format_merchant_list(self, result: DispatchResult) -> str:
        """
        Shows all transactions.  When every transaction is a credit
        (e.g. Amazon refund), appends a clarifying note.
        """
        merchant = result.merchant or "this merchant"
        txns     = result.transactions or []

        if not txns:
            return (
                f"I couldn't find any transactions for \"{merchant}\" "
                f"in this statement."
            )

        formatted = self._txn_fmt.format(txns)

        all_credits = all(
            (t.transaction_type or "").upper() == "CREDIT"
            for t in txns
        )
        if all_credits:
            formatted += (
                f"\n\nNote: These are refunds / credits from {merchant}, "
                f"not purchases."
            )

        return formatted
