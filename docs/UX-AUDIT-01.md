# UX Audit — Iteration 01

**Scope:** `apps/web` (10,549 lines across 18 routes), read end to end, plus the `apps/api` contract
surface it consumes. No code changed. Findings are grounded in file references, not impressions.

**Verdict up front:** the engineering is sound and the recent UX commits moved in the right
direction. But the product still reads as *three tools sharing a sidebar* — a job spreadsheet, an
ATS checker, and a LaTeX editor — rather than one workspace. Three structural gaps explain most of
the friction, and they are the spine of everything below:

1. **The centre of the app is a spreadsheet, not a résumé.**
2. **Context lives in the browser, not in the account.**
3. **The AI has no memory of its own decisions, so it cannot personalize.**

---

## 1. UX Audit — per screen

### 1.1 Entry: `/` → `/jobs`

| | |
|---|---|
| **Purpose** | Get the user into the product |
| **User goal** | "Continue what I was doing" |
| **What it does** | [app/page.tsx:4](../apps/web/app/page.tsx#L4) hard-redirects to `/jobs` |

**Pain points**

- A returning user lands on a **9-column, 25-row grid sorted by recency**. Nothing on screen
  reflects work already in progress: no half-tailored CV, no unfinished chat session, no
  "you were editing X".
- The brief's returning-user requirement ("restore unfinished sessions, surface unfinished work
  automatically") has **no implementation anywhere in the codebase**.
- A first-time user lands on the same empty grid, then gets a 6-step modal tour
  ([onboarding-launcher.tsx:15-46](../apps/web/components/onboarding-launcher.tsx#L15-L46)) that
  *teaches the navigation* rather than doing any work. `/onboarding` itself is a redirect stub
  ([onboarding/page.tsx:4](../apps/web/app/(authed)/onboarding/page.tsx#L4)).

**Information hierarchy:** inverted. The densest, least actionable surface is the front door.

---

### 1.2 `/jobs` — Pipeline / Submitted

| | |
|---|---|
| **Purpose** | Discover and triage roles; review submitted applications |
| **Files** | [jobs/page.tsx](../apps/web/app/(authed)/jobs/page.tsx), [submitted-applications.tsx](../apps/web/components/submitted-applications.tsx) |

**Pain points**

- **Discovery asks the user to retype what the system already knows.** The search box requires
  comma-separated roles ([jobs/page.tsx:445-455](../apps/web/app/(authed)/jobs/page.tsx#L445-L455))
  and the Find button is disabled until they're typed
  ([:461](../apps/web/app/(authed)/jobs/page.tsx#L461)). Meanwhile `master_profile.target_roles`
  already holds exactly these strings, collected during profile setup, and the discovery endpoint
  falls back to them server-side. Direct violation of "never ask users to repeat information the
  system already knows."
- **Custom tracks are trapped in `localStorage`** ([:68-80](../apps/web/app/(authed)/jobs/page.tsx#L68-L80),
  [:109](../apps/web/app/(authed)/jobs/page.tsx#L109)) — despite `tracksService` and a
  `track_entity` table existing. Switch device or browser and the user's own taxonomy vanishes.
- **Filters and the Pipeline/Submitted segment are React state, not URL state.** The segment is
  *read* from `?view=` once on mount ([:84-90](../apps/web/app/(authed)/jobs/page.tsx#L84-L90)) but
  never written back. Reload, back button, and sharing all lose the user's position.
- **Nine columns of equal visual weight**, none of which answer "which of these should I do next?"
  Ranked by recency, not fit — even though `ats_score` and `relevance_score` are on the row.
- **Row click is mouse-only** — see §9.

**AI interaction quality:** discovery is a batch job behind a button. No sense of an agent watching
for good matches.

---

### 1.3 `/jobs/[id]` — the résumé workspace

| | |
|---|---|
| **Purpose** | The document-hero screen: generate, review, edit, apply |
| **File** | [jobs/[id]/page.tsx](../apps/web/app/(authed)/jobs/[id]/page.tsx) |

This is the **best screen in the product** — the résumé genuinely occupies centre stage
([:216-227](../apps/web/app/(authed)/jobs/[id]/page.tsx#L216-L227)) and the inline edit→commit loop
([ResumeHero:437-561](../apps/web/app/(authed)/jobs/[id]/page.tsx#L437-L561)) never leaves the page.
It is the model the rest of the app should follow.

**Pain points**

- **The context rail is seven stacked cards of equal weight** — Ready to apply?, Job description,
  Cover letter, Status, Track, Outreach, Audit trail
  ([:230-428](../apps/web/app/(authed)/jobs/[id]/page.tsx#L230-L428)). Every one is always
  expanded, always visible, regardless of stage. At the "no CV yet" stage, Outreach and Audit are
  guaranteed empty and still occupy prime vertical space. This is the "dashboards and widgets
  competing for attention" the brief forbids.
- **The Cover letter card is a dead end.** It renders "Not generated"
  ([DocRow:608-618](../apps/web/app/(authed)/jobs/[id]/page.tsx#L608-L618)) with **no action**. The
  only way to produce a cover letter is to enter Edit mode, press Regenerate, switch to the Cover
  tab, and commit — four non-obvious steps behind a card that looks informational.
- **The ATS summary links the user off the page** to `/ats-checker?job_id=…`
  ([:242](../apps/web/app/(authed)/jobs/[id]/page.tsx#L242)) to see detail. Momentum broken to read
  a number.
- **The stepper is decorative** ([JobStepper:575-597](../apps/web/app/(authed)/jobs/[id]/page.tsx#L575-L597)) —
  not clickable, and "Tailored" vs "Ready" is not a distinction a user can act on.
- **Stale copy:** "Back to tracker" ([:569](../apps/web/app/(authed)/jobs/[id]/page.tsx#L569))
  points at `/jobs`, a screen no longer called the tracker.

---

### 1.4 `/ats-checker` — "Tailor"

| | |
|---|---|
| **Purpose** | Score a CV against a JD, then act on the result |
| **File** | [ats-checker/page.tsx](../apps/web/app/(authed)/ats-checker/page.tsx) (889 lines) |

**This screen is the single largest gap between the product and the vision.** The brief says the
product must never feel like an ATS checker. This is the nav's primary workspace verb ("Tailor")
and it is, structurally, an ATS checker: two large input cards, a run button, then a wall of
analysis.

**Pain points**

- **Form-first, not context-first.** Standalone, it opens with two empty textareas and demands a
  pasted JD ([:314-443](../apps/web/app/(authed)/ats-checker/page.tsx#L314-L443)) — even though the
  user has jobs in the system with JDs already stored. There is no "pick one of your jobs."
- **AI recommendations are read-only text.** `result.ai.recommendations` is a `string[]` rendered as
  `<li>` bullets ([Section:876-889](../apps/web/app/(authed)/ats-checker/page.tsx#L876-L889),
  used at [:657-662](../apps/web/app/(authed)/ats-checker/page.tsx#L657-L662)). **There is no way
  to accept or reject a single recommendation** — not here, not anywhere in the app. The user reads
  advice and then re-derives it by hand in the LaTeX editor.
- **A decision the user cannot make:** the "Include AI analysis (requires LLM on API)" checkbox
  ([:468-476](../apps/web/app/(authed)/ats-checker/page.tsx#L468-L476)) asks about infrastructure,
  not intent.
- **Resume Intelligence is an information dump** — five tabs (Tools / Structure / Verbs /
  Standards / Coaching) of unranked findings
  ([:732-874](../apps/web/app/(authed)/ats-checker/page.tsx#L732-L874)), with no indication of which
  matters most or what to do first.
- **Handoffs run through browser storage.** `goCreateApplication` writes `tailor-apply-handoff` to
  `sessionStorage` ([:101-115](../apps/web/app/(authed)/ats-checker/page.tsx#L101-L115));
  `goRegenerate` writes `latex-regen-standalone` ([:117-143](../apps/web/app/(authed)/ats-checker/page.tsx#L117-L143)).
  Both are one-shot, same-tab-only, and silently lost on refresh.

---

### 1.5 `/manual` — "Create application"

| | |
|---|---|
| **Purpose** | Confirm true facts, then generate a tracked application |
| **File** | [manual/page.tsx](../apps/web/app/(authed)/manual/page.tsx) |

**Pain points**

- **The session is destroyed by a page refresh.** `session` is held only in React state
  ([:48](../apps/web/app/(authed)/manual/page.tsx#L48)); the `session_id` is never written to the
  URL or storage. `chatService.getSession(id)` **already exists**
  ([chat.ts:16-18](../apps/web/lib/api/services/chat.ts#L16-L18)) and the server persists the whole
  thing — `chat_session` holds `jd_text`, `track`, `ats_breakdown`, `confirmed_facts`, and every
  prompt answer. The user's confirmations are safe on the server and unreachable in the UI. This is
  the sharpest single instance of "context should never be lost unnecessarily."
- **The JD is pasted a second time** unless the user arrived via the exact sessionStorage handoff
  ([:212-239](../apps/web/app/(authed)/manual/page.tsx#L212-L239)).
- **A save button for data the system already has.** "Update details" requires an explicit press
  ([:367-380](../apps/web/app/(authed)/manual/page.tsx#L367-L380)) for company/role/track that were
  auto-extracted seconds earlier.
- **"Vet with AI" is a manual step** ([:281-289](../apps/web/app/(authed)/manual/page.tsx#L281-L289))
  that filters noise out of the gap list. If it improves the result, it should not be opt-in; the
  copy even admits the un-vetted list contains noise
  ([:300-306](../apps/web/app/(authed)/manual/page.tsx#L300-L306)).
- **Naming drift:** the page is titled "Create application", the back link says "Back to analysis",
  and it lives at `/manual`.

---

### 1.6 `/profile`

The **strongest-designed screen**: single active track, derived step machine
(`upload → reading → confirm → roles → ready`,
[profile/page.tsx:129-137](../apps/web/app/(authed)/profile/page.tsx#L129-L137)), everything
optional collapsed into an accordion
([:567-575](../apps/web/app/(authed)/profile/page.tsx#L567-L575)). This is genuine progressive
disclosure and should be the template for `/ats-checker`.

**Pain points**

- 1,128 lines and ~8 independent save surfaces (cover template, LaTeX CV, LaTeX cover, preferred
  skills, verified extras, target roles, career details, confirm) — each with its own dirty state
  and Save button.
- The "reading your CV" step tells the user to *refresh the page manually* if it doesn't update
  ([:462-464](../apps/web/app/(authed)/profile/page.tsx#L462-L464)) — no polling.

---

### 1.7 `/builder`

Only reachable with a `sessionStorage` payload; without it the page renders an instruction to go
back to the ATS checker ([builder/page.tsx:114-118](../apps/web/app/(authed)/builder/page.tsx#L114-L118)).
It is a screen whose empty state is an apology. Back-link copy says "Back to ATS Checker"
([:94](../apps/web/app/(authed)/builder/page.tsx#L94)) — a name used nowhere else.

---

### 1.8 Naming inconsistency (whole app)

The same surface has four names: nav **"Tailor"** ([app-shell.tsx:50](../apps/web/components/app-shell.tsx#L50))
· tour **"ATS Checker"** ([onboarding-launcher.tsx:29](../apps/web/components/onboarding-launcher.tsx#L29))
· builder back-link **"Back to ATS Checker"** · manual back-link **"Back to analysis"**. And `/jobs`
is called both "Jobs" and "tracker". Users build a mental model from names; four names for one
place prevents that.

---

## 2. Pain Point Analysis — the three root causes

### Root cause A — the centre of the app is a spreadsheet

The résumé is the workspace on exactly one screen (`/jobs/[id]`). Everywhere else the user is in a
table, a form, or an editor. Nav order (`Jobs` → `Tailor`) encodes the same priority.

### Root cause B — context lives in the browser, not the account

Seven client-side stores currently hold product state:

| Key | Store | Holds | Lost when |
|---|---|---|---|
| `jd_jobs_cache_v2` | localStorage | Full jobs list | — (cache, benign) |
| `jd_custom_tracks` | localStorage | **User's custom track taxonomy** | New device/browser |
| `jd_ats_last_check_v1` | localStorage | **Last standalone ATS analysis** | New device, cleared storage |
| `tailor-apply-handoff` | sessionStorage | **JD passed Tailor → Create application** | Refresh, new tab |
| `latex-regen-standalone` | sessionStorage | **ATS recs passed Tailor → Builder** | Refresh, new tab |
| `od:tour:v1` | localStorage | Tour seen | New device (tour replays) |
| *(none)* | React state | **The entire chat session** | **Any refresh** |

The codebase already diagnosed this. From
[ats_analysis.py:1-12](../apps/api/app/models/ats_analysis.py#L1-L12):

> *"Replaces the fragile `sessionStorage` handoff between the ATS checker and the LaTeX builder: a
> first-class feature does not talk to the rest of the app through browser storage."*

That migration was done for one path and left unfinished for the rest.

### Root cause C — the AI has no decision memory

`app/models/` contains no table for accepted or rejected suggestions — the only freeform bucket is
`master_profile.career_preferences`
([master_profile.py:43](../apps/api/app/models/master_profile.py#L43)), unused by generation.
Consequently:

- Recommendations cannot be accepted or rejected (§1.4).
- Nothing the user accepts or rejects influences the next generation.
- Nothing the user *edits by hand* in the LaTeX editor feeds back as a style signal.

Every generation starts from zero. A user who has rejected "add Kubernetes" five times is offered
it a sixth. Principle 6 (Personalization by default) is currently unimplemented, not partially
implemented.

### Secondary — the AI is a batch function, not a coach

Every AI action is a button the user must know to press: *Run ATS check*, *Vet with AI*,
*Regenerate*, *Generate résumé*, plus an *Include AI analysis* toggle. Nothing observes, nothing
volunteers, nothing explains itself unprompted. The brief's three AI modes (Guide / Collaborator /
Assistant) map to **zero** code paths — behaviour is identical for a first-time user with no CV and
a veteran on their fortieth application.

---

## 3. User Journey Evaluation

### First-time user — 14 steps, 5 screens, 3 dead ends

```
Land /jobs (empty grid) → modal tour (6 steps, teaches nav) → dismiss →
banner "Finish setting up" → /profile → pick track → upload CV → wait (manual refresh) →
confirm → add target roles → /settings for an AI key → back to /jobs →
type roles the profile already knows → Find jobs → open a job → Generate →
cover letter card says "Not generated" (dead end) → Edit → Regenerate → Cover tab → commit → Apply
```

Friction concentrations: the tour teaches instead of doing; the AI-key detour is discovered via
banner, not flow; roles are re-typed; the cover letter is a dead end.

### Returning user — no "return" concept exists

Lands on the same recency-sorted grid. To resume yesterday's half-tailored application they must
remember the company and find the row. If they were mid-session in `/manual`, that session is
already gone.

### The "two paths" problem

```
Path A  /jobs → /jobs/[id] → Generate                        (server picks everything)
Path B  /ats-checker → /manual → generate → /jobs/[id]        (user confirms facts first)
```

Both produce the same artifacts by different routes, with different context models (Path A: server
state; Path B: two sessionStorage hops). Path B produces a *better* result — the confirm-true
prompts and vetted gaps are real quality gains — but is reachable only by users who guess that
"Tailor" precedes "Jobs".

---

## 4–6. Proposed improvements, updated flow, layout & interaction

### 4.1 A real home: `/` resumes work

Replace the redirect with a **Continue** surface: the most recent job with an incomplete stage,
the most recent unfinished chat session, and one primary action derived from readiness. Falls back
to discovery when there is genuinely nothing in flight.

- **Why the issue exists:** `/` was a routing convenience, never designed.
- **Why better:** answers "what do I do next" before the user asks. Directly serves Principle 7.
- **UX impact:** high — every session starts with momentum instead of a scan.
- **Trade-offs:** one more screen to maintain; needs a cheap "unfinished work" query.
- **Complexity:** Medium (frontend-only if built from existing `/api/jobs` + `/api/readiness`).

### 4.2 Fold the analysis into the workspace; retire the standalone checker as a destination

Make `/ats-checker` a **panel inside `/jobs/[id]`**, not a screen the user is sent to. Keep a
standalone entry for the top-of-funnel "I have a JD and a CV" case, but have it *create a job*
immediately rather than hand off through storage.

- **Why the issue exists:** the checker predates the job workspace and kept its own page.
- **Why better:** removes the round trip, both sessionStorage handoffs, and the double JD paste.
- **UX impact:** high — collapses Path A and Path B into one.
- **Trade-offs:** the largest single change here; `/ats-checker` must keep working during migration.
- **Complexity:** Medium-High.

### 4.3 Recommendations become actions

Render each AI recommendation as an **accept / reject / edit** chip. Accepted items flow into the
next `latexService.regenerate` call; rejected items are suppressed and remembered.

- **Why the issue exists:** the AI response shape (`string[]`) was designed for display.
- **Why better:** turns reading into doing — the highest-value AI output currently requires manual
  re-derivation.
- **UX impact:** very high — this is the moment the AI stops being a report and becomes a
  collaborator.
- **Trade-offs:** needs the persistence layer in §8.1; recommendation strings need stable IDs.
- **Complexity:** Medium (UI) + Low-Medium (API).

### 4.4 Stage-aware context rail

Replace the seven always-open cards on `/jobs/[id]` with **one primary "next step" panel** plus
collapsed secondary sections. Show Outreach and Audit only once an application exists.

- **Why the issue exists:** cards were added incrementally, each reasonable alone.
- **Why better:** one screen, one primary purpose (Principle 3).
- **UX impact:** high — the workspace becomes calm.
- **Trade-offs:** an extra click to reach rarely-used detail.
- **Complexity:** Low-Medium.

### 4.5 Discovery uses what it knows

Prefill the role search from `target_roles`; render them as removable chips with "+ add a role"
rather than an empty comma-separated box.

- **Complexity:** Low. **Impact:** high on first discovery.

### 4.6 Give the cover letter an action

Add *Generate cover letter* / *Regenerate* directly to the card. **Complexity:** Low.

### 4.7 One name per surface

"Tailor" everywhere; `/jobs` is "Jobs"; kill "ATS Checker" and "tracker" as user-facing words.
**Complexity:** Trivial. **Impact:** disproportionate — naming is how the mental model forms.

### Updated flow (target)

```
/  Continue ──────────────────────────────────────────────────┐
   │  "Senior FE @ Acme — 2 must-haves missing"  [Continue]    │
   │  "3 new roles match your targets"           [Review]      │
   └───────────────────────────────────────────────────────────┘
                        │
                        ▼
   /jobs/[id]  ── the résumé, centre stage ──────────────────────
        Document  │  Next step: "Add 2 must-haves"
                  │    ▸ Kubernetes   [Accept] [Not true] [Edit]
                  │    ▸ Terraform    [Accept] [Not true] [Edit]
                  │  ── collapsed: JD · Cover letter · Status · Audit
                        │
                        ▼
                   Apply (docs attached, status set)
```

No screen change between analysing, accepting, editing, and applying.

---

## 7. AI behaviour improvements

**7.1 Mode by context.** Derive the AI's posture from state already available:

| Signal (already in the API) | Mode | Behaviour |
|---|---|---|
| `readiness.complete === false` | **Guide** | One instruction at a time, explain why it matters |
| Job open, CV generated, gaps present | **Collaborator** | Volunteer specific fixes with reasoning; ask before applying |
| User initiated an action | **Assistant** | Act immediately, keep all context |

Complexity: Medium. Needs no new backend data — `readiness` and `JobDetail` already carry the
signals.

**7.2 Remove decisions the user cannot make.** Drop the `use_ai` checkbox; default AI on and
degrade with an explanation when no provider is configured (the codebase already does honour-or-explain
well — see [resume-editor.tsx:58-70](../apps/web/components/resume-editor.tsx#L58-L70)).

**7.3 Make "Vet with AI" automatic.** If the vetted gap list is better, it should be the default;
keep "show unvetted" as an escape hatch.

**7.4 Always explain the number.** `deriveReadiness`
([ats-breakdown.tsx:106-136](../apps/web/components/ats-breakdown.tsx#L106-L136)) is genuinely good
plain-language work — it should be the *only* headline, with the score subordinate to it everywhere.

---

## 8. Context management improvements

**8.1 A decision-memory table (the foundation).**

```
recommendation_decision
  user_id, job_id (nullable), track
  source: 'ats_ai' | 'intelligence' | 'gap'
  text, fingerprint          -- stable hash for dedupe across runs
  decision: 'accepted' | 'rejected' | 'edited'
  reason (nullable), created_at
```

Read at generation time (suppress rejected, prioritize accepted patterns) and at display time
(never re-offer a rejected item without marking it as previously declined). This single table
unlocks Principle 6 and the brief's accepted/rejected context requirements.
**Complexity:** Medium. **Impact:** the highest long-term of anything here.

**8.2 Session id in the URL.** `/manual?session=<id>` + `getSession` on mount. Refresh stops
destroying confirmed facts. **Complexity: Low. Impact: high.** The endpoint already exists.

**8.3 Filters and segment in the URL.** `/jobs?view=submitted&status=applied&tracks=frontend`.
Back button, reload, and sharing start working. **Complexity: Low.**

**8.4 Custom tracks → server.** Move `jd_custom_tracks` onto the existing tracks API.
**Complexity: Low.**

**8.5 Retire both sessionStorage handoffs** as a consequence of §4.2 — the analysis is already
persisted in `ats_analysis`, so the receiving screen can read from the DB
(`atsService.latestRecs`, which `ResumeEditor` already does correctly).

**8.6 Long-term: conversation compression.** Roll resolved chat sessions and accepted edits into
per-track durable knowledge (extending `verified_extras` / `truth_corpus`) so the corpus grows with
use rather than resetting per application.

---

## 9. Accessibility improvements

**9.1 — 87 Tailwind utilities that produce no CSS.** `globals.css` defines only
`--color-coffee-{100,300,500,700,900}` ([globals.css:24-38](../apps/web/app/globals.css#L24-L38)),
but the app uses:

| Class | Uses | Actual result |
|---|---|---|
| `text-coffee-400` | 30 | No rule → inherits `coffee-900`. Intended-quietest text renders **full black** |
| `border-coffee-200` | 16 | Falls back to `* { border-color: coffee-300 }` → heavier than intended |
| `text-coffee-600` / `text-coffee-800` | 24 | No rule → inherits `coffee-900` |
| `bg-coffee-50` (+ `/40`, `/60`) | 13 | **No background at all** |
| `bg-coffee-200`, `bg-coffee-600`, `border-coffee-600` | 4 | No rule |

The visual hierarchy the recent commits designed is **not the one rendering**. Every tinted panel —
the setup-progress banner, the restored-check notice, the "you're set" confirmation, the JD preview
— is currently transparent. Fixing this is ~10 lines in one file and improves every screen at once.
**Complexity: Trivial. Impact: high.**

**9.2 — `coffee-300` fails WCAG AA as body text.** `#a3a3a3` on `#ffffff` is **2.5:1** (AA needs
4.5:1). It is used for job locations, "Not generated", empty-state descriptions, and placeholder
copy. Darkening to roughly `#767676` (4.54:1) keeps the tonal intent and passes.

**9.3 — Table rows are mouse-only.** [data-table.tsx:87-91](../apps/web/components/data-table.tsx#L87-L91)
puts `onClick` on `<TableRow>` with no `tabIndex`, no key handler, no role. **The primary
navigation into a job cannot be performed with a keyboard** — a WCAG 2.1.1 failure on the app's
most important interaction.

**9.4 — Dialogs don't trap or restore focus.** [dialog.tsx](../apps/web/components/ui/dialog.tsx)
handles Escape and backdrop, but never moves focus in, constrains Tab, or restores focus on close.
Same for the mobile drawer ([app-shell.tsx:191-218](../apps/web/components/app-shell.tsx#L191-L218)),
which additionally **does not close on Escape** despite `role="dialog" aria-modal="true"`.

**9.5 — Product tour is not keyboard-operable.** The spotlight is `pointer-events: none` and focus
is never moved into the tooltip ([product-tour.tsx:89-159](../apps/web/components/product-tour.tsx#L89-L159)),
so a keyboard user tabs behind the overlay.

**9.6 — No skip-to-content link**, and the résumé `<iframe>` is a large focus stop before the
context rail.

---

## 10. Implementation strategy

### High impact / low effort — Iteration 02 (~1 focused pass)

| # | Change | Files | Why now |
|---|---|---|---|
| 1 | Define the missing colour tokens; darken `coffee-300` | `globals.css` | Fixes hierarchy + contrast app-wide in one file |
| 2 | Keyboard-accessible table rows | `data-table.tsx` | WCAG blocker on the core interaction |
| 3 | Focus trap + restore in `Dialog`; Escape closes the drawer | `dialog.tsx`, `app-shell.tsx` | Standard, contained |
| 4 | `session_id` → URL in `/manual` | `manual/page.tsx` | Stops destroying confirmed facts; API exists |
| 5 | Filters + segment → URL in `/jobs` | `jobs/page.tsx` | Back/reload/share start working |
| 6 | Prefill discovery roles from `target_roles` | `jobs/page.tsx` | Removes the clearest "repeat yourself" |
| 7 | Cover-letter card gets a generate action | `jobs/[id]/page.tsx` | Removes a dead end |
| 8 | Drop the `use_ai` checkbox; default on + explain | `ats-checker/page.tsx` | Removes an unanswerable decision |
| 9 | One name per surface | 5 files | Cheap; makes the model learnable |
| 10 | `.gitignore` `tsconfig.tsbuildinfo` | `.gitignore` | Stops polluting every diff |

### High impact / medium effort — Iterations 03–04

| # | Change | Depends on |
|---|---|---|
| 11 | `/` becomes a **Continue** home | — |
| 12 | Stage-aware context rail on `/jobs/[id]` | — |
| 13 | Accept/reject recommendation chips (UI) | #14 |
| 14 | `recommendation_decision` table + read at generation | — |
| 15 | Custom tracks → server | — |
| 16 | Rank the jobs list by fit, not recency | — |
| 17 | AI mode switching (Guide/Collaborator/Assistant) | #11 |

### Long-term

| # | Change |
|---|---|
| 18 | Fold analysis into the workspace; retire `/ats-checker` and `/builder` as destinations |
| 19 | Conversation compression into durable per-track knowledge |
| 20 | Learn writing style from manual LaTeX edits and feed it into generation |
| 21 | Proactive coaching — the AI volunteers before being asked |

### Sequencing rationale

P0 is deliberately all low-risk and independently shippable: no backend changes, no contract
changes, no flow restructuring. It buys back the visual hierarchy the design already intended,
closes two hard accessibility failures, and stops the three worst context losses — before any
structural work begins.

P1 items 13 + 14 should ship together; the chips are meaningless without persistence, and the
table is invisible without the chips.

P2 item 18 is the largest change in this document and should not start until the accept/reject loop
has proven itself inside the existing workspace.

### Constraints honoured

No backend contract changes in P0. `recommendation_decision` (P1) is purely additive. The
`/ats-checker` and `/builder` routes stay live through P2 as redirects, matching the pattern already
used for `/applications` and `/onboarding`.
