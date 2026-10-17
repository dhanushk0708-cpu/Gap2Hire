import sys
import pathlib
import pytest

# Ensure the project root (parent of the 'tests' folder) is on PYTHONPATH for imports
project_root = pathlib.Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.services.embedding_service import MockEmbeddingProvider, set_embedding_provider


@pytest.fixture(autouse=True)
def default_mock_embedding_provider():
    """
    Ensures unit tests never access external networks or load heavy transformer models by default.
    Tests testing real models or specific providers can override explicitly.
    """
    set_embedding_provider(MockEmbeddingProvider(dimension=384))
    yield
    set_embedding_provider(None)
