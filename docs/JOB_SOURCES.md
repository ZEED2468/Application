# Pulling real jobs — what's required

By default the engine runs on the deterministic **fake** source
(`USE_FAKE_INTEGRATIONS=true`), so no credentials are needed in dev. To pull **real**
jobs, set `USE_FAKE_INTEGRATIONS=false` and configure the sources below.

There are two kinds of source:

## Aggregators — keyword search (just need an API key)

Search by the hunter's profile skills (no per-company setup).

| Source | Env vars | Notes |
|---|---|---|
| **Adzuna** | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Country is currently fixed to `gb`; results are not location-filtered (no location on the profile yet). |
| **SerpApi** (Google Jobs) | `SERPAPI_API_KEY` | Same: keyword-driven, location not yet passed. |

Each adapter no-ops if its key is missing, so you can enable just one.

## Board scrapers — per-company tokens (configured in the app)

**Greenhouse / Lever / Ashby** are public board APIs that fetch by a **company board
token** (the slug in the company's careers URL, e.g. `boards.greenhouse.io/`**`airbnb`**).
No API key — but they fetch nothing until you add tokens:

1. Log in as an **admin** → **Admin** → **Job boards**.
2. Add a board: pick the source, paste the company **token** (slug), optional label.
3. Active tokens are picked up by the next `poll_sources` run (every 30 min) and passed
   per-source into discovery (`source_boards.active_by_source` →
   `discover_for_user`). Aggregators ignore them.

Tokens are **global** (apply to every hunter's discovery); the relevance scorer +
track classifier still filter per hunter.

## Checklist to go live
- [ ] `USE_FAKE_INTEGRATIONS=false`
- [ ] `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` and/or `SERPAPI_API_KEY`
- [ ] `ADZUNA_COUNTRY` (default `gb`; Adzuna is per-country and has **no Nigeria/W.Africa**
      coverage — for remote/global rely on **SerpApi** + board tokens)
- [ ] Greenhouse/Lever/Ashby company tokens added in **Admin → Job boards**
- [ ] (optional, later) per-hunter location + board scoping

## "I added keys but no jobs are showing"
Click **Find jobs now** on the Jobs page — it runs discovery immediately (no 30-min wait,
no dependence on the worker/beat) and shows a **per-source report** (found / new / error).
That report usually pinpoints it. If still empty, check, in order:

1. **Migrations applied?** The api service must have run `alembic upgrade head` (a missing
   `source_board` table or `chat_session.company` column ⇒ migrations are behind ⇒ redeploy).
   Discovery is now resilient to a missing `source_board` table, but other gaps still bite.
2. **`USE_FAKE_INTEGRATIONS=false`** — if the report says `fake_mode: true`, real sources are
   bypassed.
3. **Source keys set** — the report shows e.g. `adzuna: error` with the reason in the api logs
   (`adzuna.http_error status=401`).
4. **The hunter has an onboarded profile** — discovery searches by the profile's skills; a
   hunter with no profile is skipped (the button reports `0 profiles`).
5. **worker + beat running** — only needed for the *automatic* 30-min poll and for tailoring
   discovered jobs into CVs; the **Find jobs now** button does discovery without them.
