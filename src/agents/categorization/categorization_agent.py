from src.schemas.transaction import Transaction


class CategorizationAgent:
    """
    Assigns a spending category to each transaction.

    Rule-based categorization using merchant names and transaction keywords.

    Category order matters: the first matching category wins.
    Rules with specific multi-word keywords (e.g. "reliance fresh") are
    listed before rules with generic single-word keywords so they take
    precedence.

    Change log
    ----------
    - "premium" removed from Insurance — too broad; matches Spotify Premium,
      Amazon Prime, etc.  Insurance now requires genuine insurance keywords.
    - "airtel" added to Bills (postpaid / prepaid bills).
    - "amazon prime" added to Entertainment (before amazon → Shopping).
    - "air" removed from Travel — too broad, falsely catches "Airtel".
    - "apple" added to Entertainment (App Store, Apple Music, iCloud).
    - "prime video" already present in Entertainment.
    """

    CATEGORY_RULES = {
        # ----------------------------------------------------------------
        # Specific multi-word rules first to avoid premature single-word
        # matches.
        # ----------------------------------------------------------------

        "Food": (
            "swiggy",
            "zomato",
            "restaurant",
            "restaurants",
            "cafe",
            "coffee",
            "pizza",
            "burger",
            "dominos",
            "kfc",
            "mcdonald",
            "food",
            "meal",
            "dining",
        ),

        "Groceries": (
            "reliance fresh",
            "dmart",
            "bigbasket",
            "big basket",
            "supermarket",
            "grocery",
            "groceries",
            "more",
            "spar",
            "star bazaar",
        ),

        "Fuel": (
            "petrol",
            "diesel",
            "fuel",
            "fuel station",
            "indian oil",
            "hpcl",
            "bpcl",
            "shell",
        ),

        "Entertainment": (
            # Specific streaming / entertainment merchants listed before
            # generic shopping keywords so "amazon prime" fires here, not
            # in Shopping.
            "amazon prime",
            "google play",
            "netflix",
            "spotify",
            "prime video",
            "hotstar",
            "zee5",
            "sony liv",
            "bookmyshow",
            "apple music",
            "apple store",
            "movie",
            "movies",
            "cinema",
            "apple",
        ),

        # Refund must come before Shopping to catch "REFUND - AMAZON RETURN"
        # where "amazon" would otherwise match Shopping first.
        "Refund": (
            "refund",
            "returned",
            "return",
        ),

        "Shopping": (
            "amazon",
            "flipkart",
            "myntra",
            "ajio",
            "meesho",
            "lifestyle",
            "shop",
            "shopping",
            "purchase",
        ),

        "Healthcare": (
            "medplus",
            "apollo",
            "pharmacy",
            "medicine",
            "medical",
            "hospital",
            "clinic",
            "health",
        ),

        "Insurance": (
            # "premium" alone is too broad — require it alongside a stronger
            # insurance-specific term, or match by insurer name directly.
            "insurance",
            "lic",
            "policybazaar",
            "hdfc ergo",
            "prudential",
            "bajaj allianz",
            "tata aia",
            "max life",
            "policy",
        ),

        "Bills": (
            "airtel",          # postpaid / prepaid bills
            "jio",             # Jio recharge / bill
            "vodafone",
            "vi ",             # Vodafone Idea (space to avoid partial matches)
            "bsnl",
            "electricity",
            "water",
            "gas",
            "mobile",
            "recharge",
            "broadband",
            "wifi",
            "internet",
            "bescom",
            "tatapower",
            "tata power",
            "adani",
        ),

        "Travel": (
            "uber",
            "ola",
            "rapido",
            "makemytrip",
            "flight",
            "hotel",
            "irctc",
            "railway",
            "train",
            "travel",
            "redbus",
            "abhibus",
        ),

        "EMI": (
            "emi",
            "loan",
            "bajaj",
            "bajaj finserv",
            "consumer durable",
            "installment",
            "instalment",
        ),

        "Cash Withdrawal": (
            "atm",
            "cash withdrawal",
            "cash wd",
        ),

        "Interest": (
            "interest",
            "interest credit",
            "sb interest",
        ),

        # Rent must come before Transfer to catch "UPI/LANDLORD/RENTPAY"
        # where "upi" would otherwise match Transfer first.
        "Rent": (
            "rent",
            "landlord",
            "rentpay",
            "house rent",
            "rental",
        ),

        "Salary": (
            "salary",
            "salary credit",
            "payroll",
            "salary payment",
        ),

        "Transfer": (
            "upi",
            "imps",
            "neft",
            "rtgs",
            "fund transfer",
            "bank transfer",
        ),
    }

    DEFAULT_CATEGORY = "Others"

    def categorize(self, transaction: Transaction) -> Transaction:
        """Assign a category to a single transaction."""

        description = (transaction.description or "").lower().strip()
        transaction.category = self.DEFAULT_CATEGORY

        for category, keywords in self.CATEGORY_RULES.items():
            if any(keyword in description for keyword in keywords):
                transaction.category = category
                break

        return transaction

    def categorize_all(
        self,
        transactions: list[Transaction],
    ) -> list[Transaction]:
        """Categorize every transaction in *transactions*."""
        return [self.categorize(t) for t in transactions]
