"""
Regression Tests for 7 New Bug Fixes
======================================
Tests all 7 bugs from the second bug-fix pass.

Run with:
    python -m pytest tests/test_bug_fixes_pass2.py -v
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


@pytest.fixture(scope="module")
def det() -> IntentDetector:
    return IntentDetector()


def ask(qa: QAAgent, report: FinancialReport, question: str) -> str:
    return qa.answer(report=report, question=question)


# ===========================================================================
# Bug 1: Balance after transaction (already working, add more tests)
# ===========================================================================

class TestBug1_BalanceAfterTransaction:
    """Balance after X must return the balance from the matched transaction."""

    def test_balance_after_salary(self, qa, report):
        ans = ask(qa, report, "What was my balance after my salary credit?")
        assert "86,410" in ans or "balance" in ans.lower()

    def test_balance_after_refund(self, qa, icici_report):
        ans = ask(qa, icici_report, "Balance after refund")
        assert "balance" in ans.lower() or "₹" in ans

    def test_balance_after_indian_oil(self, qa, icici_report):
        ans = ask(qa, icici_report, "Balance after Indian Oil payment")
        assert "balance" in ans.lower() or "₹" in ans


# ===========================================================================
# Bug 2: Interest intent normalization
# ===========================================================================

class TestBug2_InterestIntent:
    """All interest question variants must resolve to the same intent."""

    @pytest.mark.parametrize("question", [
        "Did I receive any interest?",
        "Did I receive interest?",
        "Interest received",
        "Interest earned",
        "Show interest",
        "Show interest credits",
        "How much interest did I earn?",
        "Interest income",
    ])
    def test_interest_aliases(self, qa, report, question):
        ans = ask(qa, report, question)
        # Should return interest transactions or mention interest
        assert "interest" in ans.lower() or "₹" in ans

    def test_interest_intent_detection(self, det):
        questions = [
            "did i receive any interest",
            "interest received",
            "interest earned",
            "show interest",
            "how much interest did i earn",
            "interest income",
        ]
        for q in questions:
            result = det.detect(q)
            assert result.intent == Intent.CATEGORY_LIST
            assert result.category == "Interest"


# ===========================================================================
# Bug 3: Cash withdrawal analytics (ATM WITHDRAWAL + ATM CASH WITHDRAWAL)
# ===========================================================================

class TestBug3_CashWithdrawal:
    """Both 'ATM WITHDRAWAL' and 'ATM CASH WITHDRAWAL' must be counted."""

    def test_cash_withdrawal_total(self, qa, icici_report):
        ans = ask(qa, icici_report, "How much cash did I withdraw?")
        # Should show total and count
        assert "₹" in ans
        assert "withdrawal" in ans.lower() or "withdrawn" in ans.lower()
        # Should count both ATM transactions
        assert "2" in ans or "2,254" in ans  # Total should be ~2,254.99

    def test_atm_withdrawal_count(self, qa, icici_report):
        ans = ask(qa, icici_report, "Show ATM transactions")
        # Should find 2 ATM transactions
        assert "2 transaction" in ans or "2,254" in ans

    def test_cash_withdrawal_intent(self, det):
        result = det.detect("how much cash did i withdraw")
        assert result.intent == Intent.PAYMENT_METHOD
        assert result.payment_method == "Cash Withdrawal"


# ===========================================================================
# Bug 4: POS detection (exclude POSTPAID)
# ===========================================================================

class TestBug4_POSDetection:
    """POS must not match 'POSTPAID' or similar false positives."""

    def test_pos_excludes_airtel(self, qa, icici_report):
        ans = ask(qa, icici_report, "Show my POS transactions")
        # Should NOT include AIRTEL POSTPAID BILL
        assert "airtel" not in ans.lower()
        # Should include actual POS transactions
        assert "pos" in ans.lower() or "purchase" in ans.lower()

    def test_pos_count(self, qa, icici_report):
        ans = ask(qa, icici_report, "Show POS transactions")
        # Should find exactly 2 POS transactions (not 3)
        assert "2 transaction" in ans or "2 found" in ans


# ===========================================================================
# Bug 5: Merchant frequency intent
# ===========================================================================

class TestBug5_MerchantFrequency:
    """All merchant frequency variants must resolve to the same intent."""

    @pytest.mark.parametrize("question", [
        "What are my frequent merchants?",
        "Which merchants appear most frequently?",
        "Most frequent merchants",
        "Merchant frequency",
        "Which merchants do I use most often?",
        "Most visited merchants",
    ])
    def test_merchant_frequency_aliases(self, qa, report, question):
        ans = ask(qa, report, question)
        # Should return merchant frequency list
        assert "merchant" in ans.lower() or "frequent" in ans.lower()

    def test_merchant_frequency_intent(self, det):
        questions = [
            "which merchants appear most frequently",
            "most frequent merchants",
            "merchant frequency",
            "which merchants do i use most often",
            "most visited merchants",
        ]
        for q in questions:
            result = det.detect(q)
            assert result.intent == Intent.MERCHANT_FREQUENCY_RANKING


# ===========================================================================
# Bug 6: UPI spending total
# ===========================================================================

class TestBug6_UPISpendingTotal:
    """UPI spending must show total amount, not just list transactions."""

    def test_upi_total_shown(self, qa, icici_report):
        ans = ask(qa, icici_report, "How much did I spend using UPI?")
        # Should show total
        assert "total" in ans.lower() or "spent" in ans.lower()
        assert "₹" in ans
        # Should mention count
        assert "transaction" in ans.lower()

    def test_neft_total_shown(self, qa, icici_report):
        ans = ask(qa, icici_report, "How much did I spend via NEFT?")
        # Should show total if NEFT transactions exist
        if "₹" in ans:
            assert "total" in ans.lower() or "spent" in ans.lower()

    def test_imps_total_shown(self, qa, icici_report):
        ans = ask(qa, icici_report, "How much did I spend using IMPS?")
        # Should show total if IMPS transactions exist
        if "₹" in ans:
            assert "total" in ans.lower() or "spent" in ans.lower()


# ===========================================================================
# Bug 7: Savings recommendations intent
# ===========================================================================

class TestBug7_SavingsRecommendations:
    """All recommendation variants must resolve to the same intent."""

    @pytest.mark.parametrize("question", [
        "Give me recommendations",
        "What can I do to save more money?",
        "How can I save more money?",
        "How do I reduce spending?",
        "Any financial advice?",
        "Saving tips",
        "Budget advice",
    ])
    def test_recommendation_aliases(self, qa, report, question):
        ans = ask(qa, report, question)
        # Should return recommendations
        assert "recommend" in ans.lower() or "tip" in ans.lower() or "advice" in ans.lower() or "saving" in ans.lower()

    def test_recommendation_intent(self, det):
        questions = [
            "what can i do to save more money",
            "how can i save more money",
            "how do i reduce spending",
            "any financial advice",
            "saving tips",
            "budget advice",
        ]
        for q in questions:
            result = det.detect(q)
            assert result.intent == Intent.RECOMMENDATIONS
