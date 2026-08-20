"""Deterministic preprocessing for raw job description text."""

import re
import unicodedata
from html import unescape
from html.parser import HTMLParser


_WHITESPACE_RE = re.compile(r"\s+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


class _HTMLTextExtractor(HTMLParser):
    """Extract visible text from HTML, inserting spaces at block boundaries."""

    _BLOCK_TAGS = frozenset(
        {
            "address",
            "article",
            "aside",
            "blockquote",
            "br",
            "div",
            "footer",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "header",
            "hr",
            "li",
            "main",
            "nav",
            "ol",
            "p",
            "section",
            "table",
            "tr",
            "ul",
        }
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._BLOCK_TAGS:
            self._parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._BLOCK_TAGS:
            self._parts.append(" ")

    def handle_data(self, data: str) -> None:
        if data:
            self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    decoded = unescape(text)
    extractor = _HTMLTextExtractor()
    extractor.feed(decoded)
    extractor.close()
    stripped = extractor.get_text()
    if stripped:
        return stripped
    return _HTML_TAG_RE.sub(" ", decoded)


def _normalize_whitespace(text: str) -> str:
    """Collapse all whitespace runs to a single space."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def _normalize_unicode(text: str) -> str:
    """Apply Unicode NFKC normalization for consistent matching."""
    return unicodedata.normalize("NFKC", text)


def preprocess_description(text: str | None) -> str:
    """
    Normalize raw job description text for downstream processing.

    Steps:
    1. Safely handle null/empty input (returns empty string).
    2. Decode HTML entities and remove HTML tags.
    3. Normalize Unicode (NFKC).
    4. Collapse whitespace and trim.
    """
    try:
        if text is None:
            return ""

        if not isinstance(text, str):
            text = str(text)

        if not text:
            return ""

        without_html = _strip_html(text)
        normalized = _normalize_unicode(without_html)
        return _normalize_whitespace(normalized)
    except Exception as exc:
        from pipeline.monitoring.recorder import record_preprocessing_failure

        record_preprocessing_failure(detail=str(exc))
        raise
