"""user_llm_credential — a hunter's own (encrypted) LLM provider key (R1, BYO-key).

Per (user, provider). The API key is stored encrypted (see llm/crypto.py) and never
returned to the client. `is_preferred` marks the provider used to override env
resolution for that user's requests.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk


class UserLlmCredential(Base, TimestampMixin):
    __tablename__ = "user_llm_credential"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_llm_credential_user_provider"),
    )

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # anthropic|openai|google
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # configured | invalid | unreachable | unknown
    status: Mapped[str] = mapped_column(String(24), default="unknown", nullable=False)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
