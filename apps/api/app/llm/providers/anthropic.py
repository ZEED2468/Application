"""Anthropic provider (Claude). Uses the official SDK."""

from __future__ import annotations

from app.llm.providers.base import register


@register
class AnthropicProvider:
    name = "anthropic"
    requires_key = True
    default_model = "claude-opus-4-8"

    async def complete(
        self, *, system: str, prompt: str, model: str, api_key: str, base_url: str,
        max_tokens: int,
    ) -> str:
        from anthropic import AsyncAnthropic

        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = AsyncAnthropic(**kwargs)
        msg = await client.messages.create(
            model=model or self.default_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if b.type == "text")
