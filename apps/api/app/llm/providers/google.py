"""Google Gemini provider (Generative Language API), via httpx (no SDK)."""

from __future__ import annotations

import asyncio

import httpx

from app.llm.providers.base import register

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_MAX_RETRIES = 2
_RETRY_STATUS = {429, 500, 502, 503, 504}


def _extract_text(data: dict) -> str:
    """Pull the text out of a Gemini response, tolerating truncated/empty candidates
    (e.g. a tiny max_tokens ping yields a candidate with no content/parts)."""
    cand = (data.get("candidates") or [{}])[0]
    parts = (cand.get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts)


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
            for attempt in range(_MAX_RETRIES + 1):
                try:
                    resp = await client.post(url, json=body)
                    if resp.status_code in _RETRY_STATUS and attempt < _MAX_RETRIES:
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue
                    resp.raise_for_status()
                    return _extract_text(resp.json())
                except httpx.TransportError:
                    if attempt >= _MAX_RETRIES:
                        raise
                    await asyncio.sleep(0.5 * (2**attempt))
        raise RuntimeError("unreachable")
