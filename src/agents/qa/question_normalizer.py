import re


class QuestionNormalizer:
    """
    Normalizes a raw user question into a clean, lowercase string
    suitable for intent detection.

    Steps:
      1. Strip leading/trailing whitespace.
      2. Lowercase.
      3. Collapse repeated whitespace.
      4. Remove trailing punctuation (?, !, .).
    """

    # Characters that are noise at the end of a question
    _TRAILING_PUNCT = re.compile(r"[?!.]+$")

    def normalize(self, question: str) -> str:
        """
        Return a cleaned, lowercase version of *question*.
        """

        text = question.strip()
        text = text.lower()
        text = re.sub(r"\s+", " ", text)
        text = self._TRAILING_PUNCT.sub("", text).strip()

        return text
