from unittest.mock import patch
import httpx
import pytest

from app.schemas.source_inspection import InspectionErrorCategory, InspectionResult
from app.services.source_inspection import (
    SourceInspector,
    extract_title_and_text,
    inspect_source_url,
    validate_url_security,
)


@pytest.mark.asyncio
async def test_valid_html_inspection():
    """Test standard valid HTML inspection with successful text and title extraction."""
    html_content = b"""
    <!DOCTYPE html>
    <html>
        <head>
            <title>Jane Doe &amp; Associates | Portfolio</title>
        </head>
        <body>
            <header><h1>Jane Doe</h1></header>
            <main>
                <p>Senior Full Stack Developer specializing in FastAPI &amp; AI.</p>
                <div>Projects: <span>Gap2Hire</span></div>
            </main>
        </body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=html_content,
        )

    transport = httpx.MockTransport(handler)

    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 443))]):
        result: InspectionResult = await inspect_source_url(
            "https://janedoe.dev/portfolio", transport=transport
        )

    assert result.is_success is True
    assert result.source_url == "https://janedoe.dev/portfolio"
    assert result.final_url == "https://janedoe.dev/portfolio"
    assert result.http_status == 200
    assert result.title == "Jane Doe & Associates | Portfolio"
    assert "Senior Full Stack Developer specializing in FastAPI & AI." in result.extracted_text
    assert "Gap2Hire" in result.extracted_text
    assert result.content_length == len(html_content)
    assert result.error_category is None


def test_html_title_and_text_extraction():
    """Test HTML parser title extraction and script/style/tag stripping."""
    html_doc = b"""
    <html>
        <head>
            <title>My Software Blog &lt;2026&gt;</title>
            <style>body { background: red; }</style>
            <script>console.log("secret tracker code");</script>
        </head>
        <body>
            <noscript>Please enable JavaScript to view this page.</noscript>
            <h1>Welcome to my site</h1>
            <p>Here is my open-source project documentation.</p>
            <svg><text>Ignored SVG Text</text></svg>
        </body>
    </html>
    """
    title, text = extract_title_and_text(html_doc, "text/html", max_text_chars=1000)

    assert title == "My Software Blog <2026>"
    assert "Welcome to my site" in text
    assert "Here is my open-source project documentation." in text
    # Excluded elements
    assert "background: red" not in text
    assert "secret tracker code" not in text
    assert "Please enable JavaScript" not in text
    assert "Ignored SVG Text" not in text


def test_unsupported_url_schemes_rejected():
    """Test that non-HTTP/HTTPS schemes are safely rejected."""
    for bad_url in [
        "file:///etc/passwd",
        "ftp://ftp.example.com/resume.pdf",
        "data:text/html,<h1>Malicious</h1>",
        "javascript:alert(1)",
        "gopher://gopher.example.com",
    ]:
        is_safe, err_cat, err_msg = validate_url_security(bad_url)
        assert is_safe is False
        assert err_cat == InspectionErrorCategory.UNSUPPORTED_SCHEME
        assert "Unsupported scheme" in err_msg


def test_empty_and_invalid_urls_rejected():
    """Test that empty, whitespace-only, and malformed URLs are rejected."""
    for invalid_url in ["", "   ", "not-a-valid-url", "://missing-scheme"]:
        is_safe, err_cat, err_msg = validate_url_security(invalid_url)
        assert is_safe is False
        assert err_cat == InspectionErrorCategory.INVALID_URL


def test_blocked_localhost_and_private_ips():
    """Test that localhost, private networks, link-local, and cloud metadata IPs are blocked."""
    blocked_urls = [
        "http://localhost:8000",
        "http://127.0.0.1:8000/admin",
        "http://127.0.0.2",
        "http://10.0.0.1/internal",
        "http://172.16.0.1/metrics",
        "http://192.168.1.1/router",
        "http://169.254.169.254/latest/meta-data",  # AWS/GCP metadata
        "http://0.0.0.0",
        "http://[::1]/debug",
    ]
    for url in blocked_urls:
        is_safe, err_cat, err_msg = validate_url_security(url)
        assert is_safe is False
        assert err_cat == InspectionErrorCategory.BLOCKED_HOST
        assert "blocked" in err_msg.lower() or "restricted" in err_msg.lower()


def test_hostname_resolving_to_private_ip_is_blocked():
    """Test that a public-looking domain that resolves to a private IP is blocked (DNS rebinding / SSRF)."""
    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 80))]):
        is_safe, err_cat, err_msg = validate_url_security("http://evil-redirect-domain.com")
        assert is_safe is False
        assert err_cat == InspectionErrorCategory.BLOCKED_HOST
        assert "resolves to restricted IP" in err_msg


@pytest.mark.asyncio
async def test_timeout_handling():
    """Test that request timeouts are caught and categorized as TIMEOUT."""
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Connection timed out", request=request)

    transport = httpx.MockTransport(timeout_handler)

    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 80))]):
        result = await inspect_source_url(
            "http://slow-server.com", timeout_seconds=2.0, transport=transport
        )

    assert result.is_success is False
    assert result.error_category == InspectionErrorCategory.TIMEOUT
    assert "timed out" in result.error_message.lower()


@pytest.mark.asyncio
async def test_http_error_handling():
    """Test that HTTP 4xx and 5xx status codes are handled as HTTP_ERROR."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, headers={"content-type": "text/html"}, content=b"<h1>404 Not Found</h1>")

    transport = httpx.MockTransport(handler)

    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 443))]):
        result = await inspect_source_url("https://example.com/not-found", transport=transport)

    assert result.is_success is False
    assert result.http_status == 404
    assert result.error_category == InspectionErrorCategory.HTTP_ERROR
    assert "status 404" in result.error_message


@pytest.mark.asyncio
async def test_response_size_limit_via_content_length_and_stream():
    """Test that responses exceeding max_response_bytes are rejected as RESPONSE_TOO_LARGE."""
    # Case A: Content-Length header exceeds limit
    def handler_header(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-length": "5000000", "content-type": "text/html"},
            content=b"Short",
        )

    inspector_a = SourceInspector(max_response_bytes=1024, transport=httpx.MockTransport(handler_header))

    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 443))]):
        result_a = await inspector_a.inspect("https://example.com/large")

    assert result_a.is_success is False
    assert result_a.error_category == InspectionErrorCategory.RESPONSE_TOO_LARGE

    # Case B: Streaming body exceeds limit without excessive Content-Length header
    def handler_stream(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"A" * 2048,
        )

    inspector_b = SourceInspector(max_response_bytes=1024, transport=httpx.MockTransport(handler_stream))

    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 443))]):
        result_b = await inspector_b.inspect("https://example.com/stream-large")

    assert result_b.is_success is False
    assert result_b.error_category == InspectionErrorCategory.RESPONSE_TOO_LARGE


def test_malformed_and_plain_text_handling():
    """Test plain text, binary, and malformed HTML handling."""
    # Plain text
    title_txt, text_txt = extract_title_and_text(
        b"Plain text resume notes\nSkills: Python, Go", "text/plain", max_text_chars=1000
    )
    assert title_txt is None
    assert text_txt == "Plain text resume notes\nSkills: Python, Go"

    # Binary / image content
    title_bin, text_bin = extract_title_and_text(b"\x89PNG\r\n\x1a\n\x00\x00", "image/png", max_text_chars=1000)
    assert title_bin is None
    assert text_bin is None

    # Malformed HTML (unclosed title, unclosed tags)
    title_malformed, text_malformed = extract_title_and_text(
        b"<title>Unclosed Title<p>Some unclosed <b>tags and messy text",
        "text/html",
        max_text_chars=1000,
    )
    assert "Unclosed Title" in (title_malformed or "")
    assert "Some unclosed tags and messy text" in (text_malformed or "")


@pytest.mark.asyncio
async def test_safe_redirect_followed_and_unsafe_redirect_blocked():
    """Test that safe redirects are followed and unsafe private/metadata redirects are intercepted and blocked."""
    # Case A: Safe redirect
    def safe_redirect_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old-url":
            return httpx.Response(301, headers={"location": "https://example.com/new-url"})
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"<title>New Page</title><p>Welcome to redirected page</p>",
        )

    transport_safe = httpx.MockTransport(safe_redirect_handler)
    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 443))]):
        result_safe = await inspect_source_url("https://example.com/old-url", transport=transport_safe)

    assert result_safe.is_success is True
    assert result_safe.final_url == "https://example.com/new-url"
    assert result_safe.title == "New Page"
    assert "Welcome to redirected page" in result_safe.extracted_text

    # Case B: Dangerous redirect to internal AWS metadata service
    def evil_redirect_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})

    transport_evil = httpx.MockTransport(evil_redirect_handler)
    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 443))]):
        result_evil = await inspect_source_url("https://example.com/open-redirect", transport=transport_evil)

    assert result_evil.is_success is False
    assert result_evil.error_category == InspectionErrorCategory.BLOCKED_HOST
    assert "Redirect to unsafe URL" in result_evil.error_message
