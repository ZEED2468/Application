"""Ingest — records the closed set of truths a run may draw from (never judges).

`facts.build_ledger` turns the run input into the ledger snapshot. In fresh-build the
ledger is derived from the stored profile's cv_json; a run may also carry an explicit
`ledger` (the independent truth source used by fixtures and by uploads/answers).
`parse_cv_text` (Slice 3) is the deterministic "honest 80%" PDF/text CV parser — it
canonicalizes section headers and normalizes dates at parse time.
"""

from app.cv_engine.ingest.facts import build_ledger
from app.cv_engine.ingest.parse_cv import ParsedCv, parse_cv_text

__all__ = ["ParsedCv", "build_ledger", "parse_cv_text"]
