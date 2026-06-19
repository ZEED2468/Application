# Deploying on Render

An alternative to the VPS + docker-compose + nginx path (in `infra/`). Both live in
the same repo off the same Dockerfiles — pick one per environment. On Render there
is **no nginx and no certbot**: Render terminates TLS and routes each service on its
own URL/custom domain.

## What gets created ([render.yaml](../render.yaml))
7 resources, all in **one region** (private networking requires it):

| Resource | Type | Public? |
|---|---|---|
| `api` | Web Service (Docker, `apps/api`) | ✅ `jd-be.quickbiteltd.org` |
| `web` | Web Service (Docker, repo-root context) | ✅ `jd.quickbiteltd.org` |
| `worker` | Background Worker (Celery) | — |
| `beat` | Background Worker (Celery beat) | — |
| `wa-bridge` | Private Service (Go) + 1GB disk | — (internal) |
| `jd-postgres` | Render Postgres | — |
| `jd-redis` | Render Key Value (Redis) | — |

## Deploy steps
1. Push the repo to GitHub.
2. Render → **New → Blueprint** → pick this repo. Render reads `render.yaml`.
3. Render will prompt for the **secret env vars** (the `sync: false` keys in the
   `jd-shared` group): `JWT_SECRET`, `BRIDGE_HMAC_SECRET`, `RESEND_WEBHOOK_SECRET`,
   `ANTHROPIC_API_KEY`, `RESEND_API_KEY`, `APOLLO_API_KEY`, `ADZUNA_*`, `SERPAPI_API_KEY`,
   `R2_*`. (Leave the AI/email/Apollo keys blank + set `USE_FAKE_INTEGRATIONS=true` in
   the group to launch without external creds.)
4. Apply → Render builds all Dockerfiles, provisions Postgres + Key Value, runs
   `alembic upgrade head` (api `preDeployCommand`), and starts everything.

## Custom domains + Cloudflare
- On the **web** service add domain `jd.quickbiteltd.org`; on **api** add
  `jd-be.quickbiteltd.org`. Render shows a target hostname for each.
- In Cloudflare DNS, add a **CNAME** for each subdomain → the Render target. Use
  **DNS-only (grey cloud)** so Render's own cert serves directly, **or** orange-cloud
  with SSL mode **Full (strict)** (Render presents a valid cert). Do **not** use
  Flexible here.
- `COOKIE_SECURE=true` is already set for the api (Render is real HTTPS).

## WhatsApp bridge
Ships with `BRIDGE_FAKE=1` so it runs with no phone. To go live: set `BRIDGE_FAKE=0`
on the `wa-bridge` service, redeploy, open its **Logs**, scan the printed QR with the
VA's WhatsApp once. The session persists on the mounted disk across restarts.

## Gotchas
- **Same region for all** — `render.yaml` uses `frankfurt`; change every `region:`
  together or private networking (and the `http://api:8000` / `http://wa-bridge:8081`
  URLs) breaks.
- **Cost** — 5 always-on services + Postgres + Key Value. `free` instances spin down
  on idle (fine for nothing here except maybe a demo). Budget `starter` for at least
  api/web/worker/beat.
- **3 builds of the api image** — api, worker, and beat each build `apps/api`
  separately. To speed up later, push one image to a registry and switch those three
  to `image:` instead of `dockerfilePath:`.
- **Postgres SSL** — the blueprint uses the same-region internal `connectionString`,
  which asyncpg accepts. If you ever wire the *external* URL and hit an asyncpg SSL
  error, strip the `?sslmode=...` query param.
- **Plan slugs** — `basic-256mb` / `starter` / `free` reflect Render's current tiers;
  adjust in `render.yaml` if the dashboard names differ.
- The `reject_compose_hosts_in_production` validator in
  [config.py](../apps/api/app/config.py) is intentional: it stops you from accidentally
  using compose hostnames (`postgres`/`redis`) here — Render injects the real DB host.

## VPS vs Render at a glance
| | VPS (`infra/`) | Render (`render.yaml`) |
|---|---|---|
| Orchestration | docker-compose | Render services |
| TLS / routing | nginx + Cloudflare Flexible | Render (built-in) |
| Postgres / Redis | containers | managed |
| Scaling | manual | per-service sliders |
| Best for | full control, lowest $ | least ops, fastest setup |
