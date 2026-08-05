"""
document_agent.py
=================
Orchestrates the full bank-statement processing pipeline.

Pipeline
--------
PDF
  ↓ Raw Text Extraction
  ↓ Document Understanding    (DocumentUnderstandingEngine)
  ↓ Transaction Segmentation  (TransactionSegmenter)
  ↓ Field Extraction          (FieldExtractionAgent)
  ↓ Validation                (TransactionValidator)
  ↓ Categorization            (CategorizationAgent)
  ↓ Report                    (ReportBuilder / ReportWriter)
"""
from __future__ import annotations

import logging
from pathlib import Path

from src.agents.categorization.categorization_agent import CategorizationAgent
from src.agents.document.document_understanding_engine import (
    DocumentUnderstandingEngine,
)
from src.agents.extraction.field_extraction_agent import FieldExtractionAgent
from src.agents.reporting.report_builder import ReportBuilder
from src.agents.reporting.report_writer import ReportWriter
from src.agents.transactions.transaction_segmenter import TransactionSegmenter
from src.agents.validation.transaction_validator import TransactionValidator
from src.context.session_context import SessionContextManager
from src.tools.pdf_reader import PDFReader

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Debug logging helper
# ---------------------------------------------------------------------------

def _debug_segmentation(
    profile,
    blocks: list[str],
    *,
    start_pattern=None,
    enabled: bool = True,
) -> None:
    """
    Structured debug log.

    Format:
        Detected Layout
        ↓
        Detected Logical Regions
        ↓
        Detected Transaction Region
        ↓
        Ignored Metadata Summary
        ↓
        Ignored Header/Footer Summary
        ↓
        Discovered Transaction Start Pattern
        ↓
        Segmentation Confidence
        ↓
        Number of Transaction Blocks
        ↓
        ========== Block 1 ==========
        ...
        ========== Block N ==========
    """
    if not enabled:
        return

    print()
    print("╔" + "═" * 58 + "╗")
    print("║  DOCUMENT UNDERSTANDING — SEGMENTATION DEBUG LOG        ║")
    print("╚" + "═" * 58 + "╝")

    print("\nDetected Layout")
    print(f"  layout_type  : {profile.layout_type}")
    print(f"  date_formats : {profile.date_formats}")
    print(f"  amount_style : {profile.amount_style}")
    print(f"  currency     : {profile.currency}")

    print("\n↓\nDetected Logical Regions")
    print("  header / metadata / account-info / transactions / summary / footer")

    print("\n↓\nDetected Transaction Region")
    if profile.transaction_region_start is not None:
        print(
            f"  lines {profile.transaction_region_start} "
            f"→ {profile.transaction_region_end or 'end'}"
        )
    else:
        print("  WARNING: region not detected — full document used as fallback")
    if profile.repeated_header_lines:
        print(f"  repeated headers suppressed : {len(profile.repeated_header_lines)}")

    print("\n↓\nIgnored Metadata Summary")
    meta_before = profile.transaction_region_start or 0
    print(f"  lines before transaction region : {meta_before}")

    print("\n↓\nIgnored Header/Footer Summary")
    print(f"  page headers/footers suppressed : {len(profile.repeated_header_lines)}")
    if profile.repeated_header_lines:
        for h in sorted(profile.repeated_header_lines)[:5]:
            print(f"    - {h[:60]}")
        if len(profile.repeated_header_lines) > 5:
            print(f"    ... and {len(profile.repeated_header_lines)-5} more")

    print("\n↓\nDiscovered Transaction Start Pattern")
    if start_pattern is not None:
        print(f"  kind        : {start_pattern.kind}")
        print(f"  description : {start_pattern.description}")
    else:
        print("  (not available)")

    print(f"\n↓\nSegmentation Confidence : {profile.confidence:.2f}")

    print(f"\n↓\nNumber of Transaction Blocks : {len(blocks)}")

    if not blocks:
        print("  (no blocks produced)")
        print()
        return

    for i, block in enumerate(blocks, start=1):
        print(f"\n========== Block {i} ==========")
        print(block)

    print()


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

class DocumentAgent:
    """Entry point of the Finance AI Agent document processing pipeline."""

    def __init__(self, debug: bool = True) -> None:
        self.reader               = PDFReader()
        self.understanding_engine = DocumentUnderstandingEngine()
        self.segmenter            = TransactionSegmenter()
        self.field_extractor      = FieldExtractionAgent()
        self.validator            = TransactionValidator()
        self.categorization_agent = CategorizationAgent()
        self.report_builder       = ReportBuilder()
        self.report_writer        = ReportWriter()
        self._debug               = debug

    def execute(
        self,
        pdf_path: str | Path,
        context: SessionContextManager,
    ) -> SessionContextManager:

        pdf_path = Path(pdf_path)

        # ── 1. Read PDF ───────────────────────────────────────────────────
        raw_document = self.reader.execute(str(pdf_path))
        context.update_metadata("raw_document", raw_document)

        # ── 2. Document Understanding ─────────────────────────────────────
        profile = self.understanding_engine.analyze(
            raw_document["text"],
            raw_document["page_count"],
        )
        context.update_metadata("document_profile", profile)

        # ── 3. Transaction Segmentation ───────────────────────────────────
        transaction_blocks = self.segmenter.segment(
            raw_document["text"],
            profile,
        )
        context.update_metadata("transaction_blocks", transaction_blocks)

        # ── 4. Debug log ──────────────────────────────────────────────────
        _debug_segmentation(
            profile,
            transaction_blocks,
            start_pattern=self.segmenter.last_start_pattern,
            enabled=self._debug,
        )

        # ── 5. Field Extraction ───────────────────────────────────────────
        raw_transactions = []
        for block in transaction_blocks:
            try:
                txn = self.field_extractor.extract(block)
                raw_transactions.append(txn)
            except Exception as exc:
                logger.warning("Extraction failed: %s", exc)
                print(f"\nExtraction failed:\n{exc}\n")

        # ── 6. Validation ─────────────────────────────────────────────────
        transactions, skipped = self.validator.validate_all(raw_transactions)
        if skipped:
            print(
                f"\nValidation: {len(transactions)} accepted, "
                f"{len(skipped)} rejected.\n"
            )

        # ── 7. Categorization ─────────────────────────────────────────────
        transactions = self.categorization_agent.categorize_all(transactions)
        context.update_metadata("transactions", transactions)

        # ── 8. Report ─────────────────────────────────────────────────────
        report = self.report_builder.build(
            statement_path=pdf_path,
            bank_name=profile.bank_name,
            transactions=transactions,
            confidence=profile.confidence,
        )
        context.update_metadata("financial_report", report)

        report_path = self.report_writer.write(report)
        context.update_metadata("report_path", report_path)

        return context
