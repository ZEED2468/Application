"""OpenAI-compatible provider (Chat Completions API).

One adapter, many backends: set `base_url` to point at OpenAI, Groq, Together,
OpenRouter, or a local Ollama/LM Studio/vLLM server. `requires_key=False` so a
keyless local server works.
"""

from __future__ import annotations

import asyncio

import httpx

from app.llm.providers.base import register

DEFAULT_BASE_URL = "https://api.openai.com/v1"
_MAX_RETRIES = 2
_RETRY_STATUS = {429, 500, 502, 503, 504}


@register
class OpenAICompatProvider:
    name = "openai"
    requires_key = False  # local servers (Ollama/LM Studio) need no key
    default_model = "gpt-4o-mini"

    async def complete(
        self, *, system: str, prompt: str, model: str, api_key: str, base_url: str,
        max_tokens: int,
    ) -> str:
        url = f"{(base_url or DEFAULT_BASE_URL).rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        body = {
            "model": model or self.default_model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            for attempt in range(_MAX_RETRIES + 1):
                try:
                    resp = await client.post(url, headers=headers, json=body)
                    if resp.status_code in _RETRY_STATUS and attempt < _MAX_RETRIES:
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue
                    resp.raise_for_status()
                    return resp.json()["choices"][0]["message"]["content"]
                except httpx.TransportError:
                    if attempt >= _MAX_RETRIES:
                        raise
                    await asyncio.sleep(0.5 * (2**attempt))
        raise RuntimeError("unreachable")
