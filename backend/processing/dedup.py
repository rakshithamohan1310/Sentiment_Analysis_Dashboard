"""
Deduplication module.

Two strategies, applied in order
---------------------------------
1. Exact deduplication (always active)
   SHA-256 of the normalised text (lowercased, whitespace-collapsed).
   Two records with identical hashes share a ``duplicate_group_id`` equal to
   that hash.  The *earliest* record (lowest raw_review_id) is kept as
   canonical (is_duplicate=False); all later ones get is_duplicate=True.

2. Near-duplicate deduplication (optional, activated when
   ``near_duplicate_threshold > 0``)
   MinHash + Jaccard similarity via the datasketch library.  If datasketch is
   not installed the near-dup pass is silently skipped.

Contract
--------
- Original records are NEVER deleted.
- ``duplicate_group_id`` is the exact hash (64-char hex).  Canonical records
  (is_duplicate=False) also have duplicate_group_id set — it is the group ID
  regardless of whether the record is canonical or a duplicate.
- Running deduplication twice on the same set produces the same result
  (idempotent).
- Duplicate records are excluded from analytics endpoints by default.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Text normalisation ────────────────────────────────────────────────────────

_WS = re.compile(r"\s+")


def _normalise(text: str) -> str:
    """Lowercase + collapse whitespace for stable hashing."""
    return _WS.sub(" ", text.lower()).strip()


def compute_text_hash(text: str) -> str:
    """Return SHA-256 hex digest of the normalised text."""
    return hashlib.sha256(_normalise(text).encode("utf-8")).hexdigest()


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class DedupResult:
    text_hash:          str
    duplicate_group_id: str          # == text_hash for exact dups
    is_duplicate:       bool
    canonical_id:       Optional[int] = None   # raw_review_id of the canonical record


# ── Deduplicator ──────────────────────────────────────────────────────────────

@dataclass
class _Record:
    """Internal scratch record used during a single dedup pass."""
    raw_review_id: int
    text_hash:     str


class Deduplicator:
    """
    Stateful deduplicator for a batch of records.

    Usage (per processing run)::

        dedup = Deduplicator(near_dup_threshold=0.85)
        for raw_id, text in records:
            result = dedup.check(raw_id, text)
            # use result.is_duplicate, result.duplicate_group_id, …

    The instance accumulates seen hashes so it correctly identifies duplicates
    *within* the current batch even when previous batches already processed
    some records.  For cross-batch idempotency, the caller must pass
    ``existing_hashes`` (a set of text hashes already present in the
    ``reviews`` table) to the constructor.
    """

    def __init__(
        self,
        near_dup_threshold: float = 0.0,
        existing_hashes: dict[str, int] | None = None,
    ) -> None:
        """
        Parameters
        ----------
        near_dup_threshold : Jaccard threshold for MinHash near-dup detection.
            0.0 (default) disables near-dup detection.
        existing_hashes : mapping of text_hash → canonical raw_review_id for
            records already in the ``reviews`` table.  Passed in by the
            orchestrator so re-running is idempotent.
        """
        self._threshold = near_dup_threshold
        # hash → canonical raw_review_id
        self._seen: dict[str, int] = dict(existing_hashes or {})
        self._minhash_index: Optional[object] = None

        if near_dup_threshold > 0:
            self._init_minhash()

    # ── MinHash setup ────────────────────────────────────────

    def _init_minhash(self) -> None:
        try:
            from datasketch import MinHashLSH  # type: ignore[import]
            self._minhash_index = MinHashLSH(
                threshold=self._threshold,
                num_perm=128,
            )
            logger.debug("MinHash LSH index initialised (threshold=%.2f).", self._threshold)
        except ImportError:
            logger.info(
                "datasketch not installed — near-duplicate detection disabled."
            )
            self._threshold = 0.0

    def _make_minhash(self, text: str) -> Optional[object]:
        try:
            from datasketch import MinHash  # type: ignore[import]
            mh = MinHash(num_perm=128)
            for token in set(_normalise(text).split()):
                mh.update(token.encode("utf-8"))
            return mh
        except Exception as exc:  # noqa: BLE001
            logger.debug("MinHash creation failed: %s", exc)
            return None

    # ── Public API ───────────────────────────────────────────

    def check(self, raw_review_id: int, text: str) -> DedupResult:
        """
        Check whether *text* is an exact or near duplicate of a previously
        seen record.

        Returns a DedupResult with is_duplicate=True when a match is found,
        pointing to the canonical record's raw_review_id.
        """
        h = compute_text_hash(text)

        # ── 1. Exact duplicate ───────────────────────────────
        if h in self._seen:
            canonical_id = self._seen[h]
            return DedupResult(
                text_hash          = h,
                duplicate_group_id = h,
                is_duplicate       = (canonical_id != raw_review_id),
                canonical_id       = canonical_id,
            )

        # ── 2. Near-duplicate (optional) ─────────────────────
        if self._threshold > 0 and self._minhash_index is not None:
            mh = self._make_minhash(text)
            if mh is not None:
                try:
                    neighbours = self._minhash_index.query(mh)
                    if neighbours:
                        # Use the first neighbour's hash as the group ID
                        neighbour_hash = neighbours[0]
                        canonical_id   = self._seen.get(neighbour_hash, raw_review_id)
                        return DedupResult(
                            text_hash          = h,
                            duplicate_group_id = neighbour_hash,
                            is_duplicate       = True,
                            canonical_id       = canonical_id,
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("MinHash query failed: %s", exc)

                # Register this record in the MinHash index
                try:
                    self._minhash_index.insert(h, mh)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("MinHash insert failed: %s", exc)

        # ── New unique record ─────────────────────────────────
        self._seen[h] = raw_review_id
        return DedupResult(
            text_hash          = h,
            duplicate_group_id = h,
            is_duplicate       = False,
            canonical_id       = raw_review_id,
        )
