"""Pipeline A orchestration: discover -> score+classify -> generate CV -> submit.

Each step is a plain async function so it can be driven by a Celery consumer in
prod or called directly in tests. `emit` is injected (defaults to the real bus)
so unit tests can capture events without a live broker.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID

import structlog

from app.config import settings
from app.core.enums import ApplicationStatus, CvStatus, JobSourceName, JobStatus, Track
from app.events import names
from app.events.bus import emit as _real_emit
from app.events.contracts import (
    ApplicationSubmitted,
    CvGenerated,
    JobDiscovered,
    JobScored,
)
from app.llm import relevance, tailoring, track_classify, experience_classify
from app.models.application import Application
from app.models.generated_cv import GeneratedCv
from app.models.job import Job
from app.models.master_profile import MasterProfile
from app.models.user import User
from app.pipelines.apply import discover_cache, render
from app.repositories import applications as app_repo
from app.repositories import jobs as jobs_repo
from app.repositories import profiles as profiles_repo
from app.repositories import source_boards as boards_repo
from app.sources import active_sources
from app.sources.base import SourceQuery
from app.sources.normalize import to_job_fields

log = structlog.get_logger(__name__)


def _emphasis_keywords(profile: MasterProfile) -> list[str]:
    return tailoring._flatten_skills(profile.skills)[:8]


def _target_roles(profile: MasterProfile) -> list[str]:
    return [r for r in (profile.target_roles or []) if isinstance(r, str) and r.strip()]


def _location(profile: MasterProfile) -> str | None:
    locs = getattr(profile, "preferred_locations", None) or []
    return next((loc for loc in locs if isinstance(loc, str) and loc.strip()), None)


# Generic job words that don't distinguish a role — dropped so a search for "Frontend
# Engineer" matches "Frontend Developer" (both distinctively about *frontend*) while a
# plain "Software Engineer" is not pulled in by the shared word "engineer".
_GENERIC_ROLE_WORDS = frozenset({
    "engineer", "engineering", "developer", "development", "dev", "programmer",
    "architect", "manager", "specialist", "analyst", "consultant", "lead", "senior",
    "junior", "mid", "staff", "principal", "associate", "contract", "contractor",
    "permanent", "remote", "hybrid", "officer", "assistant", "role", "position",
})


def title_matches_roles(title: str, roles: list[str]) -> bool:
    """True if `title` matches any target role by its DISTINCTIVE word(s) — the
    generic job words (engineer/developer/senior/…) are dropped, so 'Frontend Engineer'
    matches 'Senior Frontend Developer' but a plain 'Software Engineer' does not. A role
    with only generic words falls back to matching all of them. No roles ⇒ no filtering."""
    if not roles:
        return True
    title_tokens = set(re.findall(r"[a-z0-9]+", (title or "").lower()))
    for role in roles:
        # Keep 2-char tokens — short role words like UI, UX, Go, ML, AI, QA are meaningful
        # (a search for "UI/UX" or "Go Developer" must not filter to nothing).
        tokens = [t for t in re.findall(r"[a-z0-9]+", role.lower()) if len(t) >= 2]
        distinctive = [t for t in tokens if t not in _GENERIC_ROLE_WORDS]
        required = distinctive or tokens
        if required and all(t in title_tokens for t in required):
            return True
    return False


_BOARD_SOURCE_NAMES = {JobSourceName.greenhouse, JobSourceName.lever, JobSourceName.ashby}


def _config_note(name: JobSourceName, boards: list[str]) -> str | None:
    """Why a source found nothing, config-wise — so the diagnostics distinguish
    'skipped: not configured' from 'ran: 0 results'."""
    if name is JobSourceName.adzuna and not (settings.adzuna_app_id and settings.adzuna_app_key):
        return "no ADZUNA_APP_ID/ADZUNA_APP_KEY in this environment"
    if name is JobSourceName.serpapi and not settings.serpapi_api_key:
        return "no SERPAPI_API_KEY in this environment"
    if name in _BOARD_SOURCE_NAMES and not boards:
        return "no board tokens — add company slugs in Admin -> Job boards"
    return None


def _as_track(value) -> Track | None:
    """Coerce a profile/track value — a real profile's `Track` enum or a discovery
    placeholder's raw string — to a built-in `Track`, or `None` for a custom/unknown
    track (which can't be stored in the Enum(Track) column)."""
    if isinstance(value, Track):
        return value
    try:
        return Track(value)
    except (ValueError, TypeError):
        return None


def _decide_track(
    *, title: str, description: str | None, profile_track, selected_tracks: list[str] | None
) -> tuple[Track, bool]:
    """Decide a discovered job's track, and whether it's off-target (should be dropped).

    The keyword classifier is advisory. Priority: the JD literally names a selected
    track > a confident keyword classification > the track the search ran under
    (context) > general. So when the classifier can't tell, we keep the searched track
    instead of silently mislabeling the job "general".

    With an explicit track filter (`selected_tracks`), a job is dropped ONLY when it
    classifies CONFIDENTLY to a built-in track the user did not ask for; a job that
    merely defaulted to the searched track is kept (it already passed the role filter).
    """
    context_track = _as_track(profile_track)
    classified = track_classify.classify(title=title, description=description)
    sel = {s.lower() for s in (selected_tracks or [])}

    literal_track = None
    if selected_tracks:
        tl, dl = title.lower(), (description or "").lower()
        for st in selected_tracks:
            if st.lower() in tl or st.lower() in dl:
                # Only a *built-in* track can be stored in the Enum(Track) column.
                literal_track = _as_track(st)
                if literal_track is not None:
                    break

    if literal_track is not None:
        job_track = literal_track
    elif classified is not Track.general:
        job_track = classified
    else:
        job_track = context_track or Track.general

    if sel and literal_track is None and job_track.value not in sel:
        if classified is not Track.general:
            return job_track, True  # confidently a track the user didn't search for
        # Uncertain classification: keep it, retagged to the searched track.
        if context_track is not None and context_track.value in sel:
            job_track = context_track
    return job_track, False


async def _run_sources(
    session, *, user_id: UUID, profile: MasterProfile, boards: list[str] | None = None,
    role_titles: list[str] | None = None,
    selected_tracks: list[str] | None = None,
    selected_experience_levels: list[str] | None = None,
    cooldown: bool = True,
    emit=_real_emit,
) -> tuple[list[Job], list[dict]]:
    """Run active sources for the hunter's track; dedupe-insert; emit job.discovered.

    Each source is isolated in try/except so one failing source (or a missing
    `source_board` table) can never kill the whole run. Returns the new jobs plus a
    per-source report for the on-demand diagnostics endpoint.
    """
    # User-supplied search roles (the on-demand role box) win; else the hunter's saved
    # target roles. With NEITHER set we don't search at all (see the guard below) — a
    # role-less query returns broad, mostly-irrelevant postings and burns provider tokens.
    roles = [r.strip() for r in (role_titles or []) if r and r.strip()] or _target_roles(profile)
    # Scope the outbound query so providers return only relevant postings (saves tokens):
    # role titles + location + (on-demand) seniority all narrow the fetch, not just a
    # post-fetch discard.
    query = SourceQuery(
        track=profile.track,
        keywords=_emphasis_keywords(profile),
        boards=boards or [],
        role_titles=roles,
        location=_location(profile),
        # Only narrow the outbound query by seniority when a single level is chosen;
        # with several selected we fetch broadly and let the post-fetch filter decide,
        # otherwise the other levels would never be fetched.
        experience_level=(
            selected_experience_levels[0]
            if selected_experience_levels and len(selected_experience_levels) == 1
            else None
        ),
    )
    actives = [s for s in active_sources() if s.supports(profile.track)]
    
    track_val = profile.track.value if hasattr(profile.track, "value") else profile.track
    log.info("discover.start", user_id=str(user_id), track=track_val,
             keywords=query.keywords, roles=roles, fake_mode=settings.use_fake_integrations,
             sources=[s.name.value for s in actives])

    # No role scope → skip EVERY source (zero provider API calls). A role-less search
    # returns mostly irrelevant jobs and wastes Adzuna/SerpApi tokens; the user drives the
    # search via the on-demand role box, and the 30-min beat stays quiet for a hunter with
    # no target roles set. Only enforced with REAL integrations — fake mode has no token
    # cost, so dev/tests keep discovering without a role. Single choke point for both paths.
    if not roles and not settings.use_fake_integrations:
        log.info("discover.skipped_no_roles", user_id=str(user_id), track=track_val)
        report = [{"source": s.name.value, "found": 0, "inserted": 0, "off_target": 0,
                   "error": None,
                   "note": "skipped: enter a search role (or set target roles) to search"}
                  for s in actives]
        return [], report

    # Board scrapers (Greenhouse/Lever/Ashby) pull per-company tokens. Resilient: a
    # missing/un-migrated `source_board` table must not break discovery.
    by_source: dict = {}
    if boards is None:
        try:
            by_source = await boards_repo.active_by_source(session)
        except Exception as exc:  # noqa: BLE001 — degrade gracefully
            log.warning("discover.boards_lookup_failed", error=str(exc),
                        exc_type=type(exc).__name__)

    new_jobs: list[Job] = []
    report: list[dict] = []
    for source in actives:
        name = source.name.value
        if boards is None:
            query.boards = by_source.get(source.name, [])
        # Notes are diagnostic and only meaningful with real integrations.
        note = (
            None if settings.use_fake_integrations
            else _config_note(source.name, query.boards)
        )
        # Skip an identical query fetched within the cooldown window (saves API tokens).
        qhash = discover_cache.query_hash(name, query)
        if cooldown and await discover_cache.should_skip(user_id, name, qhash):
            log.info("discover.source.cooldown_skip", source=name)
            report.append({"source": name, "found": 0, "inserted": 0, "off_target": 0,
                           "error": None, "note": "skipped: fetched recently (cooldown)"})
            continue
        found = inserted = off_target = 0
        error: str | None = None
        log.info("discover.source.fetch", source=name, boards=query.boards or None, note=note)
        try:
            # Unconfigured adapters (no key / no board tokens) no-op immediately.
            async for raw in source.fetch(query):
                found += 1
                # Scope to the hunter's target roles (all sources, even board scrapers).
                if not title_matches_roles(raw.title, roles):
                    off_target += 1
                    continue

                # Track assignment — searched track is the fallback, never a silent
                # "general" (see _decide_track). Off-target jobs are dropped.
                job_track, off_target_drop = _decide_track(
                    title=raw.title, description=raw.description,
                    profile_track=profile.track, selected_tracks=selected_tracks,
                )
                if off_target_drop:
                    off_target += 1
                    continue

                # Experience level classification
                job_exp = experience_classify.classify(title=raw.title, description=raw.description)
                if selected_experience_levels and job_exp not in selected_experience_levels:
                    # Skip: job experience level does not match selected
                    off_target += 1
                    continue

                fields = to_job_fields(raw)
                fields.setdefault("role_title", fields["title"])  # auto jobs: posting title (capped)
                fields["track"] = job_track
                fields["experience_level"] = job_exp
                
                job = await jobs_repo.insert_if_new(session, user_id=user_id, fields=fields)
                if job is not None:
                    inserted += 1
                    new_jobs.append(job)
                    emit(names.JOB_DISCOVERED,
                         JobDiscovered(user_id=user_id, job_id=job.id, source=name))
            # A completed fetch (even 0 results) starts the cooldown for this query.
            await discover_cache.mark_ran(user_id, name, qhash)
        except Exception as exc:  # noqa: BLE001 — one bad source shouldn't stop the rest
            error = f"{type(exc).__name__}: {exc}"
            log.warning("discover.source.failed", source=name, error=error)
        log.info("discover.source.done", source=name, found=found, inserted=inserted,
                 off_target=off_target, error=error, note=note)
        report.append({"source": name, "found": found, "inserted": inserted,
                       "off_target": off_target, "error": error, "note": note})
                       
    log.info("discover.done", user_id=str(user_id), track=track_val,
             new=len(new_jobs))
    return new_jobs, report


async def discover_for_user(
    session, *, user_id: UUID, profile: MasterProfile, boards: list[str] | None = None,
    emit=_real_emit,
) -> list[Job]:
    """Run active sources for the hunter's track, dedupe-insert, emit job.discovered."""
    new_jobs, _ = await _run_sources(
        session, user_id=user_id, profile=profile, boards=boards, emit=emit
    )
    track_val = profile.track.value if hasattr(profile.track, "value") else profile.track
    log.info("apply.discovered", count=len(new_jobs), track=track_val)
    return new_jobs


def classify_track(job: Job) -> Track:
    """Assign a track from the JD text (override-able later). Track is needed
    before scoring/tailoring because the master profile is per (user, track)."""
    if job.track:
        return job.track
    track = job.track_override or track_classify.classify(
        title=job.title, description=job.description
    )
    job.track = track
    return track


async def score_relevance(session, *, job: Job, profile: MasterProfile, emit=_real_emit) -> Job:
    """Relevance prefilter against the track's profile. Emits job.scored if it passes."""
    skills = tailoring._flatten_skills(profile.skills)
    job.relevance_score = relevance.score(
        title=job.title, description=job.description, skills=skills
    )
    if not relevance.passes(job.relevance_score):
        job.status = JobStatus.rejected
        log.info("apply.rejected", job_id=str(job.id), score=job.relevance_score)
        return job
    job.status = JobStatus.scored
    await session.flush()
    emit(names.JOB_SCORED,
         JobScored(user_id=job.user_id, job_id=job.id,
                   relevance_score=job.relevance_score, track=job.track))
    return job


async def generate_cv(session, *, job: Job, profile: MasterProfile, emit=_real_emit) -> GeneratedCv:
    """Tailor + ATS + cover letter via the SHARED engine (same path as manual)."""
    from app.pipelines import generation

    owner = await session.get(User, job.user_id)
    cv, _cover = await generation.generate_cv_and_cover(
        session, job=job, profile=profile, owner=owner, emit=emit
    )
    return cv


async def submit_application(
    session, *, user_id: UUID, job: Job, generated_cv: GeneratedCv,
    va_id: UUID | None = None, emit=_real_emit,
) -> Application:
    """VA submits the application -> emits application.submitted (kicks off Pipeline B)."""
    application = Application(
        user_id=user_id, job_id=job.id, generated_cv_id=generated_cv.id, va_id=va_id,
        status=ApplicationStatus.submitted, submitted_at=datetime.now(timezone.utc),
    )
    session.add(application)
    job.status = JobStatus.submitted
    await session.flush()
    app_repo.record_event(
        session, application=application, kind="applied",
        actor=f"va:{va_id}" if va_id else "system",
        detail={"ats": generated_cv.ats_score, "origin": job.origin.value},
    )
    emit(names.APPLICATION_SUBMITTED,
         ApplicationSubmitted(user_id=user_id, application_id=application.id,
                              job_id=job.id, track=job.track))
    return application
