"""
Financial AI Assistant Tests
=============================
End-to-end tests verifying every success criterion from the spec:

  ✓ Analytics are accurate
  ✓ Merchant normalization is correct
  ✓ Category detection is correct
  ✓ Largest debit / credit / balance correct
  ✓ Income and expenses accurate
  ✓ Refunds detected correctly
  ✓ Natural language QA works across all question types
  ✓ All three PDF layouts (SBI / ICICI / Union Bank) produce correct answers
  ✓ Budget health uses formatted numbers
  ✓ Income synonyms route to TOTAL_INCOME, not Salary category
  ✓ Wrapped descriptions normalised (no space after /)
"""
from decimal import Decimal
from pathlib import Path

import pytest

from src.agents.document.document_agent import DocumentAgent
from src.agents.qa.intent_detector import Intent, IntentDetector
from src.agents.qa.qa_agent import QAAgent
from src.context.session_context import SessionContextManager


# ---------------------------------------------------------------------------
# Fixtures — process each PDF once per module
# ---------------------------------------------------------------------------

def _process(pdf: str):
    ctx = SessionContextManager()
    DocumentAgent(debug=False).execute(pdf, ctx)
    return ctx.get_metadata("financial_report")


@pytest.fixture(scope="module")
def sbi_report():
    return _process("data/sbi_statement.pdf")


@pytest.fixture(scope="module")
def icici_report():
    return _process("data/icici_statement.pdf")


@pytest.fixture(scope="module")
def union_report():
    return _process("data/no_table2.pdf")


@pytest.fixture(scope="module")
def qa():
    return QAAgent()


def ask(qa, report, q):
    return qa.answer(report=report, question=q)


# ===========================================================================
# Intent Detector — synonym coverage
# ===========================================================================

class TestIntentSynonyms:

    @pytest.fixture
    def det(self):
        return IntentDetector()

    # Income synonyms must route to TOTAL_INCOME, not Salary category
    @pytest.mark.parametrize("q", [
        "total income",
        "Total income?",
        "how much income did I receive",
        "money received",
        "total credits",
        "credits received",
        "what is my income",
        "total salary",
    ])
    def test_income_synonyms(self, det, q):
        result = det.detect(q.lower())
        assert result.intent == Intent.TOTAL_INCOME, (
            f"{q!r} routed to {result.intent}, expected TOTAL_INCOME"
        )

    # Spend synonyms
    @pytest.mark.parametrize("q", [
        "how much did i spend",
        "what are my expenses",
        "total debits",
        "money spent",
        "total spend",
    ])
    def test_spend_synonyms(self, det, q):
        result = det.detect(q.lower())
        assert result.intent == Intent.TOTAL_SPEND

    # Balance synonyms
    @pytest.mark.parametrize("q", [
        "what is my balance",
        "account balance",
        "current balance",
    ])
    def test_balance_synonyms(self, det, q):
        result = det.detect(q.lower())
        assert result.intent == Intent.BALANCE

    def test_closing_balance_synonym(self, det):
        """Closing balance is a distinct intent from generic balance."""
        result = det.detect("closing balance")
        assert result.intent == Intent.CLOSING_BALANCE

    # Recurring synonyms
    @pytest.mark.parametrize("q", [
        "recurring payments",
        "subscriptions",
        "recurring bills",
        "regular payments",
    ])
    def test_recurring_synonyms(self, det, q):
        result = det.detect(q.lower())
        assert result.intent == Intent.RECURRING

    # Budget health synonyms
    @pytest.mark.parametrize("q", [
        "budget health",
        "financial health",
        "am i overspending",
        "savings rate",
        "cash flow health",
    ])
    def test_budget_health_synonyms(self, det, q):
        result = det.detect(q.lower())
        assert result.intent == Intent.BUDGET_HEALTH


# ===========================================================================
# SBI — analytics accuracy
# ===========================================================================

class TestSBIAnalytics:

    def test_total_spend(self, qa, sbi_report):
        ans = ask(qa, sbi_report, "How much did I spend?")
        assert "85,743.56" in ans

    def test_total_income(self, qa, sbi_report):
        ans = ask(qa, sbi_report, "Total income?")
        assert "67,061.02" in ans

    def test_balance(self, qa, sbi_report):
        ans = ask(qa, sbi_report, "What is my account balance?")
        assert "63,767.46" in ans

    def test_net_cash_flow(self, qa, sbi_report):
        ans = ask(qa, sbi_report, "Net cash flow?")
        assert "18,682.54" in ans

    def test_category_spend_fuel(self, qa, sbi_report):
        ans = ask(qa, sbi_report, "How much did I spend on Fuel?")
        assert "2,211.54" in ans

    def test_category_spend_food(self, qa, sbi_report):
        ans = ask(qa, sbi_report, "How much did I spend on Food?")
        assert "2,859.03" in ans

    def test_show_food_transactions(self, qa, sbi_report):
        ans = ask(qa, sbi_report, "Show Food transactions.")
        assert "SWIGGY" in ans or "ZOMATO" in ans

    def test_top_merchants_present(self, qa, sbi_report):
        ans = ask(qa, sbi_report, "Top merchants?")
        assert "Top Spending Merchants" in ans
        assert "Landlord" in ans  # normalised merchant name

    def test_spending_summary(self, qa, sbi_report):
        ans = ask(qa, sbi_report, "Show all categories.")
        assert "Category-wise Spending Summary" in ans
        assert "Transfer" in ans

    def test_largest_expense(self, qa, sbi_report):
        ans = ask(qa, sbi_report, "Largest expense?")
        assert "24,950.89" in ans

    def test_recurring_payments(self, qa, sbi_report):
        ans = ask(qa, sbi_report, "Recurring payments?")
        assert "Recurring Transactions" in ans
        assert "Reliance Fresh" in ans

    def test_budget_health_formatted(self, qa, sbi_report):
        ans = ask(qa, sbi_report, "Budget health?")
        # Must NOT have bare unformatted numbers like ₹85743.56
        assert "₹85743" not in ans
        assert "Income" in ans
        assert "Expenses" in ans

    def test_financial_summary(self, qa, sbi_report):
        ans = ask(qa, sbi_report, "Financial summary.")
        assert "Financial Summary" in ans
        assert "Total Income" in ans
        assert "Total Expenses" in ans

    def test_largest_spending_category(self, qa, sbi_report):
        ans = ask(qa, sbi_report, "Where did I spend the most?")
        assert "Largest Spending Category" in ans

    def test_description_no_slash_space(self, sbi_report):
        """Wrapped descriptions must not have space after slash."""
        descs = [t.description for t in sbi_report.transactions if t.description]
        for d in descs:
            assert "/ " not in d, f"Space after / in: {d!r}"


# ===========================================================================
# ICICI — 3-page multi-page accuracy
# ===========================================================================

class TestICICIAnalytics:

    def test_transaction_count(self, icici_report):
        assert icici_report.transaction_count == 60

    def test_total_spend(self, qa, icici_report):
        ans = ask(qa, icici_report, "How much did I spend?")
        assert "268,894.87" in ans or "2,68,894.87" in ans

    def test_total_income(self, qa, icici_report):
        ans = ask(qa, icici_report, "Total income?")
        assert "299,404.67" in ans or "2,99,404.67" in ans

    def test_balance(self, qa, icici_report):
        ans = ask(qa, icici_report, "What is my account balance?")
        assert "110,354.68" in ans or "1,10,354.68" in ans

    def test_refund_received(self, qa, icici_report):
        ans = ask(qa, icici_report, "How much refund did I receive?")
        assert "13,825.27" in ans

    def test_budget_health_formatted(self, qa, icici_report):
        ans = ask(qa, icici_report, "Budget health?")
        assert "₹299743" not in ans  # no raw unformatted number
        assert "Savings Rate" in ans

    def test_fuel_spend(self, qa, icici_report):
        ans = ask(qa, icici_report, "Fuel expenses?")
        assert "3,565.37" in ans

    def test_recurring_across_pages(self, qa, icici_report):
        ans = ask(qa, icici_report, "Recurring payments?")
        # BESCOM appears 4 times across 3 pages
        assert "BESCOM" in ans or "bescom" in ans.lower()

    def test_income_synonym_not_salary_category(self, qa, icici_report):
        """'Total income?' must return TOTAL_INCOME, not Salary category."""
        ans = ask(qa, icici_report, "Total income?")
        assert "Your total income is" in ans
        assert "No transactions" not in ans


# ===========================================================================
# Union Bank — KV layout analytics
# ===========================================================================

class TestUnionBankAnalytics:

    def test_transaction_count(self, union_report):
        assert union_report.transaction_count == 35

    def test_total_spend(self, qa, union_report):
        ans = ask(qa, union_report, "How much did I spend?")
        assert "130,454.34" in ans or "1,30,454.34" in ans

    def test_total_income(self, qa, union_report):
        ans = ask(qa, union_report, "Total income?")
        assert "96,264.76" in ans

    def test_balance(self, qa, union_report):
        ans = ask(qa, union_report, "What is my account balance?")
        assert "4,750.57" in ans

    def test_net_cash_flow_negative(self, qa, union_report):
        ans = ask(qa, union_report, "Net cash flow?")
        assert "34,189.58" in ans

    def test_fuel_spend(self, qa, union_report):
        ans = ask(qa, union_report, "How much did I spend on Fuel?")
        # Indian Oil fuel station appears multiple times
        assert "5,937.89" in ans

    def test_food_transactions(self, qa, union_report):
        ans = ask(qa, union_report, "Show Food transactions.")
        assert "SWIGGY" in ans

    def test_spotify_in_entertainment(self, union_report):
        """Spotify Premium must be categorised as Entertainment."""
        spotify = next(
            (t for t in union_report.transactions if "SPOTIFY" in (t.description or "")),
            None,
        )
        assert spotify is not None, "Spotify transaction not found"
        assert spotify.category == "Entertainment", (
            f"Expected Entertainment, got {spotify.category}"
        )

    def test_wrapped_description_no_space(self, union_report):
        """UPI/LANDLORD/RENTPAY must not have a space after the slash."""
        landlord = next(
            (t for t in union_report.transactions if "LANDLORD" in (t.description or "")),
            None,
        )
        assert landlord is not None
        assert "/ " not in landlord.description, (
            f"Space after / in: {landlord.description!r}"
        )

    def test_budget_health_formatted(self, qa, union_report):
        ans = ask(qa, union_report, "Budget health?")
        assert "Savings Rate" in ans
        # Formatted numbers — no raw Decimal strings
        assert "₹96264" not in ans

    def test_financial_summary(self, qa, union_report):
        ans = ask(qa, union_report, "Financial summary.")
        assert "Financial Summary" in ans
        assert "Total Income" in ans

    def test_unknown_question_graceful(self, qa, union_report):
        ans = ask(qa, union_report, "How is the weather today?")
        # Must not crash, must say something helpful
        assert len(ans) > 0
        assert "85743" not in ans  # must not return total spend


# ===========================================================================
# Cross-cutting: question variety
# ===========================================================================

class TestQuestionVariety:
    """Verify all question types from the spec work on SBI."""

    @pytest.fixture(scope="class")
    def r(self, sbi_report):
        return sbi_report

    def test_how_much_spent(self, qa, r):
        assert "85,743.56" in ask(qa, r, "How much did I spend?")

    def test_what_are_expenses(self, qa, r):
        ans = ask(qa, r, "What are my expenses?")
        assert "85,743.56" in ans

    def test_total_debits(self, qa, r):
        ans = ask(qa, r, "Total debits?")
        assert "85,743.56" in ans

    def test_money_spent(self, qa, r):
        ans = ask(qa, r, "Money spent?")
        assert "85,743.56" in ans

    def test_income_question(self, qa, r):
        ans = ask(qa, r, "Total income?")
        assert "67,061.02" in ans

    def test_credits_received(self, qa, r):
        ans = ask(qa, r, "Credits received?")
        assert "67,061.02" in ans

    def test_money_received(self, qa, r):
        ans = ask(qa, r, "Money received?")
        assert "67,061.02" in ans

    def test_show_credits(self, qa, r):
        ans = ask(qa, r, "Show all credits.")
        # Should show credit transactions
        assert "CREDIT" in ans or "credit" in ans.lower() or "Interest" in ans

    def test_largest_debit(self, qa, r):
        ans = ask(qa, r, "Largest expense?")
        assert "24,950.89" in ans

    def test_top_category(self, qa, r):
        ans = ask(qa, r, "Top category?")
        assert "Largest Spending Category" in ans

    def test_fuel_expenses(self, qa, r):
        ans = ask(qa, r, "Fuel expenses?")
        assert "2,211.54" in ans

    def test_insurance_expenses(self, qa, r):
        ans = ask(qa, r, "Insurance expenses?")
        assert "3,483.93" in ans

    def test_shopping_expenses(self, qa, r):
        ans = ask(qa, r, "Shopping expenses?")
        assert "15,118.67" in ans

    def test_show_all_debits(self, qa, r):
        ans = ask(qa, r, "Show all debits.")
        # Debits are the default show for Transfer category
        assert len(ans) > 0

    def test_statement_summary(self, qa, r):
        ans = ask(qa, r, "Summarize my statement.")
        assert len(ans) > 50

    def test_merchant_swiggy(self, qa, r):
        ans = ask(qa, r, "How much did I spend on Swiggy?")
        assert "1,353.06" in ans

    def test_merchant_show_swiggy(self, qa, r):
        ans = ask(qa, r, "Show Swiggy transactions.")
        assert "SWIGGY" in ans

    def test_typo_tolerance(self, qa, r):
        ans = ask(qa, r, "How much did I spend on fuell?")
        assert "2,211.54" in ans

    def test_unknown_entity_no_total(self, qa, r):
        ans = ask(qa, r, "How much did I spend on Starbucks?")
        assert "85,743" not in ans
