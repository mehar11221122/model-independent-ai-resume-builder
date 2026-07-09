from app.core.config import get_settings


def save_upload(filename: str, data: bytes) -> str:
    """Persist an uploaded file via the configured backend and return its
    location (a local path or an s3:// URI)."""
    settings = get_settings()

    if settings.storage_backend == "s3":
        from app.storage.s3 import save_upload as _save

        return _save(filename, data)

    from app.storage.local import save_upload as _save

    return _save(filename, data)
