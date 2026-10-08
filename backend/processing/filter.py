"""
Quality filter module.

Responsibilities:
1. Reject records that cannot be processed (empty text, spam patterns, too short).
2. Compute a relevance_score based on keyword overlap with domain config keywords.
3. Apply a minimum relevance threshold (configurable, default 0.0 = accept all).

All keyword lists and spam patterns come from the domain YAML config.
No domain-specific strings live in this file.

Return value:
  - FilterResult.accepted = True  → record passes
  - FilterResult.accepted = False → record is rejected with reason stored in
    reject_reason (e.g. "empty_text", "too_short", "spam", "low_relevance")
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    accepted: bool
    reject_reason: str | None
    relevance_score: float


class QualityFilter:
    """
    Applies spam detection and relevance scoring to cleaned review text.

    Args:
        domain_config: The full parsed YAML dict for a domain (keyword_groups,
                       quality sections, etc.).
        min_relevance_score: Override the threshold from config (0.0 = off).
    """

    def __init__(
        self,
        domain_config: dict[str, Any],
        min_relevance_score: float | None = None,
    ) -> None:
        quality = domain_config.get("quality", {})

        self._min_text_length: int = quality.get("min_text_length", 20)

        # Compile spam patterns from config
        raw_spam = quality.get("spam_patterns", [])
        self._spam_patterns: list[re.Pattern] = []
        for p in raw_spam:
            try:
                self._spam_patterns.append(re.compile(p, re.IGNORECASE))
            except re.error as exc:
                logger.warning("Bad spam pattern %r: %s", p, exc)

        # Relevance threshold
        cfg_threshold = quality.get("min_relevance_score", 0.0)
        self._min_relevance: float = (
            min_relevance_score if min_relevance_score is not None else cfg_threshold
        )

        # Flat list of all keywords for relevance scoring
        kg = domain_config.get("keyword_groups", {})
        self._keywords: list[str] = [
            kw.lower()
            for group in kg.values()
            for kw in group
        ]

    def filter(self, text: str | None, title: str | None = None) -> FilterResult:
        """
        Evaluate a single record.

        Args:
            text:  Cleaned review text (output of cleaner.clean_text).
            title: Optional cleaned title.

        Returns:
            FilterResult with accepted flag, optional reject_reason, and
            relevance_score.
        """
        combined = " ".join(filter(None, [title, text])).strip()

        # 1. Empty text
        if not combined:
            return FilterResult(accepted=False, reject_reason="empty_text", relevance_score=0.0)

        # 2. Too short after cleaning
        if len(combined) < self._min_text_length:
            return FilterResult(accepted=False, reject_reason="too_short", relevance_score=0.0)

        # 3. Spam / ad patterns
        for pattern in self._spam_patterns:
            if pattern.search(combined):
                return FilterResult(accepted=False, reject_reason="spam", relevance_score=0.0)

        # 4. Relevance score
        relevance = self._compute_relevance(combined)
        if relevance < self._min_relevance:
            return FilterResult(
                accepted=False,
                reject_reason="low_relevance",
                relevance_score=round(relevance, 4),
            )

        return FilterResult(accepted=True, reject_reason=None, relevance_score=round(relevance, 4))

    def _compute_relevance(self, text: str) -> float:
        """
        Keyword-overlap relevance score in [0, 1].

        Score = (number of distinct keywords found in text) / total keywords.
        Returns 1.0 if there are no keywords defined (don't penalise absent config).
        """
        if not self._keywords:
            return 1.0
        text_lower = text.lower()
        hits = sum(1 for kw in self._keywords if kw in text_lower)
        return hits / len(self._keywords)
