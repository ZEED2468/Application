"""Deterministic weak-verb detection for resume bullets (advisory, read-only).

It never rewrites text — a reworded bullet cannot pass the exact-substring truth
guard (`tailoring.assert_truth_bounded`). It only *flags* weak/passive bullet openers
and offers stronger, still-truthful verb alternatives the user/VA may choose to apply
through the reviewed tailoring path. Detection is pure and works in fake + live modes.
"""

from __future__ import annotations

import re

# weak opener -> stronger alternatives that describe the SAME action at a higher
# register (no exaggeration of scope; the human confirms accuracy before applying).
WEAK_VERBS: dict[str, list[str]] = {
    "managed": ["directed", "led", "oversaw", "orchestrated"],
    "worked": ["built", "engineered", "developed", "delivered"],
    "helped": ["enabled", "facilitated", "supported", "drove"],
    "did": ["executed", "performed", "delivered"],
    "made": ["built", "created", "crafted", "produced"],
    "handled": ["managed", "resolved", "processed", "administered"],
    "assisted": ["supported", "enabled", "facilitated"],
    "involved": ["contributed to", "drove", "delivered"],
    "participated": ["contributed to", "collaborated on", "drove"],
    "used": ["leveraged", "applied", "employed"],
    "wrote": ["authored", "developed", "engineered"],
    "responsible": ["owned", "led", "drove", "directed"],  # matches "responsible for"
}
_PHRASE = "responsible for"
_LEAD = re.compile(r"^[\-*••\d.)\s]+")
_WORD = re.compile(r"[a-z']+")


def _opening_word(bullet: str) -> str:
    s = _LEAD.sub("", bullet or "").strip().lower()
    m = _WORD.match(s)
    return m.group(0) if m else ""


def detect(bullets: list[str], *, limit: int = 25) -> list[dict]:
    """Return [{bullet, weak_verb, suggestions}] for bullets that open weakly."""
    out: list[dict] = []
    for b in bullets:
        text = (b or "").strip()
        if not text:
            continue
        low = _LEAD.sub("", text).strip().lower()
        if low.startswith(_PHRASE):
            out.append({"bullet": text, "weak_verb": _PHRASE, "suggestions": WEAK_VERBS["responsible"]})
        else:
            w = _opening_word(text)
            if w in WEAK_VERBS:
                out.append({"bullet": text, "weak_verb": w, "suggestions": WEAK_VERBS[w]})
        if len(out) >= limit:
            break
    return out
