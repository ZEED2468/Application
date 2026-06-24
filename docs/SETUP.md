# Production setup — end to end

Get the engine running for real: jobs discovered from live sources, CVs stored in
Cloudflare R2, AI tailoring on, downloads working.

Architecture: **backend** = one Docker image run 3 ways (api / worker / beat) on Render
+ Postgres + Redis; **frontend** = Next.js (Vercel or Render); **storage** = Cloudflare R2.

---

## 1. Gather the credentials

| Service | What you need | Where |
|---|---|---|
| **Cloudflare R2** | Account ID, an S3 API token (key + secret), a bucket | dash.cloudflare.com → R2 |
| **Anthropic** | API key (for tailoring / CV structuring / cover letters) | console.anthropic.com |
| **Adzuna** | App ID + App Key (free dev tier) | developer.adzuna.com |
| **SerpApi** | API key (Google Jobs — main source for remote/global) | serpapi.com |

(Optional, only for outreach later: Resend, Apollo.)

---

## 2. Cloudflare R2 (storage)

1. R2 → **Create bucket** → name it **`jd-cvs`** (keep it **private** — no public access).
2. R2 → **Manage R2 API Tokens** → create a token with **Object Read & Write**, scoped to
   *all buckets* (or at least `jd-cvs`). Copy the **Access Key ID** + **Secret Access Key**.
3. Your **endpoint** is `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`.
4. Do **not** set a public URL — CVs are served via short-lived presigned links behind login.

---

## 3. Backend env (Render → `api`, `worker`, `beat` — the shared env group)

```bash
# Master switch
USE_FAKE_INTEGRATIONS=false

# Auth / cookies
JWT_SECRET=<a long random string>
COOKIE_SECURE=true
COOKIE_SAMESITE=lax        # 'lax' if frontend is same-origin via proxy (recommended);
                           # 'none' if the browser calls the API cross-origin (direct mode)
CORS_ORIGINS=              # leave empty in proxy mode; else your frontend origin

# Data stores — Render auto-injects these when Postgres/Redis are linked (don't hand-set)
DATABASE_URL=...
REDIS_URL=...
CELERY_BROKER_URL=...
CELERY_RESULT_BACKEND=...

# LLM (AI tailoring / CV structuring / cover letters / achievement-rewrite)
ANTHROPIC_API_KEY=<key>
ANTHROPIC_MODEL=claude-opus-4-8

# Storage (R2)
R2_ENDPOINT=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=<key>
R2_SECRET_ACCESS_KEY=<secret>
R2_BUCKET=jd-cvs
R2_ACCOUNT_ID=<account id>     # optional

# Job sources
ADZUNA_APP_ID=<id>
ADZUNA_APP_KEY=<key>
ADZUNA_COUNTRY=gb              # Adzuna is per-country (no Nigeria); SerpApi covers remote/global
SERPAPI_API_KEY=<key>
```

> The `worker` and `beat` services use the **same** env group — they need the DB, Redis,
> Anthropic, R2, and source keys too.

---

## 4. Frontend env (Vercel or Render `web`)

**Recommended: proxy mode** (simplest — no CORS, same-origin cookies):
```bash
BACKEND_URL=https://<your-backend-host>     # server-side; the Next /api proxy forwards here
# leave NEXT_PUBLIC_API_BASE UNSET
```
Then on the backend keep `COOKIE_SAMESITE=lax` and `CORS_ORIGINS` empty.

**Direct mode** (browser calls the API cross-origin): set `NEXT_PUBLIC_API_BASE=<backend url>`,
and on the backend set `COOKIE_SAMESITE=none` + `CORS_ORIGINS=<frontend origin>`.

---

## 5. Deploy + migrate

1. Push to the branch Render/Vercel build from.
2. The `api` service runs **`alembic upgrade head`** on deploy (Render `preDeployCommand`) —
   confirm it succeeded (a failed migration leaves columns/tables missing → 500s). If needed,
   run it manually from the Render **Shell**: `alembic upgrade head`.
3. Make sure **`api`, `worker`, AND `beat` are all running**. The worker tailors discovered
   jobs (classify → score → generate CV); `beat` fires the 30-min auto-poll. Without the
   worker, jobs appear but never get an ATS score / CV.

---

## 6. Bootstrap the first admin + log in

From the Render `api` **Shell** (one-time), seed the bootstrap admin + a default platform:
```bash
python -m scripts.seed
```
This creates an admin (`ada@jd.dev`) + a `Default` platform (and some demo hunters/VA you can
ignore or delete). Log in at the frontend `/login` as that admin, then **change the password**
and use the invite flow for real people.

---

## 7. First real run (per hunter)

1. **Invite a hunter:** as admin → **Team** → invite by email → share the signup link.
2. **Onboard:** the hunter logs in → **Profile** → upload a source CV per track (PDF/DOCX) →
   it lands in R2 at `{user}/role-cv/{track}/source.pdf`, gets parsed into the profile →
   **Confirm profile**. The **Download** link should open the uploaded file.
3. **Discover jobs:** **Jobs** → **Find jobs now** → the per-source report shows what each
   source returned. Real jobs appear in the table.
4. **Tailor:** with the worker running, jobs auto-tailor (ATS score + CV/cover PDFs); or open a
   job and **Generate**. The **Open** links download the tailored CV/cover via presigned R2.
5. **Manual apply:** **Manual Apply** → paste a JD → confirm-true prompts → **Generate**.

---

## 8. Admin / ongoing

- **Job-board scrapers** (Greenhouse/Lever/Ashby): **Admin → Job boards** → add company board
  tokens (the slug in a company's careers URL). Aggregators (Adzuna/SerpApi) need no tokens.
- **More users:** admin invites hunters; each hunter invites their VAs (Team page).
- **Platforms:** Admin → create platforms, attach admins.

## Quick troubleshooting (read the Render `api` logs)
- Upload 500 → `r2.put_failed` → wrong bucket/endpoint/keys (`NoSuchBucket` = create/rename the bucket).
- No jobs → click **Find jobs now**: the report's `note`/`error` tells you (no key / no board tokens / 0 results).
- Empty ATS/CV columns → the **worker** isn't running/processing.
- Login fails on a cross-origin frontend → `COOKIE_SAMESITE=none` + `CORS_ORIGINS` set, or switch to proxy mode.
