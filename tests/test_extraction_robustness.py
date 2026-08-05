"""
Extraction Robustness & Classification Tests
============================================
Covers Problems 1–7 from the extraction robustness prompt.

P1  — KeyValueBlockExtractor (Layout B: Txn Date / Particulars / Amount)
P2  — Amount normalization (negative, DR/CR suffix, ₹ prefix)
P3  — Boilerplate line suppression
P4  — Multi-line description joining
P5  — Category rule refinement (Spotify→Entertainment, Airtel→Bills, etc.)
P6  — Merchant aggregation (no duplicates in top merchants)
P7  — Refund total intent ("how much refund did i receive?")
"""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from src.agents.categorization.categorization_agent import CategorizationAgent
from src.agents.extraction.extractors.key_value_block_extractor import (
    KeyValueBlockExtractor,
)
from src.agents.extraction.extractors.table_row_extractor import (
    TableRowExtractor,
)
from src.agents.extraction.field_extraction_agent import FieldExtractionAgent
from src.agents.extraction.shared.amount_normalizer import parse_amount
from src.agents.qa.intent_detector import Intent, IntentDetector
from src.agents.qa.qa_agent import QAAgent
from src.agents.transactions.transaction_segmenter import TransactionSegmenter
from src.schemas.document_profile import DocumentProfile
from src.schemas.financial_report import FinancialReport
from src.schemas.transaction import Transaction

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
# P2 — Amount normalization (parse_amount utility)
# ===========================================================================

class TestAmountNormalizer:
    """parse_amount() must always return a non-negative Decimal."""

    @pytest.mark.parametrize("raw,expected_amount,expected_type", [
        ("-1354.33",          Decimal("1354.33"), "DEBIT"),
        ("1354.33 DR",        Decimal("1354.33"), "DEBIT"),
        ("1354.33 (Dr)",      Decimal("1354.33"), "DEBIT"),
        ("₹1354.33 (Dr)",     Decimal("1354.33"), "DEBIT"),
        ("1354.33 Debit",     Decimal("1354.33"), "DEBIT"),
        ("78096.46 (Cr)",     Decimal("78096.46"), "CREDIT"),
        ("599.60 CR",         Decimal("599.60"),  "CREDIT"),
        ("599.60 Credit",     Decimal("599.60"),  "CREDIT"),
        ("24,950.89",         Decimal("24950.89"), None),   # no explicit type
        ("1,00,000.00",       Decimal("100000.00"), None),
    ])
    def test_parse_amount(self, raw, expected_amount, expected_type):
        amount, txn_type = parse_amount(raw)
        assert amount is not None, f"parse_amount({raw!r}) returned None"
        assert amount == expected_amount, f"Expected {expected_amount}, got {amount}"
        assert txn_type == expected_type, f"Expected type {expected_type}, got {txn_type}"

    def test_negative_stored_as_positive(self):
        amount, txn_type = parse_amount("-1354.33")
        assert amount >= 0
        assert txn_type == "DEBIT"

    def test_empty_string_returns_none(self):
        amount, txn_type = parse_amount("")
        assert amount is None
        assert txn_type is None


# ===========================================================================
# P2 — TableRowExtractor handles DR/CR amounts
# ===========================================================================

class TestTableRowExtractorNormalization:
    """TableRowExtractor must produce amount >= 0 and correct type."""

    def test_plain_debit_block(self):
        block = "01/05/2024\nUPI/LANDLORD/RENTPAY\n24,950.89\n57,499.11"
        txn = TableRowExtractor().extract(block)
        assert txn.amount >= 0
        assert txn.transaction_type == "DEBIT"
        assert txn.amount == Decimal("24950.89")

    def test_negative_amount_normalised(self):
        """Amount stored as -1354.33 must become 1354.33 DEBIT."""
        block = "14/05/2024\nUPI/SWIGGY/ORDERPAY\n-1353.06\n78590.80"
        txn = TableRowExtractor().extract(block)
        assert txn.amount == Decimal("1353.06")
        assert txn.amount >= 0
        assert txn.transaction_type == "DEBIT"

    def test_credit_keyword_sets_credit_type(self):
        block = "12/05/2024\nSALARY CREDIT - INFOTECH\n63509.05\n86410.04"
        txn = TableRowExtractor().extract(block)
        assert txn.transaction_type == "CREDIT"
        assert txn.amount >= 0


# ===========================================================================
# P1 — KeyValueBlockExtractor (Layout B)
# ===========================================================================

class TestKeyValueBlockExtractor:

    @pytest.fixture
    def extractor(self):
        return KeyValueBlockExtractor()

    def test_can_handle_detects_kv_block(self, extractor):
        block = (
            "Txn Date   : 16/05/2024\n"
            "Particulars: SPOTIFY PREMIUM\n"
            "Amount     : 199.00 DR\n"
            "Balance    : 45678.12 CR\n"
        )
        assert extractor.can_handle(block) is True

    def test_can_handle_rejects_table_row(self, extractor):
        block = "01/05/2024\nUPI/LANDLORD/RENTPAY\n24950.89\n57499.11"
        # Table row has no Particulars label
        assert extractor.can_handle(block) is False

    def test_basic_debit_extraction(self, extractor):
        block = (
            "Txn Date   : 16/05/2024\n"
            "Particulars: SPOTIFY PREMIUM\n"
            "Amount     : 199.00 DR\n"
            "Balance    : 45678.12 CR\n"
        )
        txn = extractor.extract(block)
        assert txn.transaction_date is not None
        assert txn.transaction_date.day == 16
        assert txn.transaction_date.month == 5
        assert "SPOTIFY" in (txn.description or "").upper()
        assert txn.amount == Decimal("199.00")
        assert txn.amount >= 0
        assert txn.transaction_type == "DEBIT"

    def test_credit_transaction(self, extractor):
        block = (
            "Txn Date   : 12/05/2024\n"
            "Particulars: SALARY CREDIT INFOTECH\n"
            "Amount     : 63509.05 CR\n"
            "Balance    : 86410.04\n"
        )
        txn = extractor.extract(block)
        assert txn.transaction_type == "CREDIT"
        assert txn.amount == Decimal("63509.05")
        assert txn.amount >= 0

    def test_multiline_particulars(self, extractor):
        block = (
            "Txn Date   : 16/05/2024\n"
            "Particulars: INDIAN OIL\n"
            "             FUEL STATION\n"
            "Amount     : 2211.54 DR\n"
            "Balance    : 73726.64\n"
        )
        txn = extractor.extract(block)
        desc_upper = (txn.description or "").upper()
        assert "INDIAN OIL" in desc_upper
        assert txn.amount == Decimal("2211.54")

    def test_balance_is_extracted(self, extractor):
        block = (
            "Txn Date   : 17/05/2024\n"
            "Particulars: ZOMATO ORDER\n"
            "Amount     : 1505.97 DR\n"
            "Balance    : 72220.67 CR\n"
        )
        txn = extractor.extract(block)
        assert txn.balance == Decimal("72220.67")

    def test_boilerplate_lines_ignored(self, extractor):
        block = (
            "Txn Date   : 14/05/2024\n"
            "Particulars: MEDPLUS HEALTH SERVICES\n"
            "Statement of Account\n"
            "Page 2 of 5\n"
            "Amount     : 3568.74 DR\n"
            "Balance    : 82841.30\n"
        )
        txn = extractor.extract(block)
        desc = (txn.description or "").upper()
        assert "MEDPLUS" in desc
        assert "STATEMENT" not in desc
        assert "PAGE" not in desc


# ===========================================================================
# P1 — FieldExtractionAgent routes to KeyValueBlockExtractor
# ===========================================================================

class TestFieldExtractionAgentRouting:

    @pytest.fixture
    def agent(self):
        return FieldExtractionAgent()

    def test_routes_table_row(self, agent):
        block = "01/05/2024\nUPI/LANDLORD/RENTPAY\n24950.89\n57499.11"
        txn = agent.extract(block)
        assert txn.transaction_date is not None
        assert txn.amount == Decimal("24950.89")
        assert txn.amount >= 0

    def test_routes_kv_block(self, agent):
        block = (
            "Txn Date: 16/05/2024\n"
            "Particulars: SPOTIFY PREMIUM\n"
            "Amount: 199.00 DR\n"
            "Balance: 45678.12\n"
        )
        txn = agent.extract(block)
        assert txn.amount == Decimal("199.00")
        assert txn.amount >= 0
        assert "SPOTIFY" in (txn.description or "")

    def test_normalizer_uppercases_description(self, agent):
        block = "01/05/2024\nswiggy order\n1353.06\n78590.80"
        txn = agent.extract(block)
        assert txn.description == txn.description.upper()


# ===========================================================================
# P3 — Boilerplate line suppression in TransactionSegmenter
# ===========================================================================

class TestBoilerplateFiltering:

    @pytest.fixture
    def segmenter(self):
        return TransactionSegmenter()

    def test_page_header_not_in_transactions(self, segmenter):
        raw = (
            "Statement of Account\n"
            "Page 1 of 3\n"
            "01/05/2024\n"
            "UPI/LANDLORD/RENTPAY\n"
            "24950.89\n"
            "57499.11\n"
            "Page 2 of 3\n"
            "Customer Name: Test User\n"
            "02/05/2024\n"
            "FLIPKART ONLINE PAYMENT\n"
            "8498.42\n"
            "49000.69\n"
        )
        profile = DocumentProfile(layout_type="table")
        blocks = segmenter.segment(raw, profile)
        assert len(blocks) == 2
        for block in blocks:
            assert "statement" not in block.lower()
            assert "page" not in block.lower()
            assert "customer" not in block.lower()

    def test_closing_balance_line_not_a_transaction(self, segmenter):
        raw = (
            "01/05/2024\n"
            "UPI/LANDLORD/RENTPAY\n"
            "24950.89\n"
            "57499.11\n"
            "Closing Balance: 57499.11\n"
        )
        profile = DocumentProfile(layout_type="table")
        blocks = segmenter.segment(raw, profile)
        assert len(blocks) == 1


# ===========================================================================
# P5 — Category rule refinement
# ===========================================================================

class TestCategoryRules:

    @pytest.fixture
    def cat(self):
        return CategorizationAgent()

    def _make_txn(self, description):
        return Transaction(
            description=description,
            amount=Decimal("100"),
            transaction_type="DEBIT",
        )

    def test_spotify_premium_is_entertainment(self, cat):
        txn = cat.categorize(self._make_txn("SPOTIFY PREMIUM"))
        assert txn.category == "Entertainment"

    def test_netflix_is_entertainment(self, cat):
        txn = cat.categorize(self._make_txn("NETFLIX SUBSCRIPTION"))
        assert txn.category == "Entertainment"

    def test_amazon_prime_is_entertainment_not_shopping(self, cat):
        txn = cat.categorize(self._make_txn("AMAZON PRIME VIDEO"))
        assert txn.category == "Entertainment"

    def test_airtel_postpaid_is_bills(self, cat):
        txn = cat.categorize(self._make_txn("AIRTEL POSTPAID BILL"))
        assert txn.category == "Bills"

    def test_airtel_recharge_is_bills(self, cat):
        txn = cat.categorize(self._make_txn("AIRTEL PREPAID RECHARGE"))
        assert txn.category == "Bills"

    def test_lic_is_insurance(self, cat):
        txn = cat.categorize(self._make_txn("LIC POLICY PREMIUM"))
        assert txn.category == "Insurance"

    def test_hdfc_ergo_is_insurance(self, cat):
        txn = cat.categorize(self._make_txn("HDFC ERGO MOTOR INSURANCE"))
        assert txn.category == "Insurance"

    def test_plain_amazon_is_shopping(self, cat):
        txn = cat.categorize(self._make_txn("AMAZON ONLINE PAYMENT"))
        assert txn.category == "Shopping"

    def test_google_play_is_entertainment(self, cat):
        txn = cat.categorize(self._make_txn("GOOGLE PLAY"))
        assert txn.category == "Entertainment"

    def test_makemytrip_is_travel(self, cat):
        txn = cat.categorize(self._make_txn("MAKEMYTRIP FLIGHT BOOKING"))
        assert txn.category == "Travel"

    def test_standalone_premium_word_not_insurance(self, cat):
        """
        A description containing only 'premium' (e.g. from Spotify Premium)
        must NOT be classified as Insurance after the rule fix.
        """
        txn = cat.categorize(self._make_txn("PREMIUM SUBSCRIPTION SERVICE"))
        # Should NOT be Insurance (premium alone is too broad)
        assert txn.category != "Insurance"


# ===========================================================================
# P6 — Merchant aggregation (no duplicates in top merchants)
# ===========================================================================

class TestMerchantAggregation:

    def test_top_merchants_no_duplicates(self, qa, report):
        """
        The top merchants list must not show the same merchant twice.
        Previously two rent payments appeared as duplicate entries.
        """
        ans = ask(qa, report, "Top merchants.")
        # Each merchant name should appear at most once in the response
        lines = [l.strip() for l in ans.splitlines() if l.strip()]
        merchant_lines = [l for l in lines if l[0].isdigit()]
        # Extract just the name portion (before the ₹)
        names = []
        for line in merchant_lines:
            # Format: "1. Merchant Name"
            parts = line.split(".", 1)
            if len(parts) == 2:
                names.append(parts[1].strip())
        assert len(names) == len(set(names)), (
            f"Duplicate merchants found: {names}"
        )

    def test_top_merchants_header_present(self, qa, report):
        ans = ask(qa, report, "Top merchants.")
        assert "Top Spending Merchants" in ans


# ===========================================================================
# P7 — Refund total intent
# ===========================================================================

class TestRefundIntent:

    @pytest.fixture
    def detector(self):
        return IntentDetector()

    def test_refund_phrase_detected(self, detector):
        d = detector.detect("how much refund did i receive")
        assert d.intent == Intent.REFUND_TOTAL

    def test_refund_received_phrase(self, detector):
        d = detector.detect("total refund received")
        assert d.intent == Intent.REFUND_TOTAL

    def test_refund_total_phrase(self, detector):
        d = detector.detect("refund total")
        assert d.intent == Intent.REFUND_TOTAL

    def test_show_refund_transactions_still_category_list(self, detector):
        """'Show refund transactions' should remain CATEGORY_LIST."""
        d = detector.detect("show refund transactions")
        assert d.intent == Intent.CATEGORY_LIST

    def test_refund_total_end_to_end(self, qa, report):
        """
        'How much refund did I receive?' must return a meaningful response.
        In the SBI statement, REFUND - AMAZON RETURN is categorised as
        Shopping (not Refund), so the refund category total is 0 — the
        response must still be graceful and must NOT return total expenses.
        """
        ans = ask(qa, report, "How much refund did I receive?")
        assert "85,743" not in ans
        assert "refund" in ans.lower()

    def test_refund_query_does_not_return_total_spend(self, qa, report):
        ans = ask(qa, report, "How much refund did I receive?")
        assert "85,743" not in ans


# ===========================================================================
# Preservation — existing SBI tests still work
# ===========================================================================

class TestSBIPreservation:
    """Smoke test that key SBI queries are unaffected."""

    def test_total_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend?")
        assert "85,743.56" in ans

    def test_balance(self, qa, report):
        ans = ask(qa, report, "What is my account balance?")
        assert "63,767.46" in ans

    def test_food_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Food?")
        assert "2,859.03" in ans

    def test_fuel_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Fuel?")
        assert "2,211.54" in ans

    def test_show_swiggy(self, qa, report):
        ans = ask(qa, report, "Show Swiggy transactions.")
        assert "SWIGGY" in ans

    def test_shopping_spend(self, qa, report):
        ans = ask(qa, report, "How much did I spend on Shopping?")
        assert "15,118.67" in ans
