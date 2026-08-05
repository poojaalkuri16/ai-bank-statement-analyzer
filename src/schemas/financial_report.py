from datetime import date

from pydantic import BaseModel, Field

from src.schemas.transaction import Transaction


class FinancialReport(BaseModel):
    """
    Represents the complete financial understanding of a bank statement.
    """

    statement_name: str

    bank_name: str

    statement_start_date: date | None = None

    statement_end_date: date | None = None

    generated_at: date

    transaction_count: int = 0

    extraction_confidence: float = 0.0

    transactions: list[Transaction] = Field(default_factory=list)

    metadata: dict = Field(default_factory=dict)