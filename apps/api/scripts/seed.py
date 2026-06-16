"""Idempotent dev seed: 3 hunters (one admin), 1 VA, per-track profiles + role CVs,
a cover-letter template, and the 9 (hunter, track) sending domains.

Run:  python -m scripts.seed   (from apps/api, with DATABASE_URL set)
Prints the login credentials. Safe to run repeatedly.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.enums import ParseStatus, Track, UserRole
from app.db import AsyncSessionLocal
from app.models.cover_letter import CoverLetterTemplate
from app.models.master_profile import MasterProfile
from app.models.role_cv import RoleCv
from app.models.user import User
from app.models.va import Va
from app.models.va_assignment import VaAssignment
from app.repositories import domains as domains_repo
from app.security import hash_password

PASSWORD = "password123"

HUNTERS = [
    ("ada@jd.dev", "Ada Lovelace", UserRole.admin),
    ("alan@jd.dev", "Alan Turing", UserRole.hunter),
    ("grace@jd.dev", "Grace Hopper", UserRole.hunter),
]

SKILLS = {
    Track.frontend: ["React", "React Native", "TypeScript", "Tailwind", "animation", "mobile"],
    Track.backend: ["Go", "NestJS", "Kubernetes", "microservices", "Postgres", "distributed"],
    Track.general: ["full-stack", "Next.js", "Python", "product", "hackathon", "end-to-end"],
}
HEADLINES = {
    Track.frontend: "I ship production mobile + web frontends.",
    Track.backend: "I build and deploy production backend systems.",
    Track.general: "I build complete products across the stack.",
}


async def _seed_hunter(session, email: str, name: str, role: UserRole) -> User:
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(email=email, name=name, role=role, password_hash=hash_password(PASSWORD))
        session.add(user)
        await session.flush()

    for track in Track:
        profile = (await session.execute(
            select(MasterProfile).where(
                MasterProfile.user_id == user.id, MasterProfile.track == track
            )
        )).scalar_one_or_none()
        if profile is None:
            session.add(MasterProfile(
                user_id=user.id, track=track, headline=HEADLINES[track],
                summary=f"{name} — {HEADLINES[track]}", skills=SKILLS[track],
                experience=[{"title": f"{track.value.title()} Engineer", "company": "Streamline",
                             "bullets": [f"Built production {track.value} systems",
                                         "Owned features end-to-end"]}],
                projects=[{"name": "Proof of Work", "description": f"A {track.value} demo project"}],
                education=[], links={track.value: f"https://demo.jd.dev/{track.value}"},
                truth_corpus=f"{name} has genuine {track.value} experience: {', '.join(SKILLS[track])}.",
            ))
        role_cv = (await session.execute(
            select(RoleCv).where(RoleCv.user_id == user.id, RoleCv.track == track)
        )).scalar_one_or_none()
        if role_cv is None:
            session.add(RoleCv(user_id=user.id, track=track, original_filename=f"{name}-{track.value}.pdf",
                               source_file_key=f"{user.id}/role-cv/{track.value}/seed.pdf",
                               parse_status=ParseStatus.parsed))
        await domains_repo.ensure_domain(session, user_id=user.id, track=track, verified=True)

    tpl = (await session.execute(
        select(CoverLetterTemplate).where(CoverLetterTemplate.user_id == user.id)
    )).scalar_one_or_none()
    if tpl is None:
        session.add(CoverLetterTemplate(
            user_id=user.id, name="Default",
            body="Warm, specific, and concise. Lead with a real company detail.",
        ))
    return user


async def main() -> None:
    async with AsyncSessionLocal() as session:
        hunters = [await _seed_hunter(session, e, n, r) for e, n, r in HUNTERS]

        va = (await session.execute(select(Va).where(Va.email == "vera@jd.dev"))).scalar_one_or_none()
        if va is None:
            va = Va(name="Vera VA", email="vera@jd.dev", password_hash=hash_password(PASSWORD),
                    whatsapp_jid="2348000000001@s.whatsapp.net")
            session.add(va)
            await session.flush()
        for h in hunters:
            exists = (await session.execute(
                select(VaAssignment).where(
                    VaAssignment.va_id == va.id, VaAssignment.user_id == h.id,
                    VaAssignment.track.is_(None),
                )
            )).scalar_one_or_none()
            if exists is None:
                session.add(VaAssignment(va_id=va.id, user_id=h.id, track=None))

        await session.commit()

    print("\nSeed complete. Login (password for all = '%s'):" % PASSWORD)
    for e, n, r in HUNTERS:
        print(f"  hunter {r.value:6} {e}  ({n})")
    print("  va            vera@jd.dev  (Vera VA)")
    print("9 sending domains seeded (3 hunters x 3 tracks).\n")


if __name__ == "__main__":
    asyncio.run(main())
