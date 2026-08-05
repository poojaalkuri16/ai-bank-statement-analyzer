from abc import ABC, abstractmethod

from src.schemas.transaction import Transaction


class StatementParser(ABC):
    """
    Base class for all bank statement parsers.

    Responsibilities:
    - Convert raw extracted text into Transaction objects.

    This class does NOT:
    - Read PDFs
    - Categorize transactions
    - Generate reports
    """

    @abstractmethod
    def parse(
        self,
        raw_text: str,
    ) -> list[Transaction]:
        """
        Convert statement text into transactions.
        """
        raise NotImplementedError