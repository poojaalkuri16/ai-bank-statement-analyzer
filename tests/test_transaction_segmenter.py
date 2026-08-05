from src.agents.transactions.transaction_segmenter import TransactionSegmenter
from src.schemas.document_profile import DocumentProfile


def test_segment_table_filters_statement_header_and_footer():
    raw_text = """STATE BANK OF INDIA PERSONAL BANKING DIVISION
ACCOUNT STATEMENT CUSTOMER NAME: POOJA NAIR
01/05/2024
UPI/LANDLORD/RENTPAY
24,950.89
57,499.11
12/05/2024
SALARY CREDIT - INFOTECH SOLUTIONS PVT LTD
63,509.05
86,410.04
This is a computer-generated statement and does not require a signature.
"""

    profile = DocumentProfile(layout_type="table")
    segmenter = TransactionSegmenter()

    blocks = segmenter.segment(raw_text, profile)

    assert len(blocks) == 2
    assert "UPI/LANDLORD/RENTPAY" in blocks[0]
    assert "SALARY CREDIT - INFOTECH SOLUTIONS PVT LTD" in blocks[1]
    assert "ACCOUNT STATEMENT" not in "\n".join(blocks)
    assert "computer-generated statement" not in "\n".join(blocks)
