from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.core.config import get_settings


class StorageAdapter(Protocol):
    async def save(self, filename: str, data: bytes) -> str:
        ...

    async def read(self, path: str) -> bytes:
        ...


class LocalStorageAdapter:
    def __init__(self, base_path: Path) -> None:
        self._base_path = base_path
        self._base_path.mkdir(parents=True, exist_ok=True)

    async def save(self, filename: str, data: bytes) -> str:
        target = self._base_path / filename
        target.write_bytes(data)
        return str(target)

    async def read(self, path: str) -> bytes:
        target = Path(path)
        return target.read_bytes()


class StorageFactory:
    @staticmethod
    def create() -> StorageAdapter:
        settings = get_settings()
        provider = settings.storage_provider
        if provider == "local":
            return LocalStorageAdapter(Path(settings.storage_local_path))
        raise ValueError(f"Unsupported storage provider: {provider}")
