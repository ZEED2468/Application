"""LaTeX CV rendering: cv_json -> ATS-safe single-column .tex -> PDF via tectonic.

If the tectonic binary is unavailable (dev without the toolchain), the .tex is
still produced and stored, and a minimal placeholder PDF stands in so the
pipeline completes; production runs tectonic in the Docker image.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

_LATEX_ESCAPE = {
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
    "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
}


def _esc(text) -> str:
    return "".join(_LATEX_ESCAPE.get(c, c) for c in str(text or ""))


def build_tex(cv_json: dict, *, name: str) -> str:
    """Single-column, ATS-safe LaTeX (no multicol, no graphics, plain text flow)."""
    lines = [
        r"\documentclass[11pt]{article}",
        r"\usepackage[margin=1in]{geometry}",
        r"\usepackage{enumitem}",
        r"\setlist{nosep}",
        r"\pagestyle{empty}",
        r"\begin{document}",
        rf"\begin{{center}}{{\Large\bfseries {_esc(name)}}}\end{{center}}",
    ]
    if cv_json.get("headline"):
        lines.append(rf"\begin{{center}}{_esc(cv_json['headline'])}\end{{center}}")
    if cv_json.get("summary"):
        lines += [r"\section*{Summary}", _esc(cv_json["summary"])]

    skills = cv_json.get("skills") or []
    if skills:
        lines += [r"\section*{Skills}", _esc(", ".join(skills))]

    experience = cv_json.get("experience") or []
    if experience:
        lines.append(r"\section*{Experience}")
        for e in experience:
            title = " - ".join(filter(None, [e.get("title") or e.get("role"), e.get("company")]))
            lines.append(rf"\textbf{{{_esc(title)}}}\\")
            for b in e.get("bullets", []):
                lines.append(rf"\hspace*{{1em}}$\bullet$ {_esc(b)}\\")

    projects = cv_json.get("projects") or []
    if projects:
        lines.append(r"\section*{Projects}")
        for p in projects:
            lines.append(rf"\textbf{{{_esc(p.get('name'))}}}: {_esc(p.get('description'))}\\")

    lines.append(r"\end{document}")
    return "\n".join(lines)


def build_cover_letter_tex(body: str, *, name: str) -> str:
    """Single-column letter LaTeX from the 3-paragraph body text."""
    paragraphs = "\n\n".join(_esc(p.strip()) for p in body.split("\n\n") if p.strip())
    return "\n".join([
        r"\documentclass[11pt]{article}",
        r"\usepackage[margin=1in]{geometry}",
        r"\pagestyle{empty}",
        r"\setlength{\parskip}{1em}",
        r"\setlength{\parindent}{0pt}",
        r"\begin{document}",
        rf"{{\large\bfseries {_esc(name)}}}\\[1em]",
        paragraphs,
        r"\end{document}",
    ])


async def render_pdf(tex_source: str) -> bytes:
    """Compile .tex -> PDF bytes via tectonic; fall back to a stub PDF if absent."""
    if shutil.which("tectonic") is None:
        return _stub_pdf()
    with tempfile.TemporaryDirectory() as tmp:
        tex_path = Path(tmp) / "cv.tex"
        tex_path.write_text(tex_source, encoding="utf-8")
        proc = await asyncio.create_subprocess_exec(
            "tectonic", "--untrusted", "--outdir", tmp, str(tex_path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        pdf_path = Path(tmp) / "cv.pdf"
        if proc.returncode == 0 and pdf_path.exists():
            return pdf_path.read_bytes()
    return _stub_pdf()


async def render_pdf_checked(
    tex_source: str, *, timeout: float = 30.0
) -> tuple[bytes | None, str]:
    """Compile arbitrary (user/LLM-authored) .tex and report failures.

    Returns ``(pdf_bytes, "")`` on success or ``(None, stderr)`` on a non-zero exit
    or timeout, so callers can surface the compile error to the editor instead of
    silently producing a broken document. Runs tectonic in ``--untrusted`` mode
    (shell-escape off, restricted IO). In dev without the tectonic binary, returns a
    stub PDF so previews still render.
    """
    if shutil.which("tectonic") is None:
        return _stub_pdf(), ""
    with tempfile.TemporaryDirectory() as tmp:
        tex_path = Path(tmp) / "doc.tex"
        tex_path.write_text(tex_source, encoding="utf-8")
        proc = await asyncio.create_subprocess_exec(
            "tectonic", "--untrusted", "--outdir", tmp, str(tex_path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            _out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except (asyncio.TimeoutError, TimeoutError):
            proc.kill()
            await proc.wait()
            return None, f"compile timed out after {timeout:.0f}s"
        pdf_path = Path(tmp) / "doc.pdf"
        if proc.returncode == 0 and pdf_path.exists():
            return pdf_path.read_bytes(), ""
        return None, (err.decode("utf-8", "replace") if err else "compile failed")


def _stub_pdf() -> bytes:
    """Smallest valid PDF — placeholder when tectonic isn't installed."""
    return (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF"
    )
