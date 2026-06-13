# Job Application & Outreach Engine

A conversion-optimized job-application pipeline for 3 hunters with VAs running
the human-in-the-loop steps. **Modular monolith**: one FastAPI app (all pipelines
as internal modules sharing a DB + Celery), a Next.js dashboard, and a thin Go
whatsmeow bridge. See [PRD](als_PRD.pdf) and the build plan in
`~/.claude/plans/`.

## Layout

```
backend/   FastAPI + Celery monolith (api / worker / beat off one image)
  app/
    models/      13 entities — Day-0 schema freeze (additive-only after)
    events/      6 frozen event contracts + JSON fixtures (the inter-team API)
    api/         routers (auth wired; jobs/outreach/respond/webhooks to come)
    pipelines/   apply (A) · outreach (B) · respond (C) — the 3 parallel seams
    email/       governor.py (single send choke point) + addressing + caps
    workers/     celery_app + beat_schedule
    sources/     pluggable job-source interface (to come)
    integrations/ resend · apollo · r2 · anthropic · bridge_client (to come)
bridge/    Go whatsmeow sidecar (transport only) — to come
frontend/  Next.js dashboard (replaces the Vite scaffold) — to come
infra/     docker-compose (postgres, redis, api, worker, beat, bridge)
```

## The parallel-build seam

Pipelines communicate **only** through Celery events (never direct calls), so the
three engineers build against fixtures and integrate last. Dependency order at
integration time is C → B → A; until then each works in isolation.

| Event (`app/events/names.py`) | Producer | Consumer |
|---|---|---|
| `evt.job.discovered` | source poller | Pipeline A |
| `evt.application.submitted` | Pipeline A (VA submit) | Pipeline B |
| `evt.reply.received` | Resend inbound / poll | Pipeline C |

`evt.job.scored`, `evt.cv.generated`, `evt.outreach.sent` are intra-pipeline
transitions (contracts + fixtures frozen, wired as each pipeline lands).

Every payload carries `user_id`. Fixtures in `app/events/fixtures/*.json` are
validated against the contracts by `tests/test_event_contracts.py` (CI gate) —
a contract change that breaks a fixture is a visible, reviewable failure.

## Run (local dev)

Local Postgres/Redis already occupy 5432/6379, so the containers publish
**5433 / 6380** (see `backend/.env`).

```bash
# infra
cd infra && docker compose up -d postgres redis

# backend
cd backend
uv venv && uv pip install -e . --group dev
cp .env.example .env          # already present for host-run dev
uv run alembic upgrade head   # applies the frozen schema
uv run uvicorn app.main:app --reload
uv run celery -A app.workers.celery_app worker -Q default,email,render,poll
uv run celery -A app.workers.celery_app beat

# tests
uv run pytest -q              # 16 passing: contracts, governor, addressing, auth
```

Full stack (once frontend + bridge land): `cd infra && docker compose up`.

## Status

- **Day-0 foundation** — schema freeze + migration, event contracts + bus +
  fixtures, cookie/JWT auth (hunters + VAs), the warm-up governor, pipeline seams.
- **Pipeline A (Apply)** — pluggable sources (greenhouse/lever/ashby + adzuna/serpapi
  + a deterministic fake), per-hunter dedupe, rules-based relevance prefilter,
  track classification, **truth-bounded tailoring** (provably no fabrication in the
  deterministic path), tectonic render → R2, and the `/api/jobs` surface
  (list, track override, generate, VA submit → `application.submitted`).
  External IO (LLM/R2/HTTP sources) is faked under `USE_FAKE_INTEGRATIONS=true`,
  so the whole pipeline runs end-to-end with no credentials. 25 tests passing.

Next: Pipeline B (Apollo people lookup, hook-finder, draft, Resend send through
the governor, follow-up sequencer), Pipeline C (reply match, classify, dossier,
Go bridge), and the Next.js dashboard.
