"""Hook-finder — one real, specific company detail to anchor outreach + cover
letters. Track-aware. The hook must be REAL: in fake mode it is derived
deterministically; in live mode the model is constrained to verifiable signals
(recent launch, eng blog post, tech stack, repo, funding) and must cite the source.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from app.core.enums import Track

_log = structlog.get_logger(__name__)


@dataclass(slots=True)
class Hook:
    text: str
    source: str  # where the detail came from (url/description) — never invented


_TRACK_ANGLE = {
    Track.frontend: "recent UI/mobile work",
    Track.backend: "backend/infra architecture",
    Track.general: "product and engineering breadth",
}


def _fake_hook(company: str, track: Track, job_description: str | None) -> Hook:
    angle = _TRACK_ANGLE.get(track, "engineering work")
    snippet = (job_description or "").strip().split(".")[0][:140] if job_description else ""
    if snippet:
        return Hook(
            text=f"your team's {angle} — the JD's note that \"{snippet}\" stood out",
            source="job_description",
        )
    return Hook(text=f"{company}'s {angle}", source="company_name")


async def find_hook(*, company: str, track: Track, job_description: str | None = None) -> Hook:
    from app.llm import client

    if not client.is_live("hookfinder"):
        return _fake_hook(company, track, job_description)

    system = (
        "Find ONE real, specific, verifiable detail about the company to anchor a "
        "cold email — a recent launch, eng blog post, notable tech-stack choice, "
        "open-source repo, or funding/news. It MUST be real; if you are unsure, "
        "use only what is in the provided job description. Return: <detail> || <source>."
    )
    prompt = f"Company: {company}\nTrack angle: {_TRACK_ANGLE.get(track)}\nJD:\n{job_description or ''}"
    try:
        text = await client.complete_text(system, prompt, max_tokens=300, feature="hookfinder")
    except Exception as exc:  # noqa: BLE001 — a bad key / provider outage must not crash
        # generation. Fall back to the deterministic (still truthful) hook, like tailoring.
        _log.warning("hookfinder.live_failed", error=str(exc), exc_type=type(exc).__name__)
        return _fake_hook(company, track, job_description)
    detail, _, source = text.partition("||")
    return Hook(text=detail.strip(), source=(source.strip() or "model"))
