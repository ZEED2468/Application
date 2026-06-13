"""Cloudflare R2 (S3-compatible) object storage.

Fake mode writes to a local directory and returns file:// URLs so the whole
pipeline runs without cloud credentials.
"""

from __future__ import annotations

from pathlib import Path

from app.config import settings

_LOCAL_ROOT = Path(__file__).resolve().parents[2] / ".r2store"


async def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Store bytes under `key`; return a retrievable URL."""
    if settings.use_fake_integrations or not settings.r2_endpoint:
        path = _LOCAL_ROOT / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path.as_uri()

    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
    )
    client.put_object(Bucket=settings.r2_bucket, Key=key, Body=data, ContentType=content_type)
    return f"{settings.r2_endpoint}/{settings.r2_bucket}/{key}"
