import io
from pathlib import Path
from uuid import UUID, uuid4
import fitz
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.db.session import async_session_factory
from app.main import app
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.candidate_source import CandidateSource
from app.models.job import Job
from app.models.organization import Organization
from app.models.user import User
from app.services.candidate_sources import (
    ApplicationNotFoundError,
    list_candidate_sources,
)
from app.services.resume_url_discovery import (
    clean_url_string,
    discover_sources_from_resume_text,
    extract_urls_from_text,
    normalize_resume_url,
    sync_resume_candidate_sources,
)


@pytest.fixture(autouse=True)
def cleanup_uploaded_test_files():
    yield
    storage_path = Path(settings.storage_dir)
    if storage_path.exists():
        resumes_path = storage_path / "resumes"
        if resumes_path.exists():
            for file_path in resumes_path.glob("*"):
                if file_path.is_file():
                    try:
                        file_path.unlink()
                    except OSError:
                        pass


def create_sample_pdf_bytes(page_texts: list[str]) -> bytes:
    doc = fitz.open()
    for text in page_texts:
        page = doc.new_page()
        page.insert_text((50, 50), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


async def setup_test_tenant_and_application(client: AsyncClient):
    """Helper to create an organization, job, candidate, and application."""
    org_name = f"Discovery Corp {uuid4()}"
    email = f"manager-{uuid4()}@gap2hire.com"
    password = "SecurePassword123!"

    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Discovery Test Manager",
            "organization_name": org_name,
        },
    )
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    job_resp = await client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "title": "Backend AI Engineer",
            "description": "Python, FastAPI, LangGraph, LLMs",
        },
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    cand_resp = await client.post(
        "/api/v1/candidates",
        headers=headers,
        json={
            "email": f"cand-{uuid4()}@example.com",
            "full_name": "Test Candidate",
        },
    )
    assert cand_resp.status_code == 201
    candidate_id = cand_resp.json()["id"]

    app_resp = await client.post(
        "/api/v1/applications",
        headers=headers,
        json={
            "candidate_id": candidate_id,
            "job_id": job_id,
        },
    )
    assert app_resp.status_code == 201
    application_id = app_resp.json()["id"]

    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    org_id = me_resp.json()["organization_id"]

    return {
        "headers": headers,
        "organization_id": UUID(org_id),
        "job_id": UUID(job_id),
        "candidate_id": UUID(candidate_id),
        "application_id": UUID(application_id),
    }


# 1. One GitHub URL
def test_extract_one_github_url():
    text = "Candidate resume summary. Projects include https://github.com/octocat/Hello-World for testing."
    urls = extract_urls_from_text(text)
    assert urls == ["https://github.com/octocat/Hello-World"]
    sources = discover_sources_from_resume_text(text)
    assert len(sources) == 1
    assert sources[0].url == "https://github.com/octocat/Hello-World"
    assert sources[0].source_type == "GITHUB"
    assert sources[0].discovery_depth == 0
    assert sources[0].discovered_from == "RESUME"


# 2. Multiple arbitrary URLs
def test_extract_multiple_arbitrary_urls():
    text = """
    Jane Doe - Full Stack Developer
    Portfolio: https://janedoe.me/projects
    GitHub: https://github.com/janedoe/app
    GitLab: https://gitlab.com/janedoe/infra
    YouTube Demo: https://youtu.be/abc123xyz
    Research Paper: https://arxiv.org/abs/2301.00001
    Notion Site: https://janedoe.notion.site/portfolio
    """
    urls = extract_urls_from_text(text)
    assert len(urls) == 6
    assert "https://janedoe.me/projects" in urls
    assert "https://github.com/janedoe/app" in urls
    assert "https://gitlab.com/janedoe/infra" in urls
    assert "https://youtu.be/abc123xyz" in urls
    assert "https://arxiv.org/abs/2301.00001" in urls
    assert "https://janedoe.notion.site/portfolio" in urls


# 3. Unknown domain becomes OTHER
def test_unknown_domain_becomes_other():
    text = "Check out https://myportfolio.example and https://some-new-platform.example/profile/123."
    sources = discover_sources_from_resume_text(text)
    assert len(sources) == 2
    assert sources[0].url == "https://myportfolio.example"
    assert sources[0].source_type == "OTHER"
    assert sources[1].url == "https://some-new-platform.example/profile/123"
    assert sources[1].source_type == "OTHER"


# 4. Multiple known domains classify correctly
def test_multiple_known_domains_classification():
    text = """
    GitHub: https://github.com/user/repo
    GitHub Pages: https://user.github.io/blog
    GitLab: https://gitlab.com/user/repo
    Bitbucket: https://bitbucket.org/user/repo
    LinkedIn: https://linkedin.com/in/user
    Kaggle: https://www.kaggle.com/user/datasets
    Hugging Face: https://huggingface.co/models/nlp
    Devpost: https://devpost.com/software/my-hackathon
    YouTube: https://youtube.com/watch?v=12345
    YouTu.be: https://youtu.be/12345
    Medium: https://medium.com/@author/post
    Dev.to: https://dev.to/author/post
    Documentation: https://docs.myproject.org/guide
    Portfolio: https://user-portfolio.dev/projects
    """
    sources = discover_sources_from_resume_text(text)
    classified = {s.url: s.source_type for s in sources}
    assert classified["https://github.com/user/repo"] == "GITHUB"
    assert classified["https://user.github.io/blog"] == "GITHUB"
    assert classified["https://gitlab.com/user/repo"] == "GITLAB"
    assert classified["https://bitbucket.org/user/repo"] == "BITBUCKET"
    assert classified["https://linkedin.com/in/user"] == "LINKEDIN"
    assert classified["https://www.kaggle.com/user/datasets"] == "KAGGLE"
    assert classified["https://huggingface.co/models/nlp"] == "HUGGING_FACE"
    assert classified["https://devpost.com/software/my-hackathon"] == "DEVPOST"
    assert classified["https://youtube.com/watch?v=12345"] == "YOUTUBE"
    assert classified["https://youtu.be/12345"] == "YOUTUBE"
    assert classified["https://medium.com/@author/post"] == "BLOG"
    assert classified["https://dev.to/author/post"] == "BLOG"
    assert classified["https://docs.myproject.org/guide"] == "DOCS"
    assert classified["https://user-portfolio.dev/projects"] == "PORTFOLIO"


# 5. Trailing punctuation removed & balanced parens preserved
def test_trailing_punctuation_and_brackets_removal():
    test_cases = [
        ("https://example.com/project.", "https://example.com/project"),
        ("https://github.com/user/repo)", "https://github.com/user/repo"),
        ("[GitHub](https://github.com/user/repo)", "https://github.com/user/repo"),
        ("(https://example.com/docs)", "https://example.com/docs"),
        ("<https://example.com/api>", "https://example.com/api"),
        ("https://example.com/repo,", "https://example.com/repo"),
        ("https://example.com/repo;", "https://example.com/repo"),
        ("https://example.com/repo:", "https://example.com/repo"),
        ("https://example.com/repo!", "https://example.com/repo"),
        ("https://example.com/repo?", "https://example.com/repo"),
        ("https://example.com/repo).", "https://example.com/repo"),
        ("https://en.wikipedia.org/wiki/Python_(programming_language)", "https://en.wikipedia.org/wiki/Python_(programming_language)"),
        ("(https://en.wikipedia.org/wiki/Python_(programming_language))", "https://en.wikipedia.org/wiki/Python_(programming_language)"),
    ]

    for raw, expected in test_cases:
        extracted = extract_urls_from_text(f"Text containing {raw} in sentence.")
        assert extracted == [expected], f"Failed for raw input: {raw}"


# 6. Duplicate URLs deduplicated
def test_duplicate_urls_deduplicated():
    text = """
    Projects:
    - https://github.com/user/project
    - Description of https://github.com/user/project
    - See also (https://github.com/user/project).
    """
    urls = extract_urls_from_text(text)
    assert len(urls) == 1
    assert urls[0] == "https://github.com/user/project"


# 7. Unsupported schemes rejected
def test_unsupported_schemes_rejected():
    text = """
    Contact: mailto:dev@example.com
    Script: javascript:alert(1)
    Phone: tel:+1234567890
    FTP Server: ftp://files.example.com/archive.zip
    Local File: file:///C:/secret/passwords.txt
    Data URI: data:text/html,<h1>Hello</h1>
    Gopher: gopher://gopher.example.com
    Valid: https://example.com/legitimate
    """
    urls = extract_urls_from_text(text)
    assert urls == ["https://example.com/legitimate"]
    assert normalize_resume_url("mailto:test@example.com") is None
    assert normalize_resume_url("javascript:void(0)") is None
    assert normalize_resume_url("ftp://ftp.example.com") is None


# 8. URL path and query preserved, fragments stripped
def test_url_path_and_query_preserved():
    text = "Visit https://example.com/search?query=machine+learning&sort=stars#results-heading for results."
    urls = extract_urls_from_text(text)
    assert urls == ["https://example.com/search?query=machine+learning&sort=stars"]


# 9. No URLs produces no sources
def test_no_urls_produces_no_sources():
    text = "Experienced software engineer with 5 years in Python, SQL, and system design. No external links here."
    urls = extract_urls_from_text(text)
    assert urls == []
    sources = discover_sources_from_resume_text(text)
    assert sources == []


# 10. CandidateSource registration works with correct metadata
@pytest.mark.asyncio
async def test_candidate_source_registration_db():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        setup = await setup_test_tenant_and_application(client)
        org_id = setup["organization_id"]
        app_id = setup["application_id"]

        resume_text = """
        John Doe Resume
        GitHub: https://github.com/johndoe/project-ai
        Portfolio: https://johndoe-portfolio.dev
        """

        async with async_session_factory() as session:
            sources = await sync_resume_candidate_sources(
                session=session,
                organization_id=org_id,
                application_id=app_id,
                resume_text=resume_text,
            )
            assert len(sources) == 2
            for src in sources:
                assert src.application_id == app_id
                assert src.discovered_from == "RESUME"
                assert src.discovery_depth == 0
                assert src.status == "DISCOVERED"

            listed = await list_candidate_sources(session, org_id, app_id)
            assert len(listed) == 2
            urls = {s.url for s in listed}
            assert "https://github.com/johndoe/project-ai" in urls
            assert "https://johndoe-portfolio.dev" in urls


# 11. Repeated resume processing does not create duplicates (idempotency)
@pytest.mark.asyncio
async def test_repeated_processing_idempotency():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        setup = await setup_test_tenant_and_application(client)
        org_id = setup["organization_id"]
        app_id = setup["application_id"]

        resume_text = "GitHub: https://github.com/johndoe/single-repo"

        async with async_session_factory() as session:
            first_run = await sync_resume_candidate_sources(
                session=session,
                organization_id=org_id,
                application_id=app_id,
                resume_text=resume_text,
            )
            assert len(first_run) == 1

            second_run = await sync_resume_candidate_sources(
                session=session,
                organization_id=org_id,
                application_id=app_id,
                resume_text=resume_text,
            )
            assert len(second_run) == 0  # No new sources added

            listed = await list_candidate_sources(session, org_id, app_id)
            assert len(listed) == 1
            assert listed[0].url == "https://github.com/johndoe/single-repo"


# 12. Tenant isolation enforced
@pytest.mark.asyncio
async def test_tenant_isolation_enforced():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        tenant1 = await setup_test_tenant_and_application(client)
        tenant2 = await setup_test_tenant_and_application(client)

        async with async_session_factory() as session:
            with pytest.raises(ApplicationNotFoundError):
                # Tenant 2 tries to sync sources for Tenant 1's application
                await sync_resume_candidate_sources(
                    session=session,
                    organization_id=tenant2["organization_id"],
                    application_id=tenant1["application_id"],
                    resume_text="https://github.com/sneaky/repo",
                )


# 13. Cross-application isolation
@pytest.mark.asyncio
async def test_cross_application_isolation():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        setup = await setup_test_tenant_and_application(client)
        headers = setup["headers"]
        org_id = setup["organization_id"]
        app1_id = setup["application_id"]

        # Create candidate 2 and application 2 under same organization
        cand2_resp = await client.post(
            "/api/v1/candidates",
            headers=headers,
            json={"email": f"cand2-{uuid4()}@example.com", "full_name": "Candidate Two"},
        )
        cand2_id = cand2_resp.json()["id"]

        app2_resp = await client.post(
            "/api/v1/applications",
            headers=headers,
            json={"candidate_id": cand2_id, "job_id": str(setup["job_id"])},
        )
        app2_id = UUID(app2_resp.json()["id"])

        shared_url = "https://github.com/shared-org/shared-project"

        async with async_session_factory() as session:
            # Sync for App 1
            await sync_resume_candidate_sources(
                session=session,
                organization_id=org_id,
                application_id=app1_id,
                resume_text=f"App1 resume: {shared_url}",
            )
            # Sync for App 2
            await sync_resume_candidate_sources(
                session=session,
                organization_id=org_id,
                application_id=app2_id,
                resume_text=f"App2 resume: {shared_url}",
            )

            app1_sources = await list_candidate_sources(session, org_id, app1_id)
            app2_sources = await list_candidate_sources(session, org_id, app2_id)

            assert len(app1_sources) == 1
            assert len(app2_sources) == 1
            assert app1_sources[0].application_id == app1_id
            assert app2_sources[0].application_id == app2_id
            assert app1_sources[0].id != app2_sources[0].id


# 14. Integration test: upload resume PDF -> process -> verify sources via API
@pytest.mark.asyncio
async def test_integration_resume_process_endpoint_registers_sources():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        setup = await setup_test_tenant_and_application(client)
        headers = setup["headers"]
        app_id = setup["application_id"]

        resume_page = """
        Jane Candidate
        Backend Developer
        Projects:
        - Inslight: https://github.com/janecand/Inslight
        - Live Demo: https://inslight-demo.example.com
        - LinkedIn: https://linkedin.com/in/janecand
        """
        pdf_bytes = create_sample_pdf_bytes([resume_page])

        # Upload resume
        files = {"file": ("resume.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        upload_res = await client.post(
            f"/api/v1/applications/{app_id}/resume",
            headers=headers,
            files=files,
        )
        assert upload_res.status_code == 200

        # Process resume text
        process_res = await client.post(
            f"/api/v1/applications/{app_id}/resume/process",
            headers=headers,
        )
        assert process_res.status_code == 200

        # Query sources endpoint
        sources_res = await client.get(
            f"/api/v1/applications/{app_id}/sources",
            headers=headers,
        )
        assert sources_res.status_code == 200
        sources = sources_res.json()
        assert len(sources) == 3

        sources_by_url = {s["url"]: s for s in sources}
        assert "https://github.com/janecand/Inslight" in sources_by_url
        assert sources_by_url["https://github.com/janecand/Inslight"]["source_type"] == "GITHUB"
        assert sources_by_url["https://github.com/janecand/Inslight"]["discovered_from"] == "RESUME"
        assert sources_by_url["https://github.com/janecand/Inslight"]["discovery_depth"] == 0
        assert sources_by_url["https://github.com/janecand/Inslight"]["status"] == "DISCOVERED"

        assert "https://inslight-demo.example.com" in sources_by_url
        assert sources_by_url["https://inslight-demo.example.com"]["source_type"] == "OTHER"
        assert sources_by_url["https://inslight-demo.example.com"]["discovered_from"] == "RESUME"
        assert sources_by_url["https://inslight-demo.example.com"]["discovery_depth"] == 0

        assert "https://linkedin.com/in/janecand" in sources_by_url
        assert sources_by_url["https://linkedin.com/in/janecand"]["source_type"] == "LINKEDIN"
        assert sources_by_url["https://linkedin.com/in/janecand"]["discovered_from"] == "RESUME"
        assert sources_by_url["https://linkedin.com/in/janecand"]["discovery_depth"] == 0


# 15. Real test data: Dhanush application (591ea6bb-cfa3-4c97-a5b5-9e6c6d031f5c)
@pytest.mark.asyncio
async def test_real_dhanush_application_source_discovery():
    dhanush_app_id = UUID("591ea6bb-cfa3-4c97-a5b5-9e6c6d031f5c")

    async with async_session_factory() as session:
        stmt = (
            select(Application, Job)
            .join(Job, Job.id == Application.job_id)
            .where(Application.id == dhanush_app_id)
        )
        res = (await session.execute(stmt)).first()
        if not res:
            pytest.skip("Real Dhanush application record not in test DB environment")

        app_obj, job_obj = res
        org_id = job_obj.organization_id

        # Sync resume candidate sources from the existing resume text
        sources = await sync_resume_candidate_sources(
            session=session,
            organization_id=org_id,
            application_id=dhanush_app_id,
            resume_text=app_obj.resume_text,
        )

        # Retrieve registered sources
        all_sources = await list_candidate_sources(session, org_id, dhanush_app_id)
        inslight_src = next(
            (s for s in all_sources if s.url == "https://github.com/dhanushk0708-cpu/Inslight"),
            None,
        )

        assert inslight_src is not None, "Expected Inslight GitHub URL to be registered as CandidateSource"
        assert inslight_src.source_type == "GITHUB"
        assert inslight_src.discovered_from == "RESUME"
        assert inslight_src.discovery_depth == 0
        assert inslight_src.status == "DISCOVERED"
