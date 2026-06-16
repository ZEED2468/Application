"""UUIDv7 helpers (time-sortable primary keys)."""

import uuid

try:
    from uuid_extensions import uuid7  # provided by the `uuid7` package
except ImportError:  # pragma: no cover - fallback for environments without uuid7
    def uuid7() -> uuid.UUID:
        return uuid.uuid4()


def new_id() -> uuid.UUID:
    return uuid7()
