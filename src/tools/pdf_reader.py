from pathlib import Path
from typing import Any

import fitz


class PDFReader:
    """
    Reads a PDF file and extracts its contents.

    Responsibilities:
    - Validate the PDF path.
    - Read every page.
    - Extract text.
    - Extract metadata.
    - Return structured output.

    This class does NOT:
    - Parse transactions.
    - Categorize data.
    - Call LLMs.
    """

    def execute(self, pdf_path: str) -> dict[str, Any]:
        """
        Read a PDF and return its extracted contents.

        Args:
            pdf_path: Absolute or relative path to a PDF.

        Returns:
            Dictionary containing:
            - text
            - page_count
            - metadata

        Raises:
            FileNotFoundError
            ValueError
        """

        path = Path(pdf_path)

        if not path.exists():
            raise FileNotFoundError(
                f"PDF not found: {pdf_path}"
            )

        if path.suffix.lower() != ".pdf":
            raise ValueError(
                "Provided file is not a PDF."
            )

        document = fitz.open(path)

        text = []

        for page in document:
            text.append(page.get_text())

        result = {
            "text": "\n".join(text),
            "page_count": document.page_count,
            "metadata": document.metadata,
        }

        document.close()

        return result