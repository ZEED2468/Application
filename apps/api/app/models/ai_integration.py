"""ai_integration — a user's configured AI provider connection (BYO-key, evolved).

Generalizes the earlier per-provider `user_llm_credential`: a user may have MANY
integrations (e.g. "Anthropic Prod", "My Local Ollama"), built from a template or
fully custom. The API key is stored encrypted (llm/crypto.py) and never returned in
plaintext. `is_default` marks the one the routing engine uses for that user.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk
from app.models.master_profile import JsonB


class AiIntegration(Base, TimestampMixin):
    __tablename__ = "ai_integration"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)  # display name
    # Adapter key the routing engine dispatches to: anthropic | openai | google.
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # The template it was created from (anthropic | google | openai | custom); label only.
    template: Mapped[str | None] = mapped_column(String(32), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)  # default model
    config: Mapped[dict] = mapped_column(JsonB, default=dict)  # extra (headers, auth, …)
    models: Mapped[list] = mapped_column(JsonB, default=list)  # available model ids
    capabilities: Mapped[dict] = mapped_column(JsonB, default=dict)
    # unknown | healthy | invalid | offline | rate_limited
    status: Mapped[str] = mapped_column(String(24), default="unknown", nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
