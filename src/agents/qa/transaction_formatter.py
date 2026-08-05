from collections.abc import Iterable

from src.agents.qa.formatters import fmt_date, fmt_inr
from src.schemas.transaction import Transaction


class TransactionFormatter:
    """
    Formats a list of transactions into a human-readable response.

    Each entry shows:
      <index>. <DD Mon YYYY>  [DEBIT / CREDIT]
         <description>
         <₹X,XX,XXX.XX>
    """

    def format(
        self,
        transactions: Iterable[Transaction],
        limit: int = 10,
    ) -> str:

        transactions = list(transactions)

        if not transactions:
            return "No matching transactions were found."

        lines: list[str] = []
        displayed = transactions[:limit]

        for index, txn in enumerate(displayed, start=1):
            date_str   = fmt_date(txn.transaction_date)
            desc       = txn.description or "No Description"
            amount_str = fmt_inr(txn.amount)
            txn_type   = (txn.transaction_type or "").upper()
            type_label = f"[{txn_type}]" if txn_type else ""

            lines.append(
                f"{index}. {date_str}  {type_label}\n"
                f"   {desc}\n"
                f"   {amount_str}"
            )

        if len(transactions) > limit:
            remaining = len(transactions) - limit
            lines.append("")
            lines.append(f"...and {remaining} more transaction(s).")

        return "\n\n".join(lines)
