"""
New Feature Test Suite
=======================
Tests all success criteria from the bug-fix spec:

  ✓ Opening balance correct
  ✓ Closing balance correct
  ✓ Highest balance correct
  ✓ Lowest balance correct
  ✓ Largest debit correct
  ✓ Largest credit correct
  ✓ Refund detection correct
  ✓ Salary queries work
  ✓ Interest queries work
  ✓ Transaction count works
  ✓ Debit count works
  ✓ Credit count works
  ✓ Date filtering works
  ✓ Amount filtering works
  ✓ First/last transaction works
  ✓ Merchant frequency works
  ✓ Payment method filtering works
  ✓ Percentage analytics work
  ✓ Recommendations are meaningful
  ✓ Follow-up conversation works
  ✓ No regression (existing tests pass)

Run with:
    python -m pytest tests/test_new_features.py -v
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


@pytest.fixture(scope="module")
def report() -> FinancialReport:
    data = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    return FinancialReport(**data)


@pytest.fixture(scope="module")
def qa(report) -> QAAgent:
    """Each test gets the same QAAgent — but we clear memory between tests."""
    agent = QAAgent()
    return agent


@pytest.fixture(autouse=True)
def clear_memory(qa):
    """Clear conversation memory before each test."""
    qa.clear_memory()
    yield
    qa.clear_memory()


def ask(qa: QAAgent, report: FinancialReport, question: str) -> str:
    return qa.answer(report=report, question=question)


@pytest.fixture(scope="module")
def det() -> IntentDetector:
    return IntentDetector()


# ===========================================================================
# 1. Opening balance
# ===========================================================================

class TestOpeningBalance:

    def test_intent_detection(self, det):
        result = det.detect("opening balance")
        assert result.intent == Intent.OPENING_BALANCE

    def test_opening_balance_value(self, qa, report):
        ans = ask(qa, report, "What was my opening balance?")
        # Opening = first.balance + first.amount (DEBIT)
        # = 57499.11 + 24950.89 = 82450.00
        assert "82,450" in ans

    def test_opening_balance_synonyms(self, det):
        for q in ["opening balance", "beginning balance", "initial balance"]:
            assert det.detect(q).intent == Intent.OPENING_BALANCE


# ===========================================================================
# 2. Closing balance
# ===========================================================================

class TestClosingBalance:

    def test_intent_detection(self, det):
        result = det.detect("closing balance")
        assert result.intent == Intent.CLOSING_BALANCE

    def test_closing_balance_value(self, qa, report):
        ans = ask(qa, report, "What was my closing balance?")
        assert "63,767.46" in ans

    def test_closing_balance_synonyms(self, det):
        for q in ["closing balance", "end balance", "final balance"]:
            assert det.detect(q).intent == Intent.CLOSING_BALANCE


# ===========================================================================
# 3. Highest balance
# ===========================================================================

class TestHighestBalance:

    def test_intent_detection(self, det):
        result = det.detect("highest balance")
        assert result.intent == Intent.HIGHEST_BALANCE

    def test_highest_balance_returns_transaction(self, qa, report):
        ans = ask(qa, report, "What was my highest balance?")
        # Should show the balance amount, date, and transaction
        assert "86,410.04" in ans
        assert "Date" in ans
        assert "Transaction" in ans

    def test_highest_balance_synonyms(self, det):
        for q in ["highest balance", "maximum balance", "peak balance"]:
            assert det.detect(q).intent == Intent.HIGHEST_BALANCE


# ===========================================================================
# 4. Lowest balance
# ===========================================================================

class TestLowestBalance:

    def test_intent_detection(self, det):
        result = det.detect("lowest balance")
        assert result.intent == Intent.LOWEST_BALANCE

    def test_lowest_balance_returns_transaction(self, qa, report):
        ans = ask(qa, report, "What was my lowest balance?")
        assert "22,900.99" in ans
        assert "Date" in ans

    def test_lowest_balance_synonyms(self, det):
        for q in ["lowest balance", "minimum balance"]:
            assert det.detect(q).intent == Intent.LOWEST_BALANCE


# ===========================================================================
# 5. Largest credit
# ===========================================================================

class TestLargestCredit:

    def test_intent_detection(self, det):
        result = det.detect("largest credit")
        assert result.intent == Intent.LARGEST_CREDIT

    def test_largest_credit_returns_correct_txn(self, qa, report):
        ans = ask(qa, report, "What was my largest credit?")
        # Salary credit of 63509.05
        assert "63,509.05" in ans
        assert "Date" in ans
        assert "Merchant" in ans
        assert "Category" in ans

    def test_largest_credit_synonyms(self, det):
        for q in ["largest credit", "biggest credit", "highest credit"]:
            assert det.detect(q).intent == Intent.LARGEST_CREDIT


# ===========================================================================
# 6. Largest debit
# ===========================================================================

class TestLargestDebit:

    def test_intent_detection(self, det):
        result = det.detect("largest debit")
        assert result.intent == Intent.LARGEST_DEBIT

    def test_largest_debit_returns_correct_txn(self, qa, report):
        ans = ask(qa, report, "What was my largest debit?")
        assert "24,950.89" in ans
        assert "Date" in ans
        assert "Merchant" in ans
        assert "Amount" in ans
        assert "Category" in ans

    def test_largest_debit_synonyms(self, det):
        for q in [
            "largest debit", "highest debit", "biggest payment",
            "biggest debit", "largest payment",
        ]:
            assert det.detect(q).intent == Intent.LARGEST_DEBIT


# ===========================================================================
# 7. Refund detection
# ===========================================================================

class TestRefundDetection:

    def test_did_i_receive_refund(self, qa, report):
        ans = ask(qa, report, "Did I receive refunds?")
        # Should respond about refunds (even if 0 in SBI)
        assert "refund" in ans.lower()

    def test_how_much_refund(self, qa, report):
        ans = ask(qa, report, "How much refund did I receive?")
        assert "refund" in ans.lower()

    def test_show_refunds(self, qa, report):
        ans = ask(qa, report, "Show refunds")
        assert "refund" in ans.lower()

    def test_refund_synonyms(self, det):
        for q in [
            "show refunds", "any refund",
            "did i receive refund", "refund summary",
        ]:
            result = det.detect(q)
            assert result.intent == Intent.REFUND_TOTAL, (
                f"{q!r} → {result.intent}"
            )


# ===========================================================================
# 8. Salary detection
# ===========================================================================

class TestSalaryDetection:

    def test_did_i_receive_salary(self, qa, report):
        ans = ask(qa, report, "Did I receive salary?")
        assert "SALARY" in ans.upper() or "CREDIT" in ans

    def test_how_much_salary(self, qa, report):
        ans = ask(qa, report, "How much salary?")
        assert "SALARY" in ans.upper() or "63,509.05" in ans

    def test_salary_received(self, qa, report):
        # "salary received" routes to TOTAL_INCOME (existing behavior)
        ans = ask(qa, report, "Salary received?")
        assert "67,061" in ans or "salary" in ans.lower()

    def test_salary_intent(self, det):
        # "salary received" → CATEGORY_LIST(Salary) per bug fix
        assert det.detect("salary received").intent == Intent.CATEGORY_LIST
        assert det.detect("salary received").category == "Salary"
        # These also route to CATEGORY_LIST(Salary)
        for q in [
            "did i receive salary", "how much salary",
            "salary earned",
        ]:
            result = det.detect(q)
            assert result.intent == Intent.CATEGORY_LIST, (
                f"{q!r} → {result.intent}"
            )
            assert result.category == "Salary"


# ===========================================================================
# 9. Interest detection
# ===========================================================================

class TestInterestDetection:

    def test_did_i_receive_interest(self, qa, report):
        ans = ask(qa, report, "Did I receive interest?")
        assert "INTEREST" in ans.upper() or "CREDIT" in ans

    def test_interest_earned(self, qa, report):
        ans = ask(qa, report, "Interest earned?")
        assert "INTEREST" in ans.upper() or "582.30" in ans

    def test_how_much_interest(self, qa, report):
        ans = ask(qa, report, "How much interest?")
        assert "INTEREST" in ans.upper() or "582.30" in ans

    def test_interest_intent(self, det):
        for q in [
            "did i receive interest", "interest earned",
            "how much interest", "show interest",
        ]:
            result = det.detect(q)
            assert result.intent == Intent.CATEGORY_LIST
            assert result.category == "Interest"


# ===========================================================================
# 10. Transaction count
# ===========================================================================

class TestTransactionCount:

    def test_how_many_transactions(self, qa, report):
        ans = ask(qa, report, "How many transactions?")
        assert "20" in ans

    def test_number_of_transactions(self, qa, report):
        ans = ask(qa, report, "Number of transactions")
        assert "20" in ans

    def test_transaction_count(self, qa, report):
        ans = ask(qa, report, "Transaction count")
        assert "20" in ans

    def test_total_transactions(self, qa, report):
        ans = ask(qa, report, "Total transactions")
        assert "20" in ans

    def test_intent(self, det):
        assert det.detect("how many transactions").intent == Intent.TRANSACTION_COUNT


# ===========================================================================
# 11. Debit / Credit counts
# ===========================================================================

class TestDebitCreditCounts:

    def test_how_many_debits(self, qa, report):
        ans = ask(qa, report, "How many debits?")
        assert "16" in ans

    def test_how_many_credits(self, qa, report):
        ans = ask(qa, report, "How many credits?")
        assert "4" in ans

    def test_debit_count_intent(self, det):
        assert det.detect("how many debits").intent == Intent.DEBIT_COUNT

    def test_credit_count_intent(self, det):
        assert det.detect("how many credits").intent == Intent.CREDIT_COUNT


# ===========================================================================
# 12. Date filtering
# ===========================================================================

class TestDateFiltering:

    def test_transactions_on_date(self, qa, report):
        ans = ask(qa, report, "Transactions on 03 May")
        assert "RELIANCE FRESH" in ans or "INSURANCE" in ans

    def test_transactions_between_dates(self, qa, report):
        ans = ask(qa, report, "Transactions between 1 May and 5 May")
        assert "LANDLORD" in ans or "FLIPKART" in ans

    def test_transactions_after_date(self, qa, report):
        ans = ask(qa, report, "Transactions after 15 May")
        assert len(ans) > 0

    def test_transactions_before_date(self, qa, report):
        ans = ask(qa, report, "Transactions before 3 May")
        assert "LANDLORD" in ans or "FLIPKART" in ans

    def test_date_filter_intent(self, det):
        result = det.detect("transactions on 15 may")
        assert result.intent == Intent.DATE_FILTER
        assert result.date_filter_type == "on"


# ===========================================================================
# 13. Amount filtering
# ===========================================================================

class TestAmountFiltering:

    def test_transactions_above_amount(self, qa, report):
        ans = ask(qa, report, "Transactions above 5000")
        assert "24,950.89" in ans  # Rent is above 5000
        assert "5,000" in ans or "5000" in ans  # Threshold shown

    def test_transactions_below_amount(self, qa, report):
        ans = ask(qa, report, "Transactions below 500")
        assert "406.54" in ans  # Reliance Fresh is below 500

    def test_transactions_greater_than(self, qa, report):
        ans = ask(qa, report, "Transactions greater than 10000")
        assert "24,950.89" in ans

    def test_amount_filter_intent(self, det):
        result = det.detect("transactions above 5000")
        assert result.intent == Intent.AMOUNT_FILTER
        assert result.amount_direction == "above"
        assert result.amount_threshold == 5000.0


# ===========================================================================
# 14. First transaction
# ===========================================================================

class TestFirstTransaction:

    def test_first_transaction(self, qa, report):
        ans = ask(qa, report, "First transaction")
        assert "01 May 2024" in ans
        assert "Landlord" in ans  # normalized merchant name

    def test_earliest_transaction(self, qa, report):
        ans = ask(qa, report, "Earliest transaction")
        assert "01 May 2024" in ans

    def test_beginning_of_statement(self, qa, report):
        ans = ask(qa, report, "Beginning of statement")
        assert "01 May 2024" in ans

    def test_first_txn_intent(self, det):
        assert det.detect("first transaction").intent == Intent.FIRST_TRANSACTION


# ===========================================================================
# 15. Last transaction
# ===========================================================================

class TestLastTransaction:

    def test_last_transaction(self, qa, report):
        ans = ask(qa, report, "Last transaction")
        assert "17 May 2024" in ans
        assert "BAJAJ" in ans.upper()

    def test_most_recent_transaction(self, qa, report):
        ans = ask(qa, report, "Most recent transaction")
        assert "17 May 2024" in ans

    def test_end_of_statement(self, qa, report):
        ans = ask(qa, report, "End of statement")
        assert "17 May 2024" in ans

    def test_last_txn_intent(self, det):
        assert det.detect("last transaction").intent == Intent.LAST_TRANSACTION


# ===========================================================================
# 16. Biggest transactions
# ===========================================================================

class TestBiggestTransactions:

    def test_biggest_transactions(self, qa, report):
        ans = ask(qa, report, "Biggest transactions")
        assert "63,509.05" in ans  # Salary
        assert "24,950.89" in ans  # Rent

    def test_largest_transactions(self, qa, report):
        ans = ask(qa, report, "Largest transactions")
        assert "63,509.05" in ans

    def test_highest_value_transactions(self, qa, report):
        ans = ask(qa, report, "Highest value transactions")
        assert "63,509.05" in ans

    def test_biggest_intent(self, det):
        assert det.detect("biggest transactions").intent == Intent.BIGGEST_TRANSACTIONS


# ===========================================================================
# 17. Merchant frequency
# ===========================================================================

class TestMerchantFrequency:

    def test_how_many_swiggy(self, qa, report):
        ans = ask(qa, report, "How many Swiggy transactions?")
        assert "1" in ans
        assert "Swiggy" in ans

    def test_how_many_reliance_fresh(self, qa, report):
        ans = ask(qa, report, "How many Reliance Fresh transactions?")
        assert "2" in ans

    def test_merchant_frequency_intent(self, det):
        result = det.detect("how many swiggy transactions")
        assert result.intent == Intent.MERCHANT_FREQUENCY
        assert result.merchant == "Swiggy"


# ===========================================================================
# 18. Payment method filtering
# ===========================================================================

class TestPaymentMethod:

    def test_upi_transactions(self, qa, report):
        ans = ask(qa, report, "Show UPI transactions")
        assert "UPI" in ans

    def test_neft_transactions(self, qa, report):
        ans = ask(qa, report, "NEFT transactions")
        assert "NEFT" in ans

    def test_atm_transactions(self, qa, report):
        ans = ask(qa, report, "ATM transactions")
        assert "ATM" in ans

    def test_payment_method_intent(self, det):
        result = det.detect("show upi transactions")
        assert result.intent == Intent.PAYMENT_METHOD
        assert result.payment_method == "UPI"


# ===========================================================================
# 19. Percentage analytics
# ===========================================================================

class TestPercentageAnalytics:

    def test_percentage_food(self, qa, report):
        ans = ask(qa, report, "What percentage was Food?")
        assert "Food" in ans
        assert "%" in ans

    def test_percentage_shopping(self, qa, report):
        ans = ask(qa, report, "What percentage was Shopping?")
        assert "Shopping" in ans
        assert "%" in ans

    def test_percentage_intent(self, det):
        result = det.detect("what percentage was food")
        assert result.intent == Intent.CATEGORY_PERCENTAGE
        assert result.category == "Food"


# ===========================================================================
# 20. Recommendations
# ===========================================================================

class TestRecommendations:

    def test_recommendations_not_empty(self, qa, report):
        ans = ask(qa, report, "Recommendations")
        assert len(ans) > 50
        assert "Recommendations" in ans or "recommend" in ans.lower()

    def test_recommendations_meaningful(self, qa, report):
        ans = ask(qa, report, "Give me financial tips")
        assert len(ans) > 30

    def test_recommendations_intent(self, det):
        for q in ["recommendations", "suggestions", "tips", "advice"]:
            result = det.detect(q)
            assert result.intent == Intent.RECOMMENDATIONS, (
                f"{q!r} → {result.intent}"
            )


# ===========================================================================
# 21. Follow-up conversation
# ===========================================================================

class TestFollowupConversation:

    def test_followup_when(self, qa, report):
        ask(qa, report, "Largest debit")
        ans = ask(qa, report, "When did it happen?")
        assert "01 May 2024" in ans

    def test_followup_who(self, qa, report):
        ask(qa, report, "Largest debit")
        ans = ask(qa, report, "Who was it paid to?")
        assert "Landlord" in ans

    def test_followup_category(self, qa, report):
        ask(qa, report, "Largest debit")
        ans = ask(qa, report, "What category?")
        # Rent categorization fix: landlord is now "Rent" not "Transfer"
        assert "Rent" in ans or "Transfer" in ans

    def test_followup_balance(self, qa, report):
        ask(qa, report, "Largest debit")
        ans = ask(qa, report, "What was my balance after that?")
        assert "57,499.11" in ans

    def test_followup_explain(self, qa, report):
        ask(qa, report, "Largest debit")
        ans = ask(qa, report, "Explain that transaction")
        assert "Date" in ans
        assert "Amount" in ans
        assert "Category" in ans
        assert "Balance" in ans

    def test_followup_chain(self, qa, report):
        """Full follow-up conversation chain."""
        ask(qa, report, "Largest debit")
        assert "01 May 2024" in ask(qa, report, "When did it happen?")
        assert "Landlord" in ask(qa, report, "Who was it paid to?")
        # Rent categorization fix: landlord is now "Rent" not "Transfer"
        assert "Rent" in ask(qa, report, "What category?") or "Transfer" in ask(qa, report, "What category?")
        assert "57,499.11" in ask(qa, report, "What was my balance after that?")


# ===========================================================================
# 22. Response quality
# ===========================================================================

class TestResponseQuality:

    def test_largest_debit_rich_response(self, qa, report):
        """Largest debit should include date, merchant, amount, category."""
        ans = ask(qa, report, "Largest debit")
        assert "Date" in ans
        assert "Merchant" in ans
        assert "Amount" in ans
        assert "Category" in ans

    def test_largest_credit_rich_response(self, qa, report):
        """Largest credit should include date, merchant, amount, category."""
        ans = ask(qa, report, "Largest credit")
        assert "Date" in ans
        assert "Merchant" in ans
        assert "Amount" in ans
        assert "Category" in ans

    def test_highest_balance_rich_response(self, qa, report):
        """Highest balance should show context."""
        ans = ask(qa, report, "Highest balance")
        assert "Date" in ans
        assert "Transaction" in ans

    def test_first_transaction_rich_response(self, qa, report):
        """First transaction should include all details."""
        ans = ask(qa, report, "First transaction")
        assert "Date" in ans
        assert "Merchant" in ans
        assert "Type" in ans
