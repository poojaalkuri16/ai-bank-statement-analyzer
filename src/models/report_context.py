"""
Report Context Model

This dataclass represents the structured financial analytics that are
passed from the Analytics Agent to the Reporting Agent.

The Reporting Agent should NEVER calculate financial values.
It only interprets the values stored in this context.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ReportContext:
    """
    Structured analytics used by the Reporting Agent.
    """

    # Core Financial Metrics
    total_income: float
    total_expense: float
    net_cash_flow: float

    # Budget Analysis
    budget_health: str
    largest_spending_category: str

    # Category Analytics
    category_totals: Dict[str, float] = field(default_factory=dict)
    spending_distribution: Dict[str, float] = field(default_factory=dict)

    # Merchant Analytics
    top_merchants: List[dict] = field(default_factory=list)

    # Recurring Payments
    recurring_transactions: List[dict] = field(default_factory=list)

    # Significant Transactions
    highest_expense: dict = field(default_factory=dict)
    highest_income: dict = field(default_factory=dict)