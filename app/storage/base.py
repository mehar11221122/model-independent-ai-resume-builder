from typing import Protocol


class StorageBackend(Protocol):
    def save_upload(self, filename: str, data: bytes) -> str:
        """Persist `data` and return a location identifier (path or object key)."""
        ...
