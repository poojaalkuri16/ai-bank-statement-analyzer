from decimal import Decimal

from src.agents.analytics.analytics_agent import AnalyticsAgent
from src.schemas.financial_report import FinancialReport


class FinancialInsights:
    """
    Generates human-readable financial insights
    from the statement analytics.
    """

    def __init__(self) -> None:
        self.analytics = AnalyticsAgent()

    def generate(
        self,
        report: FinancialReport,
    ) -> list[str]:

        insights: list[str] = []

        income = self.analytics.total_income(
            report.transactions,
        )

        expenses = self.analytics.total_expense(
            report.transactions,
        )

        if income > Decimal("0"):

            savings = income - expenses

            if savings >= 0:
                insights.append(
                    f"You saved ₹{savings} during this statement period."
                )
            else:
                insights.append(
                    f"Your expenses exceeded your income by ₹{abs(savings)}."
                )

        totals = self.analytics.category_totals(
            report.transactions,
        )

        if totals:

            top_category = max(
                totals.items(),
                key=lambda item: item[1],
            )

            insights.append(
                f"Your highest spending category was "
                f"{top_category[0]} (₹{top_category[1]})."
            )

        largest = self.analytics.highest_expense(
            report.transactions,
        )

        if largest:

            insights.append(
                f"Your largest expense was "
                f"₹{largest.amount} "
                f"for '{largest.description}'."
            )

        return insights