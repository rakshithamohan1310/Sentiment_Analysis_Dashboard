"""
Loads domain YAML configs from config/domains/<name>.yaml and converts them
into CollectorConfig objects.

The core pipeline code never mentions "EV" or any domain name directly.
All domain knowledge lives in the YAML files.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from backend.collectors.base import CollectorConfig

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "domains"


def _flatten_keywords(keyword_groups: dict[str, list[str]]) -> list[str]:
    """Flatten grouped keywords into a deduplicated list."""
    seen: set[str] = set()
    result: list[str] = []
    for group_keywords in keyword_groups.values():
        for kw in group_keywords:
            if kw not in seen:
                seen.add(kw)
                result.append(kw)
    return result


@lru_cache(maxsize=32)
def _load_yaml(name: str) -> dict[str, Any]:
    path = _CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Domain config not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_collector_config(domain_name: str, overrides: dict[str, Any] | None = None) -> CollectorConfig:
    """
    Build a CollectorConfig from a domain YAML file, with optional overrides
    from a request body (keywords, date range, max_records, etc.).
    """
    raw = _load_yaml(domain_name)
    overrides = overrides or {}

    # Keywords: use override if provided, otherwise flatten from YAML groups
    keyword_groups: dict = raw.get("keyword_groups", {})
    base_keywords = _flatten_keywords(keyword_groups)
    keywords = overrides.get("keywords") or base_keywords

    subreddits = overrides.get("subreddits") or raw.get("subreddits", [])
    max_records = overrides.get("max_records") or raw.get("max_records_per_source", 500)
    language = overrides.get("language") or raw.get("language_filter")

    return CollectorConfig(
        keywords=keywords,
        subreddits=subreddits,
        date_from=overrides.get("date_from"),
        date_to=overrides.get("date_to"),
        max_records=max_records,
        language=language,
    )


def list_available_domains() -> list[str]:
    """Return domain config names available on disk."""
    if not _CONFIG_DIR.exists():
        return []
    return [p.stem for p in sorted(_CONFIG_DIR.glob("*.yaml"))]
