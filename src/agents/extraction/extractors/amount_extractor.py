import re
from decimal import Decimal

from src.agents.extraction.shared.money_candidate_detector import (
    MoneyCandidateDetector,
)
from src.schemas.extraction_candidate import ExtractionCandidate
from src.schemas.extraction_result import ExtractionResult


class AmountExtractor:
    """
    Selects the most likely transaction amount from detected monetary values.

    The returned amount is always non-negative.  Negative values from
    statements that use sign-based debit encoding are converted here;
    the caller (FieldExtractionAgent → legacy path) should also consult
    description keywords to determine transaction type.
    """

    def __init__(self):
        self.detector = MoneyCandidateDetector()

    def select_amount(
        self,
        candidates: list[ExtractionCandidate],
        transaction_block: str,
    ) -> ExtractionCandidate | None:

        if not candidates:
            return None

        lines = transaction_block.splitlines()
        best_candidate = None
        best_score = float("-inf")

        for candidate in candidates:
            score = 0.0
            line = lines[candidate.line_number - 1].upper()

            if "AMOUNT" in line:
                score += 0.50
            if re.search(r"\bDR\b|\bCR\b", line):
                score += 0.40
            if "DEBIT" in line or "CREDIT" in line:
                score += 0.30
            if "BALANCE" in line:
                score -= 0.60

            candidate.confidence = max(0.0, min(score, 1.0))

            if score > best_score:
                best_score = score
                best_candidate = candidate

        return best_candidate

    def extract(self, transaction_block: str) -> ExtractionResult:

        candidates = self.detector.detect(transaction_block)
        best = self.select_amount(candidates, transaction_block)

        if best is None:
            return ExtractionResult(
                value=None,
                confidence=0.0,
                extractor=self.__class__.__name__,
                reasoning="No monetary value detected.",
            )

        # Ensure the stored value is always non-negative
        value = abs(best.value)

        return ExtractionResult(
            value=value,
            confidence=best.confidence,
            extractor=self.__class__.__name__,
            source_text=best.raw_text,
            reasoning="Highest ranked monetary candidate (normalised to positive).",
        )
