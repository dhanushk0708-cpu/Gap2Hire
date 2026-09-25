import html
import re
from html.parser import HTMLParser
from typing import Optional, Set
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

from app.core.config import settings
from app.schemas.link_discovery import DiscoveredLink

# Schemes supported for discovered candidate sources
ALLOWED_SCHEMES: Set[str] = {"http", "https"}

# Tags whose internal content should not be scanned for links
IGNORE_TAGS: Set[str] = {"script", "style", "noscript"}


class HTMLLinkExtractor(HTMLParser):
    """
    Lightweight, streaming HTML parser that extracts raw anchor links and
    their visible text while ignoring scripts, styles, and non-content tags.
    """

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []  # List of (href, anchor_text)
        self.current_href: Optional[str] = None
        self.current_anchor_parts: list[str] = []
        self.ignore_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag_lower = tag.lower()
        if tag_lower in IGNORE_TAGS:
            self.ignore_depth += 1
            return

        if self.ignore_depth > 0:
            return

        if tag_lower == "a":
            # If an unclosed anchor was open, flush it
            if self.current_href is not None:
                self._flush_current()

            href_val = None
            for attr_name, attr_val in attrs:
                if attr_name.lower() == "href":
                    href_val = attr_val
                    break

            if href_val is not None:
                self.current_href = href_val
                self.current_anchor_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in IGNORE_TAGS:
            if self.ignore_depth > 0:
                self.ignore_depth -= 1
            return

        if tag_lower == "a" and self.current_href is not None:
            self._flush_current()

    def handle_data(self, data: str) -> None:
        if self.ignore_depth == 0 and self.current_href is not None:
            if data:
                self.current_anchor_parts.append(data)

    def _flush_current(self) -> None:
        if self.current_href is not None:
            anchor_text = "".join(self.current_anchor_parts)
            self.links.append((self.current_href, anchor_text))
            self.current_href = None
            self.current_anchor_parts = []

    def close(self) -> None:
        self._flush_current()
        super().close()


def normalize_url(raw_url: str) -> Optional[str]:
    """
    Performs basic deterministic URL normalization:
    - Strips URL fragments (#section)
    - Normalizes scheme and host to lowercase
    - Strips trailing slash on path if non-root or normalizes root path
    """
    if not raw_url or not isinstance(raw_url, str):
        return None

    cleaned = raw_url.strip()
    if not cleaned:
        return None

    # Strip fragments
    defragged, _ = urldefrag(cleaned)
    if not defragged:
        return None

    try:
        parts = urlsplit(defragged)
    except Exception:
        return None

    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        return None

    netloc = parts.netloc.lower()
    if not netloc:
        return None

    path = parts.path
    # Normalize empty path to empty or single root slash
    if path == "/":
        path = ""
    elif path.endswith("/") and len(path) > 1:
        path = path.rstrip("/")

    normalized = urlunsplit((scheme, netloc, path, parts.query, ""))
    return normalized


def classify_source_url(url: str) -> str:
    """
    Deterministic basic source classification based on domain and path patterns.
    """
    try:
        parts = urlsplit(url)
        hostname = (parts.hostname or "").lower()
        path = (parts.path or "").lower()
    except Exception:
        return "OTHER"

    if hostname == "github.com" or hostname.endswith(".github.com") or hostname == "github.io" or hostname.endswith(".github.io"):
        return "GITHUB"
    if hostname == "gitlab.com" or hostname.endswith(".gitlab.com"):
        return "GITLAB"
    if hostname == "bitbucket.org" or hostname.endswith(".bitbucket.org"):
        return "BITBUCKET"
    if hostname == "linkedin.com" or hostname.endswith(".linkedin.com"):
        return "LINKEDIN"
    if hostname == "kaggle.com" or hostname.endswith(".kaggle.com"):
        return "KAGGLE"
    if hostname == "huggingface.co" or hostname.endswith(".huggingface.co"):
        return "HUGGING_FACE"
    if hostname == "devpost.com" or hostname.endswith(".devpost.com"):
        return "DEVPOST"
    if hostname in {"youtube.com", "youtu.be"} or hostname.endswith(".youtube.com") or hostname.endswith(".youtu.be"):
        return "YOUTUBE"
    if hostname in {"twitter.com", "x.com"} or hostname.endswith(".twitter.com") or hostname.endswith(".x.com"):
        return "TWITTER"
    if any(b in hostname for b in ("medium.com", "dev.to", "hashnode.dev", "hashnode.com", "substack.com")):
        return "BLOG"
    if hostname.startswith("docs.") or "/docs" in path or "/documentation" in path:
        return "DOCS"
    if "/portfolio" in path or "/projects" in path:
        return "PORTFOLIO"

    return "OTHER"


class LinkDiscovery:
    """
    Controlled link extraction and discovery service from inspected HTML content.
    Extracts, normalizes, deduplicates, and classifies links without performing network I/O.
    """

    def __init__(self, max_links: Optional[int] = None) -> None:
        self.max_links = (
            max_links
            if max_links is not None
            else settings.source_discovery_max_links
        )

    def discover_links(
        self,
        page_url: str,
        html_content: str | bytes,
        current_depth: int = 0,
    ) -> list[DiscoveredLink]:
        """
        Discovers and structures links from HTML content resolved against page_url.
        """
        normalized_page_url = normalize_url(page_url)
        if not normalized_page_url:
            return []

        # Convert bytes to string if needed
        if isinstance(html_content, bytes):
            try:
                html_text = html_content.decode("utf-8", errors="replace")
            except Exception:
                html_text = html_content.decode("latin-1", errors="replace")
        else:
            html_text = str(html_content)

        if not html_text.strip():
            return []

        parser = HTMLLinkExtractor()
        try:
            parser.feed(html_text)
            parser.close()
        except Exception:
            # Fallback regex extraction if parser fails on severely corrupted markup
            raw_links = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html_text, re.IGNORECASE | re.DOTALL)
            parser.links = [(href, re.sub(r"<[^>]+>", "", text)) for href, text in raw_links]

        discovered: list[DiscoveredLink] = []
        seen_urls: set[str] = set()
        next_depth = current_depth + 1

        for raw_href, raw_anchor in parser.links:
            if not raw_href or not raw_href.strip():
                continue

            cleaned_href = raw_href.strip()

            # Ignore fragment-only or empty anchors
            if cleaned_href.startswith("#"):
                continue

            # Ignore non-http schemes like mailto:, javascript:, tel:, data:
            try:
                split_href = urlsplit(cleaned_href)
                if split_href.scheme and split_href.scheme.lower() not in ALLOWED_SCHEMES:
                    continue
            except Exception:
                continue

            # Resolve relative URLs
            try:
                resolved = urljoin(page_url, cleaned_href)
            except Exception:
                continue

            normalized = normalize_url(resolved)
            if not normalized:
                continue

            # Skip self-references to the inspected page
            if normalized == normalized_page_url:
                continue

            # Deduplicate repeated links on the same page
            if normalized in seen_urls:
                continue

            seen_urls.add(normalized)

            # Clean anchor text
            clean_anchor = None
            if raw_anchor:
                unescaped = html.unescape(raw_anchor)
                collapsed = re.sub(r"\s+", " ", unescaped).strip()
                if collapsed:
                    clean_anchor = collapsed

            source_type = classify_source_url(normalized)

            discovered.append(
                DiscoveredLink(
                    url=normalized,
                    anchor_text=clean_anchor,
                    source_url=page_url,
                    discovery_depth=next_depth,
                    discovered_from=page_url,
                    source_type=source_type,
                )
            )

            if len(discovered) >= self.max_links:
                break

        return discovered


def discover_links_from_html(
    page_url: str,
    html_content: str | bytes,
    current_depth: int = 0,
    max_links: Optional[int] = None,
) -> list[DiscoveredLink]:
    """
    Convenience function for link discovery from HTML content.
    """
    discovery = LinkDiscovery(max_links=max_links)
    return discovery.discover_links(
        page_url=page_url,
        html_content=html_content,
        current_depth=current_depth,
    )
