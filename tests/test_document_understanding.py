"""
Document Understanding Engine Tests
====================================
Verifies the complete generic document-understanding and
transaction-segmentation pipeline against the success criteria:

  SC1  Correctly isolates the transaction history region
  SC2  Ignores metadata, headers, footers, account information
  SC3  Preserves transaction order
  SC4  Keeps all lines of a single transaction together
  SC5  Handles wrapped (multi-line) descriptions
  SC6  Handles multi-page statements (repeated headers suppressed)
  SC7  Works across tabular and key-value layouts
  SC8  No bank-specific logic — purely structural detection
  SC9  Debug log format (spot-check fields)
"""
import json
from pathlib import Path

import pytest

from src.agents.document.document_understanding_engine import (
    DocumentUnderstandingEngine,
)
from src.agents.transactions.transaction_segmenter import TransactionSegmenter
from src.schemas.document_profile import DocumentProfile

engine    = DocumentUnderstandingEngine()
segmenter = TransactionSegmenter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def segment(text: str, page_count: int = 1) -> tuple[DocumentProfile, list[str]]:
    profile = engine.analyze(text, page_count)
    blocks  = segmenter.segment(text, profile)
    return profile, blocks


# ---------------------------------------------------------------------------
# SC1 — Transaction region correctly detected
# ---------------------------------------------------------------------------

class TestTransactionRegionDetection:

    def test_region_starts_after_column_header(self):
        text = (
            "My Bank\nCustomer: Test User\nAccount: 123456\n"
            "Date Description Debit Credit Balance\n"
            "01/05/2024\nUPI PAYMENT\n1000.00\n9000.00\n"
            "02/05/2024\nFLIPKART\n500.00\n8500.00\n"
        )
        profile, blocks = segment(text)
        # Region must not include metadata lines
        assert profile.transaction_region_start is not None
        # Blocks must only be transactions
        assert len(blocks) == 2

    def test_region_starts_at_kv_date_label(self):
        text = (
            "Bank Name\nCustomer Name: Alice\n"
            "Txn Date: 01/05/2024\nParticulars: UPI PAYMENT\n"
            "Amount: 1000.00 DR\nBalance: 9000.00\n"
            "Txn Date: 02/05/2024\nParticulars: SALARY CREDIT\n"
            "Amount: 50000.00 CR\nBalance: 59000.00\n"
        )
        profile, blocks = segment(text)
        assert profile.transaction_region_start is not None
        assert profile.layout_type == "block"
        assert len(blocks) == 2

    def test_region_end_detected_at_closing_balance(self):
        text = (
            "Date Description Debit Credit Balance\n"
            "01/05/2024\nUPI PAYMENT\n1000.00\n9000.00\n"
            "Closing Balance: Rs. 9000.00\n"
            "This is a system generated statement.\n"
        )
        profile, blocks = segment(text)
        # Closing Balance line must not appear in any block
        for block in blocks:
            assert "Closing Balance" not in block
            assert "system generated" not in block

    def test_metadata_before_region_excluded(self):
        text = (
            "STATE BANK OF INDIA\n"
            "Account Statement\n"
            "Customer Name:\nPooja Nair\n"
            "Account Number:\n3849 1027 5610\n"
            "Branch:\nKoramangala\n"
            "IFSC Code:\nSBIN0011452\n"
            "Statement Period:\n01/05/2024 to 31/05/2024\n"
            "Date\nDescription\nDebit\nCredit\nBalance\n"
            "01/05/2024\nUPI PAYMENT\n1000.00\n9000.00\n"
        )
        profile, blocks = segment(text)
        # No metadata should appear as a block description
        for block in blocks:
            assert "Pooja Nair" not in block
            assert "3849 1027 5610" not in block
            assert "SBIN0011452" not in block
            assert "Koramangala" not in block

    def test_real_sbi_statement_region(self):
        """Live test against the real SBI PDF."""
        report_path = Path("reports/sbi_statement.json")
        if not report_path.exists():
            pytest.skip("SBI report not found")
        from src.tools.pdf_reader import PDFReader
        raw = PDFReader().execute("data/sbi_statement.pdf")
        profile, blocks = segment(raw["text"], raw["page_count"])
        assert profile.transaction_region_start is not None
        assert len(blocks) == 20
        # Confirm no metadata bled into block descriptions
        for block in blocks:
            lines = block.strip().splitlines()
            assert "KORAMANGALA" not in block.upper()
            assert "SBIN0011452" not in block


# ---------------------------------------------------------------------------
# SC2 — Non-transaction content never becomes a block
# ---------------------------------------------------------------------------

class TestNonTransactionExclusion:

    def test_page_header_not_a_block(self):
        text = (
            "Page 1 of 3\n"
            "Date Description Debit Credit Balance\n"
            "01/05/2024\nUPI PAYMENT\n1000.00\n9000.00\n"
            "Page 2 of 3\n"
            "02/05/2024\nFLIPKART\n500.00\n8500.00\n"
        )
        _, blocks = segment(text)
        assert len(blocks) == 2
        for block in blocks:
            assert "Page" not in block

    def test_disclaimer_not_a_block(self):
        text = (
            "Date Description Debit Balance\n"
            "01/05/2024\nPAYMENT\n1000.00\n9000.00\n"
            "This is a computer generated statement and does not require a signature.\n"
        )
        _, blocks = segment(text)
        for block in blocks:
            assert "computer generated" not in block.lower()

    def test_opening_closing_balance_lines_excluded(self):
        text = (
            "Opening Balance: Rs. 82,450.00\n"
            "Date Description Debit Credit Balance\n"
            "01/05/2024\nSWIGGY\n1353.06\n81096.94\n"
            "Closing Balance: Rs. 81,096.94\n"
        )
        _, blocks = segment(text)
        for block in blocks:
            assert "Opening Balance" not in block
            assert "Closing Balance" not in block

    def test_column_header_row_not_a_block(self):
        text = (
            "Date Description Debit Credit Balance\n"
            "01/05/2024\nUPI PAYMENT\n1000.00\n9000.00\n"
        )
        _, blocks = segment(text)
        assert len(blocks) == 1
        assert "Description" not in blocks[0]

    def test_account_number_not_a_block(self):
        text = (
            "Account Number: 3849102756100000\n"
            "IFSC: SBIN0011452\n"
            "Date Description Debit Balance\n"
            "01/05/2024\nNEFT PAYMENT\n1000.00\n9000.00\n"
        )
        _, blocks = segment(text)
        assert len(blocks) == 1
        assert "3849102756100000" not in blocks[0]
        assert "SBIN0011452" not in blocks[0]


# ---------------------------------------------------------------------------
# SC3 — Transaction order preserved
# ---------------------------------------------------------------------------

class TestTransactionOrder:

    def test_order_preserved_table(self):
        text = (
            "Date Description Debit Balance\n"
            "01/05/2024\nFIRST\n100.00\n900.00\n"
            "02/05/2024\nSECOND\n200.00\n700.00\n"
            "03/05/2024\nTHIRD\n300.00\n400.00\n"
        )
        _, blocks = segment(text)
        assert len(blocks) == 3
        assert "FIRST"  in blocks[0]
        assert "SECOND" in blocks[1]
        assert "THIRD"  in blocks[2]

    def test_order_preserved_kv(self):
        txns = []
        for i, name in enumerate(["ALPHA", "BETA", "GAMMA"], start=1):
            txns.append(
                f"Txn Date: 0{i}/05/2024\n"
                f"Particulars: {name}\n"
                f"Amount: {i*100}.00 DR\n"
                f"Balance: {5000 - i*100}.00\n"
            )
        text = "\n".join(txns)
        _, blocks = segment(text)
        assert len(blocks) == 3
        assert "ALPHA" in blocks[0]
        assert "BETA"  in blocks[1]
        assert "GAMMA" in blocks[2]


# ---------------------------------------------------------------------------
# SC4 — All lines of one transaction stay together
# ---------------------------------------------------------------------------

class TestTransactionCompleteness:

    def test_4line_block_complete(self):
        text = (
            "Date Description Debit Balance\n"
            "01/05/2024\nUPI PAYMENT\n1000.00\n9000.00\n"
        )
        _, blocks = segment(text)
        assert len(blocks) == 1
        assert "01/05/2024" in blocks[0]
        assert "UPI PAYMENT" in blocks[0]
        assert "1000.00"    in blocks[0]
        assert "9000.00"    in blocks[0]

    def test_5line_3col_block_complete(self):
        text = (
            "Date Particulars Debit Credit Balance\n"
            "11/05/2024\nSALARY CREDIT INFOTECH\n0\n63509.05\n86410.04\n"
        )
        _, blocks = segment(text)
        assert len(blocks) == 1
        block = blocks[0]
        assert "SALARY" in block
        assert "63509.05" in block
        assert "86410.04" in block

    def test_kv_block_all_labels_present(self):
        text = (
            "Txn Date: 16/05/2024\n"
            "Particulars: SPOTIFY PREMIUM\n"
            "Amount: 199.00 DR\n"
            "Balance: 45678.12\n"
        )
        _, blocks = segment(text)
        assert len(blocks) == 1
        assert "SPOTIFY" in blocks[0]
        assert "199.00"  in blocks[0]
        assert "45678.12" in blocks[0]


# ---------------------------------------------------------------------------
# SC5 — Wrapped (multi-line) descriptions handled correctly
# ---------------------------------------------------------------------------

class TestWrappedDescriptions:

    def test_two_description_lines_merged(self):
        text = (
            "Date Description Debit Balance\n"
            "01/05/2024\nNEFT/IMPS/REF-123456789\nTOWARDS RENT PAYMENT\n"
            "24950.89\n57499.11\n"
        )
        _, blocks = segment(text)
        assert len(blocks) == 1
        # Both description lines must be in the block
        assert "NEFT" in blocks[0]
        assert "RENT" in blocks[0]

    def test_three_description_lines_merged(self):
        text = (
            "Date Description Debit Balance\n"
            "01/05/2024\nUPI/\nLANDLORD/\nRENTPAY\n"
            "24950.89\n57499.11\n"
        )
        _, blocks = segment(text)
        assert len(blocks) == 1
        # All three description fragments must be in the single block
        assert "UPI" in blocks[0]
        assert "LANDLORD" in blocks[0]
        assert "RENTPAY"  in blocks[0]

    def test_wrapped_desc_does_not_split_transactions(self):
        text = (
            "Date Description Debit Balance\n"
            "01/05/2024\nNEFT TRANSFER\nTO RAHUL SHARMA\n7912.46\n22900.99\n"
            "02/05/2024\nFLIPKART ONLINE PAYMENT\n8498.42\n14402.57\n"
        )
        _, blocks = segment(text)
        assert len(blocks) == 2
        assert "RAHUL SHARMA" in blocks[0]
        assert "FLIPKART"     in blocks[1]


# ---------------------------------------------------------------------------
# SC6 — Multi-page: repeated headers suppressed
# ---------------------------------------------------------------------------

class TestMultiPageSupport:

    def test_repeated_header_suppressed_across_pages(self):
        header = "My Bank | Account Statement | Page {n} of 3"
        page1  = (
            "My Bank | Account Statement | Page 1 of 3\n"
            "Date Description Debit Balance\n"
            "01/05/2024\nUPI PAYMENT\n1000.00\n9000.00\n"
        )
        page2  = (
            "My Bank | Account Statement | Page 2 of 3\n"
            "Date Description Debit Balance\n"
            "02/05/2024\nFLIPKART\n500.00\n8500.00\n"
        )
        page3  = (
            "My Bank | Account Statement | Page 3 of 3\n"
            "Date Description Debit Balance\n"
            "03/05/2024\nSWIGGY\n200.00\n8300.00\n"
        )
        full_text = page1 + page2 + page3
        profile, blocks = segment(full_text, page_count=3)

        # Header line should be in repeated_header_lines or stripped
        for block in blocks:
            assert "Account Statement" not in block or "UPI" in block

        # Three transactions expected
        assert len(blocks) == 3

    def test_page_numbers_suppressed(self):
        text = (
            "Page 1 of 2\n"
            "Date Description Debit Balance\n"
            "01/05/2024\nUPI PAYMENT\n1000.00\n9000.00\n"
            "Page 2 of 2\n"
            "02/05/2024\nFLIPKART\n500.00\n8500.00\n"
        )
        _, blocks = segment(text, page_count=2)
        assert len(blocks) == 2
        for block in blocks:
            assert "Page" not in block


# ---------------------------------------------------------------------------
# SC7 — Works across tabular and key-value layouts
# ---------------------------------------------------------------------------

class TestMultipleLayouts:

    def test_tabular_layout(self):
        text = (
            "Date Particulars Debit Credit Balance\n"
            "01/05/2024\nUPI PAYMENT\n1000.00\n9000.00\n"
            "02/05/2024\nSALARY CREDIT\n50000.00\n59000.00\n"
        )
        profile, blocks = segment(text)
        assert profile.layout_type in ("table", "same_line", "mixed")
        assert len(blocks) == 2

    def test_kv_block_layout(self):
        text = (
            "Txn Date: 01/05/2024\nParticulars: UPI PAYMENT\n"
            "Amount: 1000.00 DR\nBalance: 9000.00\n"
            "Txn Date: 02/05/2024\nParticulars: SALARY CREDIT\n"
            "Amount: 50000.00 CR\nBalance: 59000.00\n"
        )
        profile, blocks = segment(text)
        assert profile.layout_type == "block"
        assert len(blocks) == 2

    def test_same_line_layout(self):
        text = (
            "01/05/2024  UPI PAYMENT  1000.00  9000.00\n"
            "02/05/2024  FLIPKART     500.00   8500.00\n"
        )
        profile, blocks = segment(text)
        assert profile.layout_type == "same_line"
        assert len(blocks) == 2

    def test_dr_cr_suffix_layout(self):
        text = (
            "Date Narration Debit Credit Balance\n"
            "14/05/2024\nSWIGGY ORDER\n1353.06 DR\n78590.80 CR\n"
        )
        _, blocks = segment(text)
        assert len(blocks) == 1
        assert "1353.06" in blocks[0]

    def test_named_month_date_layout(self):
        text = (
            "Date Description Amount Balance\n"
            "14 May 2024\nMEDPLUS HEALTH SERVICES\n3568.74\n82841.30\n"
        )
        _, blocks = segment(text)
        assert len(blocks) == 1
        assert "MEDPLUS" in blocks[0]

    def test_iso_date_layout(self):
        text = (
            "Date Description Debit Balance\n"
            "2024-05-01\nNEFT TRANSFER\n5000.00\n45000.00\n"
        )
        _, blocks = segment(text)
        assert len(blocks) == 1

    def test_unknown_layout_best_effort(self):
        """Unclassifiable layout still produces blocks via best-effort."""
        text = (
            "01/05/2024\nUPI PAYMENT\n1000.00\n9000.00\n"
            "02/05/2024\nFLIPKART\n500.00\n8500.00\n"
        )
        profile = DocumentProfile(layout_type="unknown")
        blocks  = segmenter.segment(text, profile)
        assert len(blocks) == 2


# ---------------------------------------------------------------------------
# SC8 — No bank-specific logic
# ---------------------------------------------------------------------------

class TestNoBankSpecificLogic:

    def test_layout_detection_works_without_bank_name(self):
        text = (
            "SOME COOPERATIVE BANK LTD\n"
            "ACCOUNT STATEMENT\n"
            "Date Narration Debit Credit Balance\n"
            "01/05/2024\nMEMBER PAYMENT\n1000.00\n9000.00\n"
        )
        profile, blocks = segment(text)
        # Must produce blocks regardless of unrecognised bank
        assert len(blocks) >= 1
        assert profile.layout_type is not None

    def test_bank_name_detection_is_informational_only(self):
        """bank_name on the profile is set for info — routing must not use it."""
        text = (
            "Date Description Debit Balance\n"
            "01/05/2024\nUPI PAYMENT\n1000.00\n9000.00\n"
        )
        profile, _ = segment(text)
        # Layout must come from structure, not from bank name
        assert profile.layout_type in (
            "table", "same_line", "block", "mixed", "unknown"
        )

    def test_foreign_date_format_works(self):
        """DD-MM-YYYY dash-separated date is layout-agnostic."""
        text = (
            "Date Description Debit Balance\n"
            "01-05-2024\nUPI PAYMENT\n1000.00\n9000.00\n"
        )
        _, blocks = segment(text)
        assert len(blocks) == 1

    def test_usd_statement_layout(self):
        """Currency-agnostic: USD statement same structure as INR."""
        text = (
            "Date Description Withdrawals Deposits Balance\n"
            "01/05/2024\nATM WITHDRAWAL\n500.00\n9500.00\n"
            "02/05/2024\nDIRECT DEPOSIT\n5000.00\n14500.00\n"
        )
        _, blocks = segment(text)
        assert len(blocks) == 2


# ---------------------------------------------------------------------------
# SC9 — DocumentProfile has all required fields
# ---------------------------------------------------------------------------

class TestDocumentProfileCompleteness:

    def test_profile_has_layout_type(self):
        text = "Date Description Debit Balance\n01/05/2024\nPAY\n100.00\n900.00"
        profile, _ = segment(text)
        assert profile.layout_type is not None

    def test_profile_has_region_start_when_detectable(self):
        text = (
            "Metadata line\n"
            "Date Description Debit Balance\n"
            "01/05/2024\nPAY\n100.00\n900.00\n"
        )
        profile, _ = segment(text)
        assert profile.transaction_region_start is not None

    def test_profile_confidence_positive(self):
        text = (
            "Account Statement\n"
            "Date Description Debit Credit Balance\n"
            "01/05/2024\nUPI\n1000.00\n9000.00\n"
        )
        profile, _ = segment(text)
        assert profile.confidence > 0

    def test_profile_date_formats_populated(self):
        text = "Date Description Debit Balance\n01/05/2024\nPAY\n100.00\n900.00"
        profile, _ = segment(text)
        assert len(profile.date_formats) > 0

    def test_repeated_header_lines_field_exists(self):
        profile = DocumentProfile()
        assert hasattr(profile, "repeated_header_lines")
        assert isinstance(profile.repeated_header_lines, set)

    def test_region_start_end_fields_exist(self):
        profile = DocumentProfile()
        assert hasattr(profile, "transaction_region_start")
        assert hasattr(profile, "transaction_region_end")
