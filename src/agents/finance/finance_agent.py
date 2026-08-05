from pathlib import Path

from src.agents.document.document_agent import DocumentAgent
from src.agents.qa.qa_agent import QAAgent
from src.agents.reporting.report_agent import ReportingAgent
from src.agents.reporting.report_writer import ReportWriter
from src.agents.validation.validation_agent import ValidationAgent
from src.context.session_context import SessionContextManager
from src.utils.progress_reporter import ProgressReporter


class FinanceAgent:
    """
    High-level AI agent responsible for processing financial statements
    and answering questions.
    """

    def __init__(self) -> None:

        self.document_agent = DocumentAgent()
        self.reporting_agent = ReportingAgent()
        self.validation_agent = ValidationAgent()
        self.report_writer = ReportWriter()

        self.qa_agent = QAAgent()

        self.progress = ProgressReporter()

    def process_statement(
        self,
        pdf_path: str | Path,
    ) -> SessionContextManager:

        pdf_path = Path(pdf_path)

        self.progress.info("Statement uploaded")
        self.progress.info("Reading PDF...")
        self.progress.info("Understanding statement structure...")
        self.progress.info("Extracting transactions...")
        self.progress.info("Building financial knowledge...")
        self.progress.info("Generating financial report...")

        context = SessionContextManager()

        self.document_agent.execute(
            pdf_path=pdf_path,
            context=context,
        )

        report = self.get_report(context)

        self.progress.info(
            "Generating AI financial insights..."
        )

        ai_summary = self.reporting_agent.generate(
            report,
        )

        self.progress.info(
            "Validating AI report..."
        )

        validation = self.validation_agent.validate(
            ai_summary,
        )

        report.metadata["ai_summary"] = ai_summary
        report.metadata["ai_validation"] = validation

        self.progress.info(
            "Saving final report..."
        )

        report_path = self.report_writer.write(
            report,
        )

        context.update_metadata(
            "financial_report",
            report,
        )

        context.update_metadata(
            "report_path",
            report_path,
        )

        self.progress.info(
            "Report generated successfully."
        )

        return context

    def get_report(
        self,
        context: SessionContextManager,
    ):
        return context.get_metadata(
            "financial_report",
        )

    def get_report_path(
        self,
        context: SessionContextManager,
    ):
        return context.get_metadata(
            "report_path",
        )

    def ask(
        self,
        context: SessionContextManager,
        question: str,
    ) -> str:
        """
        Answer a question about the processed statement.
        """

        report = self.get_report(
            context,
        )

        return self.qa_agent.answer(
            report=report,
            question=question,
        )