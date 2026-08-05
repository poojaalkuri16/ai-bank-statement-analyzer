from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ExtractionCandidate(BaseModel):
    """
    Represents a possible value extracted from a transaction block.

    Multiple candidates may exist before the extractor determines
    the most likely value.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    value: Decimal = Field(
        description="Detected monetary value."
    )

    raw_text: str = Field(
        description="Original matched text."
    )

    line_number: int = Field(
        description="Line where the value was detected."
    )

    confidence: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="Confidence assigned during ranking."
    )