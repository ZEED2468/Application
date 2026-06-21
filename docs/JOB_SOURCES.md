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
- [ ] Greenhouse/Lever/Ashby company tokens added in **Admin → Job boards**
- [ ] (optional, later) per-hunter location + board scoping
