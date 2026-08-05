from pathlib import Path

from src.tools import PDFReader


def run_tests():
    print("Running PDFReader tests...")

    reader = PDFReader()

    # --------------------------------------------------
    # Automatically find the first PDF in the data folder
    # --------------------------------------------------
    pdf_files = list(Path("data").glob("*.pdf"))

    if not pdf_files:
        print("Skipping valid PDF test. No PDF files found in the data folder.")
    else:
        pdf_path = str(pdf_files[0])

        result = reader.execute(pdf_path)

        assert isinstance(result, dict)

        assert "text" in result
        assert "page_count" in result
        assert "metadata" in result

        assert isinstance(result["text"], str)
        assert isinstance(result["page_count"], int)
        assert isinstance(result["metadata"], dict)

        assert result["page_count"] > 0

        print(f"✓ Successfully read: {pdf_path}")

    # --------------------------------------------------
    # Missing file
    # --------------------------------------------------
    try:
        reader.execute("does_not_exist.pdf")
        raise AssertionError(
            "Expected FileNotFoundError."
        )
    except FileNotFoundError:
        print("✓ Missing file test passed.")

    # --------------------------------------------------
    # Wrong extension
    # --------------------------------------------------
    txt_file = Path("dummy.txt")
    txt_file.write_text("dummy")

    try:
        reader.execute(str(txt_file))
        raise AssertionError(
            "Expected ValueError."
        )
    except ValueError:
        print("✓ Invalid extension test passed.")
    finally:
        if txt_file.exists():
            txt_file.unlink()

    print("All PDFReader tests passed!")


if __name__ == "__main__":
    run_tests()