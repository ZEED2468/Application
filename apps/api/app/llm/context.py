"""Per-request LLM credential override (R1 BYO-key).

A ContextVar holds the current user's resolved LLM override ({provider, model,
api_key, base_url}) so `config.resolve()` can prefer it without threading a param
through every LLM call site. Set by the `bind_user_llm` dependency on the request;
empty in background/Celery tasks (which fall back to env). No imports from `config`
to avoid a cycle.
"""

from __future__ import annotations

import contextvars

_user_llm: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "user_llm", default=None
)


def set_user_llm(override: dict | None):
    return _user_llm.set(override)


def get_user_llm() -> dict | None:
    return _user_llm.get()


def reset_user_llm(token) -> None:
    _user_llm.reset(token)
