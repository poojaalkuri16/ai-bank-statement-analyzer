from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Transaction(BaseModel):
    """
    Represents a normalized bank transaction.

    Lifecycle:

        PDF Reader
            ↓
        Layout Analyzer
            ↓
        Transaction Segmenter
            ↓
        Field Extraction Agent
            ↓
        Normalizer
            ↓
        Validation Agent
            ↓
        Categorization Agent
            ↓
        Reporting / Insights
    """

    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    # ------------------------------------------------------------------
    # Core Transaction Information
    # ------------------------------------------------------------------

    transaction_date: date | None = Field(
        default=None,
        description="Normalized transaction date.",
    )

    description: str = Field(
        default="",
        description="Transaction narration extracted from the statement.",
    )

    amount: Decimal | None = Field(
        default=None,
        ge=0,
        description="Transaction amount.",
    )

    transaction_type: Literal["DEBIT", "CREDIT"] | None = Field(
        default=None,
        description="Debit or Credit transaction.",
    )

    balance: Decimal | None = Field(
        default=None,
        description="Running account balance after the transaction.",
    )

    # ------------------------------------------------------------------
    # Optional Metadata
    # ------------------------------------------------------------------

    mode: str | None = Field(
        default=None,
        description="Payment mode (UPI, IMPS, NEFT, RTGS, ATM, POS, CASH, CHEQUE, etc.).",
    )

    reference_number: str | None = Field(
        default=None,
        description="Bank transaction reference number if available.",
    )

    category: str | None = Field(
        default=None,
        description="Predicted transaction category.",
    )

    # ------------------------------------------------------------------
    # AI Metadata
    # ------------------------------------------------------------------

    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score assigned by the extraction/categorization agent.",
    )

    reasoning: str | None = Field(
        default=None,
        description="Reasoning behind the assigned category.",
    )

    # ------------------------------------------------------------------
    # Traceability
    # ------------------------------------------------------------------

    source_text: str | None = Field(
        default=None,
        description="Original transaction block extracted from the statement.",
    )