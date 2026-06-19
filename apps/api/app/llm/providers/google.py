"""Google Gemini provider (Generative Language API), via httpx (no SDK)."""

from __future__ import annotations

import httpx

from app.llm.providers.base import register

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


@register
class GoogleProvider:
    name = "google"
    requires_key = True
    default_model = "gemini-2.0-flash"

    async def complete(
        self, *, system: str, prompt: str, model: str, api_key: str, base_url: str,
        max_tokens: int,
    ) -> str:
        m = model or self.default_model
        base = (base_url or DEFAULT_BASE_URL).rstrip("/")
        url = f"{base}/models/{m}:generateContent?key={api_key}"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
