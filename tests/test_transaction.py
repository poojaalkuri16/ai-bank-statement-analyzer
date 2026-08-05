from pydantic import ValidationError

from src.schemas import Transaction


def run_tests():
    print("Running Transaction schema tests...")

    # -------------------------
    # Valid Transaction
    # -------------------------
    transaction = Transaction(
        date="2026-07-22",
        description="SWIGGY INSTAMART",
        amount=542.50,
        transaction_type="DEBIT",
        balance=15432.20,
    )

    assert transaction.date == "2026-07-22"
    assert transaction.description == "SWIGGY INSTAMART"
    assert transaction.amount == 542.50
    assert transaction.transaction_type == "DEBIT"
    assert transaction.balance == 15432.20
    assert transaction.category is None
    assert transaction.confidence is None
    assert transaction.reasoning is None

    # -------------------------
    # JSON Serialization
    # -------------------------
    data = transaction.model_dump()

    assert isinstance(data, dict)
    assert data["description"] == "SWIGGY INSTAMART"

    # -------------------------
    # Invalid Transaction Type
    # -------------------------
    try:
        Transaction(
            date="2026-07-22",
            description="Amazon",
            amount=100,
            transaction_type="Debit",
        )
        raise AssertionError(
            "Expected ValidationError for transaction_type."
        )
    except ValidationError:
        pass

    # -------------------------
    # Invalid Confidence
    # -------------------------
    try:
        Transaction(
            date="2026-07-22",
            description="Amazon",
            amount=100,
            transaction_type="DEBIT",
            confidence=1.5,
        )
        raise AssertionError(
            "Expected ValidationError for confidence."
        )
    except ValidationError:
        pass

    # -------------------------
    # Invalid Amount
    # -------------------------
    try:
        Transaction(
            date="2026-07-22",
            description="Amazon",
            amount=-10,
            transaction_type="DEBIT",
        )
        raise AssertionError(
            "Expected ValidationError for amount."
        )
    except ValidationError:
        pass

    print("All Transaction schema tests passed!")


if __name__ == "__main__":
    run_tests()