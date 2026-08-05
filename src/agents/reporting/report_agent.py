"""
Reporting Agent

Generates an AI-powered financial narrative from a FinancialReport.

Responsibilities:
- Read the FinancialReport.
- Compute analytics using AnalyticsAgent.
- Build a ReportContext.
- Generate a professional financial narrative using Ollama.

The Reporting Agent NEVER performs financial calculations itself.
"""

from src.agents.analytics.analytics_agent import AnalyticsAgent
from src.llm.ollama_client import OllamaClient
from src.models.report_context import ReportContext
from src.schemas.financial_report import FinancialReport


class ReportingAgent:
    """
    Generates an AI-powered financial report.
    """

    def __init__(self) -> None:
        self.analytics = AnalyticsAgent()
        self.llm = OllamaClient()

    def _create_context(
        self,
        report: FinancialReport,
    ) -> ReportContext:

        transactions = report.transactions

        largest_category = self.analytics.largest_spending_category(
            transactions,
        )

        return ReportContext(
            total_income=float(
                self.analytics.total_income(transactions)
            ),
            total_expense=float(
                self.analytics.total_expense(transactions)
            ),
            net_cash_flow=float(
                self.analytics.net_cash_flow(transactions)
            ),
            budget_health=self.analytics.budget_health(
                transactions
            ),
            largest_spending_category=(
                largest_category[0]
                if largest_category
                else "N/A"
            ),
            category_totals={
                key: float(value)
                for key, value in self.analytics.category_totals(
                    transactions
                ).items()
            },
            spending_distribution={
                key: float(value)
                for key, value in self.analytics.spending_percentages(
                    transactions
                ).items()
            },
            top_merchants=[
                {
                    "merchant": merchant,
                    "amount": float(amount),
                }
                for merchant, amount in self.analytics.top_merchants(
                    transactions
                )
            ],
            recurring_transactions=[
                {
                    "merchant": merchant,
                    "occurrences": len(txns),
                }
                for merchant, txns in self.analytics.recurring_transactions(
                    transactions
                ).items()
            ],
            highest_expense=(
                self.analytics.highest_expense(
                    transactions
                ).model_dump()
                if self.analytics.highest_expense(transactions)
                else {}
            ),
            highest_income=(
                self.analytics.highest_income(
                    transactions
                ).model_dump()
                if self.analytics.highest_income(transactions)
                else {}
            ),
        )

    def _build_prompt(
        self,
        report: FinancialReport,
        context: ReportContext,
    ) -> str:

        return f"""
You are a senior financial analyst.

Analyse the customer's bank statement using ONLY the supplied data.

Rules:

- Never invent values.
- Never perform calculations.
- Never assume missing information.
- Use only the supplied analytics.

Bank:
{report.bank_name}

Statement Period:
{report.statement_start_date} to {report.statement_end_date}

Total Income:
₹{context.total_income:,.2f}

Total Expense:
₹{context.total_expense:,.2f}

Net Cash Flow:
₹{context.net_cash_flow:,.2f}

Budget Health:
{context.budget_health}

Largest Spending Category:
{context.largest_spending_category}

Category Totals:
{context.category_totals}

Top Merchants:
{context.top_merchants}

Recurring Transactions:
{context.recurring_transactions}

Highest Expense:
{context.highest_expense}

Highest Income:
{context.highest_income}

Write a report with these headings:

1. Executive Summary
2. Spending Analysis
3. Income Analysis
4. Recurring Payments
5. Financial Health
6. Recommendations

Keep the report concise, professional and easy to understand.
"""

    def generate(
        self,
        report: FinancialReport,
    ) -> str:
        """
        Generate an AI financial narrative.
        """

        context = self._create_context(
            report,
        )

        prompt = self._build_prompt(
            report,
            context,
        )

        return self.llm.generate(
            task="reporting",
            prompt=prompt,
            system_prompt=(
                "You are a professional financial analyst. "
                "Only use the supplied information."
            ),
            temperature=0.2,
        )