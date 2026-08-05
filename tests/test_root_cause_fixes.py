"""
Root Cause Fix Tests
====================
Verifies the three specific bugs identified by tracing actual runtime
values through the extraction pipeline.

Bug 1 — MoneyCandidateDetector leaked date-fragment numbers as money
         candidates, causing amount=11 or amount=1 instead of the real
         transaction amount.

Bug 2 — TransactionSegmenter capped blocks at 4 lines, dropping the
         balance line from 3-column (debit|credit|balance) statements.

Bug 3 — TableRowExtractor rejected 3-column blocks where one amount
         column was "0" because "0" didn't match the decimal pattern.

All three bugs together caused CREDIT transactions in 3-column formats
to receive amount=0 / type=None instead of the correct values.

These tests use only synthetic blocks — no bank-specific logic.
"""
from decimal import Decimal
from datetime import date

import pytest

from src.agents.extraction.extractors.table_row_extractor import TableRowExtractor
from src.agents.extraction.field_extraction_agent import FieldExtractionAgent
from src.agents.extraction.shared.money_candidate_detector import (
    MoneyCandidateDetector,
)
from src.agents.transactions.transaction_segmenter import TransactionSegmenter
from src.agents.validation.transaction_validator import TransactionValidator
from src.schemas.document_profile import DocumentProfile


# ===========================================================================
# Bug 1 — MoneyCandidateDetector must not produce date-fragment candidates
# ===========================================================================

class TestMoneyCandidateDetectorDateExclusion:

    @pytest.fixture
    def detector(self):
        return MoneyCandidateDetector()

    def test_date_line_produces_no_candidates(self, detector):
        """Numbers inside a date string must never become money candidates."""
        block = "01/05/2024\nUPI PAYMENT\n1000.00\n9000.00"
        candidates = detector.detect(block)
        # Only the two actual money lines should produce candidates
        values = {c.value for c in candidates}
        assert Decimal("1") not in values, "Date fragment '01' leaked as candidate"
        assert Decimal("5") not in values, "Date fragment '05' leaked as candidate"
        assert Decimal("2024") not in values, "Date fragment '2024' leaked as candidate"
        assert Decimal("11") not in values, "Composite date digit '11' leaked"

    def test_amount_candidates_still_detected(self, detector):
        block = "01/05/2024\nUPI PAYMENT\n1353.06\n78590.80"
        candidates = detector.detect(block)
        values = {c.value for c in candidates}
        assert Decimal("1353.06") in values
        assert Decimal("78590.80") in values

    def test_three_column_block_candidates(self, detector):
        """In a 3-column block the zero placeholder must appear as a candidate."""
        block = "11/05/2024\nSALARY CREDIT\n0\n582.30\n32469.20"
        candidates = detector.detect(block)
        values = {c.value for c in candidates}
        # Date fragments must be absent
        assert Decimal("11") not in values
        assert Decimal("2024") not in values
        # Real values must be present
        assert Decimal("582.30") in values
        assert Decimal("32469.20") in values

    def test_no_candidates_from_bare_date_line(self, detector):
        """A block containing only a date should produce zero candidates."""
        block = "01/05/2024"
        candidates = detector.detect(block)
        assert candidates == []

    def test_yyyy_mm_dd_date_line_excluded(self, detector):
        block = "2024-05-01\nNEFT TRANSFER\n5000.00\n45000.00"
        candidates = detector.detect(block)
        values = {c.value for c in candidates}
        assert Decimal("2024") not in values
        assert Decimal("1") not in values

    def test_named_month_date_line_excluded(self, detector):
        block = "01 May 2024\nSALARY CREDIT\n63509.05\n86410.04"
        candidates = detector.detect(block)
        values = {c.value for c in candidates}
        assert Decimal("1") not in values
        assert Decimal("2024") not in values
        assert Decimal("63509.05") in values


# ===========================================================================
# Bug 2 — TransactionSegmenter must collect 5 lines for 3-column blocks
# ===========================================================================

class TestSegmenterFiveLineBlocks:

    @pytest.fixture
    def seg(self):
        return TransactionSegmenter()

    def test_5line_block_is_collected(self, seg):
        """
        A 3-column transaction produces 5 non-empty lines.
        The segmenter must not drop the 5th line (balance).
        """
        text = (
            "01/05/2024\n"
            "UPI PAYMENT\n"
            "24950.89\n"       # debit column
            "0\n"              # credit column (empty)
            "57499.11\n"       # balance
        )
        profile = DocumentProfile(layout_type="table")
        blocks = seg.segment(text, profile)
        assert len(blocks) == 1
        assert "57499.11" in blocks[0], "Balance line was dropped"
        assert "24950.89" in blocks[0], "Amount line was dropped"

    def test_credit_5line_block_collected(self, seg):
        text = (
            "11/05/2024\n"
            "SB INTEREST CREDIT\n"
            "0\n"              # debit column (empty)
            "582.30\n"         # credit column
            "32469.20\n"       # balance
        )
        profile = DocumentProfile(layout_type="table")
        blocks = seg.segment(text, profile)
        assert len(blocks) == 1
        assert "582.30" in blocks[0]
        assert "32469.20" in blocks[0]

    def test_4line_block_still_works(self, seg):
        """Existing 4-line blocks must continue to be collected correctly."""
        text = "01/05/2024\nUPI PAYMENT\n24950.89\n57499.11\n"
        profile = DocumentProfile(layout_type="table")
        blocks = seg.segment(text, profile)
        assert len(blocks) == 1

    def test_multiple_5line_blocks(self, seg):
        text = (
            "01/05/2024\nUPI PAYMENT\n24950.89\n0\n57499.11\n"
            "11/05/2024\nSALARY CREDIT\n0\n63509.05\n86410.04\n"
        )
        profile = DocumentProfile(layout_type="table")
        blocks = seg.segment(text, profile)
        assert len(blocks) == 2

    def test_mixed_4line_and_5line_blocks(self, seg):
        text = (
            "01/05/2024\nUPI PAYMENT\n24950.89\n57499.11\n"      # 4-line
            "11/05/2024\nSALARY CREDIT\n0\n63509.05\n86410.04\n" # 5-line
            "14/05/2024\nSWIGGY ORDER\n1353.06\n78590.80\n"      # 4-line
        )
        profile = DocumentProfile(layout_type="table")
        blocks = seg.segment(text, profile)
        assert len(blocks) == 3


# ===========================================================================
# Bug 3 — TableRowExtractor must accept "0" as empty-column placeholder
# ===========================================================================

class TestTableRowExtractorThreeColumns:

    @pytest.fixture
    def extractor(self):
        return TableRowExtractor()

    def test_zero_credit_col_accepted(self, extractor):
        """5-line block with credit=0 → DEBIT transaction."""
        block = "01/05/2024\nUPI PAYMENT\n24950.89\n0\n57499.11"
        assert extractor.can_handle(block) is True

    def test_zero_debit_col_accepted(self, extractor):
        """5-line block with debit=0 → CREDIT transaction."""
        block = "11/05/2024\nSALARY CREDIT\n0\n63509.05\n86410.04"
        assert extractor.can_handle(block) is True

    def test_5col_debit_amount_correct(self, extractor):
        block = "01/05/2024\nUPI PAYMENT\n24950.89\n0\n57499.11"
        txn = extractor.extract(block)
        assert txn.amount == Decimal("24950.89")
        assert txn.transaction_type == "DEBIT"
        assert txn.balance == Decimal("57499.11")

    def test_5col_credit_amount_correct(self, extractor):
        block = "11/05/2024\nSALARY CREDIT\n0\n63509.05\n86410.04"
        txn = extractor.extract(block)
        assert txn.amount == Decimal("63509.05")
        assert txn.transaction_type == "CREDIT"
        assert txn.balance == Decimal("86410.04")

    def test_5col_refund_credit(self, extractor):
        block = "09/05/2024\nREFUND - AMAZON RETURN\n0\n2849.80\n31886.90"
        txn = extractor.extract(block)
        assert txn.amount == Decimal("2849.80")
        assert txn.transaction_type == "CREDIT"

    def test_5col_interest_credit(self, extractor):
        block = "11/05/2024\nSB INTEREST CREDIT - QTR\n0\n582.30\n32469.20"
        txn = extractor.extract(block)
        assert txn.amount == Decimal("582.30")
        assert txn.transaction_type == "CREDIT"

    def test_4col_still_works(self, extractor):
        block = "01/05/2024\nUPI PAYMENT\n24950.89\n57499.11"
        assert extractor.can_handle(block) is True
        txn = extractor.extract(block)
        assert txn.amount == Decimal("24950.89")

    def test_amount_never_zero_from_date_fragments(self, extractor):
        """
        The original bug: amount was set to 11 (from '01' in date '01/05/2024').
        After the fix, amount must equal the real transaction value.
        """
        block = "11/05/2024\nSALARY CREDIT\n0\n63509.05\n86410.04"
        txn = extractor.extract(block)
        # Before fix: amount = 11 (date fragment). After fix: amount = 63509.05
        assert txn.amount != Decimal("11"), "Date fragment leaked into amount"
        assert txn.amount == Decimal("63509.05")

    def test_type_never_none(self, extractor):
        """transaction_type must always be DEBIT or CREDIT, never None."""
        for block in [
            "01/05/2024\nUPI PAYMENT\n24950.89\n0\n57499.11",
            "11/05/2024\nSALARY CREDIT\n0\n63509.05\n86410.04",
        ]:
            txn = extractor.extract(block)
            assert txn.transaction_type in ("DEBIT", "CREDIT"), (
                f"transaction_type is None for block: {block!r}"
            )


# ===========================================================================
# End-to-end: pipeline contract for both 4-col and 5-col layouts
# ===========================================================================

class TestPipelineContract:
    """
    Every transaction entering analytics must satisfy:
      transaction_date != None
      description != ""
      amount > 0
      transaction_type in {DEBIT, CREDIT}
    """

    @pytest.fixture
    def agent(self):
        return FieldExtractionAgent()

    @pytest.fixture
    def validator(self):
        return TransactionValidator()

    @pytest.mark.parametrize("block,exp_amount,exp_type", [
        # 4-column layouts
        ("01/05/2024\nUPI PAYMENT\n24950.89\n57499.11",           Decimal("24950.89"), "DEBIT"),
        ("12/05/2024\nSALARY CREDIT - INFOTECH\n63509.05\n86410.04", Decimal("63509.05"), "CREDIT"),
        ("14/05/2024\nSWIGGY ORDER\n1353.06 DR\n78590.80 CR",     Decimal("1353.06"),  "DEBIT"),
        # 5-column layouts (debit | credit | balance)
        ("01/05/2024\nUPI PAYMENT\n24950.89\n0\n57499.11",        Decimal("24950.89"), "DEBIT"),
        ("11/05/2024\nSALARY CREDIT\n0\n63509.05\n86410.04",      Decimal("63509.05"), "CREDIT"),
        ("09/05/2024\nREFUND - AMAZON RETURN\n0\n2849.80\n31886.90", Decimal("2849.80"), "CREDIT"),
        ("11/05/2024\nSB INTEREST CREDIT - QTR\n0\n582.30\n32469.20", Decimal("582.30"), "CREDIT"),
        # Named-month date
        ("14 May 2024\nMEDPLUS\n3568.74\n82841.30",               Decimal("3568.74"),  "DEBIT"),
        # YYYY-MM-DD date
        ("2024-05-01\nNEFT TRANSFER\n5000.00\n45000.00",          Decimal("5000.00"),  "DEBIT"),
    ])
    def test_transaction_contract(self, agent, validator, block, exp_amount, exp_type):
        txn = agent.extract(block)

        # Validate contract
        ok, reason = validator.validate(txn)
        assert ok, f"Transaction invalid ({reason}) for block: {block!r}"

        # Verify specific values
        assert txn.amount == exp_amount, (
            f"amount={txn.amount}, expected {exp_amount} for block: {block!r}"
        )
        assert txn.transaction_type == exp_type, (
            f"type={txn.transaction_type}, expected {exp_type} for block: {block!r}"
        )
        assert txn.amount > 0, f"amount must be > 0, got {txn.amount}"
        assert txn.transaction_date is not None
        assert txn.description != ""
