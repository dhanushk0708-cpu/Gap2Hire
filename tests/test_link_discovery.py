from uuid import uuid4
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.session import async_session_factory
from app.main import app
from app.models.candidate_source import CandidateSource
from app.schemas.link_discovery import DiscoveredLink
from app.services.candidate_sources import register_discovered_sources
from app.services.link_discovery import (
    LinkDiscovery,
    classify_source_url,
    discover_links_from_html,
    normalize_url,
)


def test_extract_absolute_http_and_https_links():
    """Test extraction of normal absolute HTTP and HTTPS links."""
    html = """
    <html>
        <body>
            <a href="https://github.com/janedoe">GitHub Profile</a>
            <a href="http://my-blog.com/posts/1">My Blog Post</a>
        </body>
    </html>
    """
    links = discover_links_from_html("https://janedoe.dev", html, current_depth=0)

    assert len(links) == 2
    assert links[0].url == "https://github.com/janedoe"
    assert links[0].anchor_text == "GitHub Profile"
    assert links[0].source_type == "GITHUB"
    assert links[0].discovery_depth == 1

    assert links[1].url == "http://my-blog.com/posts/1"
    assert links[1].anchor_text == "My Blog Post"
    assert links[1].discovery_depth == 1


def test_resolve_relative_links():
    """Test that relative URLs are correctly resolved against the source page URL."""
    html = """
    <div>
        <a href="/projects/gap2hire">Project Details</a>
        <a href="about/team">About Team</a>
        <a href="../resume.html">Old Resume</a>
    </div>
    """
    links = discover_links_from_html("https://example.com/subpage/index.html", html, current_depth=0)

    urls = [link.url for link in links]
    assert "https://example.com/projects/gap2hire" in urls
    assert "https://example.com/subpage/about/team" in urls
    assert "https://example.com/resume.html" in urls


def test_remove_fragments_from_urls():
    """Test that fragments (#section) are stripped during URL normalization."""
    html = """
    <a href="https://docs.example.com/guide#installation">Installation Guide</a>
    <a href="/faq#how-it-works">FAQ</a>
    """
    links = discover_links_from_html("https://docs.example.com", html)

    assert len(links) == 2
    assert links[0].url == "https://docs.example.com/guide"
    assert links[1].url == "https://docs.example.com/faq"


def test_ignore_unsupported_schemes_and_special_links():
    """Test that non-HTTP schemes (mailto, tel, javascript, data) and fragment-only links are ignored."""
    html = """
    <nav>
        <a href="mailto:jane@example.com">Email Me</a>
        <a href="tel:+1234567890">Call Me</a>
        <a href="javascript:void(0);">Run Script</a>
        <a href="data:text/html,test">Data URL</a>
        <a href="#top">Jump to Top</a>
        <a href="ftp://files.example.com/archive.zip">FTP</a>
        <a href="https://valid.com/contact">Valid Contact</a>
    </nav>
    """
    links = discover_links_from_html("https://example.com", html)

    assert len(links) == 1
    assert links[0].url == "https://valid.com/contact"
    assert links[0].anchor_text == "Valid Contact"


def test_ignore_empty_and_whitespace_hrefs():
    """Test that empty or whitespace href attributes are safely skipped."""
    html = """
    <a>No href tag</a>
    <a href="">Empty string</a>
    <a href="   ">Whitespace string</a>
    <a href="https://actual-site.com">Actual Site</a>
    """
    links = discover_links_from_html("https://example.com", html)

    assert len(links) == 1
    assert links[0].url == "https://actual-site.com"


def test_deduplicate_repeated_links():
    """Test that identical URLs appearing multiple times on a page are returned only once."""
    html = """
    <header><a href="https://github.com/janedoe">GitHub</a></header>
    <main><a href="https://github.com/janedoe#repos">GitHub Repos</a></main>
    <footer><a href="https://github.com/janedoe/">My GitHub</a></footer>
    """
    links = discover_links_from_html("https://example.com", html)

    assert len(links) == 1
    assert links[0].url == "https://github.com/janedoe"
    assert links[0].anchor_text == "GitHub"


def test_exclude_self_references():
    """Test that links referencing the inspected page itself are not returned as new sources."""
    html = """
    <a href="https://candidate-portfolio.com">Home</a>
    <a href="https://candidate-portfolio.com/">Home with slash</a>
    <a href="/#about">Self with fragment</a>
    <a href="https://candidate-portfolio.com/projects">Projects</a>
    """
    links = discover_links_from_html("https://candidate-portfolio.com", html)

    assert len(links) == 1
    assert links[0].url == "https://candidate-portfolio.com/projects"


def test_preserve_and_clean_anchor_text():
    """Test that nested markup inside anchor tags is stripped and HTML entities unescaped."""
    html = """
    <a href="https://gitlab.com/user/project">
        <span>View &amp; Fork on <strong>GitLab</strong></span>
    </a>
    """
    links = discover_links_from_html("https://example.com", html)

    assert len(links) == 1
    assert links[0].anchor_text == "View & Fork on GitLab"


def test_respect_max_links_limit():
    """Test that discovery respects the max_links limit."""
    html = """
    <a href="https://site1.com">Site 1</a>
    <a href="https://site2.com">Site 2</a>
    <a href="https://site3.com">Site 3</a>
    <a href="https://site4.com">Site 4</a>
    """
    links = discover_links_from_html("https://example.com", html, max_links=2)

    assert len(links) == 2
    assert links[0].url == "https://site1.com"
    assert links[1].url == "https://site2.com"


def test_discovery_depth_increment():
    """Test that discovery depth is incremented correctly relative to source page depth."""
    html = '<a href="https://project.dev">Project</a>'

    depth_1_links = discover_links_from_html("https://example.com", html, current_depth=0)
    assert depth_1_links[0].discovery_depth == 1

    depth_2_links = discover_links_from_html("https://example.com/project", html, current_depth=1)
    assert depth_2_links[0].discovery_depth == 2


def test_deterministic_source_classification():
    """Test deterministic source type classification for common platforms."""
    assert classify_source_url("https://github.com/developer/repo") == "GITHUB"
    assert classify_source_url("https://gitlab.com/group/repo") == "GITLAB"
    assert classify_source_url("https://linkedin.com/in/candidate") == "LINKEDIN"
    assert classify_source_url("https://dev.to/candidate/article") == "BLOG"
    assert classify_source_url("https://docs.myproject.org/api") == "DOCS"
    assert classify_source_url("https://janes-portfolio.com/projects") == "PORTFOLIO"
    assert classify_source_url("https://random-service.io/data") == "OTHER"


@pytest.mark.asyncio
async def test_register_discovered_sources_integration():
    """Integration test: Register discovered links with tenant isolation and deduplication."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create organization, job, candidate, and application
        org_name = f"Link Discovery Org {uuid4()}"
        email = f"lead-{uuid4()}@discovery.com"
        password = "SecurePassword123!"

        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "full_name": "Discovery Lead",
                "organization_name": org_name,
            },
        )
        assert reg_resp.status_code == 201
        token = reg_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create Job
        job_resp = await client.post(
            "/api/v1/jobs",
            headers=headers,
            json={"title": "Software Engineer", "description": "Backend & AI"},
        )
        assert job_resp.status_code == 201
        job_id = job_resp.json()["id"]

        # Create Candidate
        cand_resp = await client.post(
            "/api/v1/candidates",
            headers=headers,
            json={
                "email": f"candidate-{uuid4()}@example.com",
                "full_name": "Applicant One",
            },
        )
        assert cand_resp.status_code == 201
        candidate_id = cand_resp.json()["id"]

        # Create Application
        app_resp = await client.post(
            "/api/v1/applications",
            headers=headers,
            json={
                "candidate_id": candidate_id,
                "job_id": job_id,
            },
        )
        assert app_resp.status_code == 201
        app_id = app_resp.json()["id"]

        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        org_id = me_resp.json()["organization_id"]

        # 1. Create an initial source (e.g. from resume)
        init_source_resp = await client.post(
            f"/api/v1/applications/{app_id}/sources",
            headers=headers,
            json={
                "url": "https://github.com/existing-user",
                "source_type": "GITHUB",
                "status": "DISCOVERED",
            },
        )
        assert init_source_resp.status_code == 201

        # 2. Batch of discovered links, including a duplicate of the existing GitHub URL
        discovered = [
            DiscoveredLink(
                url="https://github.com/existing-user",  # Duplicate of initial source
                anchor_text="GitHub",
                source_url="https://portfolio.com",
                discovery_depth=1,
                discovered_from="https://portfolio.com",
                source_type="GITHUB",
            ),
            DiscoveredLink(
                url="https://docs.myproject.io",  # New discovered source
                anchor_text="Project Docs",
                source_url="https://portfolio.com",
                discovery_depth=1,
                discovered_from="https://portfolio.com",
                source_type="DOCS",
            ),
            DiscoveredLink(
                url="https://docs.myproject.io",  # Duplicate within batch
                anchor_text="Project Docs Repetition",
                source_url="https://portfolio.com",
                discovery_depth=1,
                discovered_from="https://portfolio.com",
                source_type="DOCS",
            ),
        ]

        async with async_session_factory() as session:
            created = await register_discovered_sources(
                session=session,
                organization_id=org_id,
                application_id=app_id,
                discovered_links=discovered,
            )

        # Only the 1 new unique link should be registered
        assert len(created) == 1
        assert created[0].url == "https://docs.myproject.io"
        assert created[0].source_type == "DOCS"
        assert created[0].status == "DISCOVERED"
        assert created[0].discovery_depth == 1
        assert created[0].discovered_from == "https://portfolio.com"
        assert created[0].title == "Project Docs"

        # Verify total sources in database for this application is 2
        list_resp = await client.get(f"/api/v1/applications/{app_id}/sources", headers=headers)
        assert list_resp.status_code == 200
        sources_data = list_resp.json()
        assert len(sources_data) == 2
        urls = [s["url"] for s in sources_data]
        assert "https://github.com/existing-user" in urls
        assert "https://docs.myproject.io" in urls
