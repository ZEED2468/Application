# nginx reverse proxy (Cloudflare Flexible SSL)

Two subdomains in front of the stack. **Cloudflare handles HTTPS** at its edge and
connects to this origin over plain HTTP — so nginx here serves only `:80`, no certs.

| Domain | Goes to | Notes |
|--------|---------|-------|
| `jd.quickbiteltd.org` | **WEB** (Next.js `:3000`) | The dashboard. It proxies its own authed `/api/...` calls to the backend server-side, so the auth cookie stays same-origin on this domain. |
| `jd-be.quickbiteltd.org` | **API** (FastAPI `:8000`) | External webhooks (Resend) post here; Swagger (`/docs`) + `/health` live here too. |

The WhatsApp **bridge** is never exposed by nginx — FastAPI calls it over the internal Docker network only.

## 1. Cloudflare DNS + SSL
- Add an **A record** (proxied — orange cloud) for **both** subdomains pointing at this server's public IP: `jd.quickbiteltd.org` and `jd-be.quickbiteltd.org`.
- SSL/TLS → Overview → **Flexible** (your current choice).
- SSL/TLS → Edge Certificates → enable **Always Use HTTPS** (this does the http→https redirect at Cloudflare's edge — never at the origin, or you get a redirect loop).

## 2. Run it
From the repo root (with the main stack already up via `make dev`):
```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.nginx.yml up -d
```
nginx listens on `:80` and proxies to the `web` / `api` compose services. Cloudflare
reaches it on port 80; visitors only ever see HTTPS.

> Host nginx instead of the container? Swap the upstreams in `jd.conf` to
> `127.0.0.1:3000` / `127.0.0.1:8000`, then `cp jd.conf /etc/nginx/conf.d/` and `nginx -s reload`.

## 3. Production notes
- **Cookies:** keep **`COOKIE_SECURE=false`** in `.env`. The Cloudflare→origin hop is
  HTTP, so a `Secure`-flagged cookie set by the origin can behave inconsistently on
  Flexible. (If you later move to **Full (strict)** with a Cloudflare Origin
  Certificate, set `COOKIE_SECURE=true` — and switch nginx back to a `:443` config.)
- Set a real **`JWT_SECRET`** and **`ENVIRONMENT=production`**.
- Point Resend's inbound/event webhooks at `https://jd-be.quickbiteltd.org/api/webhooks/resend/...`.
- Lock down the origin so only Cloudflare can reach it: restrict the firewall on
  port 80 to [Cloudflare's IP ranges](https://www.cloudflare.com/ips/), and once nginx
  is the only entry point, remove the `ports:` for `web`/`api` in
  `infra/docker-compose.yml`.
- Optional: uncomment the `set_real_ip_from ... CF-Connecting-IP` block in `jd.conf`
  so logs show the real visitor IP instead of Cloudflare's.

## Heads-up on Flexible
Cloudflare↔origin is **unencrypted** over the public internet. When you're ready to
harden, the cheap upgrade (still no Let's Encrypt, no renewals) is Cloudflare
**Full (strict)** + a free **Origin Certificate** pasted into nginx — ask and I'll
switch the config over.

## Notes
- `client_max_body_size 25m` is set for CV/document uploads (onboarding).
