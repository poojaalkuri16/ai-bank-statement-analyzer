"""
Regression Tests for Bug-Fix Pass 3
====================================
Tests 2 isolated bugs:
  1. Balance after transaction lookup intercepted by conversation memory
  2. Cash withdrawal aggregation missing ATM WITHDRAWAL variants

Run with:
    python -m pytest tests/test_bug_fixes_pass3.py -v
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
NO_TABLE2_PATH = Path("reports/no_table2.json")


@pytest.fixture(scope="module")
def report() -> FinancialReport:
    data = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    return FinancialReport(**data)


@pytest.fixture(scope="module")
def icici_report() -> FinancialReport:
    data = json.loads(ICICI_PATH.read_text(encoding="utf-8"))
    return FinancialReport(**data)


@pytest.fixture(scope="module")
def no_table2_report() -> FinancialReport:
    data = json.loads(NO_TABLE2_PATH.read_text(encoding="utf-8"))
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
# Bug 1: Balance after transaction — direct lookup not intercepted
#         by conversation memory
# ===========================================================================

class TestBug1_BalanceAfterDirectLookup:
    """
    Direct queries like 'What was my balance after my salary credit?'
    must resolve via BALANCE_AFTER intent even when conversation
    memory holds a different transaction.
    """

    def test_balance_after_salary_with_memory(self, qa, no_table2_report):
        """Set memory to RTGS, then ask balance after salary."""
        ask(qa, no_table2_report, "Show RTGS transactions")
        ans = ask(qa, no_table2_report,
                   "What was my balance after my salary credit?")
        # Must return the salary balance, NOT the RTGS balance
        assert "95,586.75" in ans

    def test_balance_after_refund_with_memory(self, qa, no_table2_report):
        """Set memory to a non-refund, then ask balance after refund."""
        ask(qa, no_table2_report, "Show my salary transactions")
        ans = ask(qa, no_table2_report,
                   "What was my balance after the refund?")
        assert "balance" in ans.lower() or "₹" in ans

    def test_balance_after_emi_with_memory(self, qa, no_table2_report):
        """Set memory to food, then ask balance after EMI."""
        ask(qa, no_table2_report, "Show food transactions")
        ans = ask(qa, no_table2_report,
                   "What was my balance after EMI?")
        assert "balance" in ans.lower() or "₹" in ans

    def test_balance_after_rtgs_with_memory(self, qa, no_table2_report):
        """Set memory to salary, then ask balance after RTGS."""
        ask(qa, no_table2_report, "Show my salary transactions")
        ans = ask(qa, no_table2_report,
                   "What was my balance after RTGS?")
        assert "balance" in ans.lower() or "₹" in ans

    def test_conversation_memory_still_works(self, qa, no_table2_report):
        """Verify follow-up questions using 'that' still work."""
        ask(qa, no_table2_report, "Show my largest credit")
        ans = ask(qa, no_table2_report, "What was my balance after that?")
        # Should use conversation memory, return the largest credit's balance
        assert "balance" in ans.lower() and "₹" in ans

    def test_followup_category_still_works(self, qa, no_table2_report):
        """Verify follow-up 'What category was it?' still works."""
        ask(qa, no_table2_report, "Show largest debit")
        ans = ask(qa, no_table2_report, "What category was it?")
        assert "categoris" in ans.lower() or "category" in ans.lower()

    def test_followup_date_still_works(self, qa, no_table2_report):
        """Verify follow-up 'When did it happen?' still works."""
        ask(qa, no_table2_report, "Show my salary transactions")
        ans = ask(qa, no_table2_report, "When did it happen?")
        assert "happened on" in ans.lower()

    def test_standalone_balance_no_memory(self, qa, no_table2_report):
        """'What is my balance?' without prior context → closing balance."""
        ans = ask(qa, no_table2_report, "What is my balance?")
        assert "balance" in ans.lower() and "₹" in ans

    def test_balance_after_salary_no_memory(self, qa, no_table2_report):
        """Direct balance-after query without prior context."""
        ans = ask(qa, no_table2_report,
                   "What was my balance after my salary credit?")
        assert "95,586.75" in ans

    def test_balance_after_intent_detected(self, det):
        """BALANCE_AFTER intent must be detected."""
        result = det.detect("what was my balance after my salary credit")
        assert result.intent == Intent.BALANCE_AFTER


# ===========================================================================
# Bug 2: Cash withdrawal aggregation — all ATM variants counted
# ===========================================================================

class TestBug2_CashWithdrawalAggregation:
    """
    'How much cash did I withdraw?' must include ALL ATM withdrawal
    variants: ATM CASH WITHDRAWAL, ATM WITHDRAWAL, etc.
    """

    def test_cash_withdrawal_total(self, qa, no_table2_report):
        ans = ask(qa, no_table2_report, "How much cash did I withdraw?")
        # Must include all 3 ATM variants
        assert "5,243.45" in ans
        assert "3 withdrawal" in ans

    def test_cash_withdrawal_lists_all(self, qa, no_table2_report):
        ans = ask(qa, no_table2_report, "How much cash did I withdraw?")
        # All 3 transactions should be listed
        assert "ATM CASH WITHDRAWAL" in ans.upper()
        assert "ATM WITHDRAWAL" in ans.upper()

    def test_atm_transactions_query(self, qa, no_table2_report):
        """'Show ATM transactions' should find all variants."""
        ans = ask(qa, no_table2_report, "Show ATM transactions")
        assert "3 transaction" in ans or "5,243" in ans

    def test_by_payment_method_resolves_keywords(self, no_table2_report):
        """by_payment_method must resolve canonical name to keywords."""
        from src.agents.qa.transaction_query_engine import TransactionQueryEngine
        engine = TransactionQueryEngine()
        matches = engine.by_payment_method(
            no_table2_report.transactions, "Cash Withdrawal",
        )
        assert len(matches) == 3

    def test_by_payment_method_atm(self, no_table2_report):
        """by_payment_method('ATM') should also find all ATM variants."""
        from src.agents.qa.transaction_query_engine import TransactionQueryEngine
        engine = TransactionQueryEngine()
        matches = engine.by_payment_method(
            no_table2_report.transactions, "ATM",
        )
        assert len(matches) == 3

    def test_cash_withdrawal_sbi_report(self, qa, report):
        """SBI report has 1 ATM transaction — should still work."""
        ans = ask(qa, report, "How much cash did I withdraw?")
        assert "₹" in ans
        assert "withdrawal" in ans.lower() or "withdrawn" in ans.lower()

    def test_cash_withdrawal_icici_report(self, qa, icici_report):
        """ICICI report has 2 ATM transactions — both must be counted."""
        ans = ask(qa, icici_report, "How much cash did I withdraw?")
        assert "2,254.99" in ans
        assert "2 withdrawal" in ans
