# wa-bridge

A **dumb transport pipe** between the JD FastAPI backend and a VA's WhatsApp.
It contains **no business logic** and holds **no domain state** — the only thing
it persists is the whatsmeow session. All decisions live in the FastAPI backend.

## What it does

- **FastAPI → VA**: relays dossier / chatbot text pushed by FastAPI to a VA's
  WhatsApp.
- **VA → FastAPI**: relays a VA's WhatsApp reply back to FastAPI.

```
FastAPI  --POST /push-->  wa-bridge  --whatsmeow-->  VA's WhatsApp
FastAPI  <--POST /api/webhooks/bridge/reply--  wa-bridge  <--  VA's WhatsApp
```

## HTTP API

### `POST /push`
Called by FastAPI to send text to a VA.

Request body:
```json
{ "va_jid": "15551234567@s.whatsapp.net", "dossier_id": "dos_42", "text": "..." }
```
Response: `200 { "bridge_message_ref": "<opaque-ref>" }`

In real mode the ref is the whatsmeow message id; in FAKE mode it is a generated
`br_<hex>`. In real mode the request body must be HMAC-signed (see below) or the
bridge replies `401`. Signature verification is **skipped in FAKE mode**.

### `GET /health`
Response: `200 { "status": "ok" }`

### `POST /_simulate_inbound` (FAKE mode only)
Simulates a VA replying so the round trip can be tested without a phone. Drives
the exact same outbound-to-FastAPI path as a real inbound WhatsApp message.

Request body:
```json
{ "va_jid": "15551234567@s.whatsapp.net", "in_reply_to_ref": "br_abc123", "text": "..." }
```

## Outbound call to FastAPI

On any VA reply (real or simulated), the bridge POSTs to
`{API_BASE_URL}/api/webhooks/bridge/reply`:

```json
{ "va_jid": "...", "in_reply_to_ref": "...", "text": "...", "ts": 1781576839 }
```

with header `X-Bridge-Signature: <hex hmac-sha256(raw body, BRIDGE_HMAC_SECRET)>`.
The same signature scheme is verified on inbound `/push` requests (real mode).

## Config (env vars)

| Var                    | Default                  | Meaning |
|------------------------|--------------------------|---------|
| `PORT`                 | `8081`                   | HTTP listen port |
| `API_BASE_URL`         | `http://localhost:8000`  | FastAPI base URL |
| `BRIDGE_HMAC_SECRET`   | `dev-bridge-secret`      | Shared HMAC secret |
| `BRIDGE_FAKE`          | `1`                      | `1` = no whatsmeow; log/echo + `_simulate_inbound`. `0` = real WhatsApp |
| `WHATSAPP_SESSION_DIR` | `./session`              | sqlite store dir for the whatsmeow session (real mode) |

## Run locally (FAKE mode — default)

```bash
go build -o wa-bridge .
./wa-bridge
# in another shell:
curl localhost:8081/health
curl -X POST localhost:8081/push -d '{"va_jid":"15551234567@s.whatsapp.net","dossier_id":"d1","text":"hi"}'
curl -X POST localhost:8081/_simulate_inbound \
  -d '{"va_jid":"15551234567@s.whatsapp.net","in_reply_to_ref":"br_abc","text":"reply!"}'
```

## Flip to real mode

1. Set `BRIDGE_FAKE=0`.
2. Ensure a writable `WHATSAPP_SESSION_DIR` (a mounted volume in Docker).
3. Start the bridge. On first run it prints a QR code to stdout — scan it from
   WhatsApp → **Linked Devices**. The session is then persisted; subsequent
   starts reconnect without a QR.
4. `/push` now sends a real WhatsApp message and requires a valid
   `X-Bridge-Signature`; inbound WhatsApp replies are forwarded to FastAPI.

> **Build note:** real mode uses `mattn/go-sqlite3`, which requires **CGO**
> (`CGO_ENABLED=1`) and a C compiler at build time. The provided `Dockerfile`
> builds with CGO enabled. With `CGO_ENABLED=0` the binary still compiles and
> runs in FAKE mode.

## Docker

```bash
docker build -t jd-wa-bridge apps/wa-bridge
docker run -p 8081:8081 -v wa_session:/data jd-wa-bridge          # FAKE
docker run -p 8081:8081 -v wa_session:/data \
  -e BRIDGE_FAKE=0 -e API_BASE_URL=http://api:8000 jd-wa-bridge   # real
```
