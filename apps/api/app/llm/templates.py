"""Built-in AI provider templates — convenience presets, not runtime specials.

Each template is metadata: which adapter it maps to, a config-field schema the
frontend renders forms from (so no provider-specific frontend code), and whether the
provider supports model discovery. Custom integrations use the openai-compatible
adapter with a user-supplied base_url.
"""

from __future__ import annotations


def _field(fid, label, ftype, *, required=False, placeholder="", help=""):
    return {"id": fid, "label": label, "type": ftype, "required": required,
            "placeholder": placeholder, "help": help}


_API_KEY = _field("api_key", "API key", "password", required=True, placeholder="sk-…")

TEMPLATES: list[dict] = [
    {
        "id": "anthropic",
        "name": "Anthropic (Claude)",
        "provider": "anthropic",
        "icon": "🅰️",
        "description": "Claude models via the Anthropic API.",
        "fields": [_field("api_key", "API key", "password", required=True, placeholder="sk-ant-…")],
        "default_model": "claude-opus-4-8",
        "discovery": False,
    },
    {
        "id": "google",
        "name": "Google Gemini",
        "provider": "google",
        "icon": "🇬",
        "description": "Gemini models via the Google Generative Language API.",
        "fields": [_API_KEY],
        "default_model": "gemini-2.0-flash",
        "discovery": True,
    },
    {
        "id": "openai",
        "name": "OpenAI-compatible",
        "provider": "openai",
        "icon": "🤖",
        "description": "OpenAI, Groq, Together, OpenRouter, or a local Ollama / LM Studio — set the base URL.",
        "fields": [
            _field("api_key", "API key", "password", placeholder="sk-… (blank for keyless local)"),
            _field("base_url", "Base URL", "url", placeholder="https://api.groq.com/openai/v1"),
            _field("model", "Default model", "text", placeholder="leave blank for the provider default"),
        ],
        "default_model": "gpt-4o-mini",
        "discovery": True,
    },
    {
        "id": "custom",
        "name": "Custom (OpenAI-compatible)",
        "provider": "openai",
        "icon": "🧩",
        "description": "Any OpenAI-compatible endpoint — full control over name, URL, key, and model.",
        "fields": [
            _field("name", "Integration name", "text", required=True, placeholder="My Local Ollama"),
            _field("base_url", "Base URL", "url", required=True, placeholder="http://localhost:11434/v1"),
            _field("api_key", "API key", "password", placeholder="blank for keyless local servers"),
            _field("model", "Default model", "text", placeholder="e.g. llama3.1"),
        ],
        "default_model": "",
        "discovery": True,
    },
]

_BY_ID = {t["id"]: t for t in TEMPLATES}


def get_templates() -> list[dict]:
    return TEMPLATES


def get_template(template_id: str) -> dict | None:
    return _BY_ID.get(template_id)
