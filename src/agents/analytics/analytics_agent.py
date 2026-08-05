from collections import defaultdict
from decimal import Decimal

from src.utils.merchant_normalizer import normalize_merchant
from src.schemas.transaction import Transaction


class AnalyticsAgent:
    """
    Computes financial analytics from categorized transactions.
    """

    @staticmethod
    def _transaction_type(transaction: Transaction) -> str:
        """
        Returns normalized transaction type.

        Accepts:
            DEBIT / debit / Debit
            CREDIT / credit / Credit
        """

        return (transaction.transaction_type or "").upper()

    def total_income(
        self,
        transactions: list[Transaction],
    ) -> Decimal:

        total = Decimal("0")

        for transaction in transactions:

            if self._transaction_type(transaction) == "CREDIT":
                total += transaction.amount

        return total

    def total_expense(
        self,
        transactions: list[Transaction],
    ) -> Decimal:

        total = Decimal("0")

        for transaction in transactions:

            if self._transaction_type(transaction) == "DEBIT":
                total += transaction.amount

        return total

    def net_cash_flow(
        self,
        transactions: list[Transaction],
    ) -> Decimal:

        return (
            self.total_income(transactions)
            - self.total_expense(transactions)
        )

    def highest_expense(
        self,
        transactions: list[Transaction],
    ) -> Transaction | None:

        expenses = [
            transaction
            for transaction in transactions
            if self._transaction_type(transaction) == "DEBIT"
        ]

        if not expenses:
            return None

        return max(
            expenses,
            key=lambda transaction: transaction.amount,
        )

    def highest_income(
        self,
        transactions: list[Transaction],
    ) -> Transaction | None:

        income = [
            transaction
            for transaction in transactions
            if self._transaction_type(transaction) == "CREDIT"
        ]

        if not income:
            return None

        return max(
            income,
            key=lambda transaction: transaction.amount,
        )

    def category_totals(
        self,
        transactions: list[Transaction],
    ) -> dict[str, Decimal]:

        totals: dict[str, Decimal] = defaultdict(
            lambda: Decimal("0")
        )

        for transaction in transactions:

            if self._transaction_type(transaction) != "DEBIT":
                continue

            category = transaction.category or "Others"

            totals[category] += transaction.amount

        return dict(totals)

    def category_total(
        self,
        transactions: list[Transaction],
        category: str,
    ) -> Decimal:

        totals = self.category_totals(
            transactions,
        )

        return totals.get(
            category,
            Decimal("0"),
        )

    def spending_summary(
        self,
        transactions: list[Transaction],
    ) -> str:

        totals = self.category_totals(
            transactions,
        )

        if not totals:
            return "No spending found."

        lines = []

        for category, amount in sorted(
            totals.items(),
            key=lambda item: item[1],
            reverse=True,
        ):

            lines.append(
                f"{category}: ₹{amount}"
            )

        return "\n".join(lines)

    def merchant_totals(
        self,
        transactions: list[Transaction],
    ) -> dict[str, Decimal]:
        """
        Returns total debit spending grouped by normalised merchant name.

        Raw transaction descriptions are mapped to canonical merchant names
        via normalize_merchant() before grouping, so identical merchants
        that appear with slightly different raw text (e.g. two rent payments
        both labelled "UPI/LANDLORD/RENTPAY") are aggregated into a single
        entry rather than appearing as duplicates.
        """

        totals: dict[str, Decimal] = defaultdict(
            lambda: Decimal("0")
        )

        for transaction in transactions:

            if self._transaction_type(transaction) != "DEBIT":
                continue

            raw = (
                transaction.description.strip()
                if transaction.description
                else "Unknown"
            )

            # Normalise to canonical merchant name for clean aggregation
            merchant = normalize_merchant(raw)

            totals[merchant] += transaction.amount

        return dict(totals)

    def top_merchants(
        self,
        transactions: list[Transaction],
        limit: int = 5,
    ) -> list[tuple[str, Decimal]]:

        merchants = self.merchant_totals(
            transactions,
        )

        return sorted(
            merchants.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:limit]

    def recurring_transactions(
        self,
        transactions: list[Transaction],
        minimum_occurrences: int = 2,
    ) -> dict[str, list[Transaction]]:
        """
        Groups transactions by normalised merchant name and returns those
        appearing at least *minimum_occurrences* times.
        """

        groups: dict[str, list[Transaction]] = defaultdict(list)

        for transaction in transactions:

            raw = (
                transaction.description.strip()
                if transaction.description
                else "Unknown"
            )

            merchant = normalize_merchant(raw)
            groups[merchant].append(transaction)

        return {
            merchant: txns
            for merchant, txns in groups.items()
            if len(txns) >= minimum_occurrences
        }

    def recurring_summary(
        self,
        transactions: list[Transaction],
    ) -> str:
        """
        Returns a formatted recurring payment summary.
        """

        recurring = self.recurring_transactions(
            transactions,
        )

        if not recurring:
            return "No recurring transactions detected."

        lines = []

        for merchant, txns in sorted(
            recurring.items(),
            key=lambda item: len(item[1]),
            reverse=True,
        ):

            total = sum(
                txn.amount
                for txn in txns
            )

            lines.append(
                f"{merchant} "
                f"({len(txns)} transactions) "
                f"₹{total}"
            )

        return "\n".join(lines)

    def spending_percentages(
        self,
        transactions: list[Transaction],
    ) -> dict[str, Decimal]:
        """
        Returns percentage spending for every category.
        """

        totals = self.category_totals(
            transactions,
        )

        total_spending = sum(
            totals.values(),
            Decimal("0"),
        )

        if total_spending == 0:
            return {}

        percentages: dict[str, Decimal] = {}

        for category, amount in totals.items():

            percentages[category] = (
                amount * Decimal("100")
            ) / total_spending

        return percentages

    def spending_distribution(
        self,
        transactions: list[Transaction],
    ) -> str:
        """
        Returns a formatted category-wise spending distribution.
        """

        percentages = self.spending_percentages(
            transactions,
        )

        if not percentages:
            return "No spending data found."

        totals = self.category_totals(
            transactions,
        )

        lines = []

        for category in sorted(
            percentages,
            key=percentages.get,
            reverse=True,
        ):

            lines.append(
                f"{category}: "
                f"₹{totals[category]} "
                f"({percentages[category]:.2f}%)"
            )

        return "\n".join(lines)

    def largest_spending_category(
        self,
        transactions: list[Transaction],
    ) -> tuple[str, Decimal] | None:
        """
        Returns the category with the highest spending.
        """

        totals = self.category_totals(
            transactions,
        )

        if not totals:
            return None

        return max(
            totals.items(),
            key=lambda item: item[1],
        )

    def budget_health(
        self,
        transactions: list[Transaction],
    ) -> str:
        """
        Evaluates overall budget health using income and expenses.
        """

        income  = self.total_income(transactions)
        expense = self.total_expense(transactions)

        if income == 0:
            if expense == 0:
                return "No financial activity found."
            return (
                "No income detected. "
                "Unable to evaluate budget health."
            )

        savings      = income - expense
        savings_rate = (savings * Decimal("100")) / income

        if savings_rate >= Decimal("30"):
            status = "Excellent"
        elif savings_rate >= Decimal("15"):
            status = "Good"
        elif savings_rate >= Decimal("0"):
            status = "Needs Improvement"
        else:
            status = "Overspending"

        def _fmt(v: Decimal) -> str:
            """Simple INR formatting without importing from QA."""
            abs_v = abs(v)
            s = f"{abs_v:,.2f}"
            return f"₹{s}" if v >= 0 else f"-₹{s}"

        return (
            f"Income       : {_fmt(income)}\n"
            f"Expenses     : {_fmt(expense)}\n"
            f"Savings      : {_fmt(savings)}\n"
            f"Savings Rate : {savings_rate:.2f}%\n"
            f"Budget Health: {status}"
        )

    # ------------------------------------------------------------------
    # Balance analytics
    # ------------------------------------------------------------------

    @staticmethod
    def opening_balance(
        transactions: list[Transaction],
    ) -> Decimal | None:
        """
        Compute the opening balance (balance before the first transaction).

        opening_balance = first_txn.balance + first_txn.amount  (DEBIT)
        opening_balance = first_txn.balance - first_txn.amount  (CREDIT)
        """
        if not transactions:
            return None
        first = transactions[0]
        if first.balance is None or first.amount is None:
            return None
        txn_type = (first.transaction_type or "").upper()
        if txn_type == "DEBIT":
            return first.balance + first.amount
        elif txn_type == "CREDIT":
            return first.balance - first.amount
        return first.balance

    @staticmethod
    def closing_balance(
        transactions: list[Transaction],
    ) -> Decimal | None:
        """Return the last known running balance."""
        for txn in reversed(transactions):
            if txn.balance is not None:
                return txn.balance
        return None

    @staticmethod
    def highest_balance(
        transactions: list[Transaction],
    ) -> Transaction | None:
        """Return the transaction with the highest running balance."""
        with_balance = [t for t in transactions if t.balance is not None]
        if not with_balance:
            return None
        return max(with_balance, key=lambda t: t.balance)

    @staticmethod
    def lowest_balance(
        transactions: list[Transaction],
    ) -> Transaction | None:
        """Return the transaction with the lowest running balance."""
        with_balance = [t for t in transactions if t.balance is not None]
        if not with_balance:
            return None
        return min(with_balance, key=lambda t: t.balance)

    def generate_recommendations(
        self,
        transactions: list[Transaction],
    ) -> str:
        """Generate actionable financial recommendations."""
        from src.agents.qa.formatters import fmt_inr

        income  = self.total_income(transactions)
        expense = self.total_expense(transactions)
        totals  = self.category_totals(transactions)
        recs: list[str] = []

        # Savings rate insight
        if income > 0:
            savings = income - expense
            rate = (savings * Decimal("100")) / income
            if rate < Decimal("10"):
                recs.append(
                    f"Your savings rate is only {rate:.1f}%. "
                    f"Aim to save at least 20% of your income."
                )
            elif rate < Decimal("20"):
                recs.append(
                    f"Your savings rate is {rate:.1f}%. "
                    f"You're doing well, but try to push toward 30%."
                )
            else:
                recs.append(
                    f"Excellent savings rate of {rate:.1f}%! "
                    f"Keep up the discipline."
                )

        # Top spending category insight
        if totals:
            top = max(totals.items(), key=lambda i: i[1])
            total_expense_val = sum(totals.values(), Decimal("0"))
            if total_expense_val > 0:
                pct = (top[1] * Decimal("100")) / total_expense_val
                if pct > Decimal("40"):
                    recs.append(
                        f"{top[0]} accounts for {pct:.0f}% of your spending. "
                        f"Consider if this can be reduced."
                    )

        # Recurring payments insight
        recurring = self.recurring_transactions(transactions)
        if recurring:
            recurring_total = sum(
                sum(t.amount for t in txns)
                for txns in recurring.values()
            )
            if income > 0:
                rec_pct = (recurring_total * Decimal("100")) / income
                if rec_pct > Decimal("30"):
                    recs.append(
                        f"Recurring payments are {rec_pct:.0f}% of income. "
                        f"Review subscriptions for potential savings."
                    )

        # Overspending alert
        if income > 0 and expense > income:
            over = expense - income
            recs.append(
                f"You're overspending by {fmt_inr(over)}. "
                f"Review non-essential categories to cut back."
            )

        # EMI insight
        emi_amount = totals.get("EMI", Decimal("0"))
        if emi_amount > 0 and income > 0:
            emi_pct = (emi_amount * Decimal("100")) / income
            if emi_pct > Decimal("20"):
                recs.append(
                    f"EMI payments are {emi_pct:.0f}% of income. "
                    f"Consider prepaying high-interest loans."
                )

        if not recs:
            recs.append(
                "Your finances look healthy. Keep tracking your spending "
                "to maintain good financial habits."
            )

        return "\n\n".join(f"• {r}" for r in recs)

    def financial_habits_summary(
        self,
        transactions: list[Transaction],
    ) -> str:
        """Generate a comprehensive financial habits summary."""
        from src.agents.qa.formatters import fmt_inr

        income = self.total_income(transactions)
        expense = self.total_expense(transactions)
        totals = self.category_totals(transactions)
        recurring = self.recurring_transactions(transactions)
        largest = self.highest_expense(transactions)

        lines: list[str] = ["Financial Habits Summary\n"]

        # Top spending categories
        if totals:
            sorted_cats = sorted(totals.items(), key=lambda i: i[1], reverse=True)[:3]
            lines.append("Top Spending Categories:")
            for cat, amt in sorted_cats:
                lines.append(f"  • {cat}: {fmt_inr(amt)}")
            lines.append("")

        # Recurring expenses
        if recurring:
            lines.append(f"Recurring Expenses: {len(recurring)} merchants with repeat transactions")
            recurring_total = sum(
                sum(t.amount for t in txns) for txns in recurring.values()
            )
            lines.append(f"  • Total recurring: {fmt_inr(recurring_total)}")
            lines.append("")

        # Savings rate
        if income > 0:
            savings = income - expense
            rate = (savings * Decimal("100")) / income
            if rate >= 0:
                lines.append(f"Savings Rate: {rate:.1f}% ({fmt_inr(savings)} saved)")
            else:
                lines.append(f"Savings Rate: {rate:.1f}% (overspending by {fmt_inr(abs(savings))})")
            lines.append("")

        # Budget health
        if income > 0:
            if expense > income:
                lines.append("Budget Health: Overspending — expenses exceed income")
            elif rate < Decimal("10"):
                lines.append("Budget Health: Needs Improvement — low savings rate")
            elif rate < Decimal("20"):
                lines.append("Budget Health: Good — moderate savings rate")
            else:
                lines.append("Budget Health: Excellent — strong savings rate")
            lines.append("")

        # Largest expense
        if largest:
            from src.utils.merchant_normalizer import normalize_merchant
            merchant = normalize_merchant(largest.description or "")
            lines.append(f"Largest Expense: {fmt_inr(largest.amount)} — {merchant}")
            lines.append("")

        # Actionable recommendations
        lines.append("Recommendations:")
        if income > 0 and expense > income:
            lines.append(f"  • Reduce spending by {fmt_inr(expense - income)} to balance your budget")
        if totals:
            top_cat = max(totals.items(), key=lambda i: i[1])
            total_expense_val = sum(totals.values(), Decimal("0"))
            if total_expense_val > 0:
                pct = (top_cat[1] * Decimal("100")) / total_expense_val
                if pct > Decimal("40"):
                    lines.append(f"  • {top_cat[0]} is {pct:.0f}% of spending — consider reducing")
        if income > 0 and income > expense:
            lines.append("  • Continue maintaining your current savings discipline")

        return "\n".join(lines)

    def merchant_frequency(
        self,
        transactions: list[Transaction],
        limit: int = 5,
    ) -> list[tuple[str, Decimal]]:
        """
        Returns merchants ranked by frequency (count), not amount.
        Returns list of (merchant_name, count_as_Decimal) tuples.
        """
        groups: dict[str, int] = {}

        for transaction in transactions:
            # Only count debits for frequency
            if self._transaction_type(transaction) != "DEBIT":
                continue

            raw = (
                transaction.description.strip()
                if transaction.description
                else "Unknown"
            )
            merchant = normalize_merchant(raw)
            groups[merchant] = groups.get(merchant, 0) + 1

        sorted_merchants = sorted(
            groups.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:limit]

        # Convert count to Decimal for compatibility with category_amount_pairs
        return [(merchant, Decimal(str(count))) for merchant, count in sorted_merchants]