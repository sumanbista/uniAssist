"""Validation and sanitization helpers for external ingestion content."""

import hashlib
import html
import re
from urllib.parse import urlparse

from app.domains.ingestion.schemas import SourceDefinition

MAX_HTML_BYTES = 2_000_000
SAFE_TEXT_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
WHITESPACE_PATTERN = re.compile(r"\s+")


class UnsafeContentError(ValueError):
    """Raised when external content fails ingestion safety checks."""


def validate_fetch_url(source: SourceDefinition, url: str) -> None:
    """Ensure the adapter only fetches the configured allowlisted URL."""

    if url.strip() != str(source.url):
        raise UnsafeContentError("source URL is not allowlisted")
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https":
        raise UnsafeContentError("only HTTPS ingestion sources are allowed")
    if parsed_url.username or parsed_url.password:
        raise UnsafeContentError("credentials in source URLs are not allowed")


def validate_html_response(
    content: bytes,
    content_type: str,
) -> str:
    """Validate external HTML response size and media type."""

    if len(content) > MAX_HTML_BYTES:
        raise UnsafeContentError("source response exceeds maximum allowed size")
    normalized_content_type = content_type.split(";", maxsplit=1)[0].strip().lower()
    if normalized_content_type not in {"text/html", "application/xhtml+xml"}:
        raise UnsafeContentError("source response is not HTML")
    text = content.decode("utf-8", errors="replace")
    if not text.strip():
        raise UnsafeContentError("source response is empty")
    return text


def sanitize_text(value: str, max_length: int = 2000) -> str:
    """Return text safe for canonical storage and API responses."""

    unescaped_value = html.unescape(value)
    without_controls = SAFE_TEXT_PATTERN.sub(" ", unescaped_value)
    normalized_value = WHITESPACE_PATTERN.sub(" ", without_controls).strip()
    return normalized_value[:max_length].strip()


def source_hash(*parts: str) -> str:
    """Return a deterministic SHA-256 hash for source-derived content."""

    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\x1f")
    return digest.hexdigest()

