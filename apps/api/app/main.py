"""FastAPI application factory."""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.config import settings
from app.core.errors import DomainError

API_VERSION = "1.0.0"

API_DESCRIPTION = """
Backend for the **Job Application & Outreach Engine** — a conversion-optimized,
multi-user job-application + outreach pipeline.

### Auth
Most endpoints require an authenticated principal. Logging in via
`POST /api/auth/login` sets an **httpOnly `access_token` cookie** (+ a rotating
refresh token); subsequent requests are authenticated by that cookie. The web app
proxies the cookie server-side. Webhooks (`/api/webhooks/*`) and the WhatsApp
bridge authenticate with an **HMAC signature**, not the cookie.

### Pipelines
- **Apply** — discover → score → track-classify → tailor (truth-bounded) → render → submit.
- **Outreach** — Apollo lookup → hook → draft → governed send → follow-up sequencer.
- **Respond** — match reply → classify → dossier → WhatsApp bridge → relay.
- **Manual** — VA chatbot: paste JD → match CV → ATS gaps → confirm-true → generate.

### Dev mode
With `USE_FAKE_INTEGRATIONS=true` every external dependency (LLM, email, Apollo,
R2, WhatsApp) is faked, so the whole API runs with no credentials.
"""

TAGS_METADATA = [
    {"name": "auth", "description": "Login/refresh/logout + current principal (cookie session)."},
    {"name": "jobs", "description": "Jobs list + the tracker; track override, generate, VA submit."},
    {"name": "applications", "description": "Tracker status dropdown, audit trail, and `.xlsx` export."},
    {"name": "onboarding", "description": "Multi-role CV upload, profile review, cover-letter template."},
    {"name": "chat", "description": "Manual application chatbot (paste JD → prompts → generate)."},
    {"name": "va", "description": "VA work queue: submit, first-contact review, replies."},
    {"name": "admin", "description": "9-domain health panel + per-hunter weekly quota (admin only)."},
    {"name": "webhooks", "description": "Resend (inbound mail + events) and WhatsApp bridge (HMAC)."},
    {"name": "health", "description": "Liveness probe."},
]

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Job Application & Outreach Engine",
        description=API_DESCRIPTION,
        version=API_VERSION,
        openapi_tags=TAGS_METADATA,
        debug=settings.debug,
    )

    # CORS — only needed when the browser calls this API directly (cross-origin).
    # With the same-origin Next.js proxy this stays empty and no CORS is applied.
    # allow_credentials=True is required for cookie auth, which forbids "*", so we
    # echo back the explicit allow-list from CORS_ORIGINS.
    if settings.cors_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(DomainError)
    async def _domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.message})

    @app.get("/health", tags=["health"], summary="Liveness probe")
    async def health() -> dict:
        return {"status": "ok", "env": settings.environment}

    app.include_router(api_router)
    return app


app = create_app()
