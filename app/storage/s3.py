"""S3-compatible object storage backend.

Works against real AWS S3 or any S3-compatible provider (e.g. Cloudflare R2,
Backblaze B2) by setting `S3_ENDPOINT_URL`. This is the production
alternative to local disk storage - selected via STORAGE_BACKEND=s3, no
other code changes required.
"""
import uuid
from pathlib import Path

import boto3

from app.core.config import get_settings


def _get_client():
    settings = get_settings()
    kwargs = {
        "aws_access_key_id": settings.aws_access_key_id,
        "aws_secret_access_key": settings.aws_secret_access_key,
        "region_name": settings.aws_region,
    }
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    return boto3.client("s3", **kwargs)


def save_upload(filename: str, data: bytes) -> str:
    settings = get_settings()
    if not settings.aws_s3_bucket:
        raise RuntimeError(
            "AWS_S3_BUCKET is not set. Required when STORAGE_BACKEND=s3."
        )

    key = f"{uuid.uuid4().hex}_{Path(filename).name}"
    client = _get_client()
    client.put_object(Bucket=settings.aws_s3_bucket, Key=key, Body=data)
    return f"s3://{settings.aws_s3_bucket}/{key}"
