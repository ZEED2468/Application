"""Render + extract — compile the canonical .tex and re-read the real artifact.

`compile.py` wraps the existing tectonic path; `extract.py` reads the compiled PDF
with two independent extractors (pypdf + pdfminer) so a rendered rule can check they
agree — the artifact is the truth, and the truth is whatever text actually comes back
out of the PDF, not what went in.
"""
