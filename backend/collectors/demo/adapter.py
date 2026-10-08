"""
Demo adapter – loads clearly labelled synthetic records from data/demo/*.json.

IMPORTANT:
  - source is always "demo"
  - metadata always contains {"synthetic": true}
  - These records are NEVER real user data
  - Never used in production results without explicit filtering

The adapter is always "available" (no credentials needed).
It filters records by the keywords in CollectorConfig if keywords are provided,
but never touches the network.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from backend.collectors.base import (
    CollectorConfig,
    RawRecord,
    ReviewCollector,
    hash_author_id,
    truncate_text,
)
from backend.config.settings import get_settings

logger = logging.getLogger(__name__)

# Default location of synthetic data files (relative to project root)
_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "demo"


class DemoCollector(ReviewCollector):
    """
    Reads pre-generated synthetic JSON records from data/demo/.
    Each file must be a JSON array of objects.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or _DEFAULT_DATA_DIR
        self._settings = get_settings()

    @property
    def source_name(self) -> str:
        return "demo"

    def is_available(self) -> bool:
        if not self._data_dir.exists():
            logger.warning(
                "[demo] Data directory %s not found — demo adapter skipped.",
                self._data_dir,
            )
            return False
        return True

    async def collect(self, config: CollectorConfig) -> AsyncIterator[RawRecord]:
        if not self.is_available():
            return

        salt = self._settings.author_hash_salt
        keywords_lower = [k.lower() for k in config.keywords] if config.keywords else []
        collected = 0

        json_files = sorted(self._data_dir.glob("*.json"))
        if not json_files:
            logger.warning("[demo] No JSON files found in %s", self._data_dir)
            return

        for json_file in json_files:
            if config.max_records and collected >= config.max_records:
                logger.info("[demo] Reached max_records=%d, stopping.", config.max_records)
                break

            try:
                with open(json_file, "r", encoding="utf-8") as fh:
                    records = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("[demo] Failed to load %s: %s", json_file, exc)
                continue

            if not isinstance(records, list):
                logger.warning("[demo] %s does not contain a JSON array, skipping.", json_file)
                continue

            for raw in records:
                if config.max_records and collected >= config.max_records:
                    break

                try:
                    record = self._parse_record(raw, salt, keywords_lower, config)
                    if record is None:
                        continue
                    collected += 1
                    yield record
                except Exception as exc:  # noqa: BLE001
                    logger.error("[demo] Skipping malformed record in %s: %s", json_file, exc)
                    continue

        logger.info("[demo] Yielded %d synthetic records from %s", collected, self._data_dir)

    def _parse_record(
        self,
        raw: dict,
        salt: str,
        keywords_lower: list[str],
        config: CollectorConfig,
    ) -> RawRecord | None:
        """Build a RawRecord from a raw dict. Returns None if filtered out."""
        record_id = str(raw.get("id", ""))
        if not record_id:
            raise ValueError("Record missing 'id' field")

        title = raw.get("title") or ""
        text = raw.get("text") or ""

        # Keyword filter (optional — if no keywords given, accept all)
        if keywords_lower:
            combined = f"{title} {text}".lower()
            if not any(kw in combined for kw in keywords_lower):
                return None

        # Date range filter
        pub_raw = raw.get("published_at")
        published_at: datetime | None = None
        if pub_raw:
            if isinstance(pub_raw, (int, float)):
                published_at = datetime.fromtimestamp(pub_raw, tz=timezone.utc)
            elif isinstance(pub_raw, str):
                from dateutil import parser as dp
                published_at = dp.parse(pub_raw)
                if not published_at.tzinfo:
                    published_at = published_at.replace(tzinfo=timezone.utc)

        if config.date_from and published_at and published_at < config.date_from:
            return None
        if config.date_to and published_at and published_at > config.date_to:
            return None

        author_raw = raw.get("author_id") or raw.get("author", "")
        author_hash = hash_author_id(str(author_raw), salt) if author_raw else None

        meta = dict(raw.get("metadata", {}))
        meta["synthetic"] = True  # always mark as synthetic

        return RawRecord(
            source="demo",
            source_record_id=record_id,
            source_url=raw.get("source_url"),
            published_at=published_at,
            author_id_hash=author_hash,
            title=title or None,
            text=truncate_text(text) if text else None,
            rating=raw.get("rating"),
            language=raw.get("language", config.language),
            metadata=meta,
            raw_payload=raw,
        )
