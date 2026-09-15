from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings


class BaseStorageService(ABC):
    @abstractmethod
    async def save_file(self, file_bytes: bytes, destination_key: str) -> str:
        """Saves file bytes under a relative destination key and returns the storage reference key."""
        pass

    @abstractmethod
    async def read_file(self, destination_key: str) -> bytes:
        """Reads and returns file bytes for a relative destination key."""
        pass

    @abstractmethod
    async def delete_file(self, destination_key: str) -> bool:
        """Deletes a file given its storage reference key."""
        pass


class LocalStorageService(BaseStorageService):
    def __init__(self, base_dir: str | Path | None = None):
        if base_dir is None:
            base_dir = Path(settings.storage_dir)
        self.base_dir = Path(base_dir).resolve()

    async def save_file(self, file_bytes: bytes, destination_key: str) -> str:
        target_path = (self.base_dir / destination_key).resolve()
        if not str(target_path).startswith(str(self.base_dir)):
            raise ValueError("Invalid storage path")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(file_bytes)
        return destination_key.replace("\\", "/")

    async def read_file(self, destination_key: str) -> bytes:
        target_path = (self.base_dir / destination_key).resolve()
        if not str(target_path).startswith(str(self.base_dir)) or not target_path.exists():
            raise FileNotFoundError("Storage file not found")
        return target_path.read_bytes()

    async def delete_file(self, destination_key: str) -> bool:
        target_path = (self.base_dir / destination_key).resolve()
        if not str(target_path).startswith(str(self.base_dir)):
            return False
        if target_path.exists():
            target_path.unlink()
            return True
        return False


default_storage_service = LocalStorageService()
