"""
Entity extraction module — entirely config-driven gazetteer matching.

What this does
--------------
Scans cleaned review text + title for mentions of:
  - manufacturer   (e.g. "Tesla", "Hyundai")
  - vehicle_model  (e.g. "Model 3", "Ioniq 5")
  - model_year     (e.g. 2023)
  - vehicle_type   (e.g. "SUV", "Sedan")

All lists come from the ``gazetteer`` section of the domain YAML.
No manufacturer names, model names, or vehicle types are hard-coded here.

Matching rules
--------------
- Case-insensitive substring search for aliases and model strings.
- Manufacturer is detected first via its ``aliases`` list; model is then
  searched only under that manufacturer's ``models`` dict.
- vehicle_type is searched across all configured types.
- model_year is extracted with the configurable regex pattern.
- Only the *first* match for each field is returned.
- If a field is not found it is left as None — entities are NEVER guessed.

Returns
-------
EntityResult dataclass with fields:
  manufacturer, vehicle_model, model_year, vehicle_type
All fields are Optional[str | int]; None means "not found".
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class EntityResult:
    manufacturer:  Optional[str] = None
    vehicle_model: Optional[str] = None
    model_year:    Optional[int] = None
    vehicle_type:  Optional[str] = None


class EntityExtractor:
    """
    Gazetteer-based entity extractor.

    Parameters
    ----------
    gazetteer : The ``gazetteer`` dict from the domain YAML.
    """

    def __init__(self, gazetteer: dict[str, Any]) -> None:
        self._gazetteer = gazetteer

        # Pre-compile the model-year pattern
        raw_year = gazetteer.get("model_year_pattern", r"\b(20[1-3]\d)\b")
        try:
            self._year_re = re.compile(raw_year, re.IGNORECASE)
        except re.error as exc:
            logger.warning("Bad model_year_pattern %r: %s — using default.", raw_year, exc)
            self._year_re = re.compile(r"\b(20[1-3]\d)\b")

        # Build manufacturer → [(alias_lower, canonical_name), …]
        mfr_raw: dict[str, Any] = gazetteer.get("manufacturers", {})
        self._manufacturers: list[tuple[str, str]] = []
        # manufacturer → [(model_string_lower, canonical_model_name), …]
        self._models: dict[str, list[tuple[str, str]]] = {}

        for canonical_mfr, mfr_cfg in mfr_raw.items():
            if not isinstance(mfr_cfg, dict):
                continue
            for alias in mfr_cfg.get("aliases", []):
                self._manufacturers.append((alias.lower(), canonical_mfr))
            # models
            model_entries: list[tuple[str, str]] = []
            for canonical_model, model_strings in mfr_cfg.get("models", {}).items():
                for ms in model_strings:
                    model_entries.append((ms.lower(), canonical_model))
            # Sort longest first so more-specific strings match before substrings
            model_entries.sort(key=lambda x: len(x[0]), reverse=True)
            self._models[canonical_mfr] = model_entries

        # Sort manufacturer aliases longest-first too
        self._manufacturers.sort(key=lambda x: len(x[0]), reverse=True)

        # Vehicle types: [(type_string_lower, canonical_type), …]
        vtype_raw: dict[str, Any] = gazetteer.get("vehicle_types", {})
        self._vehicle_types: list[tuple[str, str]] = []
        for canonical_type, type_strings in vtype_raw.items():
            for ts in type_strings:
                self._vehicle_types.append((ts.lower(), canonical_type))
        self._vehicle_types.sort(key=lambda x: len(x[0]), reverse=True)

    # ── Public API ───────────────────────────────────────────

    def extract(self, text: str | None, title: str | None = None) -> EntityResult:
        """
        Extract entities from *title* + *text*.

        Never guesses — all None fields mean "not found in text".
        """
        combined = " ".join(filter(None, [title, text])).lower()

        if not combined.strip():
            return EntityResult()

        manufacturer  = self._find_manufacturer(combined)
        vehicle_model = self._find_model(combined, manufacturer) if manufacturer else None
        model_year    = self._find_year(combined)
        vehicle_type  = self._find_vehicle_type(combined)

        return EntityResult(
            manufacturer  = manufacturer,
            vehicle_model = vehicle_model,
            model_year    = model_year,
            vehicle_type  = vehicle_type,
        )

    # ── Private helpers ──────────────────────────────────────

    def _find_manufacturer(self, text_lower: str) -> Optional[str]:
        for alias, canonical in self._manufacturers:
            if alias in text_lower:
                return canonical
        return None

    def _find_model(self, text_lower: str, manufacturer: str) -> Optional[str]:
        model_entries = self._models.get(manufacturer, [])
        for model_str, canonical in model_entries:
            if model_str in text_lower:
                return canonical
        return None

    def _find_year(self, text_lower: str) -> Optional[int]:
        m = self._year_re.search(text_lower)
        if m:
            try:
                return int(m.group(1))
            except (IndexError, ValueError):
                return None
        return None

    def _find_vehicle_type(self, text_lower: str) -> Optional[str]:
        for type_str, canonical in self._vehicle_types:
            if type_str in text_lower:
                return canonical
        return None


# ── Module-level singleton factory ───────────────────────────────────────────

_EXTRACTOR: Optional[EntityExtractor] = None


def get_entity_extractor(
    gazetteer: dict[str, Any] | None = None,
) -> EntityExtractor:
    """
    Return the shared EntityExtractor for this process.

    Pass *gazetteer* explicitly to override the YAML default (tests).
    """
    global _EXTRACTOR

    if gazetteer is not None:
        return EntityExtractor(gazetteer)

    if _EXTRACTOR is not None:
        return _EXTRACTOR

    from backend.api.domain_config import _load_yaml, list_available_domains
    domains = list_available_domains()
    if not domains:
        logger.warning("No domain configs found — entity extractor will be empty.")
        raw: dict[str, Any] = {}
    else:
        raw = _load_yaml(domains[0]).get("gazetteer", {})

    _EXTRACTOR = EntityExtractor(raw)
    return _EXTRACTOR


def reset_entity_extractor() -> None:
    """Reset the cached singleton (tests only)."""
    global _EXTRACTOR
    _EXTRACTOR = None
