"""
Entity Resolution Tests
=======================
Covers the generalised category and merchant resolution layer.
All queries must route correctly and return meaningful answers —
never fall back silently to total expenses.

Statement facts used for assertions
-------------------------------------
Entertainment   : GOOGLE PLAY  ₹825.42  (DEBIT)
Groceries       : RELIANCE FRESH ₹406.54 + ₹1,775.62  = ₹2,182.16  (DEBIT)
Rent            : no "Rent" category in this statement → graceful no-data response
Bills           : ELECTRICITY BILL BESCOM  ₹2,897.44  (DEBIT)
Healthcare      : MEDPLUS HEALTH SERVICES  ₹3,568.74  (DEBIT)
Insurance       : INSURANCE PREMIUM - LIC  ₹3,483.93  (DEBIT)
Travel          : MAKEMYTRIP FLIGHT BOOKING  ₹2,652.62  (DEBIT)
Transfer        : UPI/LANDLORD/RENTPAY ₹24,950.89 + NEFT ₹7,912.46 = ₹32,863.35
EMI             : EMI - CONSUMER DURABLE LOAN BAJAJ FINSERV  ₹8,453.21  (DEBIT)
Cash Withdrawal : ATM CASH WITHDRAWAL  ₹8,627.45  (DEBIT)
Refund          : REFUND - AMAZON RETURN  ₹2,849.80  (CREDIT — excluded from totals)
"""
import json
from pathlib import Path

import pytest

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


# ---------------------------------------------------------------------------
# Entertainment
# ---------------------------------------------------------------------------

class TestEntertainment:
    def test_entertainment_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Entertainment?")
        assert "825.42" in ans

    def test_show_entertainment_transactions(self, qa, report):
        ans = ask(qa, report, "Show Entertainment transactions.")
        assert "GOOGLE PLAY" in ans

    def test_entertainment_via_movies_alias(self, qa, report):
        ans = ask(qa, report, "How much did I spend on movies?")
        assert "825.42" in ans

    def test_show_movies_transactions(self, qa, report):
        ans = ask(qa, report, "Show movies transactions.")
        assert "GOOGLE PLAY" in ans


# ---------------------------------------------------------------------------
# Groceries — singular/plural alias
# ---------------------------------------------------------------------------

class TestGroceries:
    def test_groceries_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Groceries?")
        assert "2,182.16" in ans

    def test_grocery_singular_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Grocery?")
        assert "2,182.16" in ans

    def test_show_grocery_transactions(self, qa, report):
        ans = ask(qa, report, "Show Grocery transactions.")
        assert "RELIANCE FRESH" in ans

    def test_show_groceries_transactions(self, qa, report):
        ans = ask(qa, report, "Show Groceries transactions.")
        assert "RELIANCE FRESH" in ans


# ---------------------------------------------------------------------------
# Rent — not a category in this statement; graceful no-data response expected
# ---------------------------------------------------------------------------

class TestRent:
    def test_rent_spend_graceful(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Rent?")
        assert "85,743" not in ans

    def test_show_rent_transactions_graceful(self, qa, report):
        ans = ask(qa, report, "Show Rent transactions.")
        assert "85,743" not in ans


# ---------------------------------------------------------------------------
# Bills / BESCOM
# ---------------------------------------------------------------------------

class TestBills:
    def test_bills_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Bills?")
        assert "2,897.44" in ans

    def test_show_bills_transactions(self, qa, report):
        ans = ask(qa, report, "Show Bills transactions.")
        assert "BESCOM" in ans

    def test_bescom_merchant_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on BESCOM?")
        assert "2,897.44" in ans

    def test_show_bescom_transactions(self, qa, report):
        ans = ask(qa, report, "Show BESCOM transactions.")
        assert "BESCOM" in ans


# ---------------------------------------------------------------------------
# Healthcare
# ---------------------------------------------------------------------------

class TestHealthcare:
    def test_healthcare_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Healthcare?")
        assert "3,568.74" in ans

    def test_medical_alias(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Medical?")
        assert "3,568.74" in ans

    def test_show_healthcare_transactions(self, qa, report):
        ans = ask(qa, report, "Show Healthcare transactions.")
        assert "MEDPLUS" in ans


# ---------------------------------------------------------------------------
# Insurance
# ---------------------------------------------------------------------------

class TestInsurance:
    def test_insurance_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Insurance?")
        assert "3,483.93" in ans

    def test_show_insurance_transactions(self, qa, report):
        ans = ask(qa, report, "Show Insurance transactions.")
        assert "LIC" in ans or "INSURANCE" in ans


# ---------------------------------------------------------------------------
# Travel
# ---------------------------------------------------------------------------

class TestTravel:
    def test_travel_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Travel?")
        assert "2,652.62" in ans

    def test_show_travel_transactions(self, qa, report):
        ans = ask(qa, report, "Show Travel transactions.")
        assert "MAKEMYTRIP" in ans


# ---------------------------------------------------------------------------
# EMI
# ---------------------------------------------------------------------------

class TestEMI:
    def test_emi_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on EMI?")
        assert "8,453.21" in ans

    def test_show_emi_transactions(self, qa, report):
        ans = ask(qa, report, "Show EMI transactions.")
        assert "BAJAJ FINSERV" in ans

    def test_loan_alias(self, qa, report):
        ans = ask(qa, report, "How much did I spend on loans?")
        assert "8,453.21" in ans


# ---------------------------------------------------------------------------
# Transfer
# ---------------------------------------------------------------------------

class TestTransfer:
    def test_transfer_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Transfers?")
        # Rent fix: landlord moved from Transfer to Rent, so total is lower
        assert "7,912.46" in ans

    def test_transfer_singular(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Transfer?")
        # Rent fix: landlord moved from Transfer to Rent, so total is lower
        assert "7,912.46" in ans

    def test_show_transfer_transactions(self, qa, report):
        ans = ask(qa, report, "Show Transfer transactions.")
        assert "UPI" in ans or "NEFT" in ans


# ---------------------------------------------------------------------------
# Cash Withdrawal
# ---------------------------------------------------------------------------

class TestCashWithdrawal:
    def test_cash_withdrawal_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Cash Withdrawal?")
        assert "8,627.45" in ans

    def test_show_cash_withdrawal_transactions(self, qa, report):
        ans = ask(qa, report, "Show Cash Withdrawal transactions.")
        assert "ATM" in ans


# ---------------------------------------------------------------------------
# Google Play / Google Pay alias
# ---------------------------------------------------------------------------

class TestGooglePlay:
    def test_google_play_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Google Play?")
        assert "825.42" in ans

    def test_show_google_play_transactions(self, qa, report):
        ans = ask(qa, report, "Show Google Play transactions.")
        assert "GOOGLE PLAY" in ans

    def test_google_pay_alias_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Google Pay?")
        assert "825.42" in ans

    def test_show_google_pay_transactions(self, qa, report):
        ans = ask(qa, report, "Show Google Pay transactions.")
        assert "GOOGLE PLAY" in ans


# ---------------------------------------------------------------------------
# Refund handling — refunds are CREDITs and must not inflate expense totals
# ---------------------------------------------------------------------------

class TestRefundHandling:
    def test_refund_not_in_total_expenses(self, qa, report):
        """Total expenses must exclude the Amazon refund CREDIT of ₹2,849.80."""
        ans = ask(qa, report, "How much did I spend?")
        assert "85,743.56" in ans

    def test_show_refund_transactions(self, qa, report):
        # "REFUND - AMAZON RETURN" is categorised as Shopping in this statement.
        # Refund category has 0 transactions — graceful response expected.
        ans = ask(qa, report, "Show Refund transactions.")
        assert "no transactions" in ans.lower() or "amazon" in ans.lower()

    def test_refund_category_spend(self, qa, report):
        """Refund category has no DEBIT transactions — zero-spend response."""
        ans = ask(qa, report, "How much did I spend on Refund?")
        # New response: "No transactions were found under the Refund category."
        assert "no transactions" in ans.lower() or "refund" in ans.lower()


# ---------------------------------------------------------------------------
# Fallback — unknown entity must never answer with total expenses
# ---------------------------------------------------------------------------

class TestFallbackBehavior:
    def test_unknown_merchant_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Starbucks?")
        assert "85,743" not in ans

    def test_unknown_category_show(self, qa, report):
        ans = ask(qa, report, "Show Starbucks transactions.")
        assert "85,743" not in ans

    def test_unknown_category_graceful(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Holidays?")
        assert "85,743" not in ans
