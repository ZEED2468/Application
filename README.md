# Job Application & Outreach Engine

A conversion-optimized, multi-user job-application & outreach engine: discover a
real job (or paste one), tailor a **truthful** CV + cover letter, reach a specific
human with a real hook, and route replies to a VA on WhatsApp. Two application
paths — autonomous and a manual VA chatbot — converge on the **same** data objects,
so one tracker stays in sync. Postgres is the single source of truth; deliverability
is protected in code (the warm-up governor), not by discipline.

## Monorepo layout

```
apps/
  api/         FastAPI + Celery — ALL business logic (api / worker / beat off one image)
    app/
      models/        13 frozen entities + 6 additive (role_cv, cover_letter, chat, audit)
      events/        10 event contracts + JSON fixtures (the inter-pipeline API)
      api/           28 routes: auth, jobs/tracker, applications, chat, onboarding,
                     va, admin, webhooks (resend, bridge)
      pipelines/     apply (A) · outreach (B) · respond (C) · manual (chatbot) · generation
      llm/           relevance, track_classify, tailoring (truth-bounded), hookfinder,
                     draft_email, classify_reply, cover_letter
      email/         governor.py (single send choke point) + sender + addressing + caps + health
      sources/       pluggable job sources (greenhouse/lever/ashby/adzuna/serpapi + fake)
      integrations/  resend · apollo · r2 · bridge_client (all fakeable)
      workers/       celery_app + beat_schedule + runner
  web/         Next.js dashboard (coffee/Garamond, App Router, ky + React Query)
  wa-bridge/   Go + whatsmeow — dumb transport only (FAKE mode by default)
packages/
  shared-types/ TS API types
infra/         docker-compose (postgres, redis, api, worker, beat, web, wa-bridge) + Dockerfiles
docs/          PRD, application-flow, BUILD_REPORT
Makefile, pnpm-workspace.yaml
```

## The two paths, one set of objects

Both the **autonomous** pipeline and the **manual VA chatbot** call the shared
generation engine and create identical `job → generated_cv → cover_letter →
application` records. The chatbot adds: paste JD → match a per-role CV → run the
**internal ATS** scorer → raise confirm-true prompts (only real facts get added) →
generate. No path creates an application the tracker can't see; every change writes
an `application_event` audit row.

## Non-negotiables (enforced)

- **Truth boundary** — generation only reorders/reframes facts in the profile or
  VA-confirmed-true; `tailoring.assert_truth_bounded` proves no fabrication.
- **ATS** — internal 0–100 match optimized toward 90–95%; framed everywhere as
  "internal ATS match", never a guaranteed employer-ATS score.
- **Warm-up governor** — every outbound email (first contact, follow-ups, VA
  relays) passes one choke point: per-domain daily cap + ~20/week per hunter.
- **`user_id` on every row + event**; VA is a separate assignable principal;
  dossiers stamped with the owning hunter.

## Run (one command)

```bash
cp infra/.env.example .env     # USE_FAKE_INTEGRATIONS=true — runs with no creds
make dev                       # postgres, redis, api, worker, beat, web, wa-bridge
make migrate                   # alembic upgrade head
```

Backend tests: `cd apps/api && uv venv && uv pip install -e . --group dev && uv run pytest`
→ **40 passing**.

## Status

Foundation + all three pipelines + the manual chatbot + ATS + cover letters +
tracker/export/audit + the Next.js dashboard + Go bridge + infra are built and
verified. Everything runs end-to-end behind `USE_FAKE_INTEGRATIONS`; see
[docs/BUILD_REPORT.md](docs/BUILD_REPORT.md) for the full status and the seam table
showing exactly where real Resend/Apollo/Anthropic/R2 keys and a WhatsApp phone
drop in.
