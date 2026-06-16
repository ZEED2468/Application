"""Outreach email drafting — leads with the track's proof-of-work link + the real
hook + a de-risking line. Email channel only (never LinkedIn DM)."""

from __future__ import annotations

from app.core.enums import Track
from app.llm.hookfinder import Hook

_PROOF_LABEL = {
    Track.frontend: "a live mobile/web demo",
    Track.backend: "a production backend system I built",
    Track.general: "a complete product I shipped end-to-end",
}
_DERISK = "I'm remote-ready with timezone overlap and async-friendly."


def _proof_link(links: dict, track: Track) -> str:
    if not links:
        return ""
    for key in (track.value, "portfolio", "github", "website"):
        if links.get(key):
            return links[key]
    return next(iter(links.values()), "")


def _fake_draft(
    *, candidate_name: str, company: str, role_title: str, track: Track,
    hook: Hook, proof_link: str, contact_name: str,
) -> tuple[str, str]:
    subject = f"{role_title} at {company} — quick note"
    proof = _PROOF_LABEL.get(track, "my work")
    body = (
        f"Hi {contact_name.split()[0] if contact_name else 'there'},\n\n"
        f"I noticed {hook.text}. I'm {candidate_name}, and I lead with {proof}"
        + (f": {proof_link}" if proof_link else "")
        + ".\n\n"
        f"I'd love to be considered for the {role_title} role. {_DERISK}\n\n"
        f"Worth a short conversation?\n\n"
        f"Best,\n{candidate_name}"
    )
    return subject, body


async def draft_outreach(
    *, candidate_name: str, company: str, role_title: str, track: Track,
    hook: Hook, links: dict, contact_name: str = "",
) -> tuple[str, str]:
    proof_link = _proof_link(links, track)
    from app.llm import client

    if not client.is_live():
        return _fake_draft(
            candidate_name=candidate_name, company=company, role_title=role_title,
            track=track, hook=hook, proof_link=proof_link, contact_name=contact_name,
        )

    system = (
        "Write a short, non-templated cold outreach email. Lead with the proof-of-"
        "work link, reference the real hook, include one de-risking line (remote/"
        "timezone/async). Email only. Return: <subject> || <body>."
    )
    prompt = (
        f"Candidate: {candidate_name}\nCompany: {company}\nRole: {role_title}\n"
        f"Track: {track.value}\nProof link: {proof_link}\nHook: {hook.text}\n"
        f"Contact: {contact_name}"
    )
    text = await client.complete_text(system, prompt, max_tokens=500)
    subject, _, body = text.partition("||")
    return subject.strip() or f"{role_title} at {company}", body.strip()
