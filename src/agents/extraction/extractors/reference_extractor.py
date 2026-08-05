class ReferenceExtractor:
    """
    Responsible only for extracting transaction reference numbers,
    UTRs, cheque numbers, RRNs, etc.
    """

    def extract(
        self,
        transaction_block: str,
    ):
        raise NotImplementedError