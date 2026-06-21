# Progress / Handoff

Running log of the features built recently so a fresh session can pick up with full
context. The repo is the **Job Application & Outreach Engine** (FastAPI + Celery backend
in `apps/api`, Next.js dashboard in `apps/web`, Go WhatsApp bridge in `apps/wa-bridge`,
shared TS types in `packages/shared-types`).

**State at last update:** Backend `uv run python -m pytest -q` → **88 passed**.
`pnpm --filter web build` → green. The storage + discovery work below is in the working
tree — **commit + redeploy (`api` + `web`) to ship**. Reminder: secrets (Adzuna/SerpApi,
**R2**) live in the **Render dashboard env** (the local `.env` is ignored by Render); the
deploy must run `alembic upgrade head`.

> **The #1 non-negotiable is the TRUTH BOUNDARY**: generation only reorders/reframes
> facts already in the master profile / `truth_corpus` or VA-confirmed-true. Never
> fabricate. `tailoring.assert_truth_bounded` proves it on the deterministic path; the
> live LLM path is constrained by prompt. Every feature below respects this.

---

## Most recent (this session)

### Cloudflare R2 storage made real — uploads in, presigned downloads out
**Why:** files were uploaded to R2 (keys persisted) but the stored `pdf_url` was the
**private** S3 URL, the frontend opened PDFs via Google Docs Viewer (can't fetch a
private/authed URL), and there was **no download mechanism** — files went in but couldn't
come out.
- `app/integrations/r2.py`: hardened the boto3 client (`region_name="auto"`, s3v4), ran
  blocking calls via `asyncio.to_thread`, added **`presigned_url()`** (short-lived GET URL;
  honors optional `R2_PUBLIC_BASE_URL`) and **`get_bytes()`**.
- `app/api/_files.py` `serve_key()`: serve an object as a **307 → presigned redirect**
  (live) or **streamed bytes** (fake/dev); 404 if missing.
- Auth-scoped download routes: `GET /api/jobs/{id}/cv` + `/cover` (authorize_owner),
  `GET /api/onboarding/role-cv/{track}/file` + `/cover-letter-template/file` (current_user).
- `app/api/jobs.py`: `resume_doc_url`/`cover_letter_doc_url` (and detail `download_url`) now
  point at those endpoints; dropped `_gdocs_viewer_url`.
- Uploads ([onboarding.py](apps/api/app/api/onboarding.py)): validate ext (pdf/doc/docx[/txt])
  + ≤10 MB → 400; **stable keys** (`{user}/role-cv/{track}/source.{ext}`) so re-uploads
  overwrite (no orphans). Keys remain the DB recovery handle.
- Frontend: `lib/api/client.ts` `absoluteApiUrl()` (proxy-vs-direct safe); `DocLinkCell` +
  job-detail `DocLink` link straight to the download endpoint; `/profile` gains **Download**
  links for the uploaded source CV + cover-letter file. Tests: `tests/test_storage.py`.
- ⚠️ R2 creds (`R2_ACCOUNT_ID/ACCESS_KEY_ID/SECRET_ACCESS_KEY/BUCKET/ENDPOINT`) must be in
  the **Render** env; `R2_ENDPOINT = https://<account_id>.r2.cloudflarestorage.com`.

### On-demand job discovery + diagnostics
**Why:** discovery was a 30-min beat with no trigger/visibility; real jobs weren't appearing.
- `POST /api/jobs/discover` + a **"Find jobs now"** button on the Jobs page — runs discovery
  in-request (no beat/worker dependency) and returns a **per-source report**
  (`found/inserted/error/note`). `app/pipelines/apply/service.py` `_run_sources` isolates each
  source in try/except (a missing `source_board` table can't kill discovery) and emits rich
  `discover.*` structured logs (visible in Render).
- Source failures now **surface** (Adzuna/SerpApi log + raise → shown in the report/logs);
  SerpApi's "no results in a 200 body" is treated as benign empty, real errors raised.
- Query tuning for remote/global: **Adzuna `what_or`** (was AND-joining 6 skills → 0),
  **SerpApi top-3 skills + "remote"**, `ADZUNA_COUNTRY` configurable (default `gb`).

### Manual-apply 500 fix + jobs-table readability
- `app/llm/tailoring.py`: the live tailoring path now **parses tolerantly** (strips ```json
  fences) and **falls back to the deterministic, truth-bounded path** on any LLM/parse error
  — fixed the 500 on `POST /api/chat/sessions` (Analyze).
- `apps/web/app/(authed)/jobs/page.tsx`: per-column widths + 2-line clamp on Role/Company
  (tooltips), top-aligned cells, table `min-w` for horizontal scroll on small screens.

---

## Features delivered (most recent first)

### 1. ATS achievement-rewrite (truth-bounded) + board-scraper wiring
**Why:** make a CV's *real* tech usage explicit so the internal ATS parses it ("Used
`<tech>` to `<X>`, achieving `<Y>`"); and make Greenhouse/Lever/Ashby actually pull jobs.

- **Emphasis detection** — `app/pipelines/apply/ats.py`: `critical_keywords()` finds techs
  a JD marks *strongly recommended / must-have / required* (detected directly from the JD,
  independent of the top-keyword list). `score()` returns `critical_keywords` +
  `missing_critical`; `gap_skills()` surfaces critical gaps first; the fallback extractor
  now also reads comma-listed techs in prose ("strong in X, Y, Z").
- **Achievement reframe** — `app/llm/tailoring.py`: `tailor(..., priority_techs=...)`; the
  live path is told to make profile-backed critical techs explicit in achievement format,
  **only when the profile supports them**, no invented metrics. Fake path stays a
  truth-bounded reorder. Wired in `app/pipelines/generation.py` (applies to autonomous +
  manual paths).
- **Board scrapers** — new `SourceBoard` model/table (`app/models/source_board.py`,
  migration `c9d0e1f2a3b4`), repo `app/repositories/source_boards.py`
  (`active_by_source`), `discover_for_user` now passes **per-source** tokens
  (`app/pipelines/apply/service.py`). Admin API `app/api/sources.py`
  (`/api/source-boards`, admin-only) + a **"Job boards"** card on `/admin`
  (`apps/web/app/(authed)/admin/page.tsx`, `sourceBoardsService`). Docs:
  `docs/JOB_SOURCES.md`.
- Tests: `tests/test_ats_cover.py`, `tests/test_scoring.py`, `tests/test_sources.py`.

### 2. Manual ("VA chatbot") apply flow — fix + UX
**Why:** the flow was wired but broken by frontend↔backend DTO drift; aligned the backend
DTOs to the existing frontend types and added editing.

- `app/api/chat.py`: `_session_dto` now emits `matched_cv`, `{id,label}` prompt options,
  mapped `kind`, `multi:false`; `/answer` returns the **session DTO** (was `{ok,resolved}`,
  which crashed the page). New `PATCH /chat/sessions/{id}` (edit company/role/track —
  track change re-analyzes) and `POST /chat/sessions/{id}/facts` (add a known-true skill).
- `app/pipelines/manual/service.py`: extracted `_analyze`, added `reanalyze` +
  `add_confirmed_fact`; `chat_session.company` column (migration `d4e5f6a7b8c9`).
- Frontend `apps/web/app/(authed)/manual/page.tsx`: editable company/role/track + add-skill
  chips; `chatService.update`/`addFact`; `shared-types` ChatSession extended.
- Tests: `tests/test_manual_path.py`.

### 3. Admin platforms + single admin tier
**Why:** attach an admin to a named "platform" (a label). Per user decision, collapsed to a
**single `admin` role that IS the super-admin** (no separate `super_admin` tier).

- `Platform` model (`app/models/platform.py`), `user.platform_id`, `invite.platform_id`
  (migration `c3d4e5f6a7b8`). `InviteKind.admin`.
- `app/api/platforms.py`: `/api/platforms` CRUD + `/api/admins` (all `require_admin`).
  `POST /api/invites/admin` (attach to a platform). `/me` + login return `platform_*`.
- Frontend `/admin` console: platforms, invite-admin, admins list.

### 4. Invite-gated signup + VA team access
**Why:** no signup existed; gate account creation behind a one-time emailed-key invite.

- `Invite` model (`app/models/invite.py`, migration `b2c3d4e5f6a7`): email + `key_hash`
  (sha256 of a **6-char alphanumeric** code), `kind` (hunter|va|admin), `invited_by_user_id`,
  VA fields, `platform_id`, status, 7-day expiry, single-use. Helpers in `app/security.py`
  (`generate_invite_key`) + repo `app/repositories/invites.py`.
- Endpoints: `POST /api/auth/register` (redeem key → create User or Va+VaAssignment →
  auto-login), `POST /api/invites/{hunter,va,admin}`, `GET /api/invites`,
  `DELETE /api/invites/{id}` (`app/api/invites.py`).
- **VA shared-dashboard scoping** — `app/deps.py`: `scoped_user_ids` + `authorize_owner`;
  jobs/applications/chat opened to a VA scoped to their assigned hunter(s). Onboarding +
  invites stay hunter/admin-only (VAs can't edit CV/cover-letter or invite).
- Frontend: `/signup` page, `/team` page (invite VA/hunter), role-aware nav
  (`components/app-shell.tsx`), `shared-types` MeResponse fix (`type` is `user`|`va`,
  `role` is `hunter`|`admin`|`va`).
- Tests: `tests/test_invites.py`, `tests/test_platforms.py`.

---

## Added outside the above work (by user/linter — review for full context)
Present in the tree but not authored in the feature work above; a fresh session should read
these before touching adjacent code:
- `app/api/ats_checker.py` router (registered in `app/api/__init__.py`) — a separate
  ATS-checker endpoint surface.
- Migrations: `e5f6a7b8c9d0` (tracker_status values), `f6a7b8c9d0e1` (cover-letter template
  file), `a7b8c9d0e1f2` (VA login **PIN** hash), `b8c9d0e1f2a3` (explicit profile
  confirmation; reset on CV re-upload). So VAs may now log in via PIN, and profiles have an
  explicit confirmed flag.
- Frontend: a `/profile` page; `queryKeys.atsSources`, `queryKeys.coverLetterTemplate`.

---

## Gotchas for the next session
- **Cookie auth in tests:** `COOKIE_SAMESITE=none` (in `apps/api/.env`) forces `Secure`
  cookies, so ASGI test clients must use `base_url="https://test"` (see `tests/test_invites.py`).
- **Two `.env` files:** repo-root `.env` (compose injects it) and `apps/api/.env` (read by
  host-run pytest/dev). They differ.
- **Migration ids collided once** — board migration was renumbered to `c9d0e1f2a3b4` onto
  the real head `b8c9d0e1f2a3`. Keep the chain linear; check `alembic history` before adding.
- The ATS achievement reframe only does real work with a **live LLM**
  (`USE_FAKE_INTEGRATIONS=false` + `ANTHROPIC_API_KEY`); fake mode = deterministic reorder.

## To turn on real job pulling (see docs/JOB_SOURCES.md)
1. `USE_FAKE_INTEGRATIONS=false` (⚠️ also turns off LLM/email/Apollo/R2 fakes).
2. `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` and/or `SERPAPI_API_KEY` (aggregators search by
   profile skills).
3. Greenhouse/Lever/Ashby: add company **board tokens** in **Admin → Job boards** (DB, not
   env).

## Open / optional follow-ups
- Aggregators don't pass **location** (Adzuna country hard-coded `gb`); add a profile
  location + thread it into `SourceQuery`.
- Board tokens are **global**; per-hunter scoping is a future step.
- Platform attachment is a **label only** — platform-admins still see everything. Real
  per-platform data scoping was deferred (needs hunters tagged with a platform).

## Verify
```
cd apps/api && uv run python -m pytest -q          # 81 passed
cd apps/api && uv run python -m alembic history    # head: c9d0e1f2a3b4
pnpm --filter web build                            # green
```
