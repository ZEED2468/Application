"""Track classification — rule-based keyword scoring, override-able downstream."""

from __future__ import annotations

import re

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


def classify(*, title: str, description: str | None) -> Track:
    tokens = set(_TOKEN.findall(f"{title} {description or ''}".lower()))
    scores = {track: len(tokens & signals) for track, signals in _SIGNALS.items()}
    best = max(scores, key=scores.get)
    # No signal at all -> default to general (breadth).
    return best if scores[best] > 0 else Track.general
