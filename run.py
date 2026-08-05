import sys
from pathlib import Path

from src.agents.finance.finance_agent import FinanceAgent
from src.context.session_context import SessionContextManager


def print_header() -> None:
    print("━" * 50)
    print(" " * 15 + "Finance AI Agent")
    print("━" * 50)
    print()


def print_summary(
    agent: FinanceAgent,
    context: SessionContextManager,
) -> None:
    """
    Display a summary of the processed statement.
    """

    report = agent.get_report(context)
    report_path = agent.get_report_path(context)

    print()
    print("Report:")
    print(report_path)

    print()
    print("━" * 50)
    print("Statement Summary")
    print("━" * 50)

    print(f"Transactions      : {report.transaction_count}")

    period = (
        f"{report.statement_start_date or 'Unknown'}"
        f" → "
        f"{report.statement_end_date or 'Unknown'}"
    )

    print(f"Statement Period  : {period}")

    confidence = round(report.extraction_confidence * 100, 2)
    print(f"Confidence        : {confidence}%")

    print()
    print("━" * 50)


def interactive_loop(
    agent: FinanceAgent,
    context: SessionContextManager,
) -> None:
    """
    Interactive question-answering loop.
    """

    print()
    print("Finance Agent is ready.")
    print()
    print("Ask me anything about your statement.")
    print("Type 'exit' to quit.\n")

    while True:
        question = input("> ").strip()

        if question.lower() in {"exit", "quit"}:
            print("\nGoodbye!")
            break

        if not question:
            continue

        answer = agent.ask(
            context=context,
            question=question,
        )

        print(f"\n{answer}\n")


def main() -> None:
    """
    Application entry point.
    """

    if len(sys.argv) != 2:
        print_header()

        print("Usage:")
        print("    python run.py <path_to_pdf>")

        print()
        print("Example:")
        print("    python run.py data/sbi_statement.pdf")

        sys.exit(1)

    pdf_path = Path(sys.argv[1])

    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        sys.exit(1)

    print_header()

    agent = FinanceAgent()

    context = agent.process_statement(pdf_path)

    print_summary(
        agent=agent,
        context=context,
    )

    interactive_loop(
        agent=agent,
        context=context,
    )


if __name__ == "__main__":
    main()