class ProgressReporter:
    """
    Handles user-facing progress updates during statement processing.
    """

    def info(self, message: str) -> None:
        print(f"✓ {message}")