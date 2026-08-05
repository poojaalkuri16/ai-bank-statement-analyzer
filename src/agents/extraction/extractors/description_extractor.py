import re

from src.schemas.extraction_result import ExtractionResult


# ---------------------------------------------------------------------------
# Boilerplate phrases that must never appear in a narration
# ---------------------------------------------------------------------------
_BOILERPLATE_RE = re.compile(
    r"statement of account"
    r"|statement continued"
    r"|page \d+\s+of\s+\d+"
    r"|customer\s+name"
    r"|opening\s+balance"
    r"|closing\s+balance"
    r"|this is a system generated"
    r"|generated statement"
    r"|authorised\s+signatory"
    r"|branch\s+name"
    r"|account\s+number"
    r"|ifsc\s*code"
    r"|micr\s*code"
    r"|swift\s*code"
    r"|a/c\s*no"
    r"|acc(?:ount)?\s*no"
    r"|mobile\s*(?:no|number)"
    r"|email\s*(?:id|address)?"
    r"|nominee"
    r"|pan\s*(?:no|number|card)"
    r"|cif\s*(?:no|number)?"
    r"|rs\.\s*\d"
    r"|inr\s*\d"
    r"|date\s+description\s+debit"
    r"|date\s+description\s+credit"
    r"|date\s+particulars"
    r"|date\s+narration"
    r"|txn\s+date\s+value",
    re.IGNORECASE,
)


class DescriptionExtractor:
    """
    Extracts the transaction narration from a transaction block.

    Intentionally ignores:
    - Dates
    - Numeric amounts (with or without DR/CR markers)
    - Field labels (Txn Date:, Amount:, Balance:, Particulars:)
    - Boilerplate / header / footer lines

    Multi-line narrations (e.g. "INDIAN OIL" on one line and "FUEL STATION"
    on the next) are joined into a single space-separated string.
    """

    DATE_PATTERN = re.compile(
        r"\b(\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4}|\d{4}-\d{2}-\d{2})\b"
    )

    # Matches lines that are purely numeric / amount-like (with optional
    # DR/CR suffix or parenthesised Dr/Cr)
    AMOUNT_PATTERN = re.compile(
        r"^[-₹]?\s*\d[\d,]*\.?\d*"
        r"(\s*\(?\s*(?:DR|CR|Dr|Cr|Debit|Credit)\s*\)?)?$",
        re.IGNORECASE,
    )

    # Field label lines — skip entirely
    LABEL_PATTERN = re.compile(
        r"^(Txn\s*Date|Date|Amount|Balance|Particulars?)\s*:?$",
        re.IGNORECASE,
    )

    # Label lines that carry the value on the same line — skip the label
    # but potentially keep the value portion
    LABEL_WITH_VALUE_RE = re.compile(
        r"^(Txn\s*Date|Date|Amount|Balance|Particulars?)\s*:\s*(.+)$",
        re.IGNORECASE,
    )

    def extract(self, transaction_block: str) -> ExtractionResult:

        lines: list[str] = []

        for raw_line in transaction_block.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            # Skip boilerplate
            if _BOILERPLATE_RE.search(line):
                continue

            # Skip pure date lines
            if self.DATE_PATTERN.fullmatch(line):
                continue

            # Skip bare field labels (no value after the colon)
            if self.LABEL_PATTERN.match(line):
                continue

            # For "Particulars: <value>" lines, keep only the value part
            m = self.LABEL_WITH_VALUE_RE.match(line)
            if m:
                label = m.group(1).strip().lower()
                value = m.group(2).strip()
                # Only the Particulars value is a description; others skip
                if label.startswith("particular"):
                    if value and not self.AMOUNT_PATTERN.match(value):
                        lines.append(value)
                continue

            # Skip purely numeric / amount lines
            if self.AMOUNT_PATTERN.match(line):
                continue

            lines.append(line)

        description = re.sub(r"\s+", " ", " ".join(lines)).strip()

        if not description:
            return ExtractionResult(
                value=None,
                confidence=0.0,
                extractor=self.__class__.__name__,
                reasoning="No transaction description found.",
            )

        return ExtractionResult(
            value=description,
            confidence=1.0,
            extractor=self.__class__.__name__,
            source_text=description,
            reasoning="Transaction description extracted successfully.",
        )
