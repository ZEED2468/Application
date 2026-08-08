"""Compile canonical .tex → PDF, honestly reporting when no compiler was available.

Reuses `render.render_pdf_checked` (tectonic, --untrusted, timeout) but never lets its
dev-mode stub PDF masquerade as a real artifact: when the tectonic binary is absent we
return ``pdf=None, has_compiler=False`` so the format gate records ``unevaluated`` — a
missing measurement is never a pass (invariant #2).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass

from app.pipelines.apply import render


def has_compiler() -> bool:
    return shutil.which("tectonic") is not None


@dataclass
class CompileResult:
    tex: str
    pdf: bytes | None
    stderr: str
    has_compiler: bool


async def compile_tex(tex: str, *, timeout: float = 30.0) -> CompileResult:
    """Compile `tex`; return the real PDF or a truthful failure.

    - No tectonic → ``pdf=None, has_compiler=False`` (the gate will be ``unevaluated``).
    - tectonic present → the real ``render_pdf_checked`` result: bytes on success, or
      ``None`` + stderr on a non-zero exit / timeout.
    """
    if not has_compiler():
        return CompileResult(tex=tex, pdf=None, stderr="", has_compiler=False)
    pdf, stderr = await render.render_pdf_checked(tex, timeout=timeout)
    return CompileResult(tex=tex, pdf=pdf, stderr=stderr, has_compiler=True)
