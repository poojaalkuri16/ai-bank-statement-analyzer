"""
Extraction Generalization Tests
================================
Verifies that the extraction engine is layout-driven, not bank-driven.

Every test uses synthetic statement text that mimics a layout pattern
without referencing any specific bank.  The tests prove the engine can
handle previously unseen statements by understanding their structure.

Covers
------
G1  — Date parser: all supported formats
G2  — LayoutAnalyzer: broadened header detection
G3  — TransactionSegmenter: DR/CR-suffixed amounts accepted in table blocks
G4  — TransactionSegmenter: same-line layout
G5  — TransactionSegmenter: unknown layout best-effort fallback
G6  — SameLineExtractor: field inference
G7  — FieldExtractionAgent parser registry
G8  — TableRowExtractor: non-DD/MM/YYYY date formats
G9  — TransactionValidator: required field enforcement
G10 — End-to-end: all layouts produce identical Transaction schema
"""
from datetime import date
from decimal import Decimal

import pytest

from src.agents.extraction.extractors.key_value_block_extractor import (
    KeyValueBlockExtractor,
)
from src.agents.extraction.extractors.same_line_extractor import SameLineExtractor
from src.agents.extraction.extractors.table_row_extractor import TableRowExtractor
from src.agents.extraction.field_extraction_agent import FieldExtractionAgent
from src.agents.extraction.shared.date_parser import (
    detect_date_formats,
    is_date_line,
    parse_date,
)
from src.agents.layout.layout_analyzer import LayoutAnalyzer
from src.agents.transactions.transaction_segmenter import TransactionSegmenter
from src.agents.validation.transaction_validator import TransactionValidator
from src.schemas.document_profile import DocumentProfile
from src.schemas.transaction import Transaction


# ===========================================================================
# G1 — Date parser: all supported formats
# ===========================================================================

class TestDateParser:

    @pytest.mark.parametrize("text,expected", [
        ("01/05/2024",   date(2024,  5,  1)),
        ("01-05-2024",   date(2024,  5,  1)),
        ("2024-05-01",   date(2024,  5,  1)),
        ("01/05/24",     date(2024,  5,  1)),
        ("01-05-24",     date(2024,  5,  1)),
        ("01 May 2024",  date(2024,  5,  1)),
        ("1 May 2024",   date(2024,  5,  1)),
        ("01 may 2024",  date(2024,  5,  1)),
        ("May 01, 2024", date(2024,  5,  1)),
        ("May 01 2024",  date(2024,  5,  1)),
        ("01 May 24",    date(2024,  5,  1)),
        ("14 Jan 2025",  date(2025,  1, 14)),
        ("31 Dec 2023",  date(2023, 12, 31)),
        ("09 Sep 2023",  date(2023,  9,  9)),
    ])
    def test_parse_date(self, text, expected):
        result = parse_date(text)
        assert result == expected, (
            f"parse_date({text!r}) = {result!r}, expected {expected!r}"
        )

    def test_invalid_returns_none(self):
        assert parse_date("not a date") is None
        assert parse_date("") is None
        assert parse_date("99/99/9999") is None
        assert parse_date("hello world") is None

    def test_is_date_line_pure(self):
        assert is_date_line("01/05/2024")
        assert is_date_line("2024-05-01")
        assert is_date_line("01 May 2024")

    def test_is_date_line_rejects_mixed(self):
        assert not is_date_line("01/05/2024 some description")
        assert not is_date_line("UPI PAYMENT")
        assert not is_date_line("1000.00")

    def test_detect_date_formats(self):
        text = "01/05/2024 and 2024-05-01 and 01 May 2024"
        fmts = detect_date_formats(text)
        assert "DD/MM/YYYY" in fmts
        assert "YYYY-MM-DD" in fmts
        assert "DD MMM YYYY" in fmts


# ===========================================================================
# G2 — LayoutAnalyzer: broadened header detection
# ===========================================================================

class TestLayoutAnalyzerGeneralized:

    @pytest.fixture
    def analyzer(self):
        return LayoutAnalyzer()

    def test_narration_column_triggers_table(self, analyzer):
        text = "DATE\nNARRATION\nDEBIT\nCREDIT\nBALANCE\n01/05/2024\nFOO"
        p = analyzer.analyze(text)
        assert p.has_table_headers
        assert p.layout_type in ("table", "same_line")

    def test_particulars_column_triggers_table(self, analyzer):
        text = "DATE\nPARTICULARS\nAMOUNT\nBALANCE\n01/05/2024\nFOO"
        p = analyzer.analyze(text)
        assert p.has_table_headers

    def test_withdrawal_deposit_columns_trigger_table(self, analyzer):
        text = "DATE\nDETAILS\nWITHDRAWALS\nDEPOSITS\nBALANCE"
        p = analyzer.analyze(text)
        assert p.has_table_headers

    def test_unknown_bank_still_gets_positive_confidence(self, analyzer):
        text = (
            "SOME COOPERATIVE BANK\n"
            "STATEMENT OF ACCOUNT\n"
            "DATE NARRATION AMOUNT BALANCE\n"
            "01/05/2024 PAYMENT 1000.00 50000.00\n"
        )
        p = analyzer.analyze(text)
        assert p.bank_name is None        # correctly not matched
        assert p.confidence > 0           # engine still usable
        assert p.layout_type != "unknown"

    def test_kv_block_with_transaction_date_label(self, analyzer):
        text = (
            "Transaction Date: 01/05/2024\n"
            "Particulars: PAYMENT\n"
            "Amount: 500.00 DR\n"
            "Balance: 9500.00\n"
        )
        p = analyzer.analyze(text)
        assert p.has_labeled_fields
        assert p.layout_type == "block"

    def test_same_line_detected_via_inline_dates(self, analyzer):
        text = "01/05/2024  UPI PAYMENT  1500.00  85000.00"
        p = analyzer.analyze(text)
        assert p.has_inline_dates

    def test_named_month_detected_in_date_formats(self, analyzer):
        text = "01 May 2024 SALARY 63000.00 90000.00"
        p = analyzer.analyze(text)
        assert "DD MMM YYYY" in p.date_formats

    def test_confidence_does_not_require_bank_name(self, analyzer):
        """
        Confidence must be > 0 even when the bank is unrecognised.
        Previously the scoring added 0.20 for bank_name; removing that
        bonus must not drop well-formed statements to zero.
        """
        text = (
            "STATEMENT OF ACCOUNT\n"
            "DATE DESCRIPTION DEBIT CREDIT BALANCE\n"
            "01/05/2024\nPAYMENT\n1000.00\n9000.00\n"
        )
        p = analyzer.analyze(text)
        assert p.confidence > 0


# ===========================================================================
# G3 — TransactionSegmenter: DR/CR-suffixed amounts accepted
# ===========================================================================

class TestSegmenterDRCR:

    @pytest.fixture
    def seg(self):
        return TransactionSegmenter()

    def test_dr_cr_suffixed_amounts(self, seg):
        text = (
            "01/05/2024\n"
            "UPI PAYMENT\n"
            "24,950.89 DR\n"
            "57,499.11 CR\n"
        )
        blocks = seg.segment(text, DocumentProfile(layout_type="table"))
        assert len(blocks) == 1

    def test_currency_prefix_amounts(self, seg):
        text = (
            "02/05/2024\n"
            "FLIPKART PAYMENT\n"
            "₹8,498.42\n"
            "₹49,000.69\n"
        )
        blocks = seg.segment(text, DocumentProfile(layout_type="table"))
        assert len(blocks) == 1

    def test_multiple_table_blocks(self, seg):
        text = (
            "01/05/2024\nUPI PAYMENT\n24950.89\n57499.11\n"
            "02/05/2024\nFLIPKART\n8498.42\n49000.69\n"
        )
        blocks = seg.segment(text, DocumentProfile(layout_type="table"))
        assert len(blocks) == 2

    def test_named_month_date_in_table(self, seg):
        text = (
            "01 May 2024\n"
            "SALARY CREDIT\n"
            "63509.05\n"
            "86410.04\n"
        )
        blocks = seg.segment(text, DocumentProfile(layout_type="table"))
        assert len(blocks) == 1

    def test_yyyy_mm_dd_date_in_table(self, seg):
        text = (
            "2024-05-01\n"
            "NEFT TRANSFER\n"
            "5000.00\n"
            "45000.00\n"
        )
        blocks = seg.segment(text, DocumentProfile(layout_type="table"))
        assert len(blocks) == 1


# ===========================================================================
# G4 — TransactionSegmenter: same-line layout
# ===========================================================================

class TestSegmenterSameLine:

    @pytest.fixture
    def seg(self):
        return TransactionSegmenter()

    def test_same_line_two_transactions(self, seg):
        text = (
            "01/05/2024  UPI/LANDLORD/RENTPAY  24950.89  57499.11\n"
            "02/05/2024  FLIPKART ONLINE  8498.42  49000.69\n"
        )
        blocks = seg.segment(text, DocumentProfile(layout_type="same_line"))
        assert len(blocks) == 2

    def test_same_line_with_dr_cr(self, seg):
        text = "14/05/2024  SWIGGY ORDER  1353.06 DR  78590.80 CR\n"
        blocks = seg.segment(text, DocumentProfile(layout_type="same_line"))
        assert len(blocks) == 1

    def test_bare_date_lines_not_included(self, seg):
        """A line that is only a date should not become a transaction."""
        text = (
            "01/05/2024\n"
            "01/05/2024  UPI PAYMENT  500.00  9500.00\n"
        )
        blocks = seg.segment(text, DocumentProfile(layout_type="same_line"))
        assert len(blocks) == 1
        assert "UPI PAYMENT" in blocks[0]


# ===========================================================================
# G5 — TransactionSegmenter: unknown layout best-effort fallback
# ===========================================================================

class TestSegmenterBestEffort:

    @pytest.fixture
    def seg(self):
        return TransactionSegmenter()

    def test_unknown_layout_table_style(self, seg):
        """
        A table-style document whose layout wasn't detected should still
        produce transaction blocks via best-effort.
        """
        text = (
            "01/05/2024\nUPI PAYMENT\n1000.00\n9000.00\n"
            "02/05/2024\nFLIPKART\n500.00\n8500.00\n"
        )
        profile = DocumentProfile(layout_type="unknown")
        blocks = seg.segment(text, profile)
        assert len(blocks) >= 2

    def test_unknown_layout_same_line_style(self, seg):
        text = (
            "01/05/2024  UPI PAYMENT  1000.00  9000.00\n"
            "02/05/2024  FLIPKART  500.00  8500.00\n"
        )
        profile = DocumentProfile(layout_type="unknown")
        blocks = seg.segment(text, profile)
        assert len(blocks) >= 2

    def test_unknown_layout_empty_text(self, seg):
        profile = DocumentProfile(layout_type="unknown")
        blocks = seg.segment("", profile)
        assert blocks == []


# ===========================================================================
# G6 — SameLineExtractor: field inference
# ===========================================================================

class TestSameLineExtractor:

    @pytest.fixture
    def extractor(self):
        return SameLineExtractor()

    def test_can_handle_same_line(self, extractor):
        line = "01/05/2024  UPI PAYMENT  1000.00  9000.00"
        assert extractor.can_handle(line) is True

    def test_can_handle_rejects_multiline(self, extractor):
        block = "01/05/2024\nUPI PAYMENT\n1000.00\n9000.00"
        assert extractor.can_handle(block) is False

    def test_can_handle_rejects_no_money(self, extractor):
        assert extractor.can_handle("01/05/2024  SOME DESCRIPTION") is False

    def test_extracts_date(self, extractor):
        txn = extractor.extract("01/05/2024  UPI PAYMENT  1000.00  9000.00")
        assert txn.transaction_date == date(2024, 5, 1)

    def test_extracts_amount(self, extractor):
        txn = extractor.extract("01/05/2024  UPI PAYMENT  1000.00  9000.00")
        assert txn.amount == Decimal("1000.00")

    def test_extracts_balance(self, extractor):
        txn = extractor.extract("01/05/2024  UPI PAYMENT  1000.00  9000.00")
        assert txn.balance == Decimal("9000.00")

    def test_extracts_description(self, extractor):
        txn = extractor.extract("01/05/2024  UPI PAYMENT  1000.00  9000.00")
        assert "UPI" in (txn.description or "")
        assert "PAYMENT" in (txn.description or "")

    def test_amount_non_negative(self, extractor):
        txn = extractor.extract("01/05/2024  UPI PAYMENT  1000.00  9000.00")
        assert txn.amount >= 0

    def test_dr_suffix_sets_debit(self, extractor):
        txn = extractor.extract("14/05/2024  SWIGGY ORDER  1353.06 DR  78590.80 CR")
        assert txn.transaction_type == "DEBIT"
        assert txn.amount == Decimal("1353.06")

    def test_credit_keyword_sets_credit(self, extractor):
        txn = extractor.extract("12/05/2024  SALARY CREDIT  63509.05  86410.04")
        assert txn.transaction_type == "CREDIT"

    def test_named_month_date(self, extractor):
        txn = extractor.extract("01 May 2024  UPI PAYMENT  500.00  9500.00")
        assert txn.transaction_date == date(2024, 5, 1)

    def test_only_one_money_value(self, extractor):
        """When only one monetary value exists it becomes the amount."""
        txn = extractor.extract("01/05/2024  SOME PAYMENT  1500.00")
        assert txn.amount == Decimal("1500.00")
        assert txn.balance is None


# ===========================================================================
# G7 — FieldExtractionAgent parser registry
# ===========================================================================

class TestFieldExtractionAgentRegistry:

    @pytest.fixture
    def agent(self):
        return FieldExtractionAgent()

    def test_routes_table_block(self, agent):
        block = "01/05/2024\nUPI PAYMENT\n1000.00\n9000.00"
        txn = agent.extract(block)
        assert txn.transaction_date == date(2024, 5, 1)
        assert txn.amount == Decimal("1000.00")

    def test_routes_kv_block(self, agent):
        block = (
            "Txn Date: 16/05/2024\n"
            "Particulars: SPOTIFY PREMIUM\n"
            "Amount: 199.00 DR\n"
            "Balance: 45678.12\n"
        )
        txn = agent.extract(block)
        assert txn.amount == Decimal("199.00")
        assert "SPOTIFY" in (txn.description or "")

    def test_routes_same_line(self, agent):
        block = "01/05/2024  FLIPKART PAYMENT  8498.42  49000.69"
        txn = agent.extract(block)
        assert txn.transaction_date == date(2024, 5, 1)
        assert txn.amount == Decimal("8498.42")

    def test_normalizer_uppercases(self, agent):
        block = "01/05/2024\nswiggy order\n1353.06\n78590.80"
        txn = agent.extract(block)
        assert txn.description == txn.description.upper()

    def test_register_custom_parser(self, agent):
        """A custom parser can be injected at the front of the registry."""

        class AlwaysRejectParser:
            def can_handle(self, block):
                return False
            def extract(self, block):
                raise AssertionError("Should not be called")

        class CustomParser:
            def can_handle(self, block):
                return "CUSTOM_MARKER" in block
            def extract(self, block):
                from datetime import date as _date
                return Transaction(
                    transaction_date=_date(2024, 1, 1),
                    description="CUSTOM",
                    amount=Decimal("42.00"),
                    transaction_type="DEBIT",
                )

        agent.register_parser(CustomParser(), priority=0)
        txn = agent.extract("CUSTOM_MARKER some content")
        assert txn.description == "CUSTOM"
        assert txn.amount == Decimal("42.00")

    def test_dr_suffixed_table_block_handled(self, agent):
        """DR/CR suffixed amounts in table blocks must not fall through."""
        block = (
            "01/05/2024\n"
            "UPI PAYMENT\n"
            "24,950.89 DR\n"
            "57,499.11 CR\n"
        )
        txn = agent.extract(block)
        assert txn.amount == Decimal("24950.89")
        assert txn.transaction_type == "DEBIT"


# ===========================================================================
# G8 — TableRowExtractor: non-DD/MM/YYYY date formats
# ===========================================================================

class TestTableRowExtractorDates:

    @pytest.fixture
    def extractor(self):
        return TableRowExtractor()

    def test_dd_mm_yyyy(self, extractor):
        block = "01/05/2024\nUPI PAYMENT\n1000.00\n9000.00"
        assert extractor.can_handle(block)
        txn = extractor.extract(block)
        assert txn.transaction_date == date(2024, 5, 1)

    def test_yyyy_mm_dd(self, extractor):
        block = "2024-05-01\nNEFT TRANSFER\n5000.00\n45000.00"
        assert extractor.can_handle(block)
        txn = extractor.extract(block)
        assert txn.transaction_date == date(2024, 5, 1)

    def test_dd_mmm_yyyy(self, extractor):
        block = "01 May 2024\nSALARY CREDIT\n63509.05\n86410.04"
        assert extractor.can_handle(block)
        txn = extractor.extract(block)
        assert txn.transaction_date == date(2024, 5, 1)

    def test_dd_mm_yy(self, extractor):
        block = "01/05/24\nUPI PAYMENT\n1000.00\n9000.00"
        assert extractor.can_handle(block)
        txn = extractor.extract(block)
        assert txn.transaction_date == date(2024, 5, 1)

    def test_amount_always_non_negative(self, extractor):
        block = "01/05/2024\nPAYMENT\n1000.00 DR\n9000.00 CR"
        txn = extractor.extract(block)
        assert txn.amount >= 0
        assert txn.balance >= 0


# ===========================================================================
# G9 — TransactionValidator: required field enforcement
# ===========================================================================

class TestTransactionValidator:

    @pytest.fixture
    def validator(self):
        return TransactionValidator()

    def _txn(self, **kwargs):
        defaults = dict(
            transaction_date=date(2024, 5, 1),
            description="TEST PAYMENT",
            amount=Decimal("1000.00"),
            transaction_type="DEBIT",
        )
        defaults.update(kwargs)
        return Transaction(**defaults)

    def test_valid_transaction_passes(self, validator):
        ok, reason = validator.validate(self._txn())
        assert ok is True
        assert reason == ""

    def test_missing_date_rejected(self, validator):
        ok, reason = validator.validate(self._txn(transaction_date=None))
        assert ok is False
        assert "date" in reason

    def test_missing_description_rejected(self, validator):
        ok, reason = validator.validate(self._txn(description=""))
        assert ok is False
        assert "description" in reason

    def test_missing_amount_rejected(self, validator):
        ok, reason = validator.validate(self._txn(amount=None))
        assert ok is False
        assert "amount" in reason

    def test_invalid_type_rejected(self, validator):
        ok, reason = validator.validate(self._txn(transaction_type=None))
        assert ok is False
        assert "transaction_type" in reason

    def test_balance_optional(self, validator):
        ok, _ = validator.validate(self._txn(balance=None))
        assert ok is True

    def test_validate_all_filters_invalid(self, validator):
        good = self._txn()
        bad  = self._txn(transaction_date=None)
        valid, skipped = validator.validate_all([good, bad])
        assert len(valid) == 1
        assert len(skipped) == 1
        assert valid[0] is good

    def test_validate_all_empty_list(self, validator):
        valid, skipped = validator.validate_all([])
        assert valid == []
        assert skipped == []


# ===========================================================================
# G10 — End-to-end: all layouts produce identical Transaction schema
# ===========================================================================

class TestEndToEndSchemaConsistency:
    """
    Feeds three different layout representations of the same transaction
    through the FieldExtractionAgent and verifies all produce a valid,
    consistent Transaction.
    """

    EXPECTED_DATE   = date(2024, 5, 14)
    EXPECTED_AMOUNT = Decimal("1353.06")

    @pytest.fixture
    def agent(self):
        return FieldExtractionAgent()

    @pytest.fixture
    def validator(self):
        return TransactionValidator()

    def _assert_valid(self, txn: Transaction, validator: TransactionValidator):
        ok, reason = validator.validate(txn)
        assert ok, f"Transaction invalid: {reason} — {txn}"
        assert txn.amount >= 0
        assert txn.transaction_date is not None
        assert txn.transaction_type in ("DEBIT", "CREDIT")

    def test_table_layout(self, agent, validator):
        block = "14/05/2024\nUPI/SWIGGY/ORDERPAY\n1353.06\n78590.80"
        txn = agent.extract(block)
        self._assert_valid(txn, validator)
        assert txn.transaction_date == self.EXPECTED_DATE
        assert txn.amount == self.EXPECTED_AMOUNT

    def test_kv_layout(self, agent, validator):
        block = (
            "Txn Date: 14/05/2024\n"
            "Particulars: UPI/SWIGGY/ORDERPAY\n"
            "Amount: 1353.06 DR\n"
            "Balance: 78590.80\n"
        )
        txn = agent.extract(block)
        self._assert_valid(txn, validator)
        assert txn.transaction_date == self.EXPECTED_DATE
        assert txn.amount == self.EXPECTED_AMOUNT

    def test_same_line_layout(self, agent, validator):
        block = "14/05/2024  UPI/SWIGGY/ORDERPAY  1353.06  78590.80"
        txn = agent.extract(block)
        self._assert_valid(txn, validator)
        assert txn.transaction_date == self.EXPECTED_DATE
        assert txn.amount == self.EXPECTED_AMOUNT

    def test_named_month_table_layout(self, agent, validator):
        block = "14 May 2024\nUPI/SWIGGY/ORDERPAY\n1353.06\n78590.80"
        txn = agent.extract(block)
        self._assert_valid(txn, validator)
        assert txn.transaction_date == self.EXPECTED_DATE
        assert txn.amount == self.EXPECTED_AMOUNT

    def test_dr_cr_table_layout(self, agent, validator):
        block = (
            "14/05/2024\n"
            "UPI/SWIGGY/ORDERPAY\n"
            "1353.06 DR\n"
            "78590.80 CR\n"
        )
        txn = agent.extract(block)
        self._assert_valid(txn, validator)
        assert txn.amount == self.EXPECTED_AMOUNT
        assert txn.transaction_type == "DEBIT"
