"""Unicode normalization for uploaded CV text (ingest, deterministic).

The only unicode-normalization util in the repo. NFKC folds ligatures (ﬁ→fi) and
compatibility forms while KEEPING real diacritics (é stays é — it's part of a name).
Dashes and smart quotes are normalized explicitly (NFKC leaves them), and PDF
line-wrap hyphenation is repaired. Newlines are preserved — section detection is
line-anchored downstream.
"""

from __future__ import annotations

import re
import unicodedata

_DASHES = {"–": "-", "—": "-", "−": "-", "‐": "-", "‑": "-"}
_QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"', "´": "'"}
_DEHYPHEN = re.compile(r"(\w)-\n(\w)")
_BLANKS = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    for src, dst in {**_DASHES, **_QUOTES}.items():
        t = t.replace(src, dst)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = _DEHYPHEN.sub(r"\1\2", t)  # "hyphen-\nated" → "hyphenated"
    t = "\n".join(line.rstrip() for line in t.split("\n"))
    return _BLANKS.sub("\n\n", t).strip()
