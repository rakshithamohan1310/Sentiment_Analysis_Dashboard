"""
base.py – Abstract collector interface + shared Pydantic schemas.

Every adapter (reddit, youtube, demo, …) must:
  1. Subclass ReviewCollector
  2. Implement collect() as an async generator yielding RawRecord instances
  3. Never raise from collect() — log and yield nothing on unrecoverable errors

The domain keyword groups / subreddit lists come entirely from YAML config.
No domain-specific strings live in this file.
"""
from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# ── Shared data contract ──────────────────────────────────────────────────────

class RawRecord(BaseModel):
    """
    Canonical in-memory representation of one collected review item.
    Passed from collector → orchestrator → DB layer.
    No raw author names, emails, or tokens — only the hashed author_id.
    """

    # Required
    source: str = Field(..., description="Adapter name, e.g. 'reddit', 'youtube', 'demo'")
    source_record_id: str = Field(..., description="Platform-assigned unique ID")

    # Optional provenance
    source_url: Optional[str] = None
    published_at: Optional[datetime] = None

    # Privacy-safe author (SHA-256 of salt+original_id, computed by adapter)
    author_id_hash: Optional[str] = None

    # Content
    title: Optional[str] = None
    text: Optional[str] = None
    rating: Optional[float] = None
    language: Optional[str] = None

    # Structured extras (e.g. {"subreddit": "…", "score": 42})
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Full raw API payload kept verbatim for auditability / reprocessing
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_record_id", "source", mode="before")
    @classmethod
    def must_be_non_empty(cls, v: Any) -> str:
        if not v or not str(v).strip():
            raise ValueError("source and source_record_id must be non-empty strings")
        return str(v).strip()

    @field_validator("published_at", mode="before")
    @classmethod
    def coerce_datetime(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, datetime):
            # Ensure tz-aware
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v, tz=timezone.utc)
        if isinstance(v, str):
            from dateutil import parser as dp
            return dp.parse(v)
        raise ValueError(f"Cannot coerce {type(v)} to datetime")

    model_config = {"arbitrary_types_allowed": True}


class CollectorConfig(BaseModel):
    """
    Runtime configuration passed to each collector.
    Populated from the domain YAML + request parameters.
    No domain knowledge here — it's all just lists of strings.
    """
    keywords: list[str] = Field(default_factory=list)
    subreddits: list[str] = Field(default_factory=list)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    max_records: int = 500
    language: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)


# ── Abstract base ─────────────────────────────────────────────────────────────

class ReviewCollector(ABC):
    """
    Abstract base class for all review collectors.

    Contract:
    - collect() is an async generator; it never raises — exceptions are caught
      internally and logged. Caller always gets a (possibly empty) iterator.
    - is_available() returns False if credentials are missing, so the
      orchestrator can skip the adapter without an error.
    - source_name must match the value stored in the `sources` DB table.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Machine-readable source identifier, e.g. 'reddit'."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """
        Return True if the adapter can actually run (credentials present, etc.).
        If False, the orchestrator skips this adapter gracefully.
        """
        ...

    @abstractmethod
    async def collect(self, config: CollectorConfig) -> AsyncIterator[RawRecord]:
        """
        Yield RawRecord instances one at a time.
        Must never raise — log errors and stop iteration instead.
        """
        ...
        # make mypy happy — subclasses use `yield` to become async generators
        # pragma: no cover
        if False:
            yield RawRecord(source="", source_record_id="")  # type: ignore[misc]


# ── Utility helpers shared by all adapters ────────────────────────────────────

def hash_author_id(raw_author_id: str, salt: str) -> str:
    """
    Return a hex-encoded SHA-256(salt + raw_author_id).
    The raw author identifier is never stored.
    """
    payload = f"{salt}{raw_author_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def truncate_text(text: str, max_chars: int = 40_000) -> str:
    """Guard against absurdly large text blobs consuming DB space."""
    if len(text) <= max_chars:
        return text
    logger.warning("Text truncated from %d to %d chars", len(text), max_chars)
    return text[:max_chars]
