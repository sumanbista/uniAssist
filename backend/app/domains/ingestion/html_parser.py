"""Small deterministic HTML parser for Caldwell source pages."""

from html.parser import HTMLParser
from urllib.parse import urljoin

from app.domains.ingestion.security import sanitize_text


class HtmlLink:
    """Sanitized HTML link record."""

    def __init__(self, text: str, href: str) -> None:
        self.text = text
        self.href = href


class HtmlDocument:
    """Sanitized structural metadata extracted from HTML."""

    def __init__(
        self,
        title: str,
        headings: list[str],
        links: list[HtmlLink],
        visible_text: str,
    ) -> None:
        self.title = title
        self.headings = headings
        self.links = links
        self.visible_text = visible_text


class CaldwellHtmlParser(HTMLParser):
    """Parse enough HTML structure for deterministic source extraction."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_parts: list[str] = []
        self.headings: list[str] = []
        self.visible_text_parts: list[str] = []
        self.links: list[HtmlLink] = []
        self._tag_stack: list[str] = []
        self._current_link_href: str | None = None
        self._current_link_text: list[str] = []
        self._current_heading: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Track parse context for title, headings, links, and visible text."""

        normalized_tag = tag.lower()
        self._tag_stack.append(normalized_tag)
        if normalized_tag == "a":
            href = dict(attrs).get("href")
            self._current_link_href = urljoin(self.base_url, href) if href else None
            self._current_link_text = []
        if normalized_tag in {"h1", "h2", "h3", "h4"}:
            self._current_heading = []

    def handle_endtag(self, tag: str) -> None:
        """Finalize links and headings when their tags close."""

        normalized_tag = tag.lower()
        if normalized_tag == "a" and self._current_link_href:
            link_text = sanitize_text(" ".join(self._current_link_text), max_length=255)
            if link_text:
                self.links.append(HtmlLink(text=link_text, href=self._current_link_href))
            self._current_link_href = None
            self._current_link_text = []
        if normalized_tag in {"h1", "h2", "h3", "h4"}:
            heading = sanitize_text(" ".join(self._current_heading), max_length=255)
            if heading:
                self.headings.append(heading)
            self._current_heading = []
        if normalized_tag in self._tag_stack:
            self._tag_stack = self._tag_stack[: self._tag_stack.index(normalized_tag)]

    def handle_data(self, data: str) -> None:
        """Capture visible text while ignoring scripts and styles."""

        if self._is_ignored_context():
            return
        cleaned_data = sanitize_text(data, max_length=2000)
        if not cleaned_data:
            return
        if self._tag_stack and self._tag_stack[-1] == "title":
            self.title_parts.append(cleaned_data)
        if self._current_link_href:
            self._current_link_text.append(cleaned_data)
        if self._tag_stack and self._tag_stack[-1] in {"h1", "h2", "h3", "h4"}:
            self._current_heading.append(cleaned_data)
        self.visible_text_parts.append(cleaned_data)

    def to_document(self) -> HtmlDocument:
        """Return sanitized parsed document data."""

        return HtmlDocument(
            title=sanitize_text(" ".join(self.title_parts), max_length=255),
            headings=self.headings,
            links=self.links,
            visible_text=sanitize_text(" ".join(self.visible_text_parts), max_length=2000),
        )

    def _is_ignored_context(self) -> bool:
        """Return whether current text belongs to unsafe/non-content tags."""

        return any(tag in {"script", "style", "noscript", "svg"} for tag in self._tag_stack)


def parse_html(html_content: str, base_url: str) -> HtmlDocument:
    """Parse HTML into sanitized structural data."""

    parser = CaldwellHtmlParser(base_url=base_url)
    parser.feed(html_content)
    parser.close()
    return parser.to_document()

