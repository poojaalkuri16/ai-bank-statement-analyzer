"""
generate_test_statements.py
============================
Generates 5 completely different synthetic bank statement PDFs for
testing / parsing purposes, using reportlab ONLY.

All PDFs are DIGITAL (vector text drawn by reportlab) - fully selectable,
NOT scanned images.

Run:
    python generate_test_statements.py

Output:
    sample_statements/
        sbi_statement.pdf
        hdfc_statement.pdf
        icici_statement.pdf
        axis_statement.pdf
        robustness_statement.pdf
"""

import os
import random
from datetime import date, timedelta

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

random.seed(42)  # reproducible output across runs

OUTPUT_DIR = "sample_statements"

STYLES = getSampleStyleSheet()

# ---------------------------------------------------------------------------
# The built-in Helvetica font has no glyph for the Indian Rupee sign (U+20B9)
# and renders it as a solid black box. If a Unicode-capable TTF font is
# available on the system, register it so the robustness-test statement can
# genuinely include the ₹ symbol. Otherwise fall back to the "Rs." prefix,
# which is an equally realistic real-world convention.
# ---------------------------------------------------------------------------
_UNICODE_FONT_NAME = "Helvetica"
_UNICODE_FONT_BOLD = "Helvetica-Bold"
_RUPEE_GLYPH_AVAILABLE = False
for _font_path in (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
):
    if os.path.exists(_font_path):
        pdfmetrics.registerFont(TTFont("DejaVuSans", _font_path))
        bold_path = _font_path.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")
        if os.path.exists(bold_path):
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", bold_path))
            _UNICODE_FONT_BOLD = "DejaVuSans-Bold"
        else:
            _UNICODE_FONT_BOLD = "DejaVuSans"
        _UNICODE_FONT_NAME = "DejaVuSans"
        _RUPEE_GLYPH_AVAILABLE = True
        break

RUPEE = "\u20b9" if _RUPEE_GLYPH_AVAILABLE else "Rs. "


# ===========================================================================
# 1. SHARED TRANSACTION DATA / GENERATION LOGIC
# ===========================================================================
# Every category the assignment requires (Salary, Food, Travel, Fuel,
# Shopping, Medical, EMI, Insurance, Bills, Entertainment, Refunds) is
# represented with realistic, bank-statement-style narrations.

CATEGORY_DESCRIPTIONS = {
    "Salary": [
        "SALARY CREDIT - INFOTECH SOLUTIONS PVT LTD",
        "SALARY CREDIT - NEXUS SYSTEMS LTD",
        "SALARY CREDIT - APR-MAY PAYROLL",
    ],
    "Food": [
        "SWIGGY BANGALORE",
        "ZOMATO ORDER",
        "POS 5412 RELIANCE FRESH",
        "UPI/BIGBASKET/PAYMENT",
        "UPI/SWIGGY/ORDERPAY",
    ],
    "Travel": [
        "IRCTC BOOKING",
        "UPI/OLACABS/TRIP",
        "UPI/UBER/RIDEPAYMENT",
        "MAKEMYTRIP FLIGHT BOOKING",
        "REDBUS TICKET BOOKING",
    ],
    "Fuel": [
        "HP PETROL PUMP",
        "INDIAN OIL FUEL STATION",
        "BPCL FUEL PAYMENT",
        "POS 7734 SHELL FUEL STATION",
    ],
    "Shopping": [
        "UPI/AMAZONPAY/XYZ",
        "FLIPKART ONLINE PAYMENT",
        "MYNTRA FASHION PURCHASE",
        "POS 1123 LIFESTYLE STORES",
    ],
    "Medical": [
        "APOLLO PHARMACY",
        "UPI/PHARMEASY/ORDER",
        "MEDPLUS HEALTH SERVICES",
        "POS 9021 FORTIS HOSPITAL",
    ],
    "EMI": [
        "EMI - HOME LOAN HDFC BANK",
        "EMI - CAR LOAN AXIS BANK",
        "EMI - PERSONAL LOAN ICICI",
        "EMI - CONSUMER DURABLE LOAN BAJAJ FINSERV",
    ],
    "Insurance": [
        "INSURANCE PREMIUM - LIC",
        "INSURANCE PREMIUM - HDFC ERGO",
        "UPI/POLICYBAZAAR/PREMIUM",
        "INSURANCE PREMIUM - ICICI PRUDENTIAL",
    ],
    "Bills": [
        "ELECTRICITY BILL BESCOM",
        "AIRTEL POSTPAID BILL",
        "ACT FIBERNET BROADBAND BILL",
        "UPI/BESCOM/ELECBILL",
    ],
    "Entertainment": [
        "NETFLIX INDIA",
        "SPOTIFY PREMIUM",
        "GOOGLE PLAY",
        "BOOKMYSHOW TICKET",
        "AMAZON PRIME VIDEO",
    ],
    "Refunds": [
        "REFUND - AMAZON RETURN",
        "REFUND - FLIPKART CANCELLED ORDER",
        "REFUND - IRCTC TICKET CANCELLATION",
        "REFUND - ZOMATO ORDER CANCELLED",
    ],
    "Transfer": [
        "NEFT TRANSFER TO RAHUL SHARMA",
        "IMPS-HDFC-RAHUL",
        "UPI/FRIEND/SETTLEMENT",
        "CASH DEPOSIT - BRANCH",
        "RTGS TRANSFER - VENDOR PAYMENT",
    ],
    "ATM": [
        "ATM WITHDRAWAL - MG ROAD BRANCH",
        "ATM CASH WITHDRAWAL - INDIRANAGAR",
        "ATM WITHDRAWAL - HSR LAYOUT",
    ],
    "Interest": [
        "INTEREST CREDIT - SAVINGS AC",
        "SB INTEREST CREDIT - QTR",
    ],
    "Rent": [
        "RENT PAYMENT - LANDLORD",
        "UPI/LANDLORD/RENTPAY",
    ],
}

# Which categories are credits, which are debits, and which can be either.
CREDIT_ONLY = {"Salary", "Interest", "Refunds"}
DEBIT_ONLY = {"Food", "Travel", "Fuel", "Shopping", "Medical", "EMI",
              "Insurance", "Bills", "Entertainment", "ATM", "Rent"}
EITHER = {"Transfer"}

# Realistic amount ranges (in Rupees) per category: (min, max)
AMOUNT_RANGES = {
    "Salary": (45000, 95000),
    "Food": (150, 1800),
    "Travel": (300, 6500),
    "Fuel": (500, 3000),
    "Shopping": (400, 12000),
    "Medical": (200, 5000),
    "EMI": (3500, 22000),
    "Insurance": (2000, 18000),
    "Bills": (400, 4500),
    "Entertainment": (99, 999),
    "Refunds": (200, 5000),
    "Transfer": (500, 20000),
    "ATM": (1000, 10000),
    "Interest": (80, 950),
    "Rent": (12000, 28000),
}


def _pick_amount(category):
    lo, hi = AMOUNT_RANGES[category]
    return round(random.uniform(lo, hi), 2)


def generate_transactions(count, start_date, opening_balance,
                           must_include=None, min_balance=5000):
    """
    Generates a mathematically-consistent list of transactions.

    Returns a list of dicts:
        {date, category, description, debit, credit, balance}

    The running balance is always: prev_balance - debit + credit,
    and is guaranteed to never fall below `min_balance` (debit amounts
    are clamped if necessary so statements stay realistic).
    """
    must_include = must_include or list(CATEGORY_DESCRIPTIONS.keys())
    all_categories = list(CATEGORY_DESCRIPTIONS.keys())

    # Build the sequence of categories: guarantee required ones appear,
    # then fill the remainder randomly (weighted toward everyday spends).
    sequence = list(must_include)
    everyday = ["Food", "Travel", "Fuel", "Shopping", "Entertainment",
                "Transfer", "Bills"]
    while len(sequence) < count:
        sequence.append(random.choice(everyday + all_categories))
    sequence = sequence[:count]
    random.shuffle(sequence)

    transactions = []
    balance = opening_balance
    current_date = start_date

    for i, category in enumerate(sequence):
        description = random.choice(CATEGORY_DESCRIPTIONS[category])
        amount = _pick_amount(category)

        if category in CREDIT_ONLY:
            is_credit = True
        elif category in DEBIT_ONLY:
            is_credit = False
        else:  # EITHER
            is_credit = random.random() < 0.4

        if is_credit:
            debit, credit = 0.0, amount
            balance += amount
        else:
            # clamp so the account never goes below the floor
            if balance - amount < min_balance:
                amount = max(50.0, round((balance - min_balance) * 0.5, 2))
            debit, credit = amount, 0.0
            balance -= amount

        # advance the date roughly evenly across the statement period,
        # keeping transactions in chronological order
        current_date = current_date + timedelta(
            days=random.choice([0, 0, 1, 1, 1, 2])
        )

        transactions.append({
            "date": current_date,
            "category": category,
            "description": description,
            "debit": round(debit, 2),
            "credit": round(credit, 2),
            "balance": round(balance, 2),
        })

    return transactions


def fmt_amount_plain(value):
    """1234.5 -> '1,234.50' ; 0 -> '' (blank, since many bank statements
    leave the non-applicable Debit/Credit cell empty)."""
    if not value:
        return ""
    return f"{value:,.2f}"


def fmt_amount_or_dash(value):
    if not value:
        return "-"
    return f"{value:,.2f}"


DATE_FORMATS = {
    "ddmmyyyy_slash": "%d/%m/%Y",
    "ddmmyyyy_dash": "%d-%m-%Y",
    "yyyymmdd_dash": "%Y-%m-%d",
}


def fmt_date(d, style):
    return d.strftime(DATE_FORMATS[style])


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


# ===========================================================================
# 2. PDF 1 - CLEAN SBI STATEMENT
# ===========================================================================

def build_sbi_statement(path):
    opening_balance = 82450.00
    txns = generate_transactions(
        20, date(2024, 5, 1), opening_balance,
        must_include=["Salary", "Food", "Food", "Travel", "Fuel", "Shopping",
                      "Medical", "EMI", "Insurance", "Bills", "Entertainment",
                      "Refunds", "Transfer", "ATM", "Interest", "Rent"],
    )
    closing_balance = txns[-1]["balance"]

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=16 * mm, rightMargin=16 * mm,
    )
    story = []

    title_style = ParagraphStyle(
        "SBITitle", parent=STYLES["Title"], fontName="Helvetica-Bold",
        fontSize=18, textColor=colors.HexColor("#003876"), spaceAfter=2,
    )
    sub_style = ParagraphStyle(
        "SBISub", parent=STYLES["Normal"], fontSize=9,
        textColor=colors.HexColor("#333333"), alignment=TA_CENTER,
    )

    story.append(Paragraph("STATE BANK OF INDIA", title_style))
    story.append(Paragraph(
        "Personal Banking Division &nbsp;|&nbsp; www.onlinesbi.sbi &nbsp;|&nbsp; "
        "Toll Free: 1800-425-3800", sub_style
    ))
    story.append(Spacer(1, 4 * mm))

    hr_style = TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 1.2, colors.HexColor("#003876")),
    ])
    story.append(Table([[""]], colWidths=[178 * mm], style=hr_style))
    story.append(Spacer(1, 4 * mm))

    header_style = ParagraphStyle(
        "SBIHeading", parent=STYLES["Heading2"], fontSize=12,
        textColor=colors.HexColor("#003876"),
    )
    story.append(Paragraph("Account Statement", header_style))
    story.append(Spacer(1, 2 * mm))

    info_data = [
        ["Customer Name:", "Pooja Nair", "Account Number:", "3849 1027 5610"],
        ["Branch:", "Koramangala, Bengaluru", "IFSC Code:", "SBIN0011452"],
        ["Statement Period:", "01/05/2024 to 31/05/2024", "Account Type:", "Savings Account"],
        ["Opening Balance:", f"Rs. {fmt_amount_plain(opening_balance)}",
         "Closing Balance:", f"Rs. {fmt_amount_plain(closing_balance)}"],
    ]
    info_table = Table(info_data, colWidths=[32 * mm, 57 * mm, 32 * mm, 57 * mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F2F6FA")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B7C9DA")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#B7C9DA")),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 6 * mm))

    # Transaction table
    table_data = [["Date", "Description", "Debit", "Credit", "Balance"]]
    for t in txns:
        table_data.append([
            fmt_date(t["date"], "ddmmyyyy_slash"),
            t["description"],
            fmt_amount_plain(t["debit"]),
            fmt_amount_plain(t["credit"]),
            fmt_amount_plain(t["balance"]),
        ])

    col_widths = [22 * mm, 76 * mm, 24 * mm, 24 * mm, 28 * mm]
    txn_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003876")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.3),
        ("ALIGN", (2, 0), (4, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B7C9DA")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F2F6FA")))
    txn_table.setStyle(TableStyle(style))
    story.append(txn_table)

    story.append(Spacer(1, 5 * mm))
    footer_style = ParagraphStyle(
        "SBIFooter", parent=STYLES["Normal"], fontSize=7.5,
        textColor=colors.HexColor("#666666"),
    )
    story.append(Paragraph(
        "This is a computer-generated statement and does not require a signature. "
        "For queries, contact your home branch.", footer_style
    ))

    doc.build(story)


# ===========================================================================
# 3. PDF 2 - HDFC STYLE STATEMENT (long narrations, some wrap 2 lines)
# ===========================================================================

def build_hdfc_statement(path):
    opening_balance = 154200.00
    txns = generate_transactions(
        25, date(2024, 6, 1), opening_balance,
        must_include=["Salary", "Food", "Food", "Travel", "Fuel", "Shopping",
                      "Shopping", "Medical", "EMI", "Insurance", "Bills",
                      "Entertainment", "Refunds", "Transfer", "Transfer",
                      "ATM", "Interest", "Rent"],
    )
    closing_balance = txns[-1]["balance"]

    # Long-form narrations (HDFC-style single-line strings that will wrap)
    long_narration_map = {
        "Food": "UPI-{d}-SWIGGYBANGALORE@YBL-YESB0000001-{ref}-ORDER PAYMENT VIA UPI FOOD DELIVERY",
        "Shopping": "UPI-{d}-AMAZONPAYINDIA@APL-ICIC0000001-{ref}-PAYMENT FOR ONLINE PURCHASE ORDER",
        "Travel": "UPI-{d}-IRCTCTRAVEL@SBI-SBIN0000001-{ref}-TRAIN TICKET BOOKING PAYMENT VIA UPI",
        "EMI": "ACH DEBIT-HDFCBANKLOAN EMI-{d}-LOAN ACCOUNT NUMBER ENDING {ref}-MONTHLY INSTALMENT",
        "Insurance": "ACH DEBIT-{d}-LIC OF INDIA PREMIUM PAYMENT-POLICY NUMBER ENDING {ref}",
    }

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        topMargin=16 * mm, bottomMargin=16 * mm,
        leftMargin=14 * mm, rightMargin=14 * mm,
    )
    story = []

    title_style = ParagraphStyle(
        "HDFCTitle", parent=STYLES["Title"], fontName="Helvetica-Bold",
        fontSize=17, textColor=colors.HexColor("#004C8F"), spaceAfter=0,
    )
    story.append(Paragraph("HDFC BANK", title_style))
    sub_style = ParagraphStyle(
        "HDFCSub", parent=STYLES["Normal"], fontSize=9,
        textColor=colors.HexColor("#ED232A"), fontName="Helvetica-Bold",
    )
    story.append(Paragraph("We understand your world | Account Statement", sub_style))
    story.append(Spacer(1, 4 * mm))

    info_data = [
        ["Account Holder", "Pooja Nair", "A/C No.", "50100234567890"],
        ["Statement Period", "01-Jun-2024 to 30-Jun-2024", "Branch", "Indiranagar, Bengaluru"],
        ["Account Type", "Savings", "IFSC", "HDFC0000234"],
        ["Opening Balance", f"INR {fmt_amount_plain(opening_balance)}",
         "Closing Balance", f"INR {fmt_amount_plain(closing_balance)}"],
    ]
    info_table = Table(info_data, colWidths=[30 * mm, 60 * mm, 25 * mm, 52 * mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#004C8F")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#B0C4D8")),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 5 * mm))

    cell_style = ParagraphStyle(
        "Cell", parent=STYLES["Normal"], fontSize=7.3, leading=9,
    )
    header_cell_style = ParagraphStyle(
        "HeaderCell", parent=STYLES["Normal"], fontSize=8,
        textColor=colors.white, fontName="Helvetica-Bold",
    )

    headers = ["Txn Date", "Value Date", "Narration", "Ref No",
               "Withdrawal", "Deposit", "Closing Balance"]
    table_data = [[Paragraph(h, header_cell_style) for h in headers]]

    for i, t in enumerate(txns):
        ref_no = f"{random.randint(100000000000, 999999999999)}"
        value_date = t["date"] + timedelta(days=random.choice([0, 0, 1]))

        if t["category"] in long_narration_map:
            narration = long_narration_map[t["category"]].format(
                d=fmt_date(t["date"], "ddmmyyyy_slash"), ref=ref_no[-6:]
            )
        else:
            narration = f"{t['description']}-{fmt_date(t['date'], 'ddmmyyyy_slash')}-REF{ref_no[-8:]}"

        table_data.append([
            Paragraph(fmt_date(t["date"], "ddmmyyyy_slash"), cell_style),
            Paragraph(fmt_date(value_date, "ddmmyyyy_slash"), cell_style),
            Paragraph(narration, cell_style),
            Paragraph(ref_no, cell_style),
            Paragraph(fmt_amount_plain(t["debit"]), cell_style),
            Paragraph(fmt_amount_plain(t["credit"]), cell_style),
            Paragraph(fmt_amount_plain(t["balance"]), cell_style),
        ])

    col_widths = [17 * mm, 17 * mm, 55 * mm, 22 * mm, 20 * mm, 20 * mm, 22 * mm]
    txn_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#004C8F")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B0C4D8")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN", (4, 1), (6, -1), "RIGHT"),
    ]
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F0F5FA")))
    txn_table.setStyle(TableStyle(style))
    story.append(txn_table)

    doc.build(story)


# ===========================================================================
# 4. PDF 3 - ICICI MULTI-PAGE STATEMENT (60 txns, exactly 3 pages,
#    header on every page + footer with page number & running balance)
# ===========================================================================

def build_icici_statement(path):
    opening_balance = 63500.00
    total_txns = 60
    rows_per_page = 20
    total_pages = 3

    must_include = ["Salary", "Salary", "Food", "Food", "Travel", "Travel",
                     "Fuel", "Fuel", "Shopping", "Shopping", "Medical",
                     "EMI", "EMI", "Insurance", "Bills", "Bills",
                     "Entertainment", "Entertainment", "Refunds", "Refunds",
                     "Transfer", "ATM", "Interest", "Rent"]
    icici_extra = ["UPI", "IMPS", "POS", "ATM", "Interest", "Refund",
                   "Amazon", "Flipkart", "Swiggy", "Zomato", "Netflix",
                   "Spotify", "Google Play"]
    # Fold the ICICI-specific keyword list into descriptions so the
    # required brand keywords are guaranteed to appear.
    icici_desc_map = {
        "UPI": "UPI/{name}/PAYMENT",
        "IMPS": "IMPS-ICIC-{name}",
        "POS": "POS PURCHASE {name}",
        "Amazon": "UPI/AMAZONPAY/{name}",
        "Flipkart": "FLIPKART ONLINE PAYMENT {name}",
        "Swiggy": "SWIGGY BANGALORE {name}",
        "Zomato": "ZOMATO ORDER {name}",
        "Netflix": "NETFLIX INDIA SUBSCRIPTION",
        "Spotify": "SPOTIFY PREMIUM SUBSCRIPTION",
        "Google Play": "GOOGLE PLAY STORE {name}",
        "Refund": "REFUND - {name} ORDER CANCELLED",
    }

    txns = generate_transactions(
        total_txns, date(2024, 4, 1), opening_balance,
        must_include=must_include,
    )
    closing_balance = txns[-1]["balance"]

    names = ["RAHUL", "PRIYA", "VENDOR4521", "STORE882", "MERCHANT117"]
    for t in txns:
        if random.random() < 0.35:
            keyword = random.choice(icici_extra)
            if keyword in icici_desc_map:
                t["description"] = icici_desc_map[keyword].format(
                    name=random.choice(names)
                )

    c = pdfcanvas.Canvas(path, pagesize=A4)
    width, height = A4
    margin = 14 * mm
    usable_width = width - 2 * margin

    col_headers = ["Date", "Description", "Debit", "Credit", "Balance"]
    col_widths = [22 * mm, 76 * mm, 24 * mm, 24 * mm, 24 * mm]

    def draw_header(page_num):
        c.setFillColor(colors.HexColor("#F37021"))
        c.rect(0, height - 22 * mm, width, 22 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(margin, height - 13 * mm, "ICICI BANK")
        c.setFont("Helvetica", 8.5)
        c.drawString(margin, height - 19 * mm, "Account Statement | Savings Account")

        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 9)
        y = height - 30 * mm
        c.drawString(margin, y, "Customer: Pooja Nair")
        c.drawString(margin + 65 * mm, y, "Account No: 601201567890")
        y -= 5 * mm
        c.setFont("Helvetica", 9)
        c.drawString(margin, y, "Statement Period: 01/04/2024 to 30/04/2024")
        c.drawString(margin + 65 * mm, y, "IFSC: ICIC0006012")
        y -= 5 * mm
        c.drawString(margin, y, f"Opening Balance: Rs. {fmt_amount_plain(opening_balance)}")
        c.drawString(margin + 65 * mm, y, f"Closing Balance: Rs. {fmt_amount_plain(closing_balance)}")

        y -= 8 * mm
        # table header row
        c.setFillColor(colors.HexColor("#F37021"))
        c.rect(margin, y - 6 * mm, usable_width, 6 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 8.5)
        x = margin
        aligns = ["left", "left", "right", "right", "right"]
        for h, w, al in zip(col_headers, col_widths, aligns):
            if al == "left":
                c.drawString(x + 2, y - 4.2 * mm, h)
            else:
                c.drawRightString(x + w - 2, y - 4.2 * mm, h)
            x += w
        return y - 6 * mm  # y position just below header row

    def draw_footer(page_num, running_balance):
        c.setFont("Helvetica", 7.5)
        c.setFillColor(colors.HexColor("#555555"))
        c.drawCentredString(width / 2, 10 * mm, f"Page {page_num} of {total_pages}")
        c.drawString(margin, 10 * mm,
                     f"Running Balance: Rs. {fmt_amount_plain(running_balance)}")
        c.line(margin, 13 * mm, width - margin, 13 * mm)

    row_height = 6.2 * mm
    idx = 0
    for page_num in range(1, total_pages + 1):
        y = draw_header(page_num)
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.black)

        page_rows = txns[idx: idx + rows_per_page]
        for r, t in enumerate(page_rows):
            row_y = y - (r + 1) * row_height
            if r % 2 == 0:
                c.setFillColor(colors.HexColor("#FDF1EA"))
                c.rect(margin, row_y - 1.5 * mm, usable_width, row_height,
                       fill=1, stroke=0)
            c.setFillColor(colors.black)
            x = margin
            values = [
                fmt_date(t["date"], "ddmmyyyy_slash"),
                t["description"][:44],
                fmt_amount_plain(t["debit"]),
                fmt_amount_plain(t["credit"]),
                fmt_amount_plain(t["balance"]),
            ]
            aligns = ["left", "left", "right", "right", "right"]
            for v, w, al in zip(values, col_widths, aligns):
                if al == "left":
                    c.drawString(x + 2, row_y + 0.8 * mm, v)
                else:
                    c.drawRightString(x + w - 2, row_y + 0.8 * mm, v)
                x += w

        idx += rows_per_page
        last_balance = page_rows[-1]["balance"] if page_rows else opening_balance
        draw_footer(page_num, last_balance)
        c.showPage()

    c.save()


# ===========================================================================
# 5. PDF 4 - AXIS BANK "DIFFICULT" STATEMENT
#    Column order: Date | Balance | Description | Debit | Credit
#    YYYY-MM-DD dates, blank debit/credit cells, long/comma-laden
#    descriptions, explicit opening & closing balance rows.
# ===========================================================================

def build_axis_statement(path):
    opening_balance = 121340.55
    txns = generate_transactions(
        30, date(2024, 3, 1), opening_balance,
        must_include=["Salary", "Food", "Travel", "Fuel", "Shopping",
                      "Medical", "EMI", "Insurance", "Bills", "Entertainment",
                      "Refunds", "Transfer", "ATM", "Interest", "Rent"],
    )
    closing_balance = txns[-1]["balance"]

    # Inject deliberately "difficult" long descriptions containing commas.
    difficult_descriptions = {
        "Shopping": "POS PURCHASE, AMAZON RETAIL INDIA PVT LTD, BENGALURU, KARNATAKA, CARD ENDING 4521",
        "EMI": "ACH DEBIT, AXIS BANK HOUSING FINANCE LTD, LOAN A/C NO 88452210, EMI FOR APRIL, INSTALLMENT NO 14",
        "Medical": "POS PURCHASE, FORTIS HOSPITALS LTD, BANNERGHATTA ROAD, BENGALURU, IN-PATIENT BILLING, INVOICE 22841",
        "Travel": "NEFT TRANSFER, MAKEMYTRIP INDIA PVT LTD, FLIGHT BOOKING, PNR NUMBER GT4521X, PASSENGER POOJA NAIR",
        "Transfer": "RTGS TRANSFER, VENDOR PAYMENT, SUPPLIER INVOICE NO 771245, GST INCLUDED, DUE ON RECEIPT",
    }
    for t in txns:
        if t["category"] in difficult_descriptions and random.random() < 0.7:
            t["description"] = difficult_descriptions[t["category"]]

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        topMargin=16 * mm, bottomMargin=16 * mm,
        leftMargin=14 * mm, rightMargin=14 * mm,
    )
    story = []

    title_style = ParagraphStyle(
        "AxisTitle", parent=STYLES["Title"], fontName="Helvetica-Bold",
        fontSize=17, textColor=colors.HexColor("#97144D"), spaceAfter=0,
    )
    story.append(Paragraph("AXIS BANK", title_style))
    sub_style = ParagraphStyle(
        "AxisSub", parent=STYLES["Normal"], fontSize=9,
        textColor=colors.HexColor("#333333"),
    )
    story.append(Paragraph("Statement of Account", sub_style))
    story.append(Spacer(1, 4 * mm))

    info_data = [
        ["Name", "Pooja Nair", "Account No.", "917010012345678"],
        ["Statement Period", "2024-03-01 to 2024-03-31", "Branch", "Whitefield, Bengaluru"],
        ["Account Type", "Savings", "IFSC", "UTIB0001452"],
    ]
    info_table = Table(info_data, colWidths=[32 * mm, 55 * mm, 27 * mm, 58 * mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#97144D")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#DAB6C6")),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 5 * mm))

    cell_style = ParagraphStyle("AxisCell", parent=STYLES["Normal"],
                                 fontSize=7.5, leading=9.5)
    header_cell_style = ParagraphStyle(
        "AxisHeaderCell", parent=STYLES["Normal"], fontSize=8,
        textColor=colors.white, fontName="Helvetica-Bold",
    )

    # NOTE the unusual column order required by the spec:
    # Date | Balance | Description | Debit | Credit
    headers = ["Date", "Balance", "Description", "Debit", "Credit"]
    table_data = [[Paragraph(h, header_cell_style) for h in headers]]

    # Opening balance row (no debit/credit, description explains the row)
    table_data.append([
        Paragraph(fmt_date(date(2024, 3, 1), "yyyymmdd_dash"), cell_style),
        Paragraph(fmt_amount_plain(opening_balance), cell_style),
        Paragraph("OPENING BALANCE", cell_style),
        Paragraph("", cell_style),
        Paragraph("", cell_style),
    ])

    for t in txns:
        table_data.append([
            Paragraph(fmt_date(t["date"], "yyyymmdd_dash"), cell_style),
            Paragraph(fmt_amount_plain(t["balance"]), cell_style),
            Paragraph(t["description"], cell_style),
            Paragraph(fmt_amount_plain(t["debit"]), cell_style),  # blank if 0
            Paragraph(fmt_amount_plain(t["credit"]), cell_style),  # blank if 0
        ])

    # Closing balance row
    table_data.append([
        Paragraph(fmt_date(date(2024, 3, 31), "yyyymmdd_dash"), cell_style),
        Paragraph(fmt_amount_plain(closing_balance), cell_style),
        Paragraph("CLOSING BALANCE", cell_style),
        Paragraph("", cell_style),
        Paragraph("", cell_style),
    ])

    col_widths = [22 * mm, 24 * mm, 82 * mm, 22 * mm, 22 * mm]
    txn_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#97144D")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DAB6C6")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("ALIGN", (3, 1), (4, -1), "RIGHT"),
        # highlight opening/closing balance rows
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F3D9E5")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F3D9E5")),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]
    for i in range(2, len(table_data) - 1):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FBF3F7")))
    txn_table.setStyle(TableStyle(style))
    story.append(txn_table)

    doc.build(story)


# ===========================================================================
# 6. PDF 5 - WORST-CASE ROBUSTNESS TEST STATEMENT
#    Mixed date formats, ₹ symbol, thousands separators, minus signs,
#    CR/DR suffixes, extra whitespace, merged descriptions.
# ===========================================================================

def build_robustness_statement(path):
    opening_balance = 98760.40
    txns = generate_transactions(
        40, date(2024, 7, 1), opening_balance,
        must_include=["Salary", "Food", "Food", "Travel", "Fuel", "Shopping",
                      "Shopping", "Medical", "EMI", "Insurance", "Bills",
                      "Entertainment", "Refunds", "Transfer", "Transfer",
                      "ATM", "Interest", "Rent"],
    )
    closing_balance = txns[-1]["balance"]

    date_format_cycle = ["ddmmyyyy_dash", "ddmmyyyy_slash", "yyyymmdd_dash"]

    def messy_amount(value, kind):
        """Formats an amount in one of several 'difficult' real-world
        styles: ₹ symbol, thousands separators, minus sign, CR/DR suffix,
        stray whitespace."""
        if not value:
            return ""
        style = random.choice(["plain", "rupee", "signed", "suffix", "spaced"])
        base = f"{value:,.2f}"
        if style == "plain":
            return base
        if style == "rupee":
            return f"{RUPEE}{base}"
        if style == "signed":
            return f"-{base}" if kind == "debit" else base
        if style == "suffix":
            return f"{base} {'DR' if kind == 'debit' else 'CR'}"
        if style == "spaced":
            return f"  {base}  "
        return base

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        topMargin=16 * mm, bottomMargin=16 * mm,
        leftMargin=13 * mm, rightMargin=13 * mm,
    )
    story = []

    title_style = ParagraphStyle(
        "RobustTitle", parent=STYLES["Title"], fontName=_UNICODE_FONT_BOLD,
        fontSize=16, textColor=colors.HexColor("#1B4332"), spaceAfter=0,
    )
    story.append(Paragraph("UNITED NATIONAL BANK", title_style))
    sub_style = ParagraphStyle(
        "RobustSub", parent=STYLES["Normal"], fontSize=9,
        textColor=colors.HexColor("#333333"), fontName=_UNICODE_FONT_NAME,
    )
    story.append(Paragraph("Combined Statement of Transactions", sub_style))
    story.append(Spacer(1, 4 * mm))

    info_data = [
        ["Account Holder :", " Pooja Nair  "],
        ["Account No.   :", "  004501122334455"],
        ["Statement Period :", "01-07-2024  to  31/07/2024"],
        ["Opening Balance :", f"{RUPEE} {opening_balance:,.2f}"],
        ["Closing Balance :", f"{RUPEE} {closing_balance:,.2f}"],
    ]
    info_table = Table(info_data, colWidths=[35 * mm, 100 * mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), _UNICODE_FONT_BOLD),
        ("FONTNAME", (1, 0), (1, -1), _UNICODE_FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 5 * mm))

    cell_style = ParagraphStyle("RobustCell", parent=STYLES["Normal"],
                                 fontSize=7.4, leading=9.2,
                                 fontName=_UNICODE_FONT_NAME)
    header_cell_style = ParagraphStyle(
        "RobustHeaderCell", parent=STYLES["Normal"], fontSize=8,
        textColor=colors.white, fontName=_UNICODE_FONT_BOLD,
    )

    headers = ["Transaction Date", "Narration", "Debit Amount",
               "Credit Amount", "Available Balance"]
    table_data = [[Paragraph(h, header_cell_style) for h in headers]]

    for i, t in enumerate(txns):
        date_style = date_format_cycle[i % len(date_format_cycle)]
        d_str = fmt_date(t["date"], date_style)

        narration = t["description"]
        # occasionally merge two descriptive fragments together with no
        # separator / extra spacing, simulating messy real-world exports
        if random.random() < 0.25:
            narration = f"{narration}   {random.choice(list(CATEGORY_DESCRIPTIONS.values()))[0]}"
        if random.random() < 0.2:
            narration = f"   {narration}  "  # stray leading/trailing spaces

        balance_str = f"{RUPEE}{t['balance']:,.2f}"

        table_data.append([
            Paragraph(d_str, cell_style),
            Paragraph(narration, cell_style),
            Paragraph(messy_amount(t["debit"], "debit"), cell_style),
            Paragraph(messy_amount(t["credit"], "credit"), cell_style),
            Paragraph(balance_str, cell_style),
        ])

    col_widths = [24 * mm, 70 * mm, 26 * mm, 26 * mm, 28 * mm]
    txn_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B4332")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B7CFC2")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN", (2, 1), (4, -1), "RIGHT"),
    ]
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F0F6F2")))
    txn_table.setStyle(TableStyle(style))
    story.append(txn_table)

    story.append(Spacer(1, 4 * mm))
    note_style = ParagraphStyle("RobustNote", parent=STYLES["Normal"],
                                 fontSize=7, textColor=colors.HexColor("#666666"),
                                 fontName=_UNICODE_FONT_NAME)
    story.append(Paragraph(
        "Note: Date formats, currency notation and amount styles vary within "
        "this statement intentionally to simulate real-world data inconsistencies.",
        note_style
    ))

    doc.build(story)


# ===========================================================================
# 7. MAIN
# ===========================================================================

def main():
    ensure_output_dir()

    builders = [
        ("sbi_statement.pdf", build_sbi_statement),
        ("hdfc_statement.pdf", build_hdfc_statement),
        ("icici_statement.pdf", build_icici_statement),
        ("axis_statement.pdf", build_axis_statement),
        ("robustness_statement.pdf", build_robustness_statement),
    ]

    for filename, builder in builders:
        out_path = os.path.join(OUTPUT_DIR, filename)
        builder(out_path)

    print("Generated:")
    print(f"{OUTPUT_DIR}/")
    for filename, _ in builders:
        print(f"    {filename}")


if __name__ == "__main__":
    main()
