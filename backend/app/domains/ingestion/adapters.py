"""Caldwell University source adapter."""

from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

from app.core.logging import get_logger
from app.domains.ingestion.enums import IngestionContentType
from app.domains.ingestion.html_parser import HtmlDocument, parse_html
from app.domains.ingestion.schemas import (
    ParsedHtmlRecord,
    RawSourceArtifact,
    SourceDefinition,
)
from app.domains.ingestion.security import (
    UnsafeContentError,
    sanitize_text,
    source_hash,
    validate_fetch_url,
    validate_html_response,
)

logger = get_logger(__name__)


class CaldwellUniversityAdapter:
    """Fetch, validate, parse, and prepare Caldwell source records."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds

    async def fetch(self, source: SourceDefinition) -> RawSourceArtifact:
        """Fetch one configured Caldwell source and preserve raw HTML."""

        source_url = str(source.url)
        validate_fetch_url(source, source_url)
        logger.info(
            "ingestion_source_fetch_started source_id=%s url=%s",
            source.source_id,
            source_url,
        )
        if self._client is not None:
            response = await self._client.get(source_url, follow_redirects=False)
        else:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(source_url, follow_redirects=False)
        response.raise_for_status()
        html_content = validate_html_response(
            content=response.content,
            content_type=response.headers.get("content-type", ""),
        )
        content_hash = source_hash(source.source_id, source_url, html_content)
        return RawSourceArtifact(
            source=source,
            source_url=source.url,
            html_content=html_content,
            content_hash=content_hash,
            metadata={
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", ""),
                "adapter_name": source.adapter_name,
                "adapter_version": source.adapter_version,
            },
        )

    async def parse(self, artifact: RawSourceArtifact) -> list[ParsedHtmlRecord]:
        """Parse a raw Caldwell HTML artifact into sanitized records."""

        document = parse_html(
            artifact.html_content,
            base_url=str(artifact.source_url),
        )
        records = self._records_from_document(artifact, document)
        if not records:
            raise UnsafeContentError("no records were extracted from source")
        logger.info(
            "ingestion_source_parsed source_id=%s records=%s",
            artifact.source.source_id,
            len(records),
        )
        return records

    def _records_from_document(
        self,
        artifact: RawSourceArtifact,
        document: HtmlDocument,
    ) -> list[ParsedHtmlRecord]:
        """Extract source-specific records from parsed HTML."""

        if artifact.source.content_type == IngestionContentType.FORMS:
            return self._form_records(artifact, document)
        if artifact.source.content_type == IngestionContentType.CALENDAR:
            return self._calendar_records(artifact, document)
        raise UnsafeContentError("unsupported Caldwell source content type")

    def _form_records(
        self,
        artifact: RawSourceArtifact,
        document: HtmlDocument,
    ) -> list[ParsedHtmlRecord]:
        """Extract Caldwell form links or a deterministic fallback record."""

        keywords = _keywords(artifact.source)
        records = [
            _record_from_link(artifact, link.text, link.href, document.visible_text)
            for link in document.links
            if _matches_keywords(link.text, keywords)
            and _is_safe_caldwell_link(str(artifact.source.url), link.href)
        ]
        if records:
            return _dedupe_records(records)
        fallback_title = str(
            artifact.source.parser_config.get("fallback_title", artifact.source.source_name)
        )
        return [
            _record_from_text(
                artifact=artifact,
                title=fallback_title,
                description=document.visible_text,
                source_url=str(artifact.source.url),
            )
        ]

    def _calendar_records(
        self,
        artifact: RawSourceArtifact,
        document: HtmlDocument,
    ) -> list[ParsedHtmlRecord]:
        """Extract Caldwell calendar records from headings and calendar links."""

        keywords = _keywords(artifact.source)
        records = [
            _record_from_link(artifact, link.text, link.href, document.visible_text)
            for link in document.links
            if _matches_keywords(link.text, keywords)
            and _is_safe_caldwell_link(str(artifact.source.url), link.href)
        ]
        for heading in document.headings:
            if _matches_keywords(heading, keywords):
                records.append(
                    _record_from_text(
                        artifact=artifact,
                        title=heading,
                        description=document.visible_text,
                        source_url=str(artifact.source.url),
                    )
                )
        if records:
            return _dedupe_records(records)
        fallback_title = str(
            artifact.source.parser_config.get("fallback_title", artifact.source.source_name)
        )
        return [
            _record_from_text(
                artifact=artifact,
                title=fallback_title,
                description=document.visible_text,
                source_url=str(artifact.source.url),
            )
        ]


def _record_from_link(
    artifact: RawSourceArtifact,
    title: str,
    href: str,
    document_text: str,
) -> ParsedHtmlRecord:
    """Create a parsed record from a sanitized link."""

    return _record_from_text(
        artifact=artifact,
        title=title,
        description=document_text,
        source_url=href,
    )


def _record_from_text(
    artifact: RawSourceArtifact,
    title: str,
    description: str,
    source_url: str,
) -> ParsedHtmlRecord:
    """Create a parsed record with deterministic hash metadata."""

    cleaned_title = sanitize_text(title, max_length=255)
    cleaned_description = sanitize_text(description, max_length=2000)
    record_hash = source_hash(
        artifact.source.source_id,
        source_url,
        cleaned_title,
        cleaned_description,
        artifact.content_hash,
    )
    return ParsedHtmlRecord(
        source_url=source_url,
        title=cleaned_title,
        description=cleaned_description,
        extracted_at=datetime.now(UTC),
        source_hash=record_hash,
        metadata={
            "source_id": artifact.source.source_id,
            "source_content_hash": artifact.content_hash,
            "content_type": artifact.source.content_type.value,
        },
    )


def _dedupe_records(records: list[ParsedHtmlRecord]) -> list[ParsedHtmlRecord]:
    """Dedupe parsed records in stable source order."""

    seen_hashes: set[str] = set()
    deduped_records: list[ParsedHtmlRecord] = []
    for record in records:
        if record.source_hash in seen_hashes:
            continue
        seen_hashes.add(record.source_hash)
        deduped_records.append(record)
    return deduped_records


def _keywords(source: SourceDefinition) -> list[str]:
    """Return normalized parser keywords for a source."""

    values = source.parser_config.get("record_link_keywords", [])
    return [str(value).strip().lower() for value in values if str(value).strip()]


def _matches_keywords(value: str, keywords: list[str]) -> bool:
    """Return whether sanitized text includes any configured keyword."""

    normalized_value = value.lower()
    return any(keyword in normalized_value for keyword in keywords)


def _is_safe_caldwell_link(source_url: str, candidate_url: str) -> bool:
    """Allow links discovered on the page only when they stay on Caldwell hosts."""

    source_host = urlparse(source_url).hostname or ""
    candidate = urlparse(candidate_url)
    candidate_host = candidate.hostname or source_host
    if candidate.scheme not in {"http", "https"}:
        return False
    allowed_hosts = {source_host, "www.caldwell.edu", "my.caldwell.edu"}
    return candidate_host in allowed_hosts

