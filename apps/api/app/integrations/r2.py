"""Cloudflare R2 (S3-compatible) object storage.

Fake mode writes to a local directory so the pipeline runs without cloud creds.
Live mode uses boto3 against the R2 S3 endpoint. R2 objects are PRIVATE, so the DB
stores the object KEY (the canonical recovery handle) and downloads are served via
short-lived presigned URLs generated on demand.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import structlog

from app.config import settings
from app.core.errors import DomainError

log = structlog.get_logger(__name__)

_LOCAL_ROOT = Path(__file__).resolve().parents[2] / ".r2store"


def is_live() -> bool:
    """True when real R2 credentials are configured (and fakes are off)."""
    return not settings.use_fake_integrations and bool(settings.r2_endpoint)


def _client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        region_name="auto",  # required for Cloudflare R2
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
    )


async def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Store bytes under `key`; return a reference (the key is the canonical handle)."""
    if not is_live():
        path = _LOCAL_ROOT / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path.as_uri()

    def _put() -> None:
        _client().put_object(
            Bucket=settings.r2_bucket, Key=key, Body=data, ContentType=content_type
        )

    try:
        await asyncio.to_thread(_put)  # boto3 is blocking — keep the event loop free
    except Exception as exc:  # noqa: BLE001 — surface a clean, diagnosable error
        log.warning("r2.put_failed", key=key, bucket=settings.r2_bucket,
                    endpoint=settings.r2_endpoint, error=str(exc),
                    exc_type=type(exc).__name__)
        raise DomainError(
            f"Storage upload failed ({type(exc).__name__}): {str(exc)[:200]}. "
            "Check the R2 bucket name, endpoint, and access keys."
        ) from exc
    return f"{settings.r2_endpoint}/{settings.r2_bucket}/{key}"


async def get_bytes(key: str) -> bytes | None:
    """Fetch the stored bytes for `key`, or None if missing (used by fake-mode serving)."""
    if not is_live():
        path = _LOCAL_ROOT / key
        return path.read_bytes() if path.exists() else None

    def _get() -> bytes | None:
        try:
            resp = _client().get_object(Bucket=settings.r2_bucket, Key=key)
            return resp["Body"].read()
        except Exception as exc:  # noqa: BLE001
            log.warning("r2.get_failed", key=key, error=str(exc))
            return None

    return await asyncio.to_thread(_get)


def presigned_url(
    key: str, *, expires: int = 3600, filename: str | None = None, inline: bool = True
) -> str | None:
    """A short-lived download URL for `key` (live only); None in fake mode.

    `generate_presigned_url` is a local signing operation (no network call), so it's
    safe to call synchronously. If `R2_PUBLIC_BASE_URL` is configured, returns a direct
    public URL instead.
    """
    if settings.r2_public_base_url:
        return f"{settings.r2_public_base_url.rstrip('/')}/{key}"
    if not is_live():
        return None
    params: dict = {"Bucket": settings.r2_bucket, "Key": key}
    if filename:
        disp = "inline" if inline else "attachment"
        params["ResponseContentDisposition"] = f'{disp}; filename="{filename}"'
    try:
        return _client().generate_presigned_url("get_object", Params=params, ExpiresIn=expires)
    except Exception as exc:  # noqa: BLE001
        log.warning("r2.presign_failed", key=key, error=str(exc))
        return None
