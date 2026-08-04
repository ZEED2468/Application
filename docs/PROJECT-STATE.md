# The Outreach Desk — Deep Project-State & Gap Audit

> **Purpose.** A single, exhaustive reference of *everything built* and *every current gap*, written for finetuning. Read it top-to-bottom to understand the system, or jump to a module in §6 and its gaps. The consolidated, prioritized gap register is §7.
>
> **Snapshot.** `main` @ `8819f6c` · audit branch `docs/project-state` · generated 2026-08-04.
>
> **Method.** Assembled from a full-codebase sweep (seven parallel module audits) plus git history. Every claim is anchored to `path:line`. Where a fix already exists in an open (un-merged) PR, the text describes the **current `main`** state and flags the PR.

---

## 1. How to read this

- **§2–§4** — the shape of the system: architecture, stack, deployment, and the standing operational constraints.
- **§5** — delivery history (PRs #1–#19) so you can see how the codebase got here.
- **§6** — the module-by-module state. Each module has *What's built / How it works* (with file refs) and its own *Gaps* subsection.
- **§7** — the consolidated gap register, prioritized (P0 → P3). This is the finetuning backlog.
- **§8** — the three open PRs awaiting review.
- **§9** — recommended finetuning order for the remaining modules.

Two facts to hold throughout:
1. **Fake mode is the default.** `USE_FAKE_INTEGRATIONS=true` makes every external call (LLM, job sources, email, storage, WhatsApp) resolve to a local deterministic fake. Much of the system is *fully wired for real mode but only exercised in fake mode*. The audit flags, per feature, what changes when the flag flips to `false`.
2. **The live backend lags `main`.** Nothing in a merged PR is live until the Render backend is redeployed on latest `main`; this has repeatedly been the root cause of "it's not working in prod" reports.

---

## 2. Architecture & topology

**Product.** "The Outreach Desk" — a Job Application & Outreach Engine. A hunter's master profile (per career *track*) drives two pipelines:

- **Pipeline A — Apply:** discover jobs → classify (track + seniority) → relevance prefilter → tailor CV + cover letter (truth-bounded) → ATS score → render PDF (into the user's LaTeX template) → a VA submits the application.
- **Pipeline B — Outreach:** on submission, send warmed outreach email from a per-`(hunter, track)` sending domain, governed by warm-up caps, with HMAC reply-addressing and reply detection; a WhatsApp bridge is available as a second channel.

**Monorepo layout** (pnpm workspace + a Python app):

| Path | What it is |
|------|-----------|
| `apps/api` | FastAPI modular monolith + Celery (worker + beat). Python 3.12, SQLAlchemy async, Alembic. |
| `apps/web` | Next.js 15 App Router dashboard (React 19, react-query, Tailwind). |
| `apps/wa-bridge` | Go WhatsApp bridge service. |
| `packages/shared-types` | Shared TypeScript contracts consumed by `apps/web` as `@jd/shared-types`. |
| `infra/` | docker-compose (dev + nginx), central `.env.example`, nginx, README (incl. email-domain DNS checklist). |
| `docs/` | Flow/setup/render/progress docs + exported OpenAPI. |
| `Makefile`, `render.yaml` | Dev entrypoints; Render deploy manifest. |

**Runtime services** (compose): `postgres` (5432), `redis` (6379: db0 cache, db1 broker, db2 results), `api` (8000), `worker`, `beat`, `wa-bridge` (8081), `web` (3000).

---

## 3. Tech stack

- **Backend:** FastAPI, Pydantic v2 + pydantic-settings, SQLAlchemy 2.0 async (`asyncpg` in prod, `aiosqlite` in tests), Alembic (additive-only linear chain), Celery + Redis (queues `default,email,render,poll`), structlog, argon2 password hashing, PyJWT cookie auth, cryptography/Fernet for at-rest key encryption.
- **LLM:** provider-agnostic layer — `anthropic`, `openai`-compatible (Groq/Together/OpenRouter/Ollama/**Cohere-compat**), `google`. Per-feature routing (see §6.4).
- **Rendering:** `tectonic` LaTeX engine (`--untrusted`, timeout), stub PDF in dev/fake.
- **Storage:** Cloudflare R2 (S3-compatible via boto3); presigned or public-base-url downloads.
- **Email:** Resend (send + inbound webhook). **Job sources:** Adzuna, SerpApi (Google Jobs), Greenhouse/Lever/Ashby board scrapers, Apollo (contacts).
- **Frontend:** Next.js 15.5, React 19, `@tanstack/react-query` v5, `ky` HTTP, `sonner` toasts, Tailwind, `lucide-react`, `react-hook-form`.
- **Bridge:** Go (WhatsApp), HMAC-authenticated to the API.

---

## 4. Deployment & environments

- **Backend:** Render (`render.yaml`); `api` container runs `alembic upgrade head` on boot via `docker-entrypoint.sh` (`RUN_MIGRATIONS=1`). Postgres + Redis are Render-managed.
- **Frontend:** Vercel. **Storage:** Cloudflare R2. **Email/DNS:** Cloudflare DNS + Resend (9 sending domains — SPF/DKIM/DMARC/MX checklist in `infra/README.md`).
- **Config:** one central `.env` drives the whole stack; compose pins network-critical URLs per service. `USE_FAKE_INTEGRATIONS` toggles real vs fake integrations.
- **Local:** `make dev` (compose up), `make migrate`, `make seed`, `make test` (host pytest), **`make test-docker`** (hermetic offline in-container suite — open PR #19).

**Standing operational constraints**
- ⚠️ **Redeploy lag:** the live Render backend is frequently behind `main`; merged fixes require a manual redeploy to take effect.
- ⚠️ **Alembic head discipline:** the chain is additive-only and linear; a past revision collision (`a1b2c3d4e5f6` reused) broke a deploy and was hotfixed by renumbering to `f5a6b7c8d9e0` (PR #8). New migrations must extend the true head.
- ⚠️ **Secrets hygiene:** live provider keys have been pasted into chat during debugging; treat any such key as compromised and rotate.

---

## 5. Delivery history (PRs)

Merged to `main` (this is the built-up feature set):

| PR | Branch | Theme |
|----|--------|-------|
| #1 | `setup` | Repo/scaffold bootstrap |
| #5 | `feat/onboarding-career-workspace` | Onboarding & career workspace |
| #6 | `fix/job-schema-migration` | Job schema migration fix |
| #7 | `feat/track-entity-readiness` | Track entity + readiness foundations |
| #8 | `fix/track-migration-revision-collision` | Alembic revision-collision hotfix (`→ f5a6b7c8d9e0`) |
| #9 | `feat/readiness-service` | Readiness service (`/api/user/readiness`) |
| #10 | `feat/readiness-dashboard-ux` | Readiness dashboard UX |
| #11 | `feat/first-login-tour` | First-login coach-mark tour |
| #12 | `feat/ai-integrations` | AI Integration Management (backend) |
| #13 | `feat/ai-integrations-ui` | AI Integrations dashboard (Settings) |
| #14 | `fix/provider-validate-parsing` | Provider validate/health parsing (Gemini/OpenAI tolerant extract) |
| #15 | `feat/discovery-scoping-cache` | Token-efficient scoped discovery + cooldown + frontend job cache |
| #16 | `fix/regen-honor-template` | CV regen honor-or-explain + repair retry |

Open (awaiting your review — **not merged**):

| PR | Branch | Theme |
|----|--------|-------|
| **#17** | `fix/jobs-discovery-correctness` | Module 4 backend correctness (page-size cap, custom-track enum guard, single-seniority scope, cooldown boards hash, SerpApi OR grouping) + tests |
| **#18** | `feat/jobs-web-cache-ux` | Resilient job cache: stale-cache refresh, filter-aware empty state, capped-results banner |
| **#19** | `chore/docker-test-env` | Hermetic `make test-docker` + `.env.example` sync |

---

## 6. Module-by-module state

_The seven subsections below are the detailed per-module audits. Each ends with its own gaps; §7 consolidates them._

## 6.1 Discovery & Jobs Ingest

**Slice:** Pipeline A ingest — job discovery, sources, and the jobs/tracker data model + list API, in `apps/api`. Audited at main HEAD `8819f6c`. Where a fix exists only on an open PR it is flagged inline.

### The pluggable source interface — `app/sources/base.py`
- Every source (board scraper or keyword aggregator) implements the `JobSource` Protocol and self-registers via `@register`. Adding a source = new file + decorator; nothing downstream changes.
- `RawJob` (`base.py:19-31`): a posting before normalization — `source, source_job_id, company, title, location, url, description, posted_at, raw`.
- `SourceQuery` (`base.py:34-47`): `track, keywords, location, boards, role_titles, experience_level (junior|mid|senior|lead), limit=50`.
- `JobSource` Protocol (`base.py:50-56`): `name`, `supports(track)`, `fetch(query) -> AsyncIterator[RawJob]`.
- Registry `SOURCES` + `register()` instantiate-and-store by `.name` (import side-effect registration).
- **`active_sources()`** (`base.py:69-77`) — the fake/real switch: `use_fake_integrations` → `[FakeSource()]`; else all registered adapters. The single gate that makes everything "fake-mode-only" vs real.

### Aggregators
- **Adzuna** (`app/sources/adzuna.py`): no-ops without `adzuna_app_id/key`; country from `adzuna_country or "gb"`; `terms = role_titles or keywords or [track.value]`, seniority prefix on each term; uses `what_or` (ANY), `results_per_page=min(limit,50)`, `max_days_old=30`, `sort_by=date`; `where` only if location; HTTPStatusError → RuntimeError (surfaced in report). Maps `redirect_url`, `company.display_name`.
- **SerpApi / Google Jobs** (`app/sources/serpapi_jobs.py`): no-ops without `serpapi_api_key`; `q = " OR ".join(role_titles[:3])` else `keywords[:3]`; seniority prefix; ` remote` appended if no location. Handles SerpApi's 200-with-`error` body (no-results → quiet return; else RuntimeError).

### Board scrapers (per-company tokens)
Each iterates `query.boards`, isolates each board in `try/except httpx.HTTPError: continue`, sets `company=<board token>` (not a display name):
- **Greenhouse** (`greenhouse.py`): `boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true`, strips HTML from `content`.
- **Lever** (`lever.py`): `api.lever.co/v0/postings/{company}?mode=json` (bare list), maps `text`→title, `descriptionPlain`.
- **Ashby** (`ashby.py`): `api.ashbyhq.com/posting-api/job-board/{board}`, maps `descriptionPlain or description`.
Board tokens come from the `source_board` table via `boards_repo.active_by_source`; aggregators ignore `boards`.

### Fake source — `app/sources/fake.py`
Not `@register`ed (only reachable via `active_sources()` in fake mode). `name = greenhouse` (tags fake jobs as a board source). Hardcoded `_SAMPLES` per track (frontend 2 / backend 2 / general 1). Ignores boards/keywords/location/experience.

### Normalization + dedupe — `app/sources/normalize.py`
- **`dedupe_key(raw)`**: `sha256("company|title|location")` truncated to **32 hex** — deliberately not URL/source_job_id, so the same posting from different sources collapses. Backs the `(user_id, dedupe_key)` UNIQUE (per-hunter dedupe).
- `to_job_fields(raw)`: does **not** set `track`/`experience_level`/`role_title` — the service layer adds those.

### Orchestration — `app/pipelines/apply/service.py`
Helpers: `_emphasis_keywords` (first 8 skills), `_target_roles`, `_location` (first preferred location). `title_matches_roles`: every role token >2 chars present in the title tokens; `roles=[]` ⇒ everything matches.

**`_run_sources`** (`service.py:86-206`): builds one shared `SourceQuery` (experience_level = **first** selected level, `:109`); `actives = supports(track)`; board lookup fails-open if the table is missing; per source: cooldown check → `fetch` → `title_matches_roles` drop → **track classify** (`selected_tracks` substring match overwrites `job_track` with the raw string, else drop off-target) → **experience classify** (drop if not in selected) → `to_job_fields` + track/exp/role_title → `insert_if_new` → emit `JOB_DISCOVERED` → `mark_ran` cooldown. Returns `(new_jobs, report[{source,found,inserted,off_target,error,note}])`.

**`discover_for_user`** — thin wrapper (cooldown on, no selected tracks/levels); the **beat** entrypoint. `classify_track`, `score_relevance` (rule-based `relevance.score`, threshold 0.12) are later stages in the same file.

### Cooldown cache — `app/pipelines/apply/discover_cache.py`
Per-`(user, source, query)` Redis cooldown; **fails open** (Redis error / fake mode ⇒ don't skip). `query_hash` = sha256(16 hex) of `source|track|sorted keywords|sorted role_titles|location|experience` (**omits boards** on main). Disabled entirely in fake mode. `_key = discover:cd:{user}:{source}:{hash}`, TTL `discover_cooldown_seconds` (**default 3600**). Beat cadence is **30 min** → real sources are cooldown-skipped every other poll.

### Data access
- `repositories/jobs.py` `insert_if_new` (SAVEPOINT + IntegrityError→None on the dedupe collision); `list_for_user` (all rows, no SQL paging/field filter).
- `repositories/source_boards.py` `active_by_source` → `{source:[tokens]}`; `repositories/profiles.py` `get_by_user_track`.

### HTTP API — `app/api/jobs.py` + `_pagination.py`
- Router `/jobs`, `dependencies=[bind_user_llm]`.
- **`POST /jobs/discover`**: builds a **placeholder `MasterProfile(track=t)` with a raw string track** for requested tracks without a profile (`jobs.py:162-182`); runs `_run_sources(... cooldown=not force)`; returns `{discovered, fake_mode, profiles, sources[]}`. Synchronous ("Find jobs now").
- **`GET /jobs`** (`list_jobs`): filters status/track/tracks/experience_levels/origin/page/page_size; scope via `scoped_user_ids` (VA sees assigned hunters + `hunter_name`); **loads all jobs, filters + paginates in Python**; `_job_row` fires ~3 sub-queries per job (**N+1**).
- **Pagination** (`_pagination.py`): `PageSizeParam` default 25, **`le=100`** on main (→500 in PR #17). `paginate` slices in memory.
- Admin board management: `app/api/sources.py` (`/source-boards`, admin-only).

### Celery beat + tasks
- `beat_schedule.py`: `poll-sources` every **30 min** (plus warmup-rollover, sequencer-tick hourly, poll-inboxes 5 min, health-scan hourly).
- `app/pipelines/apply/tasks.py`: `poll_sources` (all active hunters × all profiles → `discover_for_user`); `on_job_discovered` (classify → score → if scored, `generate_cv`).
- Event bus `emit()` validates the contract then fire-and-forget `send_task` — downstream CV generation only runs when a worker is up.

### Data model + enums
- `Job` (`job.py`): **UNIQUE `(user_id, dedupe_key)`**; `track: Enum(Track, native_enum=False) nullable`, `track_override`, **`experience_level: String(50)`** (free string), `status: Enum(JobStatus) default discovered`, `origin` auto/manual, `raw: JsonB`.
- `Application`: UNIQUE `(job_id)`; `status` (internal) distinct from **`tracker_status`** (VA-facing, default applied).
- `SourceBoard`: **global** (per-hunter scope is future work).
- Enums: `Track = {frontend, backend, general}` (only 3); `JobStatus = {discovered, scored, rejected, tailoring, ready, submitted}`; no experience-level enum.

### Classifiers (all rule-based in the ingest path)
- `relevance.py`: skill-token overlap fraction, threshold 0.12 ("tune later"), no LLM.
- `track_classify.py`: ingest uses `classify` = `classify_rules` (hardcoded signal sets, 3 tracks). The richer CV-aware/LLM `classify_best` is **never** used during discovery.
- `experience_classify.py`: pure title-only regex → junior/lead/senior/mid; ignores `description`.

### Gaps — Discovery & Jobs Ingest
**Still present on main, fixed only in open PR #17:**
1. **`page_size` cap `le=100`** (`_pagination.py:12`) — broad client fetch 422s.
2. **Custom track strings written to `Job.track` Enum** — `_run_sources` sets `job_track = matched_track` (raw string) and `/discover` builds placeholder `MasterProfile(track=<string>)`; `Track` has only 3 members → `LookupError` bricks the jobs list.
3. **Cooldown `query_hash` omits `boards`** — a new board token is skipped until the window expires.
4. **SerpApi OR group unparenthesized** — seniority/`remote` bind only to the first term.
5. **Experience scoping injects only the first level** — multi-select fetches one level, drops/misses the rest.

**Design/operational:**
6. **Cooldown (1h) contradicts beat cadence (30m)** — real auto-discovery effectively runs hourly; only `force=true` bypasses.
7. **Real-source path is largely untested & fake-mode-gated** — default `use_fake_integrations=true` runs only `FakeSource` (5 hardcoded postings, ignores boards/keywords/location/experience).
8. **`FakeSource.fetch` calls `query.track.value`** — a placeholder profile's string track → `AttributeError` (caught, 0 jobs) for "Find jobs now" on a profile-less track.
9. **Adzuna is single-country (`gb` default), no West-Africa coverage** (`docs/JOB_SOURCES.md`); no multi-country fan-out.
10. **`experience_level` is a free string** — frontend values must exactly match the classifier vocabulary or the post-fetch filter drops everything; same brittleness for `selected_tracks` substring matching.
11. **`dedupe_key` edge cases** — different roles with same title/company/location collapse; board (`company=token`) vs aggregator (display name) never dedupe the same posting; per-hunter only.
12. **`list_jobs` N+1 + in-memory paging** — won't scale; `list_for_user` never uses its `status` param.
13. **Source registration relies on import side-effects**; shared mutable `SourceQuery.boards`; `poll_sources` unbounded fan-out; `SourceBoard.token` not unique; `posted_at` never populated; `docs/JOB_SOURCES.md` stale vs current scoping.



## 6.2 Generation, LaTeX & ATS

### Shared engine — `pipelines/generation.py`
`generate_cv_and_cover(...)` produces identical artifacts for the auto (`apply`) and manual (chat) paths: `job.status=tailoring` → `merge_confirmed_facts` (VA-confirmed skills appended **before** tailoring so they pass the truth boundary) → `priority_techs = ats.critical_keywords(jd)` → `tailoring.tailor` → `ats.score` → **`render.build_tex` (generic layout — NOT the user template)** → `_render_checked` (checked compile, stub fallback, stores `cv_stderr`) → R2 `{user}/{job}/cv.tex|pdf` → `GeneratedCv(status=ready)` → cover letter (hook + 3-paragraph body, generic render) → `job.status=ready` → emit `CV_GENERATED`.

### Truth-boundary model — `llm/tailoring.py`
Three tiers: **(1) deterministic** `tailor_fake` (select/reorder profile items) + `assert_truth_bounded` (every emitted leaf must exist verbatim in the profile, else `ValueError`); **(2) LLM-with-constrained-prompt + VA review** — `tailor` uses a strict prompt (only profile facts, achievement format only where supported, no invented metrics); `assert_truth_bounded` is **intentionally NOT run** on live output; **(3) advisory** scoring. Any live failure falls back to `tailor_fake` (`fell_back="llm_failed"`) — generation never breaks.

### Relevance vs ATS
`relevance.py` — deterministic prefilter, threshold 0.12, gates before tailoring. `ats.py` — internal 0-100 match score after tailoring (`TARGET_BAND 90-95`), requirement-zone-aware keyword extraction, `critical_keywords` (emphasis-marker scan). `ats_analyze.py` (the `ats_analyze` feature) — offline deterministic verdict or LLM JSON `{fit_score, gaps, recommendations, false_positives, verdict}`; consumed by `api/ats_checker.py`.

### LaTeX render + safety — `render.py`, `latex_safety.py`
`build_tex` (single-column ATS-safe article; **renders neither `education` nor `links`**), `build_cover_letter_tex`, `render_pdf` (stub if no tectonic **or on non-zero exit, silently**), `render_pdf_checked(timeout=30s)` (returns `(None, stderr)` on failure). `--untrusted`. `latex_safety`: `_FORBIDDEN_CMDS` (write18/input/include/directlua/…), `assert_safe` (400 on human LaTeX), `sanitize_latex` (best-effort strip on LLM output).

### Honor-or-explain regen — `latex_regen.py` (the ONLY template-honoring path)
Provider-agnostic (`_FEATURE="ats_analyze"` — reuses the ATS model/key, incl. Cohere-compat). Budgets `_CV_MAX_TOKENS=4000`/`_COVER_MAX_TOKENS=1500` (env-overridable). `_regen`: if template + live → render into the template; compile; **on failure re-prompt once with the tectonic stderr**; still failing → return the **attempt in the user's format** `compiled=False, fell_back="no_compile", stderr` (never the generic layout). Else `no_template`/`no_llm` → `build_tex`. Reasons: `None|no_compile|llm_failed|no_template|no_llm`.

### LaTeX API — `api/latex.py`
`POST /latex/preview` (`assert_safe` → 422 `{error:compile_failed, stderr}`), `POST /latex/regenerate` (drafts CV+cover in the user's template; returns `cv_latex/cover_latex/cv_compiled/cv_fell_back/cv_stderr`). Commit ("Use this") via `jobs.py from-latex` (`assert_safe` + compile + R2 upsert, 422 on failure). Builder UI (`jobs/[id]/builder`) auto-runs regenerate once, surfaces honor-or-explain notes + stderr in the compile-error panel.

### Models
`GeneratedCv` (unique `job_id`; `cv_json/ats_score/ats_breakdown/latex_source/tailoring_diff/status`; `model_version` never written). `MasterProfile` (truth corpus + `verified_extras`). `LatexTemplate` (per `(user,track,kind)`, raw `.tex`). `CvStatus = rendering|ready|failed`.

### Gaps — Generation, LaTeX & ATS
1. **The autonomous path never uses the uploaded LaTeX template (biggest gap).** `generate_cv_and_cover` calls `build_tex`/`build_cover_letter_tex` directly and never touches `LatexTemplate`/`latex_regen`. Honor-or-explain + "render in the hunter's own design" apply **only** to the manual `/latex/regenerate` builder; every auto-discovered CV/cover is the generic single-column layout.
2. **No template validation at save time** — neither upload nor editor-save runs `assert_safe`/a compile check/structural check; garbage or unsafe templates are only caught later (commit) or after a wasted regen round-trip. `.txt` allowed.
3. **Silent stub-PDF degradation** — `render_pdf` returns a blank `_stub_pdf()` on missing tectonic **or non-zero compile exit** with no signal, yet the auto path still sets `status=ready` → a "ready" application whose CV is an empty page. `_facts_present` is computed but **never enforced**. In dev without tectonic, `/preview` + `from-latex` show/commit a stub as if compiled.
4. **No LLM key → template not honored** — `is_live` False makes `_regen` return `no_llm`/generic `build_tex` even in the builder; tailoring can't reframe; cover falls back to templated text.
5. **Live tailoring output is not machine-verified** — `assert_truth_bounded` skipped on the LLM path; only the prompt + (nominal) VA review guard against a hallucinated employer/metric reaching a "ready" CV; no per-fact provenance.
6. **ATS format score is hardcoded** (always claims single-column/standard-headings/no-tables, 15% fixed) and is computed on `cv_json`, not the rendered LaTeX — so a two-column user template still scores "perfect format."
7. **Dropped sections** — `build_tex` renders neither `education` nor `links` (present in `cv_json`).
8. **Token-budget risk** — 4000-token cap on a long template + full CV can truncate on small models → compile failure → the single retry likely also truncates → `no_compile`. `openai_compat.requires_key=False` means a mis-set base_url can route real regen at an unconfigured endpoint; some compat backends ignore `max_tokens`.
9. **Field-name mismatch** — regen expects `ai_recommendations` but `ats_analyze` emits `recommendations`; if passed raw, ATS guidance is lost in the rewrite prompt.
10. **`sanitize_latex` can corrupt LaTeX** (leaves stray braces after stripping) → compile break that (on the honor path) isn't caught by a fallback.
11. **Under-tested:** `latex_safety`, `/preview` + `from-latex` 422 paths, stub-PDF fallback, and the auto-path template-ignoring behavior.



## 6.3 Outreach & Email (Pipeline B) + WhatsApp Bridge

**Bottom line:** the pipeline is architecturally complete and fully exercised in fake mode, but **not wired end-to-end for production** — the VA "approve first contact → send" step has no API endpoint, real WhatsApp reply correlation is broken, the Resend webhook signature scheme doesn't match real Resend, and there is no domain-provisioning/DNS-verification code.

### Entrypoint: application.submitted → draft
- Producer: `service.py:280` emits `APPLICATION_SUBMITTED` after a VA submits. Bus validates the frozen contract then fire-and-forgets `send_task`.
- Consumer `pipelines/outreach/tasks.py:26` `on_application_submitted` → `run_outreach` (`pipelines/outreach/service.py:39`): resolve job/user/track → `domains_repo.ensure_domain` → `apollo.lookup_people` (bail `outreach.no_people` if empty) → `hookfinder.find_hook` → persist `Contact` rows → pick `contacts[0]` (Apollo ranks engineer > HM > recruiter) → open `Thread(reply_address="")` → `draft_email.draft_outreach` → **`Outreach(sequence_step=first, status=review)`** + audit event.
- Drafting (`llm/draft_email.py`): proof-of-work label + real hook + de-risk line; fake deterministic vs live LLM split on `||`. Hook (`llm/hookfinder.py`): deterministic fake vs constrained live prompt requiring a cited signal.
- Apollo (`integrations/apollo.py`): `ROLE_RANK` engineer=0…talent=9; fake people at a slugged domain; live hits `mixed_people/search`, `[]` on error.

### Send flow (governed)
`send_outreach` (`outreach/service.py:98`) → `email_sender.make_send_fn` → **`governed_send`** → on sent stamps thread reply_address/root_message_id, `next_action_at = now + 4d`, emits `OUTREACH_SENT`. The `send_fn` (`email/sender.py:18`) is the only outbound provider call: From `<name> <track@domain>`, tagged Reply-To via `addressing.encode_reply_address`, threading headers, `resend.send_email`. Resend (`integrations/resend.py`): fake returns `<fake-N@resend.local>` + `SENT_LOG`; live lazily imports `resend` and calls `Emails.send` (blocking).

### Sending-domain model + warm-up governor
- `models/sending_domain.py`: unique `(user_id, track)` + unique `domain`; `resend_domain_id`/`dns_records`/DKIM-SPF-DMARC statuses (**never populated by code**), `warmup_stage`, `daily_sent_count`, `is_paused`, `bounce_rate`, `complaint_rate`. "9 rows total (3 hunters × 3 tracks)".
- Caps (`email/caps.py`): `STAGE_CAPS` 5/10/20/1000; `stage_for_age` d0-2/d3-6/d7-13/d14+ (docstring prose is off-by-one vs boundaries but internally consistent).
- Governor (`email/governor.py`) — the single outbound choke point: `SELECT … FOR UPDATE` locks the domain row; paused → queued; rolls daily counter; computes cap from age; `_weekly_count` across all domains/tracks (`sent AND sent_at >= now-7d`); if `daily >= cap OR weekly >= weekly_cap_per_hunter` → defer (queued, tomorrow 09:00 UTC); else `send_fn` + stamp + increment under the lock. `governed_relay` mirrors it for VA relays. `weekly_cap_per_hunter` default **20**.
- `domains_repo.ensure_domain` seeds `{track}-{hex}.jdmail.dev` marked `verified`/`warmup_stage=full` — a dev convenience.
- Admin: `api/admin_email.py` `GET /admin/domains`, `GET /admin/quota` (read-only, `require_admin`).

### Reply addressing (HMAC)
`email/addressing.py`: `apply+{job_hex}.{sig}@{domain}`, `sig = urlsafe_b64(hmac_sha256(secret, job_hex)[:6])`; decode `compare_digest`-verifies → UUID or None. **Signing key is `bridge_hmac_secret`** (reuses the WhatsApp bridge secret). Tested (round-trip + tamper).

### Reply detection / inbound webhook
- `api/webhooks/resend.py`: `POST /webhooks/resend/inbound` (verify sig → `ingest_inbound`), `POST /webhooks/resend/events` (→ `health.ingest_event`).
- `integrations/resend.py verify_webhook`: fake True; else bare `hmac_sha256(secret, body).hexdigest()` vs `X-Resend-Signature`.
- 3-tier thread match (`pipelines/respond/service.py:44`): exact reply_address → decode signed tag → job → thread; header `root_message_id == in_reply_to`; sender email → newest open thread. `ingest_inbound`: unmatched logged; idempotent on `message_id`; persists inbound `Reply`, thread → `awaiting_va`, flips `sent` outreach → `replied` (stops the sequencer), emits `REPLY_RECEIVED`.

### Respond pipeline (Pipeline C)
`on_reply_received` → `process_reply`: `classify_reply.classify` → `resolve_assignee(user_id, track)` (track-specific beats all-tracks) → `Dossier(status=pushed)` with `suggested_reply` only for routine replies → `bridge_client.push_to_va`. `relay_va_reply`: find dossier by `bridge_message_ref == in_reply_to_ref` → threaded `send_fn` → `governed_relay` → outbound `Reply`, dossier `relayed`, thread `open`.

### Celery queues + scheduled tasks
Queues `default,email,render,poll`; `acks_late`, prefetch 1. Beat: `poll-sources` 30m, `warmup-rollover` 00:05 (resets counters, advances stage, **drains queued** outreach whose `next_action_at<=now`), `sequencer-tick` hourly (`advance_followup`: first→followup1→followup2→stop), `poll-inboxes` 5m (**stub**), `health-scan` hourly (**stub**). Health (`email/health.py`): `+0.01`/bounce, `+0.001`/complaint, auto-pause at 0.05/0.001 (running counters, not rates).

### WhatsApp bridge (`apps/wa-bridge`, Go)
"A dumb transport pipe" — FastAPI→VA via `POST /push`; VA→FastAPI via `POST /api/webhooks/bridge/reply`. `POST /push` verifies `X-Bridge-Signature` (constant-time), fake returns `br_<hex>`, real returns whatsmeow msg id. `/_simulate_inbound` registered **only in fake mode**. Real (`session.go`): whatsmeow + sqlite session, QR pairing on first run; **inbound forwarded with `inReplyToRef=""`** (quoted-message context never extracted). API client `integrations/bridge_client.py` (fake `PUSH_LOG` / real signed POST). `BRIDGE_FAKE=1` pinned in Dockerfile + compose.

### Gaps — Outreach & Email (Pipeline B)
1. **No VA "approve first contact → send" endpoint — first contacts are stranded in `review`.** `send_outreach` is called only by the `queued` drainer, `advance_followup`, and tests — never by any route/task. Nothing transitions `review → queued/sent`. **First-contact emails are never sent** in the wired system. *(Single biggest end-to-end break.)*
2. **Real WhatsApp VA replies can't be correlated to a dossier.** Relay keys off `bridge_message_ref == in_reply_to_ref`, but real inbound WA is forwarded with `inReplyToRef=""` (`session.go:129`) — quoted-message `ContextInfo`/`StanzaID` never extracted. Works only via the fake `/_simulate_inbound`. No multi-dossier disambiguation.
3. **Resend webhook signature ≠ real Resend.** Uses bare `hmac_sha256(secret, body)` vs `X-Resend-Signature`; real Resend uses **Svix** (`svix-id/timestamp/signature`, `whsec_` secret). Real webhooks would be rejected in non-fake mode. No Svix code anywhere.
4. **No domain provisioning / DNS verification code.** `resend_domain_id`/`dns_records`/DKIM-SPF-DMARC are model fields never populated; `admin_email.py` is read-only; `ensure_domain` fabricates `*.jdmail.dev` marked verified. The ×9 SPF/DKIM/DMARC/MX checklist (`infra/README.md`) is entirely manual. Production sending can't route until rows are hand-inserted.
5. **Everything defaults to fake; real send double-gated** (`USE_FAKE_INTEGRATIONS=false` **and** `RESEND_API_KEY`; WhatsApp needs `BRIDGE_FAKE=0` + QR + CGO). Zero coverage of live Resend/whatsmeow/Svix paths.
6. **Follow-up cadence bug:** `next_action_at` always `now + 4d`; `FOLLOWUP2_DAYS=5` and `_NEXT_STEP` delays are dead code → followup1→2 gap is 4d not 5d.
7. **`bounce_rate`/`complaint_rate` are counters, not rates** (flat increments, no denominator, no decay) → misleading pause semantics.
8. **Deferred-send drain off by ~a day:** only `warmup_rollover` (00:05) drains `queued`, but deferrals target tomorrow 09:00 → not drained until the *next* day's rollover; nothing runs at 09:00.
9. **`poll_inboxes` + `health_scan` are stubs** → with the webhook rejecting real Resend (gap 3) and no inbound MX (gap 4), there is **no working production inbound reply ingestion**.
10. **Dossier created even with no assigned VA** (`status=pushed`, `bridge_message_ref=None`) → shows "pushed" but was never delivered and can never be relayed.
11. **Reply-address MAC reuses the bridge secret** (rotating one invalidates the other); inbound `Reply.raw` never populated (payload lost).
12. **wa-bridge is single-session/single-account for all VAs** (one linked device, single `wa_session` volume SPOF, connect-at-boot only).
13. **Blocking `resend.Emails.send` inside async while holding the `FOR UPDATE` domain lock** → serializes per-domain sends under load.

**Solid:** governor locking + cap math (well-tested), HMAC reply-address, the 3-tier thread matcher + `message_id` idempotency, the frozen-contract bus, the bridge's own HMAC + constant-time compare. The scaffolding is coherent; the gaps are last-mile production wiring.



## 6.4 AI Layer, Integrations & Settings

### Resolution engine — `app/llm/config.py`
`resolve(feature) → ResolvedLLM(provider, model, api_key, base_url)`. Precedence: **(1) per-user BYO override** (contextvar `get_user_llm()`; wins for the whole request if it has `api_key` OR `base_url`; back-fills anthropic key/model from settings) → **(2) per-feature env** `LLM_<FEATURE>_<FIELD>` → **(3) global `LLM_*`** → **(4) legacy `ANTHROPIC_*`** (anthropic only) → provider default model. `is_usable()` = `bool(api_key) or not provider.requires_key` (keyless local OpenAI-compatible counts).
Features (`config.py:22-25`): `tailoring, cover_letter, hookfinder, draft_email, classify_reply, ats_vet, ats_analyze, resume_intel, cv_structure, track_classify`. **No `chat` or `latex_cv` feature key** — those are routers; the LaTeX CV/cover rewrite deliberately reuses `ats_analyze` (`latex_regen.py:34`).

### Facade + adapters
`client.py`: `is_live(feature)` (False in fake mode), `complete_text(...feature=)` (raises `DomainError(code="llm_not_configured", remediation="Add a provider API key in Settings…")` if unusable), `try_complete_text` (returns None on any error — used by the deterministic-fallback features). Registry `providers/base.py` (`register`/`get`).
- **anthropic**: official SDK, `requires_key`, default `claude-opus-4-8`.
- **openai** (`openai_compat.py`): one adapter for OpenAI/Groq/Together/OpenRouter/Ollama/**Cohere**; `requires_key=False`; POSTs `{base_url}/chat/completions`; retries 429/5xx; tolerant `_extract_text`.
- **google** (`google.py`): raw httpx, **API key in the URL query string**; tolerant `_extract_text` (survives `finishReason: MAX_TOKENS` with no `parts`).
Every feature calls `client.complete_text(..., feature="x")` → `resolve("x")` → prefers the contextvar. So a user's key is used **only when a request set the contextvar** (see below).

### Per-user credentials — `app/llm/credentials.py`
`load_preferred_override`: reads **`AiIntegration` first** (default-first, decrypt, return `{provider,model,api_key,base_url}`), falls back to legacy **`UserLlmCredential`**. `validate_key`: fake → `configured|invalid` on key presence; live → real round-trip (`max_tokens=16`, 20s) → `configured|invalid|unreachable` (only `401/403/auth/invalid/api key/unauthor` → `invalid`).

### Encryption — `app/llm/crypto.py`
Fernet, key = `sha256(credential_enc_key or jwt_secret)` (stable, urlsafe-b64). `decrypt` swallows `InvalidToken` → None. `mask` = `••••+last4`.

### Request binding — `app/deps.py` + `app/llm/context.py`
`bind_user_llm` dependency: **only for `PrincipalType.user`** (no-op for VAs); loads the override into the contextvar, resets in `finally`. Bound on routers: `/ats`, `/jobs`, `/latex`, `/chat`. **NOT** bound on `/onboarding` (so `resume_intel`/`cv_structure` use the server key) or in background pipelines (hookfinder/draft_email/classify_reply → env only).

### AI Integrations API — `app/api/integrations.py` (`/integrations`)
Adapters `{anthropic, openai, google}`. `_out` decrypts to a `masked_key`, never returns plaintext. Endpoints: `GET /templates`, list, create (first integration auto-becomes default; encrypts key), update (new key → status `unknown`), delete (promotes a new default), `PUT /{id}/default`, `POST /{id}/validate` (stores status + latency), `GET /{id}/health`, `GET /{id}/models/discover`, `POST /{id}/models`. Model `ai_integration`: `user_id, name, provider, template, base_url, encrypted_api_key, model, config, models, capabilities, status, is_default, last_validated_at`.

### Legacy Settings API — `app/api/settings.py` (`/settings`)
Older one-row-per-`(user, provider)` BYO system (`user_llm_credential`). `GET/POST/DELETE /llm-keys`, validate, preferred. `_check_provider` returns an actionable error for `cohere` (use `openai` + base_url). **Frontend `/settings` page uses only the new integrations API**; the legacy service is effectively dead UI-side.

### Templates & discovery
`llm/templates.py`: four templates (`anthropic` discovery false; `google`/`openai`/`custom` discovery true) — schema drives the frontend form. `llm/discovery.py discover_models`: fake static lists; live google `/models?key=`, openai `/models` Bearer; `[]` on error.

### Frontend — `settings/page.tsx`
The AI Integrations dashboard. `STATUS` map tolerates both vocabularies (`configured`+`healthy`, `unreachable`+`offline`, `invalid`, `rate_limited`, `unknown`). Quick-setup cards per template; rows show `provider · base_url · model · masked_key` + model chips + Test/Models/Star/Edit/Delete; **dynamic form rendered purely from `t.fields`**. Mutations invalidate `integrations` + `readiness`. `lib/toast-error.ts` surfaces backend `remediation` + `action` route.

### Gaps — AI Layer, Integrations & Settings
1. **Readiness reads the WRONG table (real bug).** `api/user.py:41-45` computes `has_key`/`key_valid` (and `api_key_validated`) from **`UserLlmCredential` only**, but routing + the whole `/settings` UI now write **`AiIntegration`**. A user who configures + validates via the AI Integrations UI still sees "Configure an AI provider" incomplete, and every `invalidate(readiness)` on that page is a no-op for the new table. **Routing and readiness are out of sync.**
2. **Status-vocabulary mismatch.** `validate_key` writes `configured|invalid|unreachable`; the model/shared-types comments advertise `healthy|offline|rate_limited` (never written). Frontend papers over both; readiness checks `status=="configured"`.
3. **BYO override is all-or-nothing + single-model.** Once a user override exists it wins for **every** feature and bypasses per-feature env; only one `is_default` for all features — no per-feature routing.
4. **Features not wired to per-user routing:** onboarding `resume_intel`/`cv_structure` (no `bind_user_llm`), and all background pipeline features (no request context). A hunter's key is honored only for `/ats`, `/jobs`, `/latex`, `/chat`.
5. **Encryption key-rotation is a silent data-loss trap.** Key derives from `credential_enc_key or jwt_secret`; rotating either makes every stored key undecryptable — `decrypt`→None silently, falls back to env, UI shows `has_key=true` but `masked_key=null`. No versioning/re-encrypt path.
6. **Cohere requires the compat URL** (`https://api.cohere.ai/compatibility/v1`); templates don't hint this.
7. **Gemini quirks:** validate/parse mitigated, but free-tier `quota=0`/billing and 429 map to `unreachable` (shown "Offline", not actionable); API key travels in the URL query string (log-leak risk).
8. **`validate_key` doc drift** (comment says `max_tokens=1`, code uses 16).
9. **Legacy dual-system debt** (two APIs, two tables, two services; only the new one has UI; no backfill/removal plan).
10. **Discovery flag ignored** (`/models/discover` never checks the template's `discovery`).
11. **No default-integrity DB constraint** (one `is_default` per user relies on app logic; concurrency could yield 0/2 defaults).
12. **`try_complete_text` swallows BYO-key failures** — ats_*/resume_intel/cv_structure/track_classify fall back to deterministic output with only a warning log; the user is never told their key failed.
13. **Fake mode masks reality** — `validate_key` reports "Healthy" purely on key presence without contacting the provider.



## 6.5 Identity, Onboarding, Readiness & Tracks

### Auth (`app/api/auth.py`, `/api/auth/*`)
One login surface for two principal types — hunters/admins are `User`, VAs are `Va`. Session = httpOnly `access_token` JWT + rotating hashed `refresh_token` (path `/api/auth`). `_cookie_attrs`: Secure force-on when SameSite=None. `POST /login` (no `is_active` check), `POST /register` (invite-gated; VA→`Va`+`VaAssignment`, admin→`User(platform_id)`, else hunter; auto-login), `POST /refresh` (rotate: revoke old row, re-issue), `GET /me`, `POST /logout` (revoke + clear). `security.py`: argon2, HS256 JWT (`{sub,type,role,track_scope,iat,exp}`, no iss/aud), `secrets.token_urlsafe(48)` refresh → sha256 stored. Invite keys `A-Z2-9` len 6.

### Principals & access (`app/deps.py`)
`Principal(id,type,role,track_scope)`; `current_principal/current_user/current_va/require_admin`; **`scoped_user_ids`** (hunter→self; VA→all assigned `VaAssignment.user_id`) = read scope; **`authorize_owner`** = write scope (hunter own resource; VA needs covering assignment). `bind_user_llm` loads BYO key **only for `type is user`**.

### Roles & enums (`app/core/enums.py`)
`Track = {frontend, backend, general}`; **`UserRole = {hunter, admin}` — no `va`, no `super_admin`** (VA "role" is the bare string `"va"`). VA work queue `api/va.py` `GET /va/queue` unions `submit`/`outreach_review`/`reply`.

### Invites & team (`app/api/invites.py`, `/invites`)
`POST /invites/hunter|admin` (admin), `POST /invites/va` (any hunter → `VaAssignment` at register), `GET /invites`, `DELETE`. `INVITE_TTL_DAYS=7`, single-use, dup-email/dup-pending → 409. Models `Invite`, `VaAssignment` (`(va_id,user_id,track)`, NULL track = all).

### Onboarding (`app/api/onboarding.py`, `current_user`)
Upload validation 10MB + ext allowlist. `POST /onboarding/role-cv` → R2 stable key → extract text + naive skills → upsert `RoleCv` + seed `MasterProfile` + **synchronous `cv_structure` LLM** → `confirmed=False`. Editors: target-roles/verified-extras/preferences/career-details; cover-letter + LaTeX templates; `PUT /me/active-track` (enum `Track` only); `GET /onboarding/status` (4 steps); `POST /profiles/{track}/confirm` (needs parsed RoleCv). `MasterProfile` fields: skills/experience/education/projects/links/target_roles/truth_corpus/verified_extras/preferred_skills/career_preferences/preferred_locations/preferred_job_types/salary_expectation/confirmed.

### Readiness (`app/api/user.py` `GET /api/user/readiness`)
5 steps: `ai_provider` (any `encrypted_api_key`), `track_created` (any `MasterProfile`), `resume_uploaded` (any `RoleCv`), `profile_confirmed`, `cover_letter_template`. `progress`, `next_action`, `api_key_validated` (any status=="configured"), per-track block (read-only, no backfill).

### Tracks (`app/api/tracks.py`, `models/track_entity.py`)
Registry/lifecycle over per-`(user, slug)` data; readiness **derived**. `GET /tracks` (union + **lazy backfill write-on-GET**), `POST` (slugify; dup→`track_exists`; archived→un-archive+rename), rename/archive/unarchive, `resume/from/{source}` (duplicates RoleCv by **key reference** + subset of profile fields; drops target_roles/locations/salary). `require_track_resume` = the AI guard (`code=track_resume_required`, action Upload Resume).

### Errors (`app/core/errors.py`, `app/main.py`)
`DomainError(message,code,title,remediation,action)` + subclasses; handler returns `{success:false, code, error, message, title?, remediation?, action?}`.

### Gaps — Identity, Onboarding, Readiness & Tracks
1. **`UserRole` has no `va`/`super_admin`** yet `MeResponse.role` + platform code narrate a super-admin/platform-admin hierarchy that **isn't modeled** (only `admin`, differentiated by `platform_id`). **No admin bootstrap** — a fresh deploy can't mint the first admin via the API.
2. **Team/VA management is create-only** — no list-assigned-VAs, unassign, reassign, or deactivate; `is_active` never exposed (can't disable a compromised account). `VaAssignment` only ever created at registration. The `SE_gig_fe` staff UI calls `/staff/*` endpoints **that don't exist** in this backend.
3. **Custom tracks are largely cosmetic** — `MasterProfile/RoleCv/LatexTemplate/VaAssignment/Invite/User.active_track.track` are all `Enum(Track)` (3 members), but `POST /tracks` accepts arbitrary slugs and `POST /onboarding/role-cv` takes `track: Track` — so you can never upload/confirm/generate for a custom slug. `duplicate_resume` writes raw string slugs bypassing the enum.
4. **Two divergent onboarding progress surfaces** (`/onboarding/status` 4 steps vs `/user/readiness` 5 steps) that can disagree; `track_created` = a `MasterProfile` (only from CV upload), so creating a track via `/tracks` doesn't satisfy it, and `track_created`+`resume_uploaded` flip together.
5. **Auth security caveats** — default `jwt_secret="dev-insecure-change-me"`, no min-length, no iss/aud; `credential_enc_key` derives from `jwt_secret` (rotation invalidates stored keys); `cookie_secure=False`/`samesite=lax` defaults (cross-site deploy must set `none`); **no `is_active` check at login/`/me`**; no refresh reuse/breach detection; `track_scope` plumbed but dead; no login rate-limit; corrupted argon2 hash → 500.
6. **VA-triggered generation uses the wrong LLM key** — `bind_user_llm` no-ops for VAs, so a VA generating for a hunter falls back to the env key, not the hunter's stored credential.
7. **Data-lifecycle gaps** — no delete for role-CV/profile/templates (overwrite only, so a track can't be reset to `setup_required`); `duplicate_resume` shares the R2 object by reference with no divergence mechanism; `RoleCv.parsed_at` never written; `cv_structure` LLM runs synchronously in the upload request (latency/cost; empty-text DOCX → `failed` permanently blocks confirm).



## 6.6 Frontend (apps/web) & Shared Types

**Stack:** Next 15.5, React 19, react-query v5, `ky`, zustand (integrations UI only), RHF+zod, sonner, Tailwind v4 ("coffee" monochrome + 6 status tokens), Poppins. **Light-mode only.** `@jd/shared-types` consumed as raw TS (no build).

### Cross-cutting
- **Transport** (`lib/api/client.ts`): `API_ROOT = IS_PROD && NEXT_PUBLIC_API_BASE ? direct : same-origin /api proxy`. ky `credentials:include`, 30s, retry 0; `afterResponse` 401 → single-flight `/auth/refresh` → replay once → else `/login?next=`. `toApiError` unwraps `{detail|message|error|code|title|remediation|action}`. `absoluteApiUrl` for downloads/iframes.
- **Proxy** (`app/api/[...path]/route.ts`): forwards `/api/*` → `${BACKEND_URL}/api/*`, streams multipart, re-emits `Set-Cookie`, drops upstream content-encoding/length; distinct 500 (no BACKEND_URL) / 502 (cold-start hint).
- **Middleware** gate keys off `NEXT_PUBLIC_API_BASE` (direct → defers to `AuthGuard`; proxy → checks `access_token` cookie). **Providers**: one QueryClient (staleTime 30s, retry 1). Centralized `query-keys.ts`. `force-dynamic` on all authed pages.

### Pages (route group `(authed)` → `AuthGuard` + `AppShell`)
Sidebar `navFor(me)` is principal-aware (VA hides Profile/Settings/Team; admin adds Admin/Domains). **Jobs** (broad fetch + localStorage cache + client filter/paginate; PR #18 adds timestamp/empty-state/banner). **Job detail** (state-driven Generate→Apply, stepper, ATS card, outreach thread). **Builder** (auto-regenerates once on load; honor-or-explain stderr panel). **Applications/Tracker** (server-paginated, Truthful badge). **VA Queue** (submit/outreach_review/reply sections). **ATS Checker** (717 lines; debounced track-suggest; Resume-Intelligence panel; "Regenerate in your LaTeX template" handoff via sessionStorage). **Manual Apply** (chat/prompt flow → generate). **Profile** (965 lines; VA-locked; per-track CV/roles/skills/extras/career-details + cover + LaTeX templates). **Settings** = AI Integrations dashboard. **Team/Admin/Domains/Help.**

### Data layer / shared-types
Services per domain (jobs/applications/auth/ats/latex/tracks/readiness/onboarding/integrations/chat/va/admin/invites/platforms/settings). `normalizeJobDetail`, `normalizeQueue`, `adminService` all **defensively normalize** unstable backend shapes (evidence of live drift). `shared-types/src/index.ts` (783 lines) is **hand-mirrored from the backend — no codegen/OpenAPI sync**.

### Gaps — Frontend & Shared Types
1. **Broken design tokens (widespread):** `status-rejected`/`status-accepted` are used in ~14 files but `globals.css` only defines `status-rejection`/`status-offer` → **all RHF validation errors, the `danger` button, `ErrorState`, ATS chips, domain bounce/spam text render with no color.** `lib/status.ts` uses the correct names — two inconsistent conventions.
2. **`applicationsService.exportUrl()` is hardcoded same-origin** `/api/applications/export.xlsx` (not `absoluteApiUrl`) → in **direct mode** the download carries no cookie → likely 401. Used on jobs + applications pages.
3. **Jobs page (main):** cache key `jd_jobs_cache_v1` has no timestamp (stale on reload); no filter-aware empty state; no `MAX_FETCH=500` capped banner (>500 jobs silently truncated). *(All three fixed in open PR #18.)* Custom tracks can be added but never removed.
4. **Dead code:** `settingsService` + LLM-keys types (no page uses them — superseded by Integrations), `components/status-badge.tsx`, `queryKeys.llmKeys`/`chatSession`.
5. **Missing states:** ATS Checker + Manual have no page-level loading/error (silent `?? []`); Settings templates query has no error state; builder auto-fires a 120s regenerate on every visit.
6. **Accessibility/responsive:** **no mobile nav** (sidebar `hidden md:flex`, no drawer → pages unreachable on phones); table rows are `<tr onClick>` with no keyboard affordance; modals don't trap/restore focus or lock scroll; `MultiSelect` lacks listbox roles/arrow-keys.
7. **Type-drift (no codegen):** custom-track strings vs strict `Track` unions → `TRACK_LABELS[customTrack]` renders empty on Tracker/Domains/Manual/ATS (VA page guards, others don't); `AtsBreakdown.format_flags` object form silently unrendered; status-string additions degrade to "Not tested". Five `exhaustive-deps` disables on resync effects.



## 6.7 Infra, Migrations, Tests & Deployment

### Alembic — head `a2b3c4d5e6f7`
Strictly linear chain of **18 additive-only migrations**, root `f02bb8c1792d` (14 frozen tables) → head **`a2b3c4d5e6f7`** (`ai_integration`, backfills `user_llm_credential → ai_integration` on Postgres only). Notable: `f4d5e6f7a8b9` (`job.experience_level` + widen track to VARCHAR(50), **Postgres-only, no-op on SQLite**); `f5a6b7c8d9e0` (track entity — **renumbered from an `a1b2c3d4e5f6` collision**, commit `323d541`, was breaking deploy with `CycleDetected`). Two past collisions total; IDs are hand-authored sequential hex. `env.py`: async engine, `compare_type=True`, URL from settings.

### Config — `app/config.py`
Single `Settings`. Key fields: `database_url` (asyncpg-normalized via validator; production rejects compose hostnames), `jwt_secret="dev-insecure-change-me"`, `credential_enc_key=""` (falls back to jwt_secret), cookies (`secure=False`, `samesite="lax"`), `llm_provider/model/api_key/base_url` (per-feature via env `LLM_<FEATURE>_*`), integrations (blank→fakes), R2, `weekly_cap_per_hunter=20`, **`use_fake_integrations=True`**, **`discover_cooldown_seconds=3600`**. `get_settings()` lru-cached.

### Tests — in-memory SQLite + fake mode
31 files / ~132 functions (~"130-146 passed"). One `session` fixture on `sqlite+aiosqlite:///:memory:`; ASGI cookie-auth tests need `base_url="https://test"`. **Thin/no coverage:** Pipeline B (2 tests) / C (3 tests); **wa-bridge Go = 0 tests**; **frontend = 0 tests** (only `pnpm build`/typecheck); **Postgres-only migration DDL + backfill never exercised** (SQLite CI); no live-LLM/live-R2/beat-schedule tests.

### Docker / infra
`apps/api/Dockerfile` (python 3.12-slim, uv, **tectonic 0.15.0**, `RUN_MIGRATIONS=1`, entrypoint runs `alembic upgrade head`). `docker-compose.yml` (7 services; postgres host 5433, redis 6380; worker/beat `RUN_MIGRATIONS=0`); `docker-compose.nginx.yml` (Cloudflare-Flexible origin, webhook body streaming for HMAC). `render.yaml` (7 resources, `region: frankfurt`; api `preDeployCommand: alembic upgrade head`, `COOKIE_SECURE=true`; **api image built 3×**; wa-bridge = private pserv + 1GB disk). `Makefile` (`dev/up/down/migrate/seed/test/fmt`; PR #19 adds `test-docker`).

### Deployment reality
Render (backend, one image ×3) + Postgres + Key Value; frontend Vercel/Render; Cloudflare R2 (private `jd-cvs`, presigned). Secrets in Render dashboard (`sync:false`); `CREDENTIAL_ENC_KEY` flagged required. `USE_FAKE_INTEGRATIONS=false` to go live (flips **all** fakes at once). Bootstrap via `python -m scripts.seed` (admin `ada@jd.dev`). **9 sending domains** SPF/DKIM/DMARC/MX = manual.

### Repo-wide marker scan
**Zero literal `TODO/FIXME/HACK/NotImplementedError` in Python app code or Go.** Gap signals are intentional seams: `poll_inboxes` + `health_scan` are **documented no-ops**; `render.py` stub-PDF fallback; `governor.py:34` per-hunter-timezone **placeholder**; adapters no-op without creds; `jobs.py` placeholder MasterProfile. **`ARCHITECTURE.md` is stale** — still marks Pipelines B/C `[SCAFFOLD]` though they're implemented (fake-mode).

### Gaps — Infra, Migrations, Tests & Deployment
1. **Live Render backend chronically behind `main`** (`PROGRESS.md:12` — last on a broken pre-fix commit). The running system may not match the audited code; no documented auto-deploy-on-merge.
2. **Postgres-only migration logic untested** — `f4d5e6f7a8b9` DDL + `a2b3c4d5e6f7` backfill `return` on non-Postgres, so CI (SQLite) never exercises them; failure surfaces at deploy → missing columns → 500s.
3. **Migration-chain fragility** — hand-authored sequential hex IDs; two past `CycleDetected` collisions; no CI single-head guard.
4. **Frontend = zero automated tests** (largest untested surface); **wa-bridge = zero Go tests** (real WhatsApp path manual-only).
5. **Pipelines B/C thinly tested seams** with no-op `poll_inboxes`/`health_scan`; stale `ARCHITECTURE.md`.
6. **`USE_FAKE_INTEGRATIONS` is all-or-nothing** — can't mix real R2 with fake email; real-provider paths unexercised.
7. **Secrets fall back to insecure dev defaults** with no startup guard — a forgotten `JWT_SECRET`/`CREDENTIAL_ENC_KEY` deploys silently insecure (and rotating either bricks stored keys).
8. **Ops burden** — 9 sending domains fully manual; api image built 3× on Render; free-tier services idle-down (bad for worker/beat); two divergent `.env` files (root vs `apps/api`).



---

## 7. Consolidated gap register

Ranked by damage to the user experience / trust, not implementation difficulty. Each item cites the module (§6.x) with the detail. Items marked _(PR #17)_ are already fixed in an open, un-merged PR.

### P0 — trust violations & things that silently break
1. **The autonomous pipeline never uses the uploaded LaTeX template** (§6.2). Every auto-discovered CV/cover is the generic single-column layout; "render in your own design" applies only to the manual builder. Breaks the document-identity promise.
2. **Silent stub-PDF "ready"** (§6.2). `render_pdf` returns a blank placeholder on missing tectonic **or non-zero compile exit**, yet the job is still marked `ready` — a "ready" application whose CV is an empty page. `_facts_present` is computed but never enforced.
3. **Readiness reads the wrong credential table** (§6.4). `api/user.py` derives "AI configured" from the legacy `UserLlmCredential`, but routing + the whole Settings UI now write `AiIntegration` — a user who configures + validates a key still shows "not configured," and readiness invalidations are no-ops.
4. **Pipeline B has no VA "approve → send" endpoint** (§6.3). First-contact emails are created in `status=review` and nothing transitions them to send — **first contacts are never sent** in the wired system.
5. **ATS emits three uncorrelated numbers, a hardcoded 15% "format" pass, scores `cv_json` not the artifact, and silently drops recs** via the `recommendations`/`ai_recommendations` mismatch (§6.2, §6.4). _(Being fixed by the current ATS evolution — Deliverable 1.)_
6. **Jobs list P0s** — page-size cap 422 on the broad fetch; a custom track string written to the `Job.track` enum bricks the list (also `NameError`'d filtered discovery) _(PR #17)_.

### P1 — real functionality gaps / correctness under real mode
7. **Real WhatsApp reply correlation is broken** (§6.3) — inbound forwarded with `inReplyToRef=""`; the WA→email relay only works via the fake simulate path.
8. **Resend webhook ≠ Svix** (§6.3) — bare HMAC vs Svix headers; genuine Resend webhooks are rejected in real mode → no working production inbound reply ingestion (with `poll_inboxes` a stub).
9. **No domain provisioning / DNS verification code** (§6.3) — the 9 sending domains are a manual runbook; sending can't route until rows are hand-inserted.
10. **Live tailoring output is not machine-verified** (§6.2) — `assert_truth_bounded` is skipped on the LLM path; only the prompt + nominal VA review guard against a hallucinated employer/metric.
11. **VA-triggered generation uses the wrong LLM key** (§6.4/§6.5) — `bind_user_llm` no-ops for VAs → env key, not the hunter's stored credential.
12. **Encryption key-rotation is silent data loss** (§6.4) — keys derive from `credential_enc_key or jwt_secret`; rotating either makes every stored key undecryptable with no signal.
13. **Frontend broken design tokens** (§6.6) — `status-rejected`/`status-accepted` don't exist → all form validation errors, the danger button, error states render with no color.
14. **`exportUrl()` hardcoded same-origin** (§6.6) — likely 401 for the `.xlsx` download in direct (cross-origin) mode.
15. **Zero automated tests for the frontend and the Go wa-bridge; Postgres-only migration DDL + backfill never exercised** (§6.7).

### P2 — friction, honesty, and drift
16. **Custom tracks are cosmetic** (§6.5) — creatable but you can't upload/confirm/generate for a non-enum slug.
17. **Two divergent onboarding-progress surfaces** (`/onboarding/status` 4 steps vs `/user/readiness` 5) that can disagree (§6.5).
18. **Cooldown window (1h) contradicts the beat cadence (30m)** → real auto-discovery effectively hourly (§6.1).
19. **Outreach cadence/health bugs** (§6.3) — follow-up gap 4d not 5d; deferred-send drained ~a day late; bounce/complaint are counters, not rates.
20. **ATS drops `education`+`links` from `build_tex`; format score hardcoded** (§6.2).
21. **No mobile navigation + several a11y gaps** (focus trapping, keyboard row nav) (§6.6).
22. **Secrets fall back to insecure dev defaults with no startup guard**; `USE_FAKE_INTEGRATIONS` is all-or-nothing (§6.7).
23. **No delete for role-CV/profile/templates** (overwrite-only) → a track can't be reset (§6.5); team/VA management is create-only (§6.5).
24. **Jobs page (main)** — stale-cache-on-reload, no filter-aware empty state, no capped-results banner _(PR #18)_.

### P3 — scale, hygiene, and documentation
25. `dedupe_key` edge cases; `list_jobs` N+1 + in-memory paging (§6.1).
26. Legacy dual AI-key system (two tables/APIs, no backfill/removal plan) (§6.4); dead frontend code (§6.6).
27. Type-drift with no OpenAPI codegen (`shared-types` hand-mirrored) (§6.6).
28. Migration-chain fragility (hand-authored IDs, two past collisions, no single-head CI guard) (§6.7).
29. Stale `ARCHITECTURE.md` (marks Pipelines B/C `[SCAFFOLD]` though implemented) and `JOB_SOURCES.md` drift (§6.7/§6.1).



---

## 8. Open PRs pending review

- **#17 `fix/jobs-discovery-correctness`** — 5 atomic commits + tests; backend suite 146 passed. Fixes two P0s (jobs-list 422 broad-fetch; custom-track enum brick that also `NameError`'d on filtered discovery) plus discovery scoping.
- **#18 `feat/jobs-web-cache-ux`** — typecheck + `next build` green. Stale-cache refresh, honest empty/capped states.
- **#19 `chore/docker-test-env`** — config valid; in-container pytest exit 0; host suite green. Hermetic offline test runner + env-file sync.

All three are per-feature branches off `main`, independent (no file overlap), left un-merged for your review.

---

## 9. Recommended finetuning order

Sequenced by _experience gain ÷ change size_, and by dependency (trust fixes before polish):

1. **ATS module (in progress).** The settled first priority (§10 of the Constitution) — every downstream consumer inherits its errors. Gate→cap→score, one honest number, `false_positives` applied, the `recommendations` wiring fix, a persisted analysis entity, the format gate, and readiness-state UI. Fixes P0-5.
2. **Generation trust (I2/I4)** — make the autonomous path honor the uploaded template, and stop marking a stub/failed render `ready`. Fixes P0-1, P0-2; unblocks the ATS format gate (shared artifact provenance).
3. **Readiness ↔ AiIntegration** — point readiness/onboarding at the table routing actually uses (small, high-impact). Fixes P0-3.
4. **Pipeline B end-to-end** — VA approve→send endpoint, real Svix webhook verification, WhatsApp reply correlation, and domain provisioning/health. The largest area; fixes P0-4, P1-7/8/9.
5. **Identity/security hardening** — VA-key routing, key-rotation safety, `is_active` at login, secrets startup guard. Fixes P1-11/12, P2-22.
6. **Frontend correctness & UX** — design tokens, `exportUrl`, mobile nav + a11y, filter-aware/empty/capped states. Fixes P1-13/14, P2-21/24.
7. **Test & migration safety net** — frontend + wa-bridge tests, a Postgres migration test, single-head CI guard. Fixes P1-15, P3-28.
8. **Remaining module finetunes** — custom-track first-classness, onboarding-progress unification, discovery scale, doc refresh. Fixes P2-16/17/18, P3.

Modules #2–#3 are cheap and high-trust; do them right after the ATS work. #4 is a project in itself and deserves its own phased plan.

