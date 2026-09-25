import html
import ipaddress
import re
import socket
from html.parser import HTMLParser
from typing import Optional, Set
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import settings
from app.schemas.source_inspection import InspectionErrorCategory, InspectionResult

# Set of schemes permitted for source inspection
ALLOWED_SCHEMES: Set[str] = {"http", "https"}

# Tags whose inner content should be completely excluded from extracted text
IGNORE_TAGS: Set[str] = {"script", "style", "noscript", "svg", "canvas", "template"}

# Tags that typically create block-level spacing
BLOCK_TAGS: Set[str] = {
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "br",
    "section", "article", "header", "footer", "main", "blockquote", "aside"
}

# Maximum number of HTTP redirects permitted per inspection request
MAX_REDIRECTS: int = 5


class HTMLTextExtractor(HTMLParser):
    """
    Safe and robust HTML parser that extracts the page title and clean, visible text
    while stripping scripts, styles, and non-content tags.
    """

    def __init__(self) -> None:
        super().__init__()
        self.in_title: bool = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.ignore_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag_lower = tag.lower()
        if tag_lower in IGNORE_TAGS:
            self.ignore_depth += 1
        elif tag_lower == "title":
            self.in_title = True
        elif tag_lower in BLOCK_TAGS or tag_lower in {"body", "head", "html"}:
            if self.in_title:
                self.in_title = False
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in IGNORE_TAGS:
            if self.ignore_depth > 0:
                self.ignore_depth -= 1
        elif tag_lower == "title":
            self.in_title = False
        elif tag_lower in BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        elif self.ignore_depth == 0:
            if data:
                self.text_parts.append(data)

    def get_title(self) -> Optional[str]:
        raw_title = "".join(self.title_parts)
        cleaned = html.unescape(raw_title).strip()
        return cleaned if cleaned else None

    def get_text(self) -> str:
        raw_text = "".join(self.text_parts)
        unescaped = html.unescape(raw_text)
        # Normalize whitespace: collapse horizontal whitespace, normalize consecutive newlines
        lines = [re.sub(r"[^\S\r\n]+", " ", line).strip() for line in unescaped.splitlines()]
        # Remove excessive empty lines
        compact_text = "\n".join(line for line in lines if line)
        return compact_text.strip()


def validate_url_security(
    url: str,
) -> tuple[bool, Optional[InspectionErrorCategory], Optional[str]]:
    """
    Validates a URL for basic structure and SSRF safety.
    Checks scheme, host presence, and blocks private/loopback/link-local/metadata IP ranges.

    Returns:
        (is_safe, error_category, error_message)
    """
    if not url or not isinstance(url, str) or not url.strip():
        return False, InspectionErrorCategory.INVALID_URL, "URL is empty or not a string"

    url_clean = url.strip()

    try:
        parsed = urlparse(url_clean)
    except Exception as e:
        return False, InspectionErrorCategory.INVALID_URL, f"Malformed URL: {e}"

    scheme = (parsed.scheme or "").lower()
    if not scheme:
        return False, InspectionErrorCategory.INVALID_URL, "Missing URL scheme"

    if scheme not in ALLOWED_SCHEMES:
        return (
            False,
            InspectionErrorCategory.UNSUPPORTED_SCHEME,
            f"Unsupported scheme '{scheme}'. Only HTTP and HTTPS are permitted.",
        )

    hostname = parsed.hostname
    if not hostname:
        return False, InspectionErrorCategory.INVALID_URL, "URL has no valid hostname"

    hostname_lower = hostname.lower()

    # Block well-known localhost aliases
    if hostname_lower in {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}:
        return (
            False,
            InspectionErrorCategory.BLOCKED_HOST,
            f"Access to localhost '{hostname}' is blocked for security.",
        )

    # Check if hostname is an IP literal
    try:
        ip = ipaddress.ip_address(hostname_lower)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return (
                False,
                InspectionErrorCategory.BLOCKED_HOST,
                f"Access to private/restricted IP address '{ip}' is blocked.",
            )
    except ValueError:
        # Hostname is a domain name, resolve DNS to verify resolved IPs
        try:
            addr_info = socket.getaddrinfo(hostname_lower, None)
            for item in addr_info:
                sockaddr = item[4]
                ip_str = sockaddr[0]
                try:
                    ip = ipaddress.ip_address(ip_str)
                    if (
                        ip.is_private
                        or ip.is_loopback
                        or ip.is_link_local
                        or ip.is_multicast
                        or ip.is_reserved
                        or ip.is_unspecified
                    ):
                        return (
                            False,
                            InspectionErrorCategory.BLOCKED_HOST,
                            f"Host '{hostname}' resolves to restricted IP '{ip_str}'.",
                        )
                except ValueError:
                    continue
        except socket.gaierror as e:
            return (
                False,
                InspectionErrorCategory.CONNECTION_ERROR,
                f"DNS resolution failed for '{hostname}': {e}",
            )
        except Exception as e:
            return (
                False,
                InspectionErrorCategory.CONNECTION_ERROR,
                f"Unable to resolve host '{hostname}': {e}",
            )

    return True, None, None


def extract_title_and_text(
    content_bytes: bytes,
    content_type_header: str,
    max_text_chars: int,
) -> tuple[Optional[str], Optional[str]]:
    """
    Safely decodes and extracts page title and readable text from HTTP response content.
    """
    is_html = "html" in content_type_header.lower()
    is_plain_text = (
        content_type_header.lower().startswith("text/")
        or any(
            t in content_type_header.lower()
            for t in ("application/json", "application/toml", "application/yaml", "application/x-yaml", "application/xml")
        )
    )

    try:
        decoded_text = content_bytes.decode("utf-8", errors="replace")
    except Exception:
        decoded_text = content_bytes.decode("latin-1", errors="replace")

    if is_html:
        try:
            parser = HTMLTextExtractor()
            parser.feed(decoded_text)
            parser.close()
            title = parser.get_title()
            text = parser.get_text()
            if text and len(text) > max_text_chars:
                text = text[:max_text_chars]
            return title, text
        except Exception:
            # Fallback to basic tag removal if parser encounters catastrophic failure
            cleaned = re.sub(r"<[^>]+>", " ", decoded_text)
            cleaned = html.unescape(cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if cleaned and len(cleaned) > max_text_chars:
                cleaned = cleaned[:max_text_chars]
            return None, cleaned

    if is_plain_text:
        cleaned = decoded_text.strip()
        if cleaned and len(cleaned) > max_text_chars:
            cleaned = cleaned[:max_text_chars]
        return None, cleaned

    # Non-textual or binary content (e.g. image, pdf, octet-stream)
    return None, None


class SourceInspector:
    """
    Controlled HTTP/HTTPS source inspection service with SSRF validation,
    response size limits, timeouts, redirect validation, and text extraction.
    """

    def __init__(
        self,
        timeout_seconds: Optional[float] = None,
        max_response_bytes: Optional[int] = None,
        max_text_chars: Optional[int] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.source_inspection_timeout_seconds
        )
        self.max_response_bytes = (
            max_response_bytes
            if max_response_bytes is not None
            else settings.source_inspection_max_response_bytes
        )
        self.max_text_chars = (
            max_text_chars
            if max_text_chars is not None
            else settings.source_inspection_max_text_chars
        )
        self.transport = transport

    async def inspect(self, url: str) -> InspectionResult:
        """
        Inspects the specified URL safely and returns a structured InspectionResult.
        """
        is_safe, error_cat, error_msg = validate_url_security(url)
        if not is_safe:
            return InspectionResult(
                source_url=url,
                is_success=False,
                error_category=error_cat,
                error_message=error_msg,
            )

        current_url = url
        redirect_count = 0

        # Create client with timeout
        timeout_config = httpx.Timeout(self.timeout_seconds)
        headers = {
            "User-Agent": "Gap2Hire-SourceInspector/1.0 (+https://gap2hire.com)",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
        }

        async with httpx.AsyncClient(
            timeout=timeout_config,
            headers=headers,
            transport=self.transport,
        ) as client:
            while redirect_count <= MAX_REDIRECTS:
                try:
                    # Request with streaming disabled or stream to enforce size limits
                    async with client.stream(
                        "GET", current_url, follow_redirects=False
                    ) as response:
                        # Check content length header if present
                        content_length_header = response.headers.get("content-length")
                        if content_length_header:
                            try:
                                clen = int(content_length_header)
                                if clen > self.max_response_bytes:
                                    return InspectionResult(
                                        source_url=url,
                                        final_url=str(response.url),
                                        http_status=response.status_code,
                                        content_type=response.headers.get("content-type"),
                                        content_length=clen,
                                        is_success=False,
                                        error_category=InspectionErrorCategory.RESPONSE_TOO_LARGE,
                                        error_message=(
                                            f"Content-Length {clen} bytes exceeds maximum allowed "
                                            f"{self.max_response_bytes} bytes."
                                        ),
                                    )
                            except ValueError:
                                pass

                        # Handle redirect status codes manually to validate destination URLs
                        if response.status_code in {301, 302, 303, 307, 308}:
                            redirect_location = response.headers.get("location")
                            if not redirect_location:
                                return InspectionResult(
                                    source_url=url,
                                    final_url=str(response.url),
                                    http_status=response.status_code,
                                    is_success=False,
                                    error_category=InspectionErrorCategory.HTTP_ERROR,
                                    error_message="Redirect response missing Location header.",
                                )

                            next_url = urljoin(current_url, redirect_location)
                            # Validate security of redirect target
                            is_safe_next, next_err_cat, next_err_msg = validate_url_security(next_url)
                            if not is_safe_next:
                                return InspectionResult(
                                    source_url=url,
                                    final_url=next_url,
                                    http_status=response.status_code,
                                    is_success=False,
                                    error_category=next_err_cat,
                                    error_message=f"Redirect to unsafe URL: {next_err_msg}",
                                )

                            current_url = next_url
                            redirect_count += 1
                            continue

                        # Read response body in chunks to enforce size limit
                        body_chunks: list[bytes] = []
                        total_bytes = 0

                        async for chunk in response.aiter_bytes():
                            total_bytes += len(chunk)
                            if total_bytes > self.max_response_bytes:
                                return InspectionResult(
                                    source_url=url,
                                    final_url=str(response.url),
                                    http_status=response.status_code,
                                    content_type=response.headers.get("content-type"),
                                    content_length=total_bytes,
                                    is_success=False,
                                    error_category=InspectionErrorCategory.RESPONSE_TOO_LARGE,
                                    error_message=(
                                        f"Response size exceeded limit of {self.max_response_bytes} bytes."
                                    ),
                                )
                            body_chunks.append(chunk)

                        content_bytes = b"".join(body_chunks)
                        content_type = response.headers.get("content-type", "")

                        # Handle HTTP error status codes (4xx, 5xx)
                        if response.status_code >= 400:
                            return InspectionResult(
                                source_url=url,
                                final_url=str(response.url),
                                http_status=response.status_code,
                                content_type=content_type,
                                content_length=len(content_bytes),
                                is_success=False,
                                error_category=InspectionErrorCategory.HTTP_ERROR,
                                error_message=f"HTTP request returned status {response.status_code}",
                            )

                        # Extract text and title
                        title, extracted_text = extract_title_and_text(
                            content_bytes, content_type, self.max_text_chars
                        )

                        return InspectionResult(
                            source_url=url,
                            final_url=str(response.url),
                            http_status=response.status_code,
                            content_type=content_type,
                            title=title,
                            extracted_text=extracted_text,
                            content_length=len(content_bytes),
                            is_success=True,
                        )

                except httpx.TimeoutException as e:
                    return InspectionResult(
                        source_url=url,
                        final_url=current_url,
                        is_success=False,
                        error_category=InspectionErrorCategory.TIMEOUT,
                        error_message=f"Request timed out after {self.timeout_seconds} seconds: {e}",
                    )
                except (httpx.ConnectError, httpx.NetworkError) as e:
                    return InspectionResult(
                        source_url=url,
                        final_url=current_url,
                        is_success=False,
                        error_category=InspectionErrorCategory.CONNECTION_ERROR,
                        error_message=f"Connection error: {e}",
                    )
                except Exception as e:
                    return InspectionResult(
                        source_url=url,
                        final_url=current_url,
                        is_success=False,
                        error_category=InspectionErrorCategory.UNKNOWN_ERROR,
                        error_message=f"Inspection failed unexpectedly: {e}",
                    )

            # If redirect count exceeded MAX_REDIRECTS
            return InspectionResult(
                source_url=url,
                final_url=current_url,
                is_success=False,
                error_category=InspectionErrorCategory.HTTP_ERROR,
                error_message=f"Exceeded maximum redirect limit of {MAX_REDIRECTS}.",
            )


# Reusable convenience function
async def inspect_source_url(
    url: str,
    timeout_seconds: Optional[float] = None,
    max_response_bytes: Optional[int] = None,
    max_text_chars: Optional[int] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> InspectionResult:
    """
    Convenience function to inspect a source URL using the SourceInspector.
    """
    inspector = SourceInspector(
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
        max_text_chars=max_text_chars,
        transport=transport,
    )
    return await inspector.inspect(url)
