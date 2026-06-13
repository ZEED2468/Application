"""Job sources. Importing this package registers every adapter in the registry."""

from app.sources import adzuna, ashby, greenhouse, lever, serpapi_jobs  # noqa: F401
from app.sources.base import (
    SOURCES,
    JobSource,
    RawJob,
    SourceQuery,
    active_sources,
    register,
)

__all__ = [
    "SOURCES",
    "JobSource",
    "RawJob",
    "SourceQuery",
    "active_sources",
    "register",
]
