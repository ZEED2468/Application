"""Tiny pagination helper for the list endpoints.

Slices an already-built, filtered+sorted list into a page wrapper the frontend
DataTable understands. (Volumes are modest; SQL-level paging is a later optimization.)
"""

from __future__ import annotations

from fastapi import Query

PageParam = Query(default=1, ge=1, description="1-based page number")
PageSizeParam = Query(default=25, ge=1, le=100, description="items per page")


def paginate(items: list, page: int, page_size: int) -> dict:
    total = len(items)
    start = (page - 1) * page_size
    return {
        "items": items[start : start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
