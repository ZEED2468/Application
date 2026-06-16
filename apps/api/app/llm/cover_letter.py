"""Cover-letter generation — exactly three paragraphs, seeded from the hunter's
onboarding template, tailored per role. Same truth boundary as CV tailoring: the
company hook must be REAL (reuse the hook-finder), and the mirrored work must be
something the hunter genuinely did (drawn from the profile)."""

from __future__ import annotations

from app.core.enums import Track
from app.llm.hookfinder import Hook


def _pick_mirror(profile: dict, jd_text: str | None) -> str:
    """Choose a real accomplishment from the profile that maps to the role."""
    experience = profile.get("experience") or []
    projects = profile.get("projects") or []
    bullets: list[str] = []
    for e in experience:
        bullets.extend(e.get("bullets", []))
    for p in projects:
        if p.get("description"):
            bullets.append(p["description"])
    if not bullets:
        return profile.get("summary") or "work I've shipped end-to-end"
    if jd_text:
        jl = jd_text.lower()
        ranked = sorted(bullets, key=lambda b: -sum(w in jl for w in b.lower().split()))
        return ranked[0]
    return bullets[0]


def build_three_paragraphs(
    *, candidate_name: str, company: str, role_title: str, hook: Hook,
    profile: dict, jd_text: str | None,
) -> str:
    mirror = _pick_mirror(profile, jd_text)
    p1 = (
        f"Dear {company} team, I'm {candidate_name}, writing about the {role_title} "
        f"role. I noticed {hook.text} — it's exactly the kind of work I want to do."
    )
    p2 = (
        f"It maps closely to something I've actually done: {mirror} "
        "I'd bring that same hands-on experience to your team."
    )
    p3 = (
        f"I'd love to join {company} specifically because of the above, and I think "
        "the fit is mutual: you get someone who ships, communicates async, and is "
        f"remote-ready from day one. Thank you for considering me. Best, {candidate_name}"
    )
    return f"{p1}\n\n{p2}\n\n{p3}"


async def generate_cover_letter(
    *, candidate_name: str, company: str, role_title: str, track: Track,
    hook: Hook, profile: dict, jd_text: str | None = None, template_body: str | None = None,
) -> str:
    from app.llm import client

    if not client.is_live():
        return build_three_paragraphs(
            candidate_name=candidate_name, company=company, role_title=role_title,
            hook=hook, profile=profile, jd_text=jd_text,
        )

    import json

    system = (
        "Write a cover letter of EXACTLY three paragraphs: (1) intro + a specific, "
        "REAL company hook, (2) a genuine accomplishment of the candidate that mirrors "
        "that work, (3) why-join + mutual benefit. Use ONLY facts from the profile; "
        "never invent. Seed tone from the template if provided."
    )
    prompt = (
        f"Candidate: {candidate_name}\nCompany: {company}\nRole: {role_title}\n"
        f"Hook (real): {hook.text}\nTemplate: {template_body or ''}\n"
        f"Profile: {json.dumps(profile)}\nJD: {jd_text or ''}"
    )
    return await client.complete_text(system, prompt, max_tokens=900)
