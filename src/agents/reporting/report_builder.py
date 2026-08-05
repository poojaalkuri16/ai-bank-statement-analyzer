from datetime import date
from pathlib import Path

from src.schemas.financial_report import FinancialReport
from src.schemas.transaction import Transaction


class ReportBuilder:
    """
    Builds a FinancialReport from extracted transactions.
    """

    def build(
        self,
        statement_path: str | Path,
        bank_name: str,
        transactions: list[Transaction],
        confidence: float = 1.0,
    ) -> FinancialReport:

        statement_name = Path(statement_path).stem

        dates = [
            transaction.transaction_date
            for transaction in transactions
            if transaction.transaction_date is not None
        ]

        return FinancialReport(
            statement_name=statement_name,
            bank_name=bank_name,
            statement_start_date=min(dates) if dates else None,
            statement_end_date=max(dates) if dates else None,
            generated_at=date.today(),
            transaction_count=len(transactions),
            extraction_confidence=confidence,
            transactions=transactions,
        )