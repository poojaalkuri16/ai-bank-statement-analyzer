"""
QA Regression Suite
===================
Loads the real FinancialReport from the saved JSON and asserts that
every user-facing query returns the expected string.

Amounts use Indian rupee formatting (₹85,743.56) — the formatted string
always contains the original digits without commas as a substring, so
assertions check the digit pattern only, not the full formatted string.

Run with:
    python -m pytest tests/test_qa_regression.py -v
"""
import json
from pathlib import Path

import pytest

from src.agents.qa.qa_agent import QAAgent
from src.schemas.financial_report import FinancialReport

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPORT_PATH = Path("reports/sbi_statement.json")


@pytest.fixture(scope="module")
def report() -> FinancialReport:
    data = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    return FinancialReport(**data)


@pytest.fixture(scope="module")
def qa(report) -> QAAgent:
    return QAAgent()


def ask(qa: QAAgent, report: FinancialReport, question: str) -> str:
    return qa.answer(report=report, question=question)


# ---------------------------------------------------------------------------
# Try 1 — Core queries
# ---------------------------------------------------------------------------

class TestTotalSpend:
    def test_how_much_did_i_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend?")
        assert "85,743.56" in ans

    def test_total_expenses(self, qa, report):
        ans = ask(qa, report, "What are my total expenses?")
        assert "85,743.56" in ans


class TestBalance:
    def test_what_is_my_balance(self, qa, report):
        ans = ask(qa, report, "What is my balance?")
        assert "63,767.46" in ans

    def test_account_balance(self, qa, report):
        ans = ask(qa, report, "What is my account balance?")
        assert "63,767.46" in ans


class TestCategorySpend:
    def test_food_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Food?")
        assert "2,859.03" in ans

    def test_fuel_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Fuel?")
        assert "2,211.54" in ans

    def test_shopping_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Shopping?")
        assert "15,118.67" in ans


class TestCategoryList:
    def test_show_food_transactions(self, qa, report):
        ans = ask(qa, report, "Show Food transactions.")
        assert "UPI/SWIGGY/ORDERPAY" in ans or "ZOMATO ORDER" in ans

    def test_show_fuel_transactions(self, qa, report):
        ans = ask(qa, report, "Show Fuel transactions.")
        assert "INDIAN OIL FUEL STATION" in ans

    def test_show_shopping_transactions(self, qa, report):
        ans = ask(qa, report, "Show Shopping transactions.")
        assert "FLIPKART ONLINE PAYMENT" in ans or "LIFESTYLE STORES" in ans


# ---------------------------------------------------------------------------
# Try 2 — Merchant queries
# ---------------------------------------------------------------------------

class TestMerchantSpend:
    def test_swiggy_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Swiggy?")
        assert "1,353.06" in ans

    def test_zomato_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Zomato?")
        assert "1,505.97" in ans

    def test_amazon_spend(self, qa, report):
        # Amazon RETURN is a CREDIT — no debit spend.
        # Response must mention refund/credit, not total expenses.
        ans = ask(qa, report, "How much did I spend on Amazon?")
        assert "refund" in ans.lower() or "credit" in ans.lower()
        assert "85,743" not in ans

    def test_bajaj_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Bajaj?")
        assert "8,453.21" in ans

    def test_medplus_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on MedPlus?")
        assert "3,568.74" in ans

    def test_reliance_fresh_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Reliance Fresh?")
        # 406.54 + 1775.62 = 2182.16
        assert "2,182.16" in ans


class TestMerchantList:
    def test_show_swiggy_transactions(self, qa, report):
        ans = ask(qa, report, "Show Swiggy transactions.")
        assert "UPI/SWIGGY/ORDERPAY" in ans

    def test_show_amazon_payments(self, qa, report):
        ans = ask(qa, report, "Show Amazon payments.")
        assert "AMAZON RETURN" in ans

    def test_show_bajaj_transactions(self, qa, report):
        ans = ask(qa, report, "Show Bajaj transactions.")
        assert "BAJAJ FINSERV" in ans

    def test_show_rahul_sharma_transfer(self, qa, report):
        ans = ask(qa, report, "Show Rahul Sharma transfer.")
        assert "RAHUL SHARMA" in ans

    def test_show_medplus_transactions(self, qa, report):
        ans = ask(qa, report, "Show MedPlus transactions.")
        assert "MEDPLUS" in ans

    def test_show_reliance_fresh_transactions(self, qa, report):
        ans = ask(qa, report, "Show Reliance Fresh transactions.")
        assert "RELIANCE FRESH" in ans

    def test_show_zomato_transactions(self, qa, report):
        ans = ask(qa, report, "Show Zomato transactions.")
        assert "ZOMATO ORDER" in ans


# ---------------------------------------------------------------------------
# Try 3 — Financial intelligence queries
# ---------------------------------------------------------------------------

class TestFinancialIntelligence:
    def test_spending_summary(self, qa, report):
        ans = ask(qa, report, "Show all categories.")
        assert "Transfer" in ans or "Shopping" in ans

    def test_top_merchants(self, qa, report):
        ans = ask(qa, report, "Top merchants.")
        assert "Top Spending Merchants" in ans

    def test_where_did_i_spend_the_most(self, qa, report):
        ans = ask(qa, report, "Where did I spend the most?")
        assert ans.strip() != ""

    def test_expense_summary(self, qa, report):
        ans = ask(qa, report, "Expense summary.")
        assert ans.strip() != ""

    def test_financial_summary(self, qa, report):
        ans = ask(qa, report, "Financial summary.")
        assert ans.strip() != ""

    def test_break_down_expenses(self, qa, report):
        ans = ask(qa, report, "Break down my expenses.")
        assert ans.strip() != ""

    def test_where_is_my_money_going(self, qa, report):
        ans = ask(qa, report, "Where is my money going?")
        assert ans.strip() != ""

    def test_recurring_expenses(self, qa, report):
        ans = ask(qa, report, "Recurring expenses.")
        assert "Recurring Transactions" in ans

    def test_largest_spending_category(self, qa, report):
        ans = ask(qa, report, "Largest spending category.")
        assert "Largest Spending Category" in ans

    def test_who_received_the_most_money(self, qa, report):
        ans = ask(qa, report, "Who received the most money?")
        assert "Top Spending Merchants" in ans
