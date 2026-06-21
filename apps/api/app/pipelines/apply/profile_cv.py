"""Resolve CV text from a stored master profile."""

from __future__ import annotations

from app.models.master_profile import MasterProfile
from app.repositories import profiles as profiles_repo


def cv_text_from_profile(profile: MasterProfile) -> str:
    if profile.truth_corpus and profile.truth_corpus.strip():
        return profile.truth_corpus.strip()
    parts: list[str] = []

    def walk(v):
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(profiles_repo.profile_to_dict(profile))
    return "\n".join(parts).strip()
