import html
import re
from collections.abc import Sequence
from typing import Optional
from urllib.parse import urldefrag, urlsplit, urlunsplit
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate_source import CandidateSource
from app.schemas.link_discovery import DiscoveredLink
from app.services.candidate_sources import register_discovered_sources
from app.services.link_discovery import ALLOWED_SCHEMES, classify_source_url

# Regex to find candidate HTTP/HTTPS URLs in unstructured text
RAW_URL_REGEX = re.compile(r"https?://[^\s<>\"'`{}|\\^]+", re.IGNORECASE)

# Trailing punctuation characters commonly found at the end of sentences or quotes
TRAILING_PUNCTUATION = ".,;:!?'\"`"


def clean_url_string(raw_url: str) -> str:
    """
    Cleans trailing punctuation, unmatched parentheses/brackets, and markdown artifacts.
    Preserves balanced parentheses (e.g., Wikipedia URLs).
    """
    if not raw_url:
        return ""

    cleaned = raw_url.strip()

    # Repeatedly strip trailing punctuation and unmatched closing brackets
    changed = True
    while changed and cleaned:
        changed = False

        # 1. Strip trailing common sentence punctuation
        if cleaned[-1] in TRAILING_PUNCTUATION:
            cleaned = cleaned[:-1]
            changed = True
            continue

        # 2. Strip unmatched trailing closing parenthesis
        if cleaned.endswith(")"):
            open_count = cleaned.count("(")
            close_count = cleaned.count(")")
            if close_count > open_count:
                cleaned = cleaned[:-1]
                changed = True
                continue

        # 3. Strip unmatched trailing closing square bracket
        if cleaned.endswith("]"):
            open_count = cleaned.count("[")
            close_count = cleaned.count("]")
            if close_count > open_count:
                cleaned = cleaned[:-1]
                changed = True
                continue

        # 4. Strip unmatched trailing closing curly brace
        if cleaned.endswith("}"):
            open_count = cleaned.count("{")
            close_count = cleaned.count("}")
            if close_count > open_count:
                cleaned = cleaned[:-1]
                changed = True
                continue

        # 5. Strip trailing angle bracket if present
        if cleaned.endswith(">"):
            open_count = cleaned.count("<")
            close_count = cleaned.count(">")
            if close_count > open_count:
                cleaned = cleaned[:-1]
                changed = True
                continue

    return cleaned


def normalize_resume_url(raw_url: str) -> Optional[str]:
    """
    Normalizes a candidate URL extracted from resume text:
    - Cleans punctuation and unmatched delimiters
    - Strips fragment identifiers (#section)
    - Normalizes scheme and host to lowercase
    - Normalizes paths (removes trailing slashes on non-root paths)
    - Preserves query parameters
    - Enforces HTTP/HTTPS scheme and valid host
    """
    if not raw_url or not isinstance(raw_url, str):
        return None

    cleaned = clean_url_string(raw_url)
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
    if not netloc or not parts.hostname:
        return None

    path = parts.path
    if path == "/":
        path = ""
    elif path.endswith("/") and len(path) > 1:
        path = path.rstrip("/")

    normalized = urlunsplit((scheme, netloc, path, parts.query, ""))
    return normalized


def extract_urls_from_text(text: str) -> list[str]:
    """
    Extracts all unique, normalized HTTP/HTTPS URLs from raw text in document order.
    Domain-agnostic and deterministic.
    """
    if not text or not isinstance(text, str):
        return []

    found_urls: list[str] = []
    seen: set[str] = set()

    for match in RAW_URL_REGEX.finditer(text):
        raw_match = match.group(0)
        normalized = normalize_resume_url(raw_match)
        if normalized and normalized not in seen:
            seen.add(normalized)
            found_urls.append(normalized)

    return found_urls


def discover_sources_from_resume_text(resume_text: str) -> list[DiscoveredLink]:
    """
    Extracts, normalizes, deduplicates, and classifies candidate sources from resume text.
    Domain-agnostic: extracts ANY valid HTTP/HTTPS URL.
    Does NOT perform network I/O or LLM calls.
    """
    urls = extract_urls_from_text(resume_text)
    sources: list[DiscoveredLink] = []

    for url in urls:
        source_type = classify_source_url(url)
        sources.append(
            DiscoveredLink(
                url=url,
                anchor_text=None,
                source_url="RESUME",
                discovery_depth=0,
                discovered_from="RESUME",
                source_type=source_type,
            )
        )

    return sources


async def sync_resume_candidate_sources(
    session: AsyncSession,
    organization_id: UUID,
    application_id: UUID,
    resume_text: str | None,
) -> list[CandidateSource]:
    """
    Extracts URLs from resume text and registers them as CandidateSource records
    attached to the application under tenant isolation.
    Guarantees idempotency and deduplication.
    """
    if not resume_text or not resume_text.strip():
        return []

    discovered = discover_sources_from_resume_text(resume_text)
    if not discovered:
        return []

    return await register_discovered_sources(
        session=session,
        organization_id=organization_id,
        application_id=application_id,
        discovered_links=discovered,
    )
