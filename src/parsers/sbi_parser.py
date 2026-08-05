from src.parsers.statement_parser import StatementParser
from src.schemas.transaction import Transaction


class SBIParser(StatementParser):
    """
    Parser for SBI bank statements.
    """

    def parse(
        self,
        raw_text: str,
    ) -> list[Transaction]:

        raise NotImplementedError(
            "SBI parser has not been implemented yet."
        )