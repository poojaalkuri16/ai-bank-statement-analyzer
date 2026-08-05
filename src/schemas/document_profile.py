from dataclasses import dataclass, field


@dataclass(slots=True)
class DocumentProfile:
    """
    Represents the engine's structural understanding of a financial document.

    Populated by DocumentUnderstandingEngine.  Consumed by
    TransactionSegmenter and FieldExtractionAgent.

    Region coordinates
    ------------------
    transaction_region_start : index of the first line that belongs to
        the transaction history section (0-based, inclusive).
        None means the engine could not locate the section start.

    transaction_region_end   : index of the last line that belongs to
        the transaction history section (0-based, inclusive).
        None means "end of document".

    repeated_header_lines    : set of stripped line strings that appear
        on every page (page headers / footers).  These are suppressed
        before segmentation regardless of where they appear in the text.
    """

    # ----------------------------------------------------------------
    # Identification (informational only — never used for routing)
    # ----------------------------------------------------------------
    document_type: str | None = None
    bank_name:     str | None = None

    # ----------------------------------------------------------------
    # Layout classification
    # ----------------------------------------------------------------
    layout_type: str | None = None   # table | block | same_line | mixed | unknown
    page_count:  int | None = None

    # ----------------------------------------------------------------
    # Transaction region
    # ----------------------------------------------------------------
    transaction_region_start: int | None = None   # inclusive line index
    transaction_region_end:   int | None = None   # inclusive line index

    # Pre-sliced clean text of the transaction region only.
    # When set, TransactionSegmenter uses this directly rather than
    # re-slicing by line index (which can produce wrong results if the
    # index spaces differ between the engine and the segmenter).
    transaction_region_text: str | None = None

    # Lines that repeat on every page and must always be suppressed
    repeated_header_lines: set = field(default_factory=set)

    # ----------------------------------------------------------------
    # Date / currency / amount metadata
    # ----------------------------------------------------------------
    date_formats:        list[str] = field(default_factory=list)
    currency:            str | None = None
    amount_style:        str | None = None
    has_running_balance: bool = False

    # ----------------------------------------------------------------
    # Text structure flags
    # ----------------------------------------------------------------
    multiline_descriptions: bool = False
    has_table_headers:      bool = False
    has_labeled_fields:     bool = False
    has_inline_dates:       bool = False

    # ----------------------------------------------------------------
    # Overall confidence (0–1)
    # ----------------------------------------------------------------
    confidence: float = 0.0
