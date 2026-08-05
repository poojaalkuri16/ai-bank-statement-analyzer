"""
Validation Agent

Performs deterministic validation of the AI-generated financial narrative.

The Validation Agent does not evaluate financial correctness.
Its responsibility is to ensure that the generated report is
complete, well-structured, and suitable for presentation.
"""


class ValidationAgent:
    """
    Validates AI-generated financial narratives.
    """

    REQUIRED_HEADINGS = (
        "Executive Summary",
        "Spending Analysis",
        "Income Analysis",
        "Recurring Payments",
        "Financial Health",
        "Recommendations",
    )

    FORBIDDEN_PHRASES = (
        "as an ai language model",
        "i cannot determine",
        "i don't know",
        "lorem ipsum",
    )

    MINIMUM_LENGTH = 200

    def validate(
        self,
        report: str,
    ) -> dict:

        warnings: list[str] = []

        if not report.strip():
            warnings.append("Generated report is empty.")

        if len(report.strip()) < self.MINIMUM_LENGTH:
            warnings.append(
                "Generated report is shorter than expected."
            )

        lower = report.lower()

        for heading in self.REQUIRED_HEADINGS:

            if heading.lower() not in lower:
                warnings.append(
                    f"Missing section: {heading}"
                )

        for phrase in self.FORBIDDEN_PHRASES:

            if phrase in lower:
                warnings.append(
                    f"Forbidden phrase detected: '{phrase}'"
                )

        if "```" in report:
            warnings.append(
                "Markdown code block detected."
            )

        return {
            "passed": len(warnings) == 0,
            "warnings": warnings,
        }