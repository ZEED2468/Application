# Backend Architecture

The **Job Application & Outreach Engine** backend — a FastAPI **modular monolith**.
One codebase, one Docker image; the API, the Celery worker, and the Celery beat
scheduler are the same app started with different commands. The three product
pipelines (Apply / Outreach / Respond) are internal modules that communicate
**only through events**, never by importing each other.

Legend: **[BUILT]** = implemented + tested · **[SCAFFOLD]** = stub/seam with a
defined interface but TODO body · **[PLANNED]** = not yet created.

---

## 1. Overview & principles

- **One image, three commands.** `uvicorn app.main:app` (API), `celery -A
  app.workers.celery_app worker`, `... beat`. Producer and consumer share code,
  so an event payload can never drift between the side that emits it and the side
  that handles it.
- **Events are the seam.** A Celery task named exactly like an event *is* the
  subscriber. `emit("evt.application.submitted", payload)` in Pipeline A reaches
  Pipeline B without A importing B. This is what lets three engineers build in
  parallel against fixtures.
- **`user_id` everywhere.** Every owned row and every event payload carries the
  owning hunter's `user_id`. Repositories require it — there is no implicit
  "all users" query. It is the partition key for dedupe, caps, domains, dossiers.
- **Additive-only schema.** The 13 entities were frozen on day one
  ([app/models/__init__.py](app/models/__init__.py)). Later changes are new
  nullable columns / new tables only. Pipeline A shipped with **no migration**,
  proving the discipline holds.
- **Fakes via config.** `USE_FAKE_INTEGRATIONS=true` swaps every external
  dependency (LLM, R2, HTTP job sources) for deterministic in-process fakes, so
  the whole pipeline runs end-to-end with zero credentials — in tests and in dev.

### Topology

```
Next.js dashboard ──HTTP──> FastAPI (app.main:app) ──> Postgres
                                  │                      Redis (broker + cache)
                                  │                      R2 (CV .tex/.pdf)
                                  ▼
                       Celery worker + beat  ──internal HTTP──> Go whatsmeow bridge ──> VA WhatsApp
```

### `app/` tree

```
app/
  main.py            FastAPI factory, error handler, /health        [BUILT]
  config.py          pydantic-settings; all secrets + feature flags  [BUILT]
  db.py              async engine, session factory, Base             [BUILT]
  deps.py            get_session, current_user/current_va/require_admin [BUILT]
  security.py        argon2 hashing + JWT access/refresh helpers      [BUILT]
  core/              enums, ids (uuid7), errors                       [BUILT]
  models/            the 13 entities (+ RefreshToken)                 [BUILT]
  events/            names, contracts (6 schemas), bus, fixtures      [BUILT]
  schemas/           auth + jobs DTOs                                 [BUILT]
  repositories/      jobs, profiles (user_id-scoped data access)      [BUILT]
  sources/           job-source protocol, registry, 5 adapters, fake  [BUILT]
  llm/               client + relevance, track_classify, tailoring    [BUILT]
  integrations/      r2 [BUILT]; resend/apollo/anthropic/...          [PLANNED]
  email/             governor, caps, addressing [BUILT]; tasks        [SCAFFOLD]
  pipelines/
    apply/           service, render, tasks                           [BUILT]
    outreach/        tasks (seam)                                     [SCAFFOLD]
    respond/         tasks (seam)                                     [SCAFFOLD]
  api/               router aggregation, auth, jobs                   [BUILT]
  workers/           celery_app, beat_schedule, runner                [BUILT]
```

---

## 2. Module reference

### `config` · `db` · `core` — [BUILT]
- **Purpose:** Process configuration, the async DB layer, and shared primitives.
- **Key files:** [config.py](app/config.py), [db.py](app/db.py),
  [core/enums.py](app/core/enums.py), [core/ids.py](app/core/ids.py),
  [core/errors.py](app/core/errors.py).
- **Public surface:** `settings` (singleton), `get_settings()`; `engine`,
  `AsyncSessionLocal`, `Base`, `get_session()`; all domain enums (`Track`,
  `JobStatus`, `WarmupStage`, `OutreachStatus`, …); `new_id()` (uuid7);
  `DomainError`/`NotFoundError`/`AuthError`/`ForbiddenError`/`ConflictError`.
- **Connects via:** imported by nearly everything; `DomainError` subclasses map
  to HTTP status codes in `main.py`.

### `models` — [BUILT]
- **Purpose:** The frozen relational schema (13 entities + `RefreshToken`).
- **Key files:** [models/__init__.py](app/models/__init__.py) (imports all — the
  Alembic autogenerate source of truth), one file per entity,
  [models/base.py](app/models/base.py) (`TimestampMixin`, `pk()`, `user_fk()`).
- **Public surface:** `User`, `RefreshToken`, `MasterProfile`, `SendingDomain`,
  `Va`, `VaAssignment`, `Job`, `GeneratedCv`, `Application`, `Contact`,
  `Outreach`, `Thread`, `Reply`, `Dossier`. See §4 for the constraint map.
- **Connects via:** queried through repositories + services; migration lives at
  [alembic/versions/](alembic/versions/).

### `events` — [BUILT]
- **Purpose:** The inter-pipeline API. Names, validated payloads, and the bus.
- **Key files:** [events/names.py](app/events/names.py),
  [events/contracts.py](app/events/contracts.py),
  [events/bus.py](app/events/bus.py), [events/fixtures/](app/events/fixtures/).
- **Public surface:** event-name constants + `ALL_EVENTS`; payload models
  (`JobDiscovered`, `JobScored`, `CvGenerated`, `ApplicationSubmitted`,
  `OutreachSent`, `ReplyReceived`) all extending `EventPayload(user_id)` with
  `extra="forbid"`; `CONTRACTS` map; `emit(event_name, payload)`.
- **Connects via:** `emit()` validates against `CONTRACTS` then
  `celery_app.send_task(name, kwargs={"payload": ...})`. Consumers bind
  `@celery_app.task(name=EVENT)`. Fixtures must validate against contracts (CI).

### `security` · `deps` · `api/auth` — [BUILT]
- **Purpose:** Authentication for two principal types (hunter `User`, `Va`).
- **Key files:** [security.py](app/security.py), [deps.py](app/deps.py),
  [api/auth.py](app/api/auth.py), [schemas/auth.py](app/schemas/auth.py).
- **Public surface:** `hash_password`/`verify_password` (argon2);
  `create_access_token`/`decode_access_token` (JWT claims `sub/type/role/
  track_scope`); `generate_refresh_token`/`hash_refresh_token` (store hash only);
  `Principal`, `current_principal`, `current_user`, `current_va`, `require_admin`;
  routes `POST /api/auth/login|refresh|logout`, `GET /api/auth/me`.
- **Connects via:** httpOnly `access_token` cookie + rotating `refresh_token`
  (scoped to `/api/auth`, hashed + revocable in the `refresh_token` table).
  Matches the reference Next.js frontend's cookie/refresh pattern.

### `repositories` — [BUILT]
- **Purpose:** Data access, always `user_id`-scoped. No business logic.
- **Key files:** [repositories/jobs.py](app/repositories/jobs.py),
  [repositories/profiles.py](app/repositories/profiles.py).
- **Public surface:** `jobs.insert_if_new` (portable dedupe via SAVEPOINT +
  IntegrityError on `(user_id, dedupe_key)`), `jobs.list_for_user`,
  `jobs.get_owned`; `profiles.get_by_user_track`, `profiles.profile_to_dict`.
- **Connects via:** called by the apply service and the jobs API.

### `sources` — [BUILT]
- **Purpose:** Pluggable job discovery. Board scrapers + aggregators behind one
  protocol; adding a source is a new file + decorator.
- **Key files:** [sources/base.py](app/sources/base.py),
  [sources/normalize.py](app/sources/normalize.py), adapters
  ([greenhouse](app/sources/greenhouse.py), [lever](app/sources/lever.py),
  [ashby](app/sources/ashby.py), [adzuna](app/sources/adzuna.py),
  [serpapi_jobs](app/sources/serpapi_jobs.py)), [fake](app/sources/fake.py).
- **Public surface:** `RawJob`, `SourceQuery`, `JobSource` (Protocol), `register`
  (decorator), `SOURCES` (registry), `active_sources()` (fake in dev, real
  otherwise); `normalize.dedupe_key`, `normalize.to_job_fields`.
- **Connects via:** real adapters no-op without creds; the apply service iterates
  `active_sources()`, normalizes, and inserts. Output feeds `evt.job.discovered`.

### `llm` — [BUILT]
- **Purpose:** Scoring + tailoring. Deterministic where possible (the v1 prefilter
  is rules-based), LLM only for true tailoring — and even that is truth-bounded.
- **Key files:** [llm/client.py](app/llm/client.py) (Anthropic wrapper,
  `is_live()` gate), [llm/relevance.py](app/llm/relevance.py),
  [llm/track_classify.py](app/llm/track_classify.py),
  [llm/tailoring.py](app/llm/tailoring.py).
- **Public surface:** `relevance.score(...)` + `passes()` + `RELEVANCE_THRESHOLD`;
  `track_classify.classify(...) -> Track`; `tailoring.tailor(...)` (async; fake =
  pure selection/reorder of the profile's own facts), `tailoring.tailor_fake`,
  **`tailoring.assert_truth_bounded(profile, cv_json)`** (proves no fabrication).
- **Connects via:** called by the apply service during score + generate.

### `integrations` — r2 [BUILT], rest [PLANNED]
- **Purpose:** Adapters to external services, each fakeable.
- **Key files:** [integrations/r2.py](app/integrations/r2.py) — `put_bytes(key,
  data, content_type)`; fake writes to `.r2store/` and returns a `file://` URL,
  live uses boto3 against the R2 S3 endpoint.
- **Planned:** `resend.py` (send + inbound/event webhooks), `apollo.py` (people
  lookup), `anthropic.py` (shared client), `postmaster.py` (deliverability
  signals), `bridge_client.py` (HTTP client to the Go sidecar).

### `email` — governor/caps/addressing [BUILT], tasks [SCAFFOLD]
- **Purpose:** The single outbound-mail choke point + warm-up safety.
- **Key files:** [email/governor.py](app/email/governor.py),
  [email/caps.py](app/email/caps.py), [email/addressing.py](app/email/addressing.py),
  [email/tasks.py](app/email/tasks.py).
- **Public surface:** `governor.governed_send(session, outreach_id, *, send_fn)
  -> SendResult{sent|deferred|paused}` — locks the `sending_domain` row
  (`SELECT … FOR UPDATE`), checks the per-domain daily cap **and** per-hunter
  weekly cap, sends + increments atomically or queues for tomorrow;
  `caps.stage_for_age`, `caps.daily_cap`, `caps.is_new_day`, `STAGE_CAPS`
  (5/10/20/full); `addressing.encode_reply_address`/`decode_reply_address`
  (HMAC-signed `apply+<token>@<domain>`).
- **Connects via:** Pipeline B/C route *all* sends through `governed_send`.
  `email/tasks.py` holds the `task.email.warmup_rollover` + `task.email.health_scan`
  beat stubs (bodies TODO).

### `pipelines/apply` — [BUILT]
- **Purpose:** Pipeline A end-to-end: discover → classify → score → tailor →
  render → store → submit.
- **Key files:** [pipelines/apply/service.py](app/pipelines/apply/service.py),
  [pipelines/apply/render.py](app/pipelines/apply/render.py),
  [pipelines/apply/tasks.py](app/pipelines/apply/tasks.py).
- **Public surface:** `service.discover_for_user`, `service.classify_track`,
  `service.score_relevance`, `service.generate_cv`, `service.submit_application`
  (each takes an injectable `emit` for testability); `render.build_tex`,
  `render.render_pdf` (tectonic, stub PDF fallback); tasks `on_job_discovered`
  (consumes `evt.job.discovered`) and `poll_sources` (beat).
- **Connects via:** consumes `evt.job.discovered`; emits `evt.job.scored`,
  `evt.cv.generated`, `evt.application.submitted` (→ Pipeline B).

### `pipelines/outreach` — [SCAFFOLD]
- **Purpose:** Pipeline B (the conversion engine).
- **Key file:** [pipelines/outreach/tasks.py](app/pipelines/outreach/tasks.py).
- **Public surface:** `on_application_submitted` (consumes
  `evt.application.submitted`) and `sequencer_tick` (beat) — interfaces defined,
  bodies TODO: Apollo lookup → hook-finder → draft → `governed_send` → follow-ups.
- **Connects via:** will emit `evt.outreach.sent`.

### `pipelines/respond` — [SCAFFOLD]
- **Purpose:** Pipeline C (reply handling + VA relay).
- **Key file:** [pipelines/respond/tasks.py](app/pipelines/respond/tasks.py).
- **Public surface:** `on_reply_received` (consumes `evt.reply.received`) and
  `poll_inboxes` (beat) — bodies TODO: match → classify → dossier → bridge push →
  relay VA reply through the governor.
- **Connects via:** consumes `evt.reply.received`; inbound webhook/poll will emit it.

### `api` — [BUILT]
- **Purpose:** HTTP surface.
- **Key files:** [api/__init__.py](app/api/__init__.py) (aggregates under `/api`),
  [api/auth.py](app/api/auth.py), [api/jobs.py](app/api/jobs.py).
- **Public surface:** `GET /api/jobs`, `GET /api/jobs/{id}`,
  `PATCH /api/jobs/{id}/track`, `POST /api/jobs/{id}/generate`,
  `POST /api/jobs/{id}/submit` (VA-submit with assignment auth) + the auth routes.
- **Planned:** `webhooks/resend`, `webhooks/bridge`, `admin_email` (health panel).

### `workers` — [BUILT]
- **Purpose:** The Celery app, periodic schedule, and async-in-task runner.
- **Key files:** [workers/celery_app.py](app/workers/celery_app.py),
  [workers/beat_schedule.py](app/workers/beat_schedule.py),
  [workers/runner.py](app/workers/runner.py).
- **Public surface:** `celery_app`, `UserScopedTask` (binds `user_id` into log
  context); `beat_schedule` (poll_sources 30m, warmup_rollover daily, sequencer
  hourly, poll_inboxes 5m, health_scan hourly); `run_with_session(fn)` (runs an
  async coroutine with a committed session inside a sync task).
- **Connects via:** autodiscovers `tasks` modules in each pipeline + `email`;
  queue routing sends `task.email.*`→`email`, render→`render`, poll→`poll`.

---

## 3. Event catalogue

| Event | Payload (beyond `user_id`) | Emitter | Consumer | Status |
|---|---|---|---|---|
| `evt.job.discovered` | `job_id, source` | apply `discover_for_user` / `poll_sources` | apply `on_job_discovered` | [BUILT] |
| `evt.job.scored` | `job_id, relevance_score, track` | apply `score_relevance` | (dashboard / metrics) | [BUILT] |
| `evt.cv.generated` | `job_id, generated_cv_id` | apply `generate_cv` | (dashboard: VA submit queue) | [BUILT] |
| `evt.application.submitted` | `application_id, job_id, track` | apply `submit_application` | outreach `on_application_submitted` | emit [BUILT] · consume [SCAFFOLD] |
| `evt.outreach.sent` | `outreach_id, application_id, contact_id` | outreach (planned) | sequencer / metrics | [SCAFFOLD] |
| `evt.reply.received` | `reply_id, thread_id` | respond inbound webhook/poll (planned) | respond `on_reply_received` | [SCAFFOLD] |

Every payload extends `EventPayload` (`user_id`, `extra="forbid"`) and is
re-validated inside `emit()`. The fixtures in
[events/fixtures/](app/events/fixtures/) are the canonical examples and are
asserted against the contracts by `tests/test_event_contracts.py`.

---

## 4. Data model map

13 entities. PK = uuid7. `user_id` on every owned row. The constraints below are
the load-bearing invariants:

| Entity | Purpose | Load-bearing constraint |
|---|---|---|
| `user` | hunter/admin auth + identity | `email` UNIQUE |
| `refresh_token` | revocable sessions | `token_hash` UNIQUE (hash only) |
| `master_profile` | per-(user,track) CV data + `truth_corpus` | `(user_id, track)` UNIQUE |
| `sending_domain` | (user,track)→domain, warm-up state | `(user_id, track)` UNIQUE, `domain` UNIQUE |
| `va` | VA identity (separate principal) | `email`, `whatsapp_jid` UNIQUE |
| `va_assignment` | VA↔hunter/track (shared or per-hunter) | `(va_id, user_id, track)` UNIQUE; idx `(user_id, track)` |
| `job` | discovered posting | **`(user_id, dedupe_key)` UNIQUE** (per-hunter dedupe) |
| `generated_cv` | tailored .tex/.pdf + `tailoring_diff` | `(job_id)` UNIQUE |
| `application` | VA-submitted application + lifecycle | `(job_id)` UNIQUE |
| `contact` | Apollo person + enriched `hook` | `(job_id, email)` UNIQUE |
| `outreach` | one sequence-step message | **`(application_id, contact_id, sequence_step)` UNIQUE** (no double-send); idx `(status, next_action_at)` |
| `thread` | email conversation | **`reply_address` UNIQUE** (inbound match key) |
| `reply` | inbound/outbound message | idx `message_id`, `in_reply_to` |
| `dossier` | context pushed to VA, stamped with owner | idx `(va_id, status)` (VA work queue) |

These four uniques are what make the system idempotent under Celery's
at-least-once delivery: re-discovering a job, re-sending a step, or re-processing
a reply all collapse to a no-op.

---

## 5. Pipeline walkthroughs

### A — Apply [BUILT, verified end-to-end]
`poll_sources` (beat) → for each hunter+profile, `discover_for_user` runs
`active_sources()`, normalizes, `insert_if_new` (dedupe), emits
`evt.job.discovered` for new rows → `on_job_discovered` consumes →
`classify_track` (override-able) → load the `(user, track)` profile →
`score_relevance` (rules prefilter; below threshold → `rejected`) → emit
`evt.job.scored` → `generate_cv`: truth-bounded `tailor` → `build_tex` →
`render_pdf` (tectonic) → R2 `put_bytes` → emit `evt.cv.generated` → CV surfaces
for the VA → `POST /api/jobs/{id}/submit` → `submit_application` → emit
`evt.application.submitted`. Verified against real Postgres: all five events fire
in order, JSONB round-trips, PDF written to R2.

### B — Outreach [SCAFFOLD]
`on_application_submitted` → Apollo lookup (2–3 people, engineer > hiring manager
> recruiter) → hook-finder (one real, track-aware company detail) → draft email
(proof-of-work link + hook + de-risking line) → **`governed_send`** (warm-up +
weekly cap) → VA reviews first contact → emit `evt.outreach.sent` →
`sequencer_tick`: 4d no reply → followup1 → 5d → followup2 → stop. The governor,
caps, and reply-addressing it depends on are already **[BUILT]**.

### C — Respond [SCAFFOLD]
Resend inbound webhook (+ `poll_inboxes` backup) → matcher (signed
`apply+<jobId>@<domain>` via `decode_reply_address`; fallback `In-Reply-To` /
from-addr) → persist reply → emit `evt.reply.received` → `on_reply_received`:
classify (routine/substantive) → assemble dossier → push to assigned VA via the
Go bridge → VA replies in WhatsApp → relay as a threaded email through the
governor. Two-way state lives on `thread.state` + `dossier.status`.

---

## 6. Build status & next steps

**Done:** Day-0 foundation (config/db/core, 13-model schema + migration, events +
contracts + fixtures, cookie/JWT auth, the warm-up governor + caps + reply
addressing, Celery app + beat + runner) and **Pipeline A end-to-end** (sources,
dedupe, scoring, truth-bounded tailoring, render, R2, jobs API). **25 tests
passing.**

**Next, in dependency order:**
1. **Pipeline B** — `integrations/apollo.py`, hook-finder, draft (via `llm`),
   wire `on_application_submitted` + `sequencer_tick` through `governed_send`.
2. **Resend** — `integrations/resend.py` + `api/webhooks/resend.py` (send,
   inbound → `evt.reply.received`, events → health/auto-pause), domain seeding.
3. **Pipeline C** — matcher/classify/dossier/relay + `integrations/bridge_client.py`
   and the Go whatsmeow sidecar.
4. **Email ops** — fill in `warmup_rollover` + `health_scan` bodies; `admin_email`
   health panel.
5. **Frontend** — Next.js dashboard (replace the Vite stub).

The full roadmap, rationale, and risks live in the build plan:
`C:\Users\ADMIN\.claude\plans\this-is-the-context-synchronous-mist.md`.
