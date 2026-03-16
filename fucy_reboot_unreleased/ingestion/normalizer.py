# =============================================================================
# normalizer.py — Text cleaning and normalization
# =============================================================================

import html
import re
import unicodedata


def strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", " ", text)


def normalize_unicode(text: str) -> str:
    """Normalize unicode characters to NFC form."""
    return unicodedata.normalize("NFC", text)


def decode_escapes(text: str) -> str:
    """Decode HTML entities like &amp; &lt; etc."""
    return html.unescape(text)


def collapse_whitespace(text: str) -> str:
    """Collapse multiple whitespace/newlines into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def remove_empty_json_fields(text: str) -> str:
    """Remove JSON fields with empty/null values for cleaner embeddings."""
    # Remove patterns like "key": null, "key": "", "key": []
    text = re.sub(r'"[^"]+"\s*:\s*null\s*,?\s*', "", text)
    text = re.sub(r'"[^"]+"\s*:\s*""\s*,?\s*', "", text)
    text = re.sub(r'"[^"]+"\s*:\s*\[\]\s*,?\s*', "", text)
    # Clean up trailing commas before closing braces
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text


def normalize_text(text: str, aggressive: bool = False) -> str:
    """
    Full text normalization pipeline.

    Args:
        text: Raw text to normalize.
        aggressive: If True, also removes empty JSON fields and
                    collapses whitespace more aggressively.
    """
    text = normalize_unicode(text)
    text = decode_escapes(text)
    text = strip_html(text)

    if aggressive:
        text = remove_empty_json_fields(text)

    text = collapse_whitespace(text)
    return text
