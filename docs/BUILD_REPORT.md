# Build Report — Job Application & Outreach Engine (v1)

Status of the one-shot build against the lead-engineer prompt. Everything runs
end-to-end with **zero credentials** because all external dependencies sit behind
`USE_FAKE_INTEGRATIONS=true`; the seam table below says exactly where real keys go.

## What's built

### Monorepo (constraint #9)
```
/apps/api        FastAPI + Celery — all business logic        [BUILT, 40 tests]
/apps/web        Next.js dashboard (coffee/Garamond)          [BUILT, pnpm build green]
/apps/wa-bridge  Go + whatsmeow dumb transport                [BUILT, go build green, FAKE verified]
/packages/shared-types  TS API types                          [BUILT]
/infra           docker-compose (7 services) + Dockerfiles    [BUILT, compose config valid]
/docs            PRD, application-flow, this report
Makefile, pnpm-workspace.yaml                                 one-command bring-up: `make dev`
```

### Backend (apps/api)
- **Schema** — the frozen 13 entities + 6 additive tables (`role_cv`, `cover_letter`,
  `cover_letter_template`, `chat_session`, `chat_prompt`, `application_event`) and
  additive columns (`job.origin/role_title`, `generated_cv.ats_score/ats_breakdown/
  source_role_cv_id`, `application.tracker_status`). One additive migration; the
  frozen 13 are never altered.
- **Two paths, one set of objects** — the autonomous pipeline and the manual VA
  chatbot both call the **shared generation engine** ([pipelines/generation.py](../apps/api/app/pipelines/generation.py))
  and both create identical `job → generated_cv → cover_letter → application`
  records. A test asserts no path creates an application the tracker can't see.
- **Pipeline A** (Apply) — sources, dedupe, relevance, track classify, tailoring.
- **Pipeline B** (Outreach) — Apollo lookup, hook-finder, draft, **warm-up
  governor** send, follow-up sequencer.
- **Pipeline C** (Respond) — signed reply-address matcher (3-tier), classify,
  dossier, WhatsApp bridge push, governed relay.
- **Manual chatbot** — paste JD → match `role_cv` → **internal ATS** gaps →
  confirm-true prompts → generate CV + cover letter → create the application.
- **ATS scorer** — internal 0–100 match, optimized toward 90–95%; framed
  everywhere as "internal ATS match", never an employer-ATS guarantee.
- **Cover letters** — exactly 3 paragraphs (real hook → mirrored real work →
  why-join), same truth boundary as the CV.
- **Truth boundary** — `tailoring.assert_truth_bounded` proves no fabrication on
  the deterministic path; VA-confirmed facts are merged into the profile *before*
  tailoring, so they pass honestly.
- **Tracker + audit + export** — status dropdown writes straight to Postgres,
  every change appends an `application_event`, one-click `.xlsx` export.
- **28 API routes**, 10 Celery events, 5 beat schedules.

## Verification
- `cd apps/api && pytest` → **40 passed** (sources, dedupe, relevance/classify,
  tailoring truth-boundary, ATS, cover-letter 3-para + truth, governor caps,
  Pipeline B send + emit, Pipeline C match/dossier/relay, manual chatbot flow,
  tracker-sync + audit, and a full **A→B→C capstone** asserting all 6 core events).
- Both migrations apply cleanly (validated on SQLite; Postgres-ready).
- `apps/web`: `pnpm build` green. `apps/wa-bridge`: `go build` green, `/health`,
  `/push`, `/_simulate_inbound` verified in FAKE mode. `docker compose config` valid.

## Seam table — where real credentials/hardware drop in

| Capability | Fake (now) | Real (drop-in) |
|---|---|---|
| LLM (tailor/hook/draft/classify/cover) | deterministic | `ANTHROPIC_API_KEY` → `app/llm/client.py` (`is_live()`) |
| Email send + webhooks | `resend.SENT_LOG` | `RESEND_API_KEY` + verify 9 domains; set `RESEND_WEBHOOK_SECRET` |
| People lookup | canned people | `APOLLO_API_KEY` → `app/integrations/apollo.py` |
| Job sources | `FakeSource` | `ADZUNA_APP_ID/KEY`, `SERPAPI_API_KEY` + board tokens |
| CV/PDF storage | local `.r2store/` | `R2_*` (account/key/secret/bucket/endpoint) |
| LaTeX render | stub PDF if tectonic absent | `tectonic` (already in the api Dockerfile) |
| WhatsApp | `BRIDGE_FAKE=1` echo | scan QR (real whatsmeow); set `BRIDGE_FAKE=0` |
| Spreadsheet | `.xlsx` download | optional Google Sheets export (Sheets API creds) |
| Flip everything | `USE_FAKE_INTEGRATIONS=true` | set `false` + provide the keys above |

## Run it
```
cp infra/.env.example .env          # fake mode by default
make dev                            # postgres, redis, api, worker, beat, web, wa-bridge
make migrate                        # alembic upgrade head
cd apps/api && pytest               # 40 tests
```

## Known follow-ups (not blocking v1)
- `health_scan` Postmaster pull is a documented no-op (real-time auto-pause already
  runs via the Resend events webhook).
- First-contact outreach targets the top-priority contact; multi-contact threading
  is deferred to keep `thread.reply_address` unique.
- `apps/api/ARCHITECTURE.md` predates this build (paths/`[PLANNED]` tags lag); this
  report is the current source of truth.
