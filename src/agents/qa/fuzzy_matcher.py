"""
FuzzyMatcher
============
Lightweight typo-tolerant entity resolution using Python's stdlib
difflib.SequenceMatcher.  No external dependencies required.

Design goals
------------
- Match obviously mis-spelled category names and merchant names to their
  canonical form (e.g. "entertainmnet" → "entertainment").
- Avoid false positives: threshold is set high enough that unrelated words
  never match (e.g. "fuel" does not match "food").
- Operate on individual tokens extracted from the question so that a typo
  in one word does not poison the whole query.
- Return (canonical_display_name, kind) where kind is "category" or
  "merchant", so the caller can route appropriately.

Algorithm
---------
1. Tokenise the normalised question into individual words and bigrams
   (two-word pairs).  Bigrams catch multi-word merchants like
   "reliance fresh" even when one word is mis-spelled.
2. Score each token against every known alias / merchant keyword using
   difflib.SequenceMatcher.ratio().
3. Accept the best match only when its score exceeds THRESHOLD.
4. Multi-word keys (e.g. "google play") require a bigram match so that
   single-word "play" never fuzzy-matches "google play".

Thresholds
----------
THRESHOLD = 0.75, MIN_TOKEN_LEN = 5 — empirically tuned:
  "shpooing"   → "shopping"      ratio = 0.75  ✓  (8 chars, passes)
  "swigy"      → "swiggy"        ratio = 0.91  ✓
  "amazn"      → "amazon"        ratio = 0.91  ✓
  "fuell"      → "fuel"          ratio = 0.89  ✓
  "flipkartt"  → "flipkart"      ratio = 0.94  ✓
  "grocerries" → "groceries"     ratio = 0.95  ✓
  "googel"     → "google"        ratio = 0.83  ✓ (via bigram "googel play")
  "soap"       → "shop"          ratio = 0.75  ✗ REJECTED (4 chars < MIN_TOKEN_LEN)
  "fuel"       → "food"          ratio = 0.25  ✗ (correctly rejected)
  "starbucks"  → "shopping"      ratio = 0.12  ✗ (correctly rejected)
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass


THRESHOLD = 0.75

# Minimum token length for fuzzy single-token matching.
# Tokens shorter than this have too many near-neighbours at the 0.75
# threshold and produce false positives (e.g. "soap" → "shop").
MIN_TOKEN_LEN = 5


@dataclass(frozen=True)
class FuzzyMatch:
    """Result of a successful fuzzy lookup."""
    display_name: str          # canonical display name (e.g. "Shopping")
    kind: str                  # "category" or "merchant"
    matched_alias: str         # the alias that was matched
    score: float               # similarity score 0–1


class FuzzyMatcher:
    """
    Matches a normalised question string against known category aliases
    and merchant keywords using fuzzy similarity.

    Usage
    -----
    matcher = FuzzyMatcher(category_aliases, known_merchants)
    result  = matcher.match(normalised_question)
    # result is FuzzyMatch | None
    """

    def __init__(
        self,
        category_aliases: dict[str, list[str]],
        known_merchants: dict[str, str],
    ) -> None:
        # ---------------------------------------------------------------
        # Build a flat lookup: alias_text → (display_name, kind)
        # ---------------------------------------------------------------
        self._single: dict[str, tuple[str, str]] = {}   # single-word aliases
        self._multi:  dict[str, tuple[str, str]] = {}   # multi-word aliases

        for category, aliases in category_aliases.items():
            for alias in aliases:
                bucket = self._multi if " " in alias else self._single
                bucket[alias] = (category, "category")

        for keyword, display in known_merchants.items():
            bucket = self._multi if " " in keyword else self._single
            bucket[keyword] = (display, "merchant")

        # Pre-sorted single-word candidates for get_close_matches
        self._single_keys: list[str] = sorted(self._single)

    def match(self, normalised: str) -> FuzzyMatch | None:
        """
        Return the best fuzzy match for any token in *normalised*, or None.

        Multi-word aliases are tried first (bigrams), then single tokens.
        """
        tokens = normalised.split()

        # ------------------------------------------------------------------
        # 1. Bigram pass — try adjacent word pairs against multi-word aliases
        # ------------------------------------------------------------------
        bigrams = [
            f"{tokens[i]} {tokens[i + 1]}"
            for i in range(len(tokens) - 1)
        ]
        for bigram in bigrams:
            result = self._best_match(bigram, self._multi)
            if result is not None:
                return result

        # ------------------------------------------------------------------
        # 2. Single-token pass — try individual words against single-word
        #    aliases.  Skip short tokens: they have too many near-neighbours
        #    at the chosen threshold and produce false positives
        #    (e.g. "soap" would match "shop" at ratio 0.75).
        # ------------------------------------------------------------------
        for token in tokens:
            if len(token) < MIN_TOKEN_LEN:
                continue
            result = self._best_match(token, self._single)
            if result is not None:
                return result

        return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _best_match(
        token: str,
        candidates: dict[str, tuple[str, str]],
    ) -> FuzzyMatch | None:
        """
        Return the highest-scoring match for *token* among *candidates*
        if it meets THRESHOLD, otherwise None.
        """
        best_score = 0.0
        best_alias = None

        for alias in candidates:
            score = difflib.SequenceMatcher(None, token, alias).ratio()
            if score > best_score:
                best_score = score
                best_alias = alias

        if best_score >= THRESHOLD and best_alias is not None:
            display_name, kind = candidates[best_alias]
            return FuzzyMatch(
                display_name=display_name,
                kind=kind,
                matched_alias=best_alias,
                score=best_score,
            )

        return None
