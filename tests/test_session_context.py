from src.context import SessionContextManager


def run_tests():
    print("Running SessionContextManager tests...")

    context = SessionContextManager()

    # Initial state
    assert context.get_active_file() is None
    assert context.get_uploaded_files() == []
    assert context.get_status() == SessionContextManager.STATUS_NOT_STARTED
    assert context.get_metadata() == {}

    # Add first file
    sbi = r"C:\Users\Dell\Finance\data\SBI.pdf"
    context.add_file(sbi)

    assert context.get_active_file() == sbi
    assert context.get_uploaded_files() == [sbi]

    # Duplicate upload should be ignored
    context.add_file(sbi)

    assert context.get_uploaded_files() == [sbi]

    # Add second file
    icici = r"C:\Users\Dell\Finance\data\ICICI.pdf"
    context.add_file(icici)

    assert context.get_uploaded_files() == [sbi, icici]
    assert context.get_active_file() == icici

    # Switch active file
    context.set_active_file(sbi)

    assert context.get_active_file() == sbi

    # Invalid active file
    try:
        context.set_active_file(
            r"C:\Users\Dell\Finance\data\HDFC.pdf"
        )
        raise AssertionError("Expected ValueError was not raised.")
    except ValueError:
        pass

    # Status
    context.update_status(SessionContextManager.STATUS_PARSING)

    assert (
        context.get_status()
        == SessionContextManager.STATUS_PARSING
    )

    # Metadata
    context.update_metadata("transaction_count", 120)

    assert (
        context.get_metadata()["transaction_count"]
        == 120
    )

    # Clear session
    context.clear_session()

    assert context.get_uploaded_files() == []
    assert context.get_active_file() is None
    assert (
        context.get_status()
        == SessionContextManager.STATUS_NOT_STARTED
    )
    assert context.get_metadata() == {}

    print("All SessionContextManager tests passed!")


if __name__ == "__main__":
    run_tests()