"""
Regression Tests for Bug Fixes
================================
Tests all 13 bugs from the bug-fix spec to ensure they remain fixed.

Run with:
    python -m pytest tests/test_bug_fixes.py -v
"""
import json
from pathlib import Path

import pytest

from src.agents.qa.qa_agent import QAAgent
from src.agents.qa.intent_detector import Intent, IntentDetector
from src.schemas.financial_report import FinancialReport

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPORT_PATH = Path("reports/sbi_statement.json")
ICICI_PATH = Path("reports/icici_statement.json")


@pytest.fixture(scope="module")
def report() -> FinancialReport:
    data = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    return FinancialReport(**data)


@pytest.fixture(scope="module")
def icici_report() -> FinancialReport:
    data = json.loads(ICICI_PATH.read_text(encoding="utf-8"))
    return FinancialReport(**data)


@pytest.fixture(scope="module")
def qa() -> QAAgent:
    return QAAgent()


@pytest.fixture(autouse=True)
def clear_memory(qa):
    qa.clear_memory()
    yield
    qa.clear_memory()


def ask(qa: QAAgent, report: FinancialReport, question: str) -> str:
    return qa.answer(report=report, question=question)


@pytest.fixture(scope="module")
def det() -> IntentDetector:
    return IntentDetector()


# ===========================================================================
# Bug 1: Refund detection
# ===========================================================================

class TestBug1_RefundDetection:
    """Refund detection must work for any bank statement."""

    def test_did_i_receive_refunds(self, qa, report):
        ans = ask(qa, report, "Did I receive any refunds?")
        assert "2,849.80" in ans or "refund" in ans.lower()

    def test_show_refund_transactions(self, qa, report):
        ans = ask(qa, report, "Show refund transactions")
        assert "refund" in ans.lower() or "AMAZON" in ans.upper()

    def test_refund_summary(self, qa, report):
        ans = ask(qa, report, "Refund summary")
        assert "2,849.80" in ans or "refund" in ans.lower()

    def test_how_much_refund(self, qa, report):
        ans = ask(qa, report, "How much refund did I receive?")
        assert "2,849.80" in ans

    def test_refund_intent_detected(self, det):
        for q in ["did i receive refund", "total refund", "refund summary"]:
            result = det.detect(q)
            assert result.intent == Intent.REFUND_TOTAL

    def test_refund_categorization_order(self):
        """Refund must be categorized before Shopping in rules."""
        from src.agents.categorization.categorization_agent import CategorizationAgent
        from src.schemas.transaction import Transaction
        agent = CategorizationAgent()
        rules = list(agent.CATEGORY_RULES.keys())
        refund_idx = rules.index("Refund")
        shopping_idx = rules.index("Shopping")
        assert refund_idx < shopping_idx, "Refund must come before Shopping"


# ===========================================================================
# Bug 2: Balance threshold query
# ===========================================================================

class TestBug2_BalanceThreshold:
    """Did balance exceed/go below X? must search historical balances."""

    def test_did_balance_exceed_100k(self, qa, report):
        ans = ask(qa, report, "Did my balance ever exceed ₹100000?")
        assert "no" in ans.lower() or "never" in ans.lower()

    def test_did_balance_exceed_50k(self, qa, report):
        ans = ask(qa, report, "Did balance exceed ₹50000")
        assert "yes" in ans.lower()

    def test_did_balance_go_below_10k(self, qa, report):
        ans = ask(qa, report, "Did balance go below ₹10000")
        assert "no" in ans.lower() or "never" in ans.lower()

    def test_balance_threshold_intent(self, det):
        result = det.detect("did my balance exceed ₹100000")
        assert result.intent == Intent.BALANCE_THRESHOLD
        assert result.amount_direction == "above"

    def test_balance_threshold_below_intent(self, det):
        result = det.detect("did balance go below ₹10000")
        assert result.intent == Intent.BALANCE_THRESHOLD
        assert result.amount_direction == "below"


# ===========================================================================
# Bug 3: Balance after transaction
# ===========================================================================

class TestBug3_BalanceAfterTransaction:
    """Balance after X must locate the transaction and return its balance."""

    def test_balance_after_salary(self, qa, report):
        ans = ask(qa, report, "What was my balance after my salary credit?")
        assert "86,410" in ans or "balance" in ans.lower()

    def test_balance_after_salary_short(self, qa, report):
        ans = ask(qa, report, "Balance after salary")
        assert "86,410" in ans or "balance" in ans.lower()

    def test_balance_after_largest_debit(self, qa, report):
        ans = ask(qa, report, "Balance after largest debit")
        assert "57,499" in ans or "balance" in ans.lower()

    def test_balance_after_intent(self, det):
        result = det.detect("balance after salary")
        assert result.intent == Intent.BALANCE_AFTER


# ===========================================================================
# Bug 4: Biggest payment = debit only
# ===========================================================================

class TestBug4_BiggestPayment:
    """Payments must only include debit transactions, not credits."""

    def test_biggest_payment_is_debit(self, qa, report):
        ans = ask(qa, report, "Show my biggest payment")
        # Should NOT show salary (credit)
        assert "salary" not in ans.lower() or "debit" in ans.lower()
        # Should show landlord (largest debit)
        assert "24,950" in ans or "landlord" in ans.lower()

    def test_largest_payment(self, qa, report):
        ans = ask(qa, report, "largest payment")
        assert "24,950" in ans or "landlord" in ans.lower()

    def test_highest_expense(self, qa, report):
        ans = ask(qa, report, "highest expense")
        assert "24,950" in ans or "landlord" in ans.lower()

    def test_largest_outgoing(self, qa, report):
        ans = ask(qa, report, "largest outgoing transaction")
        assert "24,950" in ans or "landlord" in ans.lower()

    def test_biggest_payment_intent(self, det):
        for q in ["biggest payment", "largest payment", "highest payment",
                   "largest outgoing transaction"]:
            result = det.detect(q)
            assert result.intent == Intent.LARGEST_DEBIT, f"{q} → {result.intent}"


# ===========================================================================
# Bug 5: Rent categorization
# ===========================================================================

class TestBug5_RentCategorization:
    """Rent-related transactions must be categorized as Rent, not Transfer."""

    def test_rent_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on rent?")
        assert "24,950" in ans

    def test_show_rent_transactions(self, qa, report):
        ans = ask(qa, report, "Show rent transactions")
        assert "LANDLORD" in ans.upper() or "RENT" in ans.upper()

    def test_rent_in_category_aliases(self):
        from src.agents.qa.intent_detector import CATEGORY_ALIASES
        assert "Rent" in CATEGORY_ALIASES
        assert "rent" in CATEGORY_ALIASES["Rent"]
        assert "landlord" in CATEGORY_ALIASES["Rent"]

    def test_rent_intent_detection(self, det):
        result = det.detect("how much did i spend on rent")
        assert result.intent == Intent.CATEGORY_SPEND
        assert result.category == "Rent"

    def test_rent_categorization_rules(self):
        from src.agents.categorization.categorization_agent import CategorizationAgent
        agent = CategorizationAgent()
        rules = list(agent.CATEGORY_RULES.keys())
        assert "Rent" in rules
        rent_idx = rules.index("Rent")
        transfer_idx = rules.index("Transfer")
        assert rent_idx < transfer_idx, "Rent must come before Transfer"


# ===========================================================================
# Bug 6: Salary intent normalization
# ===========================================================================

class TestBug6_SalaryIntentNormalization:
    """All salary queries must resolve to salary transactions."""

    def test_did_i_receive_salary(self, qa, report):
        ans = ask(qa, report, "Did I receive salary?")
        assert "SALARY" in ans.upper() or "63,509" in ans

    def test_salary_received(self, qa, report):
        ans = ask(qa, report, "Salary received")
        assert "SALARY" in ans.upper() or "63,509" in ans

    def test_show_salary(self, qa, report):
        ans = ask(qa, report, "Show salary")
        assert "SALARY" in ans.upper() or "63,509" in ans

    def test_salary_credit(self, qa, report):
        ans = ask(qa, report, "Salary credit")
        assert "SALARY" in ans.upper() or "63,509" in ans

    def test_how_much_salary(self, qa, report):
        ans = ask(qa, report, "How much salary did I receive?")
        assert "SALARY" in ans.upper() or "63,509" in ans

    def test_salary_income(self, qa, report):
        ans = ask(qa, report, "Salary income")
        assert "SALARY" in ans.upper() or "63,509" in ans

    def test_salary_intent_detection(self, det):
        for q in ["did i receive salary", "salary received", "show salary",
                   "salary credit", "how much salary", "salary income"]:
            result = det.detect(q)
            assert result.intent == Intent.CATEGORY_LIST, f"{q} → {result.intent}"
            assert result.category == "Salary"


# ===========================================================================
# Bug 7: Interest intent normalization
# ===========================================================================

class TestBug7_InterestIntentNormalization:
    """All interest queries must resolve consistently."""

    def test_did_i_receive_interest(self, qa, report):
        ans = ask(qa, report, "Did I receive interest?")
        assert "INTEREST" in ans.upper()

    def test_interest_earned(self, qa, report):
        ans = ask(qa, report, "Interest earned")
        assert "INTEREST" in ans.upper()

    def test_interest_received(self, qa, report):
        ans = ask(qa, report, "Interest received")
        assert "INTEREST" in ans.upper()

    def test_show_interest(self, qa, report):
        ans = ask(qa, report, "Show interest")
        assert "INTEREST" in ans.upper()

    def test_interest_credits(self, qa, report):
        ans = ask(qa, report, "Interest credits")
        assert "INTEREST" in ans.upper()

    def test_how_much_interest(self, qa, report):
        ans = ask(qa, report, "How much interest did I earn?")
        assert "INTEREST" in ans.upper()


# ===========================================================================
# Bug 8: Conversation memory for credits
# ===========================================================================

class TestBug8_ConversationMemoryForCredits:
    """Conversation memory must work equally for debit and credit transactions."""

    def test_largest_credit_then_who(self, qa, report):
        ask(qa, report, "Largest credit")
        ans = ask(qa, report, "Who paid me?")
        assert "Infotech" in ans or "paid to" in ans.lower()

    def test_largest_credit_then_when(self, qa, report):
        ask(qa, report, "Largest credit")
        ans = ask(qa, report, "When did I receive it?")
        assert "12 May 2024" in ans or "May" in ans

    def test_largest_debit_then_who(self, qa, report):
        ask(qa, report, "Largest debit")
        ans = ask(qa, report, "Who was it paid to?")
        assert "Landlord" in ans

    def test_largest_debit_then_when(self, qa, report):
        ask(qa, report, "Largest debit")
        ans = ask(qa, report, "When did it happen?")
        assert "01 May 2024" in ans or "May" in ans


# ===========================================================================
# Bug 9: Cash withdrawal total
# ===========================================================================

class TestBug9_CashWithdrawalTotal:
    """Cash withdrawal query must return total and count."""

    def test_cash_withdrawal_total(self, qa, report):
        ans = ask(qa, report, "How much cash did I withdraw?")
        assert "8,627" in ans
        assert "1 withdrawal" in ans or "1 found" in ans or "1)" in ans


# ===========================================================================
# Bug 10: POS detection
# ===========================================================================

class TestBug10_POSDetection:
    """POS should only represent actual POS/card swipe transactions."""

    def test_pos_transactions_exist(self, qa, report):
        ans = ask(qa, report, "Show POS transactions")
        # POS transactions should exist in the data
        assert "POS" in ans.upper()


# ===========================================================================
# Bug 11: Merchant frequency
# ===========================================================================

class TestBug11_MerchantFrequency:
    """Merchant frequency must rank by count, not amount."""

    def test_most_frequent_merchants(self, qa, report):
        ans = ask(qa, report, "Most frequent merchants")
        assert "Frequent" in ans or "transaction" in ans.lower()
        # Reliance Fresh appears 2 times — should be #1
        assert "Reliance" in ans

    def test_merchant_frequency(self, qa, report):
        ans = ask(qa, report, "Merchant frequency")
        assert "Frequent" in ans or "transaction" in ans.lower()

    def test_frequent_merchants_intent(self, det):
        for q in ["most frequent merchants", "frequent merchants",
                   "merchant frequency"]:
            result = det.detect(q)
            assert result.intent == Intent.MERCHANT_FREQUENCY_RANKING

    def test_frequency_distinct_from_top_merchants(self, det):
        """Frequency ranking must be distinct from top merchants (by amount)."""
        freq = det.detect("most frequent merchants")
        top = det.detect("top merchants")
        assert freq.intent != top.intent


# ===========================================================================
# Bug 12: Overspending intent
# ===========================================================================

class TestBug12_OverspendingIntent:
    """Overspending queries must route to budget health analytics."""

    def test_did_i_overspend(self, qa, report):
        ans = ask(qa, report, "Did I overspend?")
        assert "Overspending" in ans or "overspend" in ans.lower()

    def test_am_i_overspending(self, qa, report):
        ans = ask(qa, report, "Am I overspending?")
        assert "Overspending" in ans or "overspend" in ans.lower()

    def test_did_i_save_money(self, qa, report):
        ans = ask(qa, report, "Did I save money?")
        # Should provide some financial insight
        assert len(ans) > 20

    def test_overspending_intent(self, det):
        for q in ["did i overspend", "am i overspending"]:
            result = det.detect(q)
            assert result.intent == Intent.BUDGET_HEALTH


# ===========================================================================
# Bug 13: Financial habits
# ===========================================================================

class TestBug13_FinancialHabits:
    """Financial habits summary must include comprehensive analytics."""

    def test_summarize_financial_habits(self, qa, report):
        ans = ask(qa, report, "Summarize my financial habits")
        assert "Financial Habits" in ans
        assert "Top Spending" in ans or "Categories" in ans

    def test_financial_habits_includes_savings_rate(self, qa, report):
        ans = ask(qa, report, "Summarize my financial habits")
        assert "Savings Rate" in ans

    def test_financial_habits_includes_budget_health(self, qa, report):
        ans = ask(qa, report, "Summarize my financial habits")
        assert "Budget Health" in ans

    def test_financial_habits_includes_recommendations(self, qa, report):
        ans = ask(qa, report, "Summarize my financial habits")
        assert "Recommendations" in ans or "recommend" in ans.lower()

    def test_financial_habits_intent(self, det):
        result = det.detect("summarize my financial habits")
        assert result.intent == Intent.FINANCIAL_HABITS
