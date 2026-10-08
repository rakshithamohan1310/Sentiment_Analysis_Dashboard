"""
Language detection module.

Rules
-----
- Uses langdetect (pip install langdetect) with a reproducible seed.
- Texts shorter than MIN_CHARS → "unknown" (too short to detect reliably).
- Any exception from the detector → "unknown" (never crashes the pipeline).
- If the raw record already has a non-empty, non-"unknown" language code it is
  returned unchanged; we never overwrite an explicit language tag.
- Language code is stored as ISO-639-1 (2-char), e.g. "en", "de", "fr".
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

MIN_CHARS: int = 20
UNKNOWN: str = "unknown"

_SEED: int = 42
_initialized: bool = False


def _init() -> None:
    global _initialized
    if _initialized:
        return
    try:
        from langdetect import DetectorFactory  # type: ignore[import]
        DetectorFactory.seed = _SEED
        _initialized = True
    except ImportError:
        logger.warning(
            "langdetect is not installed — language detection will return %r.", UNKNOWN
        )
        _initialized = True  # mark done so we don't retry on every call


def detect_language(text: str | None, existing: str | None = None) -> str:
    """
    Return a 2-char ISO-639-1 language code for *text*.

    Args:
        text:     The text to analyse. May be None or empty.
        existing: If already populated (e.g. from the collector), return it
                  unchanged so we never overwrite an explicit label.

    Returns:
        A language code string, or ``"unknown"``.
    """
    # Honour existing labels
    if existing and existing.strip() and existing.strip().lower() != UNKNOWN:
        return existing.strip().lower()[:8]

    clean = (text or "").strip()
    if len(clean) < MIN_CHARS:
        return UNKNOWN

    _init()
    try:
        from langdetect import detect  # type: ignore[import]
        lang = detect(clean)
        return (lang or UNKNOWN).lower()[:8]
    except Exception as exc:  # noqa: BLE001
        logger.debug("Language detection failed (%s chars): %s", len(clean), exc)
        return UNKNOWN
