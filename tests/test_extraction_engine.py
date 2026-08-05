"""
Extraction Engine Tests
=======================
Verifies that the general-purpose field extractor correctly transforms
segmented transaction blocks into validated Transaction objects.

Tests cover:
  - Table-row layout (SBI / ICICI style)
  - Key-value inline layout (Txn Date: value)
  - Key-value split-line layout (Union Bank: label / : value)
  - Same-line layout (date + desc + amount on one line)
  - Multi-line / wrapped descriptions
  - Multiple date formats (DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, DD MMM YYYY)
  - Multiple amount formats (plain, DR/CR, ₹, negative, parenthesised)
  - 3-column table blocks (debit / credit / balance)
  - Validation: required vs optional fields
  - Full pipeline: SBI, ICICI, Union Bank PDFs

Success criteria verified:
  ✓ Every block → exactly one Transaction object
  ✓ Dates extracted correctly
  ✓ Descriptions preserved completely
  ✓ Amounts extracted correctly
  ✓ DEBIT/CREDIT direction correct
  ✓ Running balances extracted when available
  ✓ Wrapped descriptions remain intact
  ✓ Validation accepts correctly extracted transactions
  ✓ Validation failures include meaningful reasons
  ✓ Works across all three PDF layouts
"""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.agents.document.document_understanding_engine import DocumentUnderstandingEngine
from src.agents.extraction.extractors.key_value_block_extractor import KeyValueBlockExtractor
from src.agents.extraction.extractors.same_line_extractor import SameLineExtractor
from src.agents.extraction.extractors.table_row_extractor import TableRowExtractor
from src.agents.extraction.field_extraction_agent import FieldExtractionAgent
from src.agents.transactions.transaction_segmenter import TransactionSegmenter
from src.agents.validation.transaction_validator import TransactionValidator
from src.tools.pdf_reader import PDFReader


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def fea():
    return FieldExtractionAgent()


@pytest.fixture(scope="module")
def val():
    return TransactionValidator()


@pytest.fixture(scope="module")
def table_ext():
    return TableRowExtractor()


@pytest.fixture(scope="module")
def kv_ext():
    return KeyValueBlockExtractor()


@pytest.fixture(scope="module")
def sl_ext():
    return SameLineExtractor()


def extract_and_validate(fea, val, block):
    """Helper: extract a block and validate it, returning (txn, ok, reason)."""
    txn = fea.extract(block)
    ok, reason = val.validate(txn)
    return txn, ok, reason


# ===========================================================================
# Table-Row Extractor — unit tests
# ===========================================================================

class TestTableRowExtractor:

    def test_4line_debit(self, table_ext):
        block = "01/05/2024\nUPI/LANDLORD/RENTPAY\n24,950.89\n57,499.11"
        assert table_ext.can_handle(block)
        t = table_ext.extract(block)
        assert t.transaction_date == date(2024, 5, 1)
        assert t.description == "UPI/LANDLORD/RENTPAY"
        assert t.amount == Decimal("24950.89")
        assert t.balance == Decimal("57499.11")
        assert t.transaction_type == "DEBIT"

    def test_4line_credit_keyword(self, table_ext):
        block = "12/05/2024\nSALARY CREDIT - INFOTECH\n63509.05\n86410.04"
        t = table_ext.extract(block)
        assert t.transaction_type == "CREDIT"
        assert t.amount == Decimal("63509.05")

    def test_5line_3col_debit(self, table_ext):
        block = "01/05/2024\nUPI PAYMENT\n24950.89\n0\n57499.11"
        assert table_ext.can_handle(block)
        t = table_ext.extract(block)
        assert t.amount == Decimal("24950.89")
        assert t.transaction_type == "DEBIT"
        assert t.balance == Decimal("57499.11")

    def test_5line_3col_credit(self, table_ext):
        block = "11/05/2024\nSALARY CREDIT\n0\n63509.05\n86410.04"
        t = table_ext.extract(block)
        assert t.amount == Decimal("63509.05")
        assert t.transaction_type == "CREDIT"

    def test_dr_cr_suffix(self, table_ext):
        block = "14/05/2024\nSWIGGY ORDER\n1353.06 DR\n78590.80 CR"
        assert table_ext.can_handle(block)
        t = table_ext.extract(block)
        assert t.amount == Decimal("1353.06")
        assert t.transaction_type == "DEBIT"

    def test_negative_amount(self, table_ext):
        block = "14/05/2024\nUPI PAYMENT\n-1353.06\n78590.80"
        t = table_ext.extract(block)
        assert t.amount == Decimal("1353.06")
        assert t.transaction_type == "DEBIT"

    def test_inr_symbol(self, table_ext):
        block = "01/05/2024\nPAYMENT\n₹1354.33\n₹9000.00"
        assert table_ext.can_handle(block)
        t = table_ext.extract(block)
        assert t.amount == Decimal("1354.33")

    def test_named_month_date(self, table_ext):
        block = "14 May 2024\nMEDPLUS\n3568.74\n82841.30"
        assert table_ext.can_handle(block)
        t = table_ext.extract(block)
        assert t.transaction_date == date(2024, 5, 14)

    def test_iso_date(self, table_ext):
        block = "2024-05-01\nNEFT TRANSFER\n5000.00\n45000.00"
        assert table_ext.can_handle(block)
        t = table_ext.extract(block)
        assert t.transaction_date == date(2024, 5, 1)

    def test_2digit_year(self, table_ext):
        block = "01/05/24\nPAYMENT\n1000.00\n9000.00"
        assert table_ext.can_handle(block)
        t = table_ext.extract(block)
        assert t.transaction_date == date(2024, 5, 1)

    def test_amount_always_positive(self, table_ext):
        block = "01/05/2024\nPAYMENT\n-1353.06\n78590.80"
        t = table_ext.extract(block)
        assert t.amount >= 0

    def test_account_number_not_stored_as_balance(self, table_ext):
        block = "01/05/2024\nPAYMENT\n1000.00\n38491027561000"
        t = table_ext.extract(block)
        assert t.balance is None  # bare integer rejected

    def test_multi_line_wrapped_description(self, fea, val):
        block = "01/05/2024\nNEFT/IMPS/REF-123456789\nTOWARDS RENT PAYMENT\n24950.89\n57499.11"
        t, ok, reason = extract_and_validate(fea, val, block)
        assert ok, reason
        assert "NEFT" in t.description
        assert "RENT" in t.description


# ===========================================================================
# Key-Value Block Extractor — unit tests
# ===========================================================================

class TestKeyValueBlockExtractor:

    def test_inline_format(self, kv_ext):
        block = (
            "Txn Date: 16/05/2024\n"
            "Particulars: SPOTIFY PREMIUM\n"
            "Amount: 199.00 DR\n"
            "Balance: 45678.12"
        )
        assert kv_ext.can_handle(block)
        t = kv_ext.extract(block)
        assert t.transaction_date == date(2024, 5, 16)
        assert "SPOTIFY" in t.description
        assert t.amount == Decimal("199.00")
        assert t.balance == Decimal("45678.12")
        assert t.transaction_type == "DEBIT"

    def test_split_line_format(self, kv_ext):
        """Union Bank style: label alone, value on next line with ':' prefix."""
        block = (
            "Txn Date\n"
            ": 2024-08-02\n"
            ": INDIAN OIL FUEL STATION\n"
            "Amount\n"
            ": -1,354.33 (Dr)\n"
            ": \u20b937,585.82"
        )
        t = kv_ext.extract(block)
        assert t.transaction_date == date(2024, 8, 2)
        assert "INDIAN OIL" in t.description
        assert t.amount == Decimal("1354.33")
        assert t.balance == Decimal("37585.82")
        assert t.transaction_type == "DEBIT"

    def test_credit_transaction(self, kv_ext):
        block = (
            "Txn Date: 12/05/2024\n"
            "Particulars: SALARY CREDIT INFOTECH\n"
            "Amount: 63509.05 CR\n"
            "Balance: 86410.04"
        )
        t = kv_ext.extract(block)
        assert t.transaction_type == "CREDIT"
        assert t.amount == Decimal("63509.05")

    def test_parenthesised_dr(self, kv_ext):
        block = (
            "Txn Date: 02/08/2024\n"
            "Particulars: INSURANCE PREMIUM\n"
            "Amount: \u20b93,234.64 (Dr)\n"
            "Balance: \u20b933,022.35"
        )
        t = kv_ext.extract(block)
        assert t.amount == Decimal("3234.64")
        assert t.transaction_type == "DEBIT"

    def test_wrapped_description(self, kv_ext):
        block = (
            "Txn Date\n"
            ": 2024-08-06\n"
            ": SPOTIFY\n"
            "  PREMIUM\n"
            "Amount\n"
            ": 261.76 DR\n"
            ": \u20b995,924.59"
        )
        t = kv_ext.extract(block)
        assert "SPOTIFY" in t.description
        assert t.amount == Decimal("261.76")

    def test_multiple_date_formats_in_kv(self, kv_ext):
        for date_str, expected in [
            ("02/08/2024",    date(2024, 8, 2)),
            ("02-08-2024",    date(2024, 8, 2)),
            ("2024-08-02",    date(2024, 8, 2)),
        ]:
            block = f"Txn Date: {date_str}\nParticulars: TEST\nAmount: 100.00 DR\nBalance: 900.00"
            t = kv_ext.extract(block)
            assert t.transaction_date == expected, f"Failed for {date_str}"

    def test_narration_label_variant(self, kv_ext):
        block = (
            "Date: 01/05/2024\n"
            "Narration: AMAZON PURCHASE\n"
            "Amount: 500.00\n"
            "Balance: 9500.00"
        )
        t = kv_ext.extract(block)
        assert t.description == "AMAZON PURCHASE"

    def test_description_label_variant(self, kv_ext):
        block = (
            "Date: 01/05/2024\n"
            "Description: GROCERY PURCHASE\n"
            "Amount: 300.00\n"
            "Balance: 9700.00"
        )
        t = kv_ext.extract(block)
        assert t.description == "GROCERY PURCHASE"


# ===========================================================================
# Same-Line Extractor — unit tests
# ===========================================================================

class TestSameLineExtractor:

    def test_basic_same_line(self, sl_ext):
        block = "01/05/2024  UPI PAYMENT  1000.00  9000.00"
        assert sl_ext.can_handle(block)
        t = sl_ext.extract(block)
        assert t.transaction_date == date(2024, 5, 1)
        assert t.amount == Decimal("1000.00")
        assert t.balance == Decimal("9000.00")

    def test_dr_cr_same_line(self, sl_ext):
        block = "14/05/2024  SWIGGY ORDER  1353.06 DR  78590.80 CR"
        t = sl_ext.extract(block)
        assert t.transaction_type == "DEBIT"
        assert t.amount == Decimal("1353.06")

    def test_credit_keyword_same_line(self, sl_ext):
        block = "12/05/2024  SALARY CREDIT  63509.05  86410.04"
        t = sl_ext.extract(block)
        assert t.transaction_type == "CREDIT"


# ===========================================================================
# Field Extraction Agent — routing tests
# ===========================================================================

class TestFieldExtractionAgentRouting:

    def test_routes_table_row(self, fea):
        t = fea.extract("01/05/2024\nUPI PAYMENT\n1000.00\n9000.00")
        assert t.transaction_date == date(2024, 5, 1)
        assert t.amount == Decimal("1000.00")

    def test_routes_kv_block(self, fea):
        t = fea.extract(
            "Txn Date: 16/05/2024\nParticulars: SPOTIFY\nAmount: 199.00 DR\nBalance: 45678.12"
        )
        assert t.amount == Decimal("199.00")
        assert "SPOTIFY" in t.description

    def test_routes_same_line(self, fea):
        t = fea.extract("01/05/2024  FLIPKART PAYMENT  8498.42  49000.69")
        assert t.amount == Decimal("8498.42")

    def test_normalizer_uppercases_description(self, fea):
        t = fea.extract("01/05/2024\nswiggy order\n1353.06\n78590.80")
        assert t.description == t.description.upper()

    def test_type_inferred_when_not_explicit(self, fea):
        t = fea.extract("01/05/2024\nUPI PAYMENT\n1000.00\n9000.00")
        assert t.transaction_type in ("DEBIT", "CREDIT")


# ===========================================================================
# Validator — unit tests
# ===========================================================================

class TestTransactionValidator:

    @pytest.fixture
    def v(self):
        return TransactionValidator()

    def _txn(self, **kwargs):
        from src.schemas.transaction import Transaction
        defaults = dict(
            transaction_date=date(2024, 5, 1),
            description="TEST",
            amount=Decimal("1000.00"),
            transaction_type="DEBIT",
        )
        defaults.update(kwargs)
        return Transaction(**defaults)

    def test_valid_transaction_passes(self, v):
        ok, reason = v.validate(self._txn())
        assert ok
        assert reason == ""

    def test_missing_date_rejected(self, v):
        ok, reason = v.validate(self._txn(transaction_date=None))
        assert not ok
        assert "date" in reason.lower()

    def test_missing_description_rejected(self, v):
        ok, reason = v.validate(self._txn(description=""))
        assert not ok
        assert "description" in reason.lower()

    def test_missing_amount_rejected(self, v):
        ok, reason = v.validate(self._txn(amount=None))
        assert not ok
        assert "amount" in reason.lower()

    def test_zero_amount_rejected(self, v):
        ok, reason = v.validate(self._txn(amount=Decimal("0")))
        assert not ok
        assert "zero" in reason.lower()

    def test_invalid_type_rejected(self, v):
        ok, reason = v.validate(self._txn(transaction_type=None))
        assert not ok
        assert "transaction_type" in reason.lower()

    def test_balance_optional(self, v):
        ok, _ = v.validate(self._txn(balance=None))
        assert ok

    def test_rejection_reason_is_meaningful(self, v):
        _, reason = v.validate(self._txn(amount=None))
        assert len(reason) > 5  # not empty / generic


# ===========================================================================
# Full pipeline tests — all three PDFs
# ===========================================================================

class TestFullPipelineSBI:
    """End-to-end extraction from the real SBI PDF."""

    @pytest.fixture(scope="class")
    def results(self):
        eng = DocumentUnderstandingEngine()
        seg = TransactionSegmenter()
        fea = FieldExtractionAgent()
        val = TransactionValidator()
        raw = PDFReader().execute("data/sbi_statement.pdf")
        blocks = seg.segment(raw["text"], eng.analyze(raw["text"], raw["page_count"]))
        txns = [fea.extract(b) for b in blocks]
        valid, skipped = val.validate_all(txns)
        return valid, skipped

    def test_all_20_blocks_valid(self, results):
        valid, skipped = results
        assert len(valid) == 20, f"skipped: {skipped}"
        assert len(skipped) == 0

    def test_all_have_dates(self, results):
        valid, _ = results
        assert all(t.transaction_date is not None for t in valid)

    def test_all_have_descriptions(self, results):
        valid, _ = results
        assert all(t.description for t in valid)

    def test_all_have_amounts(self, results):
        valid, _ = results
        assert all(t.amount is not None and t.amount > 0 for t in valid)

    def test_all_have_types(self, results):
        valid, _ = results
        assert all(t.transaction_type in ("DEBIT", "CREDIT") for t in valid)

    def test_all_have_balances(self, results):
        valid, _ = results
        assert all(t.balance is not None for t in valid)

    def test_total_debit_correct(self, results):
        valid, _ = results
        total = sum(t.amount for t in valid if t.transaction_type == "DEBIT")
        assert total == Decimal("85743.56")

    def test_closing_balance_correct(self, results):
        valid, _ = results
        assert valid[-1].balance == Decimal("63767.46")


class TestFullPipelineICICI:
    """End-to-end extraction from the ICICI 3-page PDF."""

    @pytest.fixture(scope="class")
    def results(self):
        eng = DocumentUnderstandingEngine()
        seg = TransactionSegmenter()
        fea = FieldExtractionAgent()
        val = TransactionValidator()
        raw = PDFReader().execute("data/icici_statement.pdf")
        blocks = seg.segment(raw["text"], eng.analyze(raw["text"], raw["page_count"]))
        txns = [fea.extract(b) for b in blocks]
        valid, skipped = val.validate_all(txns)
        return valid, skipped

    def test_all_60_blocks_valid(self, results):
        valid, skipped = results
        assert len(valid) == 60, f"skipped: {skipped}"
        assert len(skipped) == 0

    def test_all_have_dates(self, results):
        valid, _ = results
        assert all(t.transaction_date is not None for t in valid)

    def test_all_have_descriptions(self, results):
        valid, _ = results
        missing = [t for t in valid if not t.description]
        assert len(missing) == 0

    def test_all_have_amounts_positive(self, results):
        valid, _ = results
        assert all(t.amount is not None and t.amount > 0 for t in valid)

    def test_all_have_types(self, results):
        valid, _ = results
        assert all(t.transaction_type in ("DEBIT", "CREDIT") for t in valid)

    def test_all_have_balances(self, results):
        valid, _ = results
        assert all(t.balance is not None for t in valid)

    def test_credit_transactions_exist(self, results):
        valid, _ = results
        credits = [t for t in valid if t.transaction_type == "CREDIT"]
        assert len(credits) > 0


class TestFullPipelineUnionBank:
    """End-to-end extraction from the Union Bank 5-page KV-layout PDF."""

    @pytest.fixture(scope="class")
    def results(self):
        eng = DocumentUnderstandingEngine()
        seg = TransactionSegmenter()
        fea = FieldExtractionAgent()
        val = TransactionValidator()
        raw = PDFReader().execute("data/no_table2.pdf")
        blocks = seg.segment(raw["text"], eng.analyze(raw["text"], raw["page_count"]))
        txns = [fea.extract(b) for b in blocks]
        valid, skipped = val.validate_all(txns)
        return valid, skipped

    def test_all_35_blocks_valid(self, results):
        valid, skipped = results
        assert len(valid) == 35, f"skipped: {[s['reason'] for s in skipped[:5]]}"
        assert len(skipped) == 0

    def test_all_have_dates(self, results):
        valid, _ = results
        assert all(t.transaction_date is not None for t in valid)

    def test_all_have_descriptions(self, results):
        valid, _ = results
        assert all(t.description for t in valid)

    def test_all_have_amounts_positive(self, results):
        valid, _ = results
        assert all(t.amount is not None and t.amount > 0 for t in valid)

    def test_all_have_types(self, results):
        valid, _ = results
        assert all(t.transaction_type in ("DEBIT", "CREDIT") for t in valid)

    def test_all_have_balances(self, results):
        valid, _ = results
        no_bal = [t for t in valid if t.balance is None]
        assert len(no_bal) == 0

    def test_multiple_date_formats_all_parsed(self, results):
        """Union Bank uses DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD in same statement."""
        valid, _ = results
        years = {t.transaction_date.year for t in valid}
        assert 2024 in years

    def test_wrapped_description_intact(self, results):
        """SPOTIFY PREMIUM spans two lines — must be joined correctly."""
        valid, _ = results
        spotify = next((t for t in valid if "SPOTIFY" in t.description), None)
        assert spotify is not None, "SPOTIFY transaction not found"
        assert "PREMIUM" in spotify.description

    def test_wrapped_description_upi_landlord(self, results):
        """UPI/LANDLORD/RENTPAY spans lines in the original PDF."""
        valid, _ = results
        landlord = next((t for t in valid if "LANDLORD" in t.description), None)
        assert landlord is not None

    def test_credit_transactions_exist(self, results):
        valid, _ = results
        credits = [t for t in valid if t.transaction_type == "CREDIT"]
        assert len(credits) > 0

    def test_closing_balance_correct(self, results):
        valid, _ = results
        assert valid[-1].balance == Decimal("4750.57")
