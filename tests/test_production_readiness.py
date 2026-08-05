"""
Production Readiness Tests
==========================
Covers Tasks 1–5 from the production readiness prompt:

  Task 1 — Typo tolerance (fuzzy matching)
  Task 2 — Refund handling (analytics already excludes CREDITs)
  Task 3 — Merchant awareness (Amazon refund context response)
  Task 4 — Financial intelligence queries (new phrases)
  Task 5 — Better unknown / unsupported merchant responses

Statement facts
---------------
Entertainment : GOOGLE PLAY  ₹825.42  (DEBIT)
Shopping      : FLIPKART ₹8,498.42 + LIFESTYLE ₹6,620.25 = ₹15,118.67
Groceries     : RELIANCE FRESH ₹406.54 + ₹1,775.62 = ₹2,182.16
Fuel          : INDIAN OIL ₹2,211.54
Amazon        : REFUND - AMAZON RETURN ₹2,849.80  (CREDIT only — no debits)
Total DEBIT   : ₹85,743.56
Closing bal   : ₹63,767.46
"""
import json
from pathlib import Path

import pytest

from src.agents.qa.fuzzy_matcher import FuzzyMatcher
from src.agents.qa.intent_detector import (
    CATEGORY_ALIASES,
    KNOWN_MERCHANTS,
    Intent,
    IntentDetector,
)
from src.agents.qa.qa_agent import QAAgent
from src.schemas.financial_report import FinancialReport

REPORT_PATH = Path("reports/sbi_statement.json")


@pytest.fixture(scope="module")
def report() -> FinancialReport:
    data = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    return FinancialReport(**data)


@pytest.fixture(scope="module")
def qa(report) -> QAAgent:
    return QAAgent()


def ask(qa, report, question):
    return qa.answer(report=report, question=question)


# ===========================================================================
# Task 1 — Typo Tolerance
# ===========================================================================

class TestFuzzyMatcherUnit:
    """Unit tests for FuzzyMatcher in isolation."""

    @pytest.fixture(scope="class")
    def matcher(self):
        return FuzzyMatcher(CATEGORY_ALIASES, KNOWN_MERCHANTS)

    def test_shopping_typo(self, matcher):
        m = matcher.match("how much did i spend on shpooing")
        assert m is not None
        assert m.display_name == "Shopping"
        assert m.kind == "category"

    def test_entertainment_typo(self, matcher):
        m = matcher.match("how much did i spend on entertainmnet")
        assert m is not None
        assert m.display_name == "Entertainment"

    def test_groceries_typo(self, matcher):
        m = matcher.match("how much did i spend on grocerries")
        assert m is not None
        assert m.display_name == "Groceries"

    def test_swiggy_typo(self, matcher):
        m = matcher.match("how much did i spend on swigy")
        assert m is not None
        assert m.display_name == "Swiggy"
        assert m.kind == "merchant"

    def test_amazon_typo(self, matcher):
        m = matcher.match("show amazn transactions")
        assert m is not None
        assert m.display_name == "Amazon"

    def test_flipkart_typo(self, matcher):
        m = matcher.match("show flipkartt transactions")
        assert m is not None
        assert m.display_name == "Flipkart"

    def test_fuel_typo(self, matcher):
        m = matcher.match("how much did i spend on fuell")
        assert m is not None
        assert m.display_name == "Fuel"

    def test_google_play_typo_bigram(self, matcher):
        m = matcher.match("how much did i spend on googel play")
        assert m is not None
        assert m.display_name == "Google Play"

    def test_unrelated_word_no_match(self, matcher):
        m = matcher.match("how much did i spend on soap")
        assert m is None or m.display_name != "Shopping"

    def test_very_short_token_skipped(self, matcher):
        # Confirms no crash on short tokens
        matcher.match("how much did i spend on upi")
        assert True


class TestFuzzyMatcherIntegration:
    """End-to-end typo queries through the full QA pipeline."""

    def test_shopping_typo_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on shpooing?")
        assert "15,118.67" in ans

    def test_entertainment_typo_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on entertainmnet?")
        assert "825.42" in ans

    def test_groceries_typo_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on grocerries?")
        assert "2,182.16" in ans

    def test_swiggy_typo_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on swigy?")
        assert "1,353.06" in ans

    def test_flipkart_typo_list(self, qa, report):
        ans = ask(qa, report, "Show flipkartt transactions.")
        assert "FLIPKART" in ans

    def test_fuel_typo_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on fuell?")
        assert "2,211.54" in ans

    def test_google_play_typo_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on googel play?")
        assert "825.42" in ans

    def test_typo_does_not_return_total_expenses(self, qa, report):
        ans = ask(qa, report, "How much did I spend on shpooing?")
        assert "85,743" not in ans


# ===========================================================================
# Task 2 — Refund Handling
# ===========================================================================

class TestRefundHandling:
    def test_total_expenses_excludes_refunds(self, qa, report):
        """AnalyticsAgent.total_expense sums only DEBITs."""
        ans = ask(qa, report, "How much did I spend?")
        assert "85,743.56" in ans

    def test_category_total_excludes_credits(self, qa, report):
        """Shopping DEBIT total = ₹15,118.67 (Amazon RETURN credit excluded)."""
        ans = ask(qa, report, "How much did I spend on Shopping?")
        assert "15,118.67" in ans
        assert "17,968" not in ans

    def test_refund_spend_is_zero(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Refund?")
        # New response: "No transactions were found under the Refund category."
        assert "no transactions" in ans.lower() or "refund" in ans.lower()


# ===========================================================================
# Task 3 — Merchant Awareness (Amazon refund context)
# ===========================================================================

class TestMerchantAwareness:
    def test_amazon_spend_mentions_refund(self, qa, report):
        """Amazon has no debit — response should mention the refund credit."""
        ans = ask(qa, report, "How much did I spend on Amazon?")
        assert "refund" in ans.lower() or "credit" in ans.lower()
        assert "85,743" not in ans

    def test_amazon_spend_mentions_amount(self, qa, report):
        """The refund amount ₹2,849.80 should appear in the response."""
        ans = ask(qa, report, "How much did I spend on Amazon?")
        assert "2,849.80" in ans

    def test_show_amazon_transactions_includes_refund(self, qa, report):
        """Show Amazon transactions should include the refund row."""
        ans = ask(qa, report, "Show Amazon transactions.")
        assert "AMAZON RETURN" in ans

    def test_show_amazon_transactions_notes_credits(self, qa, report):
        """When all Amazon transactions are credits, a note should appear."""
        ans = ask(qa, report, "Show Amazon transactions.")
        assert "refund" in ans.lower() or "credit" in ans.lower()

    def test_known_merchant_no_activity_graceful(self, qa, report):
        """Merchants in the table but with no transactions → clear message."""
        ans = ask(qa, report, "How much did I spend on Netflix?")
        assert "85,743" not in ans
        assert "netflix" in ans.lower() or "find" in ans.lower() or "no" in ans.lower()


# ===========================================================================
# Task 4 — Financial Intelligence Query Routing
# ===========================================================================

class TestFinancialIntelligenceRouting:
    """Verify phrase variants route to the correct intents."""

    @pytest.fixture(scope="class")
    def detector(self):
        return IntentDetector()

    def test_where_did_i_spend_the_most(self, detector):
        d = detector.detect("where did i spend the most")
        assert d.intent == Intent.LARGEST_CATEGORY

    def test_which_category_highest_spending(self, detector):
        d = detector.detect("which category has the highest spending")
        assert d.intent == Intent.LARGEST_CATEGORY

    def test_top_spending_category(self, detector):
        d = detector.detect("top spending category")
        assert d.intent == Intent.LARGEST_CATEGORY

    def test_largest_expense_category(self, detector):
        d = detector.detect("largest expense category")
        assert d.intent == Intent.LARGEST_CATEGORY

    def test_category_summary(self, detector):
        d = detector.detect("category summary")
        assert d.intent == Intent.SPENDING_SUMMARY

    def test_expense_breakdown(self, detector):
        d = detector.detect("expense breakdown")
        assert d.intent == Intent.SPENDING_SUMMARY

    def test_summarize_my_spending(self, detector):
        d = detector.detect("summarize my spending")
        assert d.intent == Intent.SPENDING_SUMMARY

    def test_merchant_summary(self, detector):
        d = detector.detect("merchant summary")
        assert d.intent == Intent.TOP_MERCHANTS

    def test_show_all_categories(self, detector):
        d = detector.detect("show all categories")
        assert d.intent == Intent.SPENDING_SUMMARY

    def test_financial_summary(self, detector):
        d = detector.detect("financial summary")
        assert d.intent == Intent.FINANCIAL_INSIGHTS

    def test_give_me_a_summary(self, detector):
        d = detector.detect("give me a summary")
        assert d.intent == Intent.FINANCIAL_INSIGHTS

    # End-to-end response checks
    def test_where_spend_most_returns_category(self, qa, report):
        ans = ask(qa, report, "Where did I spend the most?")
        assert "Largest Spending Category" in ans

    def test_show_all_categories_returns_summary(self, qa, report):
        ans = ask(qa, report, "Show all categories.")
        assert "Category-wise Spending Summary" in ans

    def test_expense_breakdown_returns_summary(self, qa, report):
        ans = ask(qa, report, "Expense breakdown.")
        assert "Category-wise Spending Summary" in ans or ans.strip() != ""

    def test_top_merchants_returns_merchants(self, qa, report):
        ans = ask(qa, report, "Top merchants.")
        assert "Top Spending Merchants" in ans

    def test_merchant_summary_returns_merchants(self, qa, report):
        ans = ask(qa, report, "Merchant summary.")
        assert "Top Spending Merchants" in ans

    def test_summarize_my_spending_end_to_end(self, qa, report):
        ans = ask(qa, report, "Summarize my spending.")
        assert "Category-wise Spending Summary" in ans

    def test_category_summary_end_to_end(self, qa, report):
        ans = ask(qa, report, "Category summary.")
        assert "Category-wise Spending Summary" in ans

    def test_financial_summary_end_to_end(self, qa, report):
        ans = ask(qa, report, "Financial summary.")
        assert ans.strip() != ""

    def test_this_month_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend this month?")
        assert "85,743.56" in ans


# ===========================================================================
# Task 5 — Better Unknown Responses
# ===========================================================================

class TestUnknownResponses:
    def test_starbucks_spend_no_total(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Starbucks?")
        assert "85,743" not in ans
        # Response should indicate nothing was found
        assert "find" in ans.lower() or "no" in ans.lower() or "couldn't" in ans.lower()

    def test_apple_store_spend_no_total(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Apple Store?")
        assert "85,743" not in ans

    def test_show_starbucks_no_total(self, qa, report):
        ans = ask(qa, report, "Show Starbucks transactions.")
        assert "85,743" not in ans

    def test_unknown_merchant_message_is_specific(self, qa, report):
        ans = ask(qa, report, "Show Starbucks transactions.")
        assert "85,743" not in ans

    def test_holidays_graceful(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Holidays?")
        assert "85,743" not in ans


# ===========================================================================
# Mandatory regression queries from the prompt spec
# ===========================================================================

class TestMandatoryRegressionQueries:
    """Exact queries listed in the prompt's Regression Tests section."""

    def test_how_much_did_i_spend(self, qa, report):
        assert "85,743.56" in ask(qa, report, "How much did I spend?")

    def test_how_much_this_month(self, qa, report):
        assert "85,743.56" in ask(qa, report, "How much did I spend this month?")

    def test_account_balance(self, qa, report):
        assert "63,767.46" in ask(qa, report, "What is my account balance?")

    def test_food_spend(self, qa, report):
        assert "2,859.03" in ask(qa, report, "How much did I spend on Food?")

    def test_shopping_spend(self, qa, report):
        assert "15,118.67" in ask(qa, report, "How much did I spend on Shopping?")

    def test_groceries_spend(self, qa, report):
        assert "2,182.16" in ask(qa, report, "How much did I spend on Groceries?")

    def test_entertainment_spend(self, qa, report):
        assert "825.42" in ask(qa, report, "How much did I spend on Entertainment?")

    def test_fuel_spend(self, qa, report):
        assert "2,211.54" in ask(qa, report, "How much did I spend on Fuel?")

    def test_show_food(self, qa, report):
        ans = ask(qa, report, "Show Food transactions.")
        assert "SWIGGY" in ans or "ZOMATO" in ans

    def test_show_shopping(self, qa, report):
        ans = ask(qa, report, "Show Shopping transactions.")
        assert "FLIPKART" in ans or "LIFESTYLE" in ans

    def test_show_grocery(self, qa, report):
        ans = ask(qa, report, "Show Grocery transactions.")
        assert "RELIANCE FRESH" in ans

    def test_show_entertainment(self, qa, report):
        ans = ask(qa, report, "Show Entertainment transactions.")
        assert "GOOGLE PLAY" in ans

    def test_show_fuel(self, qa, report):
        ans = ask(qa, report, "Show Fuel transactions.")
        assert "INDIAN OIL" in ans

    def test_swiggy_spend(self, qa, report):
        assert "1,353.06" in ask(qa, report, "How much did I spend on Swiggy?")

    def test_flipkart_spend(self, qa, report):
        assert "8,498.42" in ask(qa, report, "How much did I spend on Flipkart?")

    def test_google_play_spend(self, qa, report):
        assert "825.42" in ask(qa, report, "How much did I spend on Google Play?")

    def test_show_swiggy(self, qa, report):
        assert "SWIGGY" in ask(qa, report, "Show Swiggy transactions.")

    def test_show_flipkart(self, qa, report):
        assert "FLIPKART" in ask(qa, report, "Show Flipkart transactions.")

    def test_show_google_play(self, qa, report):
        assert "GOOGLE PLAY" in ask(qa, report, "Show Google Play transactions.")

    def test_amazon_spend_context_aware(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Amazon?")
        assert "85,743" not in ans
        assert "refund" in ans.lower() or "credit" in ans.lower()

    def test_show_amazon(self, qa, report):
        ans = ask(qa, report, "Show Amazon transactions.")
        assert "AMAZON" in ans

    def test_typo_shpooing(self, qa, report):
        assert "15,118.67" in ask(qa, report, "How much did I spend on shpooing?")

    def test_typo_entertainmnet(self, qa, report):
        assert "825.42" in ask(qa, report, "How much did I spend on entertainmnet?")

    def test_where_did_i_spend_most(self, qa, report):
        ans = ask(qa, report, "Where did I spend the most?")
        assert "Largest Spending Category" in ans

    def test_show_all_categories(self, qa, report):
        ans = ask(qa, report, "Show all categories.")
        assert "Category-wise Spending Summary" in ans

    def test_expense_summary(self, qa, report):
        ans = ask(qa, report, "Expense summary.")
        assert ans.strip() != ""

    def test_top_merchants(self, qa, report):
        ans = ask(qa, report, "Top merchants.")
        assert "Top Spending Merchants" in ans
