import json
from pathlib import Path

from src.schemas.financial_report import FinancialReport


class ReportWriter:
    """
    Writes a FinancialReport to disk as JSON.
    """

    def __init__(self, reports_directory: str = "reports") -> None:
        self.reports_directory = Path(reports_directory)
        self.reports_directory.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        report: FinancialReport,
    ) -> Path:

        output_path = (
            self.reports_directory /
            f"{report.statement_name}.json"
        )

        with output_path.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                report.model_dump(
                    mode="json",
                ),
                file,
                indent=4,
                ensure_ascii=False,
            )

        return output_path