from typing import Any

from pydantic import BaseModel


class ExtractionResult(BaseModel):
    """
    Standard output returned by every field extractor.
    """

    value: Any = None

    confidence: float = 0.0

    extractor: str

    source_text: str | None = None

    reasoning: str | None = None