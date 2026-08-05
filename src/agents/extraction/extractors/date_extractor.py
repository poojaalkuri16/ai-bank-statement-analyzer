from src.agents.extraction.shared.date_parser import parse_date
from src.schemas.extraction_result import ExtractionResult


class DateExtractor:
    """
    Extracts the transaction date from a transaction block.

    Delegates all date parsing to the centralised date_parser module so
    format support is maintained in one place.

    Supported formats (see date_parser.py for the full list):
        DD/MM/YYYY    DD-MM-YYYY    YYYY-MM-DD
        DD/MM/YY      DD-MM-YY
        DD MMM YYYY   DD MMM YY     MMM DD YYYY
    """

    def extract(self, transaction_block: str) -> ExtractionResult:

        # Try every line; return the first valid date found.
        for line in transaction_block.splitlines():
            parsed = parse_date(line.strip())
            if parsed is not None:
                return ExtractionResult(
                    value=parsed,
                    confidence=1.0,
                    extractor="DateExtractor",
                    source_text=line.strip(),
                    reasoning="Date extracted using centralised date_parser.",
                )

        return ExtractionResult(
            value=None,
            confidence=0.0,
            extractor="DateExtractor",
            source_text=None,
            reasoning="No valid date found in transaction block.",
        )
