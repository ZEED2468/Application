# Application Flow

End-to-end view of how the Job Application & Outreach Engine behaves — what it
holds in state, how the Next.js frontend talks to the FastAPI backend, and the
human flow for the three hunters and their VA(s), mapped back to the PRD.

## What the system is

A conversion-optimized pipeline that automates a *validated* manual motion:
discover a real job, tailor a truthful CV, reach a specific human at the company
with a real hook, and route their replies to a VA on WhatsApp. It is multi-user:
every row and event carries the owning hunter's `user_id`, and a VA is a separate
principal linked to hunters/tracks via assignments.

## What state it holds

Postgres is the single source of truth. The 13 entities form three layers:
**identity** (`user`, `master_profile`, `va`, `va_assignment`, `sending_domain` —
the 9 (hunter,track)→domain rows), **the application object** (`job` →
`generated_cv` → `application`), and **the conversation** (`contact` → `outreach`
→ `thread` → `reply` → `dossier`). Status enums encode where each item sits:
`job.status` (discovered→scored→ready→submitted), `application.status`
(submitted→interview→offer/rejected), `outreach.sequence_step`
(first→followup1→followup2→stopped), `thread.state` and `dossier.status` for the
VA reply loop. Redis holds the Celery queues and warm-up rate limits; R2 stores
the `.tex`/`.pdf` artifacts. Events (`job.discovered` … `reply.received`) are
transient — they move work between pipelines but persist nothing themselves.

## The pipeline flow

**Apply:** a scheduler polls job sources, dedupes per hunter, scores relevance,
classifies a track, tailors the CV against the master profile (never fabricating),
renders a PDF to R2, and surfaces it for review. **Outreach:** on submit, the
system finds 2–3 right people via Apollo, enriches one real company hook, drafts
an email leading with the track's proof-of-work, and sends it from the correct
domain — but only through the warm-up governor, which enforces per-domain daily
caps and a ~20/week per-hunter cap. Unanswered mail auto-follows-up twice, then
stops. **Respond:** inbound replies match back to their job via a signed
`apply+<jobId>@<domain>` address, get classified routine vs substantive, are
assembled into a dossier, and pushed to the assigned VA on WhatsApp; the VA's
reply is relayed back as a threaded email.

## How the frontend handles the backend APIs

The Next.js dashboard never embeds business logic — it reads and acts on backend
state. Auth is an httpOnly `access_token` cookie plus a rotating refresh token;
`middleware.ts` gates the `(authed)` route group and a `/api/[...path]` route
handler proxies browser calls to FastAPI so the cookie travels server-side. A
typed service layer over `ky` + React Query fetches and caches; mutations
invalidate queries so the UI reflects new pipeline state without manual refresh.

Concretely, the frontend maps to PRD §8 screens:
- **Onboarding** — upload a PDF/Word CV → backend parses it to a structured
  `master_profile` → hunter reviews/corrects → confirm (`POST` profile).
- **Dashboard** — `GET /api/jobs` (filter by user/track/status) renders the jobs
  list; a job detail shows the JD, the track with override
  (`PATCH /api/jobs/{id}/track`), the tailored PDF, fit note, outreach status, and
  thread; `POST /api/jobs/{id}/generate` triggers tailoring on demand.
- **VA view** — a submit queue (`POST /api/jobs/{id}/submit`), first-contact
  outreach to review/edit before send, and replies to handle.
- **Domain-health panel** — all 9 domains' warm-up stage + bounce/spam from the
  admin endpoints; the per-hunter quota meter shows sends against the weekly cap.

Reply handling happens in WhatsApp via the Go bridge, not the dashboard — the UI
just shows thread history and status.

## The user flow

A **hunter** onboards once (CV → profile → confirm) and configures tracks, then
does almost nothing: jobs auto-discover, score, tailor, and queue. They glance at
the dashboard to override a track or read a fit note. A **VA** drives the
human-in-the-loop steps: submitting applications, reviewing each first-contact so
it never reads templated, and answering replies inside WhatsApp — with full
dossier context stamped with the owning hunter, so a shared VA never confuses
whose application it is. The **operator** (a hunter's second hat) watches the
domain-health panel; the warm-up governor protects deliverability in code, so no
late-night send can torch a cold domain. Near-zero hunter time per application,
exactly as the PRD intends.
