# JD Engine — Infrastructure

This directory holds the local/dev orchestration for the whole monorepo
(`apps/api`, `apps/web`, `apps/wa-bridge`) plus Postgres, Redis, and the Celery
worker + beat.

## Layout

| File                 | Purpose                                                        |
| -------------------- | ------------------------------------------------------------- |
| `docker-compose.yml` | The full stack: postgres, redis, api, worker, beat, wa-bridge, web. |
| `.env.example`       | Every env var the stack needs, with safe dev defaults.        |
| `README.md`          | This file — run instructions + DNS / email-domain checklist.  |

## Quick start

```bash
# 1. Create your env file at the repo root (compose reads ../.env)
cp infra/.env.example .env

# 2. Build + start everything
make dev          # == docker compose -f infra/docker-compose.yml up --build

# 3. Apply DB migrations (the api container also runs `alembic upgrade head` on
#    boot via its entrypoint; this is the manual escape hatch)
make migrate
```

Other targets (see root `Makefile`):

- `make down` — stop the stack (named volumes are kept).
- `make logs` — tail all service logs.
- `make test` — run the api pytest suite.
- `make fmt` — ruff format + lint-fix the api.

### Services & ports

| Service     | Port (host) | Notes                                                          |
| ----------- | ----------- | -------------------------------------------------------------- |
| `postgres`  | 5432        | `jd / jd / jd`. Data in the `pgdata` named volume.             |
| `redis`     | 6379        | DB 0 = cache, 1 = celery broker, 2 = celery result backend.   |
| `api`       | 8000        | FastAPI (`app.main:app`). Runs migrations on boot.            |
| `worker`    | —           | Celery worker, queues `default,email,render,poll`.            |
| `beat`      | —           | Celery beat scheduler.                                        |
| `wa-bridge` | 8081        | WhatsApp bridge (Go). `BRIDGE_FAKE=1` in dev. Session volume. |
| `web`       | 3000        | Next.js front end.                                            |

Inside the compose network services reach each other by service name
(`postgres:5432`, `redis:6379`, `api:8000`, `wa-bridge:8081`). The `.env`
`DATABASE_URL` / `REDIS_URL` / `CELERY_*` already use those hostnames, and the
compose file pins them again per-service so they're correct regardless of `.env`.

## Where real credentials go

All secrets live in the root `.env` (never committed). For each provider, drop
the real value into the matching key from `.env.example`:

- **LLM** — `ANTHROPIC_API_KEY`
- **Email send** — `RESEND_API_KEY`, and `RESEND_WEBHOOK_SECRET` (must match the
  signing secret configured on the Resend webhook).
- **Job sources** — `APOLLO_API_KEY`, `ADZUNA_APP_ID` / `ADZUNA_APP_KEY`,
  `SERPAPI_API_KEY`.
- **Storage** — `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
  `R2_ENDPOINT` (R2 S3 endpoint), `R2_BUCKET`.
- **Service-to-service** — `BRIDGE_HMAC_SECRET` (shared by api + wa-bridge),
  `JWT_SECRET`.

To exercise real providers instead of the local fakes, set
`USE_FAKE_INTEGRATIONS=false`.

## Email sending domains — DNS setup checklist

Outreach is sent from **9 dedicated sending domains**: one per `(hunter, track)`
pair — 3 hunters × 3 tracks. Each domain is warmed independently and governed by
per-domain daily caps + a per-hunter weekly cap. Reply addressing uses
HMAC-signed `apply+<token>@<domain>` envelopes, so inbound DNS (MX) must also be
correct.

For **every one of the 9 domains** (managed in Cloudflare DNS), publish:

### 1. SPF (authorize the email provider)

```
Type:  TXT
Name:  @            (the root of the sending domain)
Value: v=spf1 include:_spf.resend.com ~all
```

One TXT record per domain. `~all` (soft-fail) during warm-up; tighten to `-all`
once reputation is established.

### 2. DKIM (provider-issued signing keys)

Resend issues a DKIM record per domain when you add it. Publish exactly what the
provider shows — typically:

```
Type:  TXT  (or CNAME, per provider instructions)
Name:  resend._domainkey
Value: <provider-supplied public key / target>
```

Add the domain in the Resend dashboard first, copy its DKIM record into
Cloudflare, then verify.

### 3. DMARC (alignment + reporting policy)

```
Type:  TXT
Name:  _dmarc
Value: v=DMARC1; p=quarantine; rua=mailto:dmarc@<domain>; fo=1; adkim=s; aspf=s
```

Start at `p=none` while validating, then move to `p=quarantine` (and eventually
`p=reject`) as each domain warms.

### 4. MX (inbound replies)

Required so reply detection (`apply+<token>@<domain>`) can receive mail:

```
Type:     MX
Name:     @
Value:    <provider inbound MX host>
Priority: 10
```

### Per-domain checklist (repeat ×9)

| # | (hunter, track) | Domain | SPF | DKIM | DMARC | MX | Resend verified |
| - | --------------- | ------ | --- | ---- | ----- | -- | --------------- |
| 1 | hunter-1 / track-a | `…` | ☐ | ☐ | ☐ | ☐ | ☐ |
| 2 | hunter-1 / track-b | `…` | ☐ | ☐ | ☐ | ☐ | ☐ |
| 3 | hunter-1 / track-c | `…` | ☐ | ☐ | ☐ | ☐ | ☐ |
| 4 | hunter-2 / track-a | `…` | ☐ | ☐ | ☐ | ☐ | ☐ |
| 5 | hunter-2 / track-b | `…` | ☐ | ☐ | ☐ | ☐ | ☐ |
| 6 | hunter-2 / track-c | `…` | ☐ | ☐ | ☐ | ☐ | ☐ |
| 7 | hunter-3 / track-a | `…` | ☐ | ☐ | ☐ | ☐ | ☐ |
| 8 | hunter-3 / track-b | `…` | ☐ | ☐ | ☐ | ☐ | ☐ |
| 9 | hunter-3 / track-c | `…` | ☐ | ☐ | ☐ | ☐ | ☐ |

After DNS propagates, register each verified domain (and its `(user, track)`
mapping) in the `sending_domain` table so the warm-up governor can route sends.
