"""
Text cleaning and normalisation module.

Transformations applied (in order)
------------------------------------
1.  Strip HTML tags            (bleach; regex fallback if not installed).
2.  Strip Markdown code blocks ``…`` and ```…```.
3.  Convert Markdown links [text](url) → keep anchor text only.
4.  Strip Markdown heading markers (##, ###, …).
5.  Strip Markdown bold/italic markers (**text**, *text*, __text__, _text_).
6.  Remove quoted lines (> quote).
7.  Remove URLs (http/https/ftp/www).
8.  Mask e-mail addresses   → <EMAIL>
9.  Mask phone numbers       → <PHONE>
10. Unicode normalisation (NFKC).
11. Collapse whitespace.

Emojis and numbers are kept — they carry sentiment signal.
Nothing is written back to raw_reviews; cleaned text goes to reviews.review_text.
"""
from __future__ import annotations

import re
import unicodedata

# ── Compiled regexes (module-level, compiled once) ──────────────────────────

_RE_URL          = re.compile(r"(?:https?://|ftp://|www\.)\S+", re.IGNORECASE)
_RE_EMAIL        = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE
)
_RE_PHONE        = re.compile(
    r"""
    (?:
        \+?1?[\s\-.]?
        \(?\d{3}\)?
        [\s\-.]?
        \d{3}
        [\s\-.]?
        \d{4}
      |
        \+\d{7,15}
    )
    """,
    re.VERBOSE,
)
_RE_MD_CODE      = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)
_RE_MD_LINK      = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_RE_MD_HEADING   = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_RE_MD_EMPHASIS  = re.compile(r"(\*{1,3}|_{1,3})(.*?)\1", re.DOTALL)
_RE_QUOTED       = re.compile(r"^>+.*$", re.MULTILINE)
_RE_WHITESPACE   = re.compile(r"[ \t\r]+")
_RE_MULTILINE    = re.compile(r"\n{3,}")
_RE_HTML_TAG     = re.compile(r"<[^>]+>")   # fallback if bleach not installed


def clean_text(text: str | None) -> str:
    """
    Apply the full cleaning pipeline and return the result.
    Returns ``""`` for None/empty input.
    """
    if not text:
        return ""

    result: str = text

    # 1. Strip HTML
    try:
        import bleach  # type: ignore[import]
        result = bleach.clean(result, tags=[], strip=True)
    except ImportError:
        result = _RE_HTML_TAG.sub(" ", result)

    # 2. Markdown code blocks
    result = _RE_MD_CODE.sub(" ", result)

    # 3. Markdown links → anchor text
    result = _RE_MD_LINK.sub(r"\1", result)

    # 4. Markdown headings
    result = _RE_MD_HEADING.sub("", result)

    # 5. Markdown bold/italic → inner text
    result = _RE_MD_EMPHASIS.sub(r"\2", result)

    # 6. Quoted lines
    result = _RE_QUOTED.sub("", result)

    # 7. URLs
    result = _RE_URL.sub(" ", result)

    # 8. E-mails
    result = _RE_EMAIL.sub("<EMAIL>", result)

    # 9. Phone numbers
    result = _RE_PHONE.sub("<PHONE>", result)

    # 10. Unicode normalisation
    result = unicodedata.normalize("NFKC", result)

    # 11. Whitespace
    result = _RE_WHITESPACE.sub(" ", result)
    result = _RE_MULTILINE.sub("\n\n", result)
    result = result.strip()

    return result


def compute_completeness_score(title: str | None, text: str | None) -> float:
    """
    Heuristic completeness score in [0.0, 1.0].

    Factors
    -------
    +0.4  has non-empty text
    +0.2  text ≥ 50 chars
    +0.2  text ≥ 200 chars
    +0.1  has a non-empty title
    +0.1  no PII masks (<EMAIL> / <PHONE>) present
    """
    score = 0.0
    t = (text or "").strip()

    if t:
        score += 0.4
    if len(t) >= 50:
        score += 0.2
    if len(t) >= 200:
        score += 0.2
    if (title or "").strip():
        score += 0.1
    if "<EMAIL>" not in t and "<PHONE>" not in t:
        score += 0.1

    return round(min(score, 1.0), 4)
