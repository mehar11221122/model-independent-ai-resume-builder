"""Local filesystem storage backend.

S3 is the production alternative called out in the scope doc; swapping to it
means implementing the same two functions against boto3 and flipping
STORAGE_BACKEND=s3 - nothing else in the app changes.
"""
import uuid
from pathlib import Path

from app.core.config import get_settings


def save_upload(filename: str, data: bytes) -> str:
    settings = get_settings()
    upload_dir = Path(settings.local_storage_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}_{Path(filename).name}"
    path = upload_dir / safe_name
    path.write_bytes(data)
    return str(path)
