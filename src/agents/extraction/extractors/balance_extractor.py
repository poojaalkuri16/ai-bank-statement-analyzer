from src.agents.extraction.shared.money_candidate_detector import (
    MoneyCandidateDetector,
)
from src.schemas.extraction_candidate import ExtractionCandidate
from src.schemas.extraction_result import ExtractionResult


class BalanceExtractor:
    """
    Selects the most likely running balance from detected
    monetary values.
    """

    def __init__(self):

        self.detector = MoneyCandidateDetector()

    def select_balance(
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

            # Strong indicators
            if "BALANCE" in line:
                score += 0.70

            if "CLOSING BALANCE" in line:
                score += 0.80

            if "AVAILABLE BALANCE" in line:
                score += 0.80

            # Negative indicators
            if "AMOUNT" in line:
                score -= 0.50

            if "DR" in line or "CR" in line:
                score -= 0.30

            candidate.confidence = max(
                0.0,
                min(score, 1.0),
            )

            if score > best_score:
                best_score = score
                best_candidate = candidate

        return best_candidate

    def extract(
        self,
        transaction_block: str,
    ) -> ExtractionResult:

        candidates = self.detector.detect(
            transaction_block,
        )

        best = self.select_balance(
            candidates,
            transaction_block,
        )

        if best is None:

            return ExtractionResult(
                value=None,
                confidence=0.0,
                extractor=self.__class__.__name__,
                reasoning="No running balance detected.",
            )

        return ExtractionResult(
            value=best.value,
            confidence=best.confidence,
            extractor=self.__class__.__name__,
            source_text=best.raw_text,
            reasoning="Highest ranked balance candidate.",
        )