r"""LaTeX compile-safety guard.

User- and LLM-authored LaTeX is compiled by tectonic. Even though tectonic runs in
`--untrusted` mode (shell-escape disabled, restricted IO), we defence-in-depth by
rejecting / stripping the known-dangerous primitives before the source ever reaches
the compiler: shell execution (`\write18`), arbitrary file IO (`\input`, `\include`,
`\openin`, `\openout`, `\read`, `\write`), and Lua/catcode escapes.
"""

from __future__ import annotations

import re

from app.core.errors import DomainError

# Bare control sequences that must not appear. `\b` keeps `\inputencoding`,
# `\readlist`, etc. legal (the boundary fails when a word char follows).
_FORBIDDEN_CMDS = [
    "write18", "input", "include", "immediate", "openin", "openout",
    "read", "write", "directlua", "catcode", "csname",
]
_CMD_RE = re.compile(r"\\(" + "|".join(_FORBIDDEN_CMDS) + r")\b", re.IGNORECASE)
_PKG_RE = re.compile(r"\\usepackage\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}", re.IGNORECASE)
_BAD_PKGS = {"shellesc", "write18"}


def find_forbidden(tex: str) -> list[str]:
    """Return a sorted, de-duplicated list of forbidden constructs found in `tex`."""
    found: list[str] = []
    for m in _CMD_RE.finditer(tex or ""):
        found.append("\\" + m.group(1).lower())
    for m in _PKG_RE.finditer(tex or ""):
        for pkg in m.group(1).split(","):
            if pkg.strip().lower() in _BAD_PKGS:
                found.append(f"package:{pkg.strip().lower()}")
    return sorted(set(found))


def assert_safe(tex: str) -> None:
    """Raise DomainError (400) listing what was rejected. Used on human-supplied
    LaTeX (preview / commit) so the editor surfaces a clear message."""
    found = find_forbidden(tex)
    if found:
        raise DomainError("Unsafe LaTeX rejected — remove: " + ", ".join(found))


def sanitize_latex(tex: str) -> str:
    """Best-effort strip of forbidden constructs from LLM-authored output before a
    compile attempt; anything left unrenderable is caught by the deterministic
    `build_tex` fallback in the regeneration service."""
    cleaned = _CMD_RE.sub("", tex or "")
    cleaned = _PKG_RE.sub(
        lambda m: "" if any(p.strip().lower() in _BAD_PKGS for p in m.group(1).split(","))
        else m.group(0),
        cleaned,
    )
    return cleaned
