import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from app.schemas.source_inspection import InspectionResult
from app.services.source_inspection import SourceInspector

logger = logging.getLogger(__name__)

# Deterministic safety bounds for deep artifact inspection
MAX_ARTIFACTS_PER_SOURCE: int = 5
ALLOWED_GITHUB_BRANCHES: tuple[str, ...] = ("main", "master", "HEAD")


class InspectableArtifact(BaseModel):
    """
    Represents an individual inspectable artifact discovered within a candidate source.
    """
    name: str
    artifact_type: str  # "DOCUMENTATION", "DEPENDENCIES", "CONFIGURATION", "SOURCE_CODE", "OTHER"
    url: str
    relevance: str
    content: Optional[str] = None
    is_inspected: bool = False
    is_success: bool = False
    error: Optional[str] = None


class BaseSourceAdapter(ABC):
    """
    Abstract adapter interface for discovering and inspecting source-specific artifacts.
    """

    @abstractmethod
    def can_handle(self, url: str, source_type: str) -> bool:
        """Determines whether this adapter handles the given source URL / type."""
        pass

    @abstractmethod
    def discover_artifacts(
        self, url: str, source_type: str, max_artifacts: int = MAX_ARTIFACTS_PER_SOURCE
    ) -> list[InspectableArtifact]:
        """Discovers inspectable artifacts belonging to the source under safety limits."""
        pass


class GitHubSourceAdapter(BaseSourceAdapter):
    """
    Deep source adapter for public GitHub repositories.
    Extracts high-signal repository artifacts (e.g. pyproject.toml, requirements.txt,
    README.md, package.json, Dockerfile, main source entry points) under deterministic bounds.
    """

    # Bounded candidate artifact filenames in order of signal value
    CANDIDATE_FILES: list[tuple[str, str, str]] = [
        ("pyproject.toml", "DEPENDENCIES", "Python project metadata and declared dependencies"),
        ("requirements.txt", "DEPENDENCIES", "Python pip dependencies and library versions"),
        ("package.json", "DEPENDENCIES", "Node/JS/TS dependencies and scripts"),
        ("README.md", "DOCUMENTATION", "Project overview, architecture, and technology description"),
        ("Dockerfile", "CONFIGURATION", "Containerization and runtime environment configuration"),
        ("app/main.py", "SOURCE_CODE", "FastAPI / Python backend application entry point"),
        ("main.py", "SOURCE_CODE", "Primary Python application entry point"),
    ]

    def can_handle(self, url: str, source_type: str) -> bool:
        if source_type.upper() in {"GITHUB", "GITLAB"}:
            return True
        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            return host == "github.com" or host.endswith(".github.com") or host == "raw.githubusercontent.com"
        except Exception:
            return False

    def _extract_repo_coordinates(self, url: str) -> Optional[tuple[str, str]]:
        """
        Extracts (owner, repo) from a GitHub repository URL.
        Disallows system paths, settings, credentials, or arbitrary queries.
        """
        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 2:
                owner, repo = parts[0], parts[1]
                # Strip .git suffix if present
                if repo.endswith(".git"):
                    repo = repo[:-4]
                # Disallow invalid characters or system pages
                if re.match(r"^[A-Za-z0-9_.-]+$", owner) and re.match(r"^[A-Za-z0-9_.-]+$", repo):
                    if owner.lower() not in {"settings", "organizations", "features", "explore", "topics"}:
                        return owner, repo
            return None
        except Exception:
            return None

    def discover_artifacts(
        self, url: str, source_type: str, max_artifacts: int = MAX_ARTIFACTS_PER_SOURCE
    ) -> list[InspectableArtifact]:
        coords = self._extract_repo_coordinates(url)
        if not coords:
            return []

        owner, repo = coords
        artifacts: list[InspectableArtifact] = []

        # Generate bounded list of inspectable artifacts targeting raw public GitHub files
        for filename, art_type, relevance in self.CANDIDATE_FILES:
            if len(artifacts) >= max_artifacts:
                break

            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{filename}"
            artifacts.append(
                InspectableArtifact(
                    name=filename,
                    artifact_type=art_type,
                    url=raw_url,
                    relevance=relevance,
                )
            )

        return artifacts


class GenericWebSourceAdapter(BaseSourceAdapter):
    """
    Fallback adapter for generic web pages, portfolios, blogs, and documentation.
    """

    def can_handle(self, url: str, source_type: str) -> bool:
        return True

    def discover_artifacts(
        self, url: str, source_type: str, max_artifacts: int = MAX_ARTIFACTS_PER_SOURCE
    ) -> list[InspectableArtifact]:
        # Generic sources are single-page documents with possible outbound links
        return [
            InspectableArtifact(
                name="page_content",
                artifact_type="DOCUMENTATION",
                url=url,
                relevance="Main public page content",
            )
        ]


# Registered adapters in evaluation precedence
ADAPTERS: list[BaseSourceAdapter] = [
    GitHubSourceAdapter(),
    GenericWebSourceAdapter(),
]


def discover_source_artifacts(
    url: str, source_type: str, max_artifacts: int = MAX_ARTIFACTS_PER_SOURCE
) -> list[InspectableArtifact]:
    """
    Discovers high-signal inspectable artifacts for a candidate source URL using the appropriate adapter.
    """
    for adapter in ADAPTERS:
        if adapter.can_handle(url, source_type):
            return adapter.discover_artifacts(url, source_type, max_artifacts=max_artifacts)
    return []


async def inspect_source_artifacts(
    artifacts: list[InspectableArtifact],
    inspector: Optional[SourceInspector] = None,
) -> list[InspectableArtifact]:
    """
    Safely inspects a list of discovered artifacts using SourceInspector,
    populating their content and status under SSRF protection, size caps, and timeouts.
    If 'main' branch returns 404 on GitHub, automatically attempts 'master'.
    """
    insp = inspector or SourceInspector()
    inspected_results: list[InspectableArtifact] = []

    for art in artifacts:
        try:
            res: InspectionResult = await insp.inspect(art.url)
            
            # If 404 and URL was a GitHub raw URL with 'main', fallback to 'master'
            if not res.is_success and "/main/" in art.url and res.http_status == 404:
                master_url = art.url.replace("/main/", "/master/")
                master_res = await insp.inspect(master_url)
                if master_res.is_success:
                    art.url = master_url
                    res = master_res

            art.is_inspected = True
            art.is_success = res.is_success
            if res.is_success:
                art.content = res.extracted_text or ""
            else:
                art.error = res.error_message or "Failed to inspect artifact"

        except Exception as e:
            logger.warning(f"Error inspecting artifact {art.name} at {art.url}: {e}")
            art.is_inspected = True
            art.is_success = False
            art.error = str(e)

        inspected_results.append(art)

    return inspected_results


async def deep_inspect_candidate_source(
    url: str,
    source_type: str,
    max_artifacts: int = MAX_ARTIFACTS_PER_SOURCE,
    inspector: Optional[SourceInspector] = None,
) -> dict[str, Any]:
    """
    High-level helper: discovers and safely inspects artifacts for a CandidateSource.
    Returns structured results including all successfully fetched artifact contents.
    """
    artifacts = discover_source_artifacts(url, source_type, max_artifacts=max_artifacts)
    inspected = await inspect_source_artifacts(artifacts, inspector=inspector)
    successful = [a for a in inspected if a.is_success and a.content]

    return {
        "url": url,
        "source_type": source_type,
        "artifacts_discovered": len(artifacts),
        "artifacts_inspected": len(inspected),
        "successful_artifacts": len(successful),
        "artifacts": [a.model_dump() for a in inspected],
        "combined_artifact_text": "\n\n---\n\n".join(
            f"=== Artifact: {a.name} ({a.artifact_type}) ===\n{a.content}" for a in successful
        ),
    }
