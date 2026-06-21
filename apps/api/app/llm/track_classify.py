"""Track classification — rules + optional AI pick among uploaded CVs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.core.enums import Track

_TOKEN = re.compile(r"[a-z0-9+#.]+")

_SIGNALS: dict[Track, set[str]] = {
    Track.frontend: {
        "frontend", "front-end", "react", "react-native", "vue", "angular", "ui",
        "css", "tailwind", "mobile", "ios", "android", "animation", "design",
    },
    Track.backend: {
        "backend", "back-end", "go", "golang", "nestjs", "node", "microservices",
        "infrastructure", "kubernetes", "distributed", "platform", "api", "database",
    },
    Track.general: {
        "full-stack", "fullstack", "full", "stack", "product", "founding", "generalist",
    },
}


@dataclass(slots=True)
class TrackMatch:
    track: Track
    method: str  # "rules" | "ai" | "availability"
    reason: str


def classify_rules(*, title: str, description: str | None) -> Track:
    tokens = set(_TOKEN.findall(f"{title} {description or ''}".lower()))
    scores = {track: len(tokens & signals) for track, signals in _SIGNALS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else Track.general


def _preview_overlap(jd_tokens: set[str], preview: str) -> int:
    cv_tokens = set(_TOKEN.findall(preview.lower()))
    return len(jd_tokens & cv_tokens)


def _pick_by_overlap(
    jd_tokens: set[str], available: dict[Track, str], *, fallback: Track
) -> TrackMatch:
    if not available:
        return TrackMatch(
            track=fallback,
            method="rules",
            reason="No uploaded CVs; track from JD keywords only.",
        )
    if len(available) == 1:
        track = next(iter(available))
        return TrackMatch(
            track=track,
            method="availability",
            reason=f"Only the {track.value} source CV is uploaded.",
        )
    ranked = sorted(
        available.items(),
        key=lambda kv: (-_preview_overlap(jd_tokens, kv[1]), kv[0].value),
    )
    track = ranked[0][0]
    return TrackMatch(
        track=track,
        method="rules",
        reason=f"Best keyword overlap with the {track.value} CV among uploaded tracks.",
    )


async def classify_best(
    *,
    title: str,
    description: str | None,
    available: dict[Track, str],
) -> TrackMatch:
    """Pick frontend / backend / general using JD + which CVs exist."""
    rule_track = classify_rules(title=title, description=description)
    jd_tokens = set(_TOKEN.findall(f"{title} {description or ''}".lower()))

    if not available:
        return TrackMatch(
            track=rule_track,
            method="rules",
            reason="No source CVs uploaded yet; track inferred from JD keywords.",
        )

    if len(available) == 1:
        only = next(iter(available))
        return TrackMatch(
            track=only,
            method="availability",
            reason=f"Only the {only.value} source CV is uploaded.",
        )

    if rule_track in available:
        preferred = rule_track
        reason = f"JD matches {rule_track.value} signals and that CV is uploaded."
    else:
        overlap = _pick_by_overlap(jd_tokens, available, fallback=rule_track)
        preferred = overlap.track
        reason = (
            f"JD suggests {rule_track.value}, but no CV for that track — "
            f"using {overlap.track.value} CV ({overlap.reason})"
        )

    from app.llm import client

    if not client.is_live("track_classify") or len(available) < 2:
        if rule_track in available:
            return TrackMatch(track=rule_track, method="rules", reason=reason)
        return _pick_by_overlap(jd_tokens, available, fallback=rule_track)

    system = (
        "Pick the best CV track for a job. Return JSON ONLY: "
        '{"track": "frontend"|"backend"|"general", "reason": "one sentence"}. '
        "Choose ONLY from tracks that have an uploaded CV. "
        "frontend = UI/mobile/React; backend = APIs/infra/Node/Go; "
        "general = full-stack or mixed."
    )
    prompt = json.dumps(
        {
            "job_title": title,
            "job_description": description or "",
            "uploaded_cvs": {t.value: preview[:2000] for t, preview in available.items()},
        },
        indent=2,
    )
    raw = await client.try_complete_text(system, prompt, max_tokens=400, feature="track_classify")
    if raw is None:
        if rule_track in available:
            return TrackMatch(track=rule_track, method="rules", reason=reason)
        return _pick_by_overlap(jd_tokens, available, fallback=rule_track)
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)
        picked = Track(str(data.get("track", preferred.value)))
        if picked in available:
            return TrackMatch(
                track=picked,
                method="ai",
                reason=str(data.get("reason") or reason).strip(),
            )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass

    return TrackMatch(track=preferred, method="rules", reason=reason)


# Back-compat alias used across the codebase.
def classify(*, title: str, description: str | None) -> Track:
    return classify_rules(title=title, description=description)
