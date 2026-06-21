"""Serve an R2-stored object: presigned redirect (live) or streamed bytes (fake/dev)."""

from __future__ import annotations

from fastapi import Response
from fastapi.responses import RedirectResponse, StreamingResponse

from app.core.errors import NotFoundError
from app.integrations import r2


async def serve_key(
    key: str | None, *, filename: str, content_type: str = "application/pdf",
    inline: bool = True,
) -> Response:
    """Return a response that yields the object at `key`.

    Live R2: 307-redirect to a short-lived presigned URL (the browser, carrying its
    first-party backend cookie on the original request, follows it to R2). Fake/dev:
    stream the locally-stored bytes. 404 when the key is missing or empty.
    """
    if not key:
        raise NotFoundError("File not found")
    url = r2.presigned_url(key, filename=filename, inline=inline)
    if url:
        return RedirectResponse(url, status_code=307)
    data = await r2.get_bytes(key)
    if data is None:
        raise NotFoundError("File not found")
    disposition = "inline" if inline else "attachment"
    return StreamingResponse(
        iter([data]),
        media_type=content_type,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )
