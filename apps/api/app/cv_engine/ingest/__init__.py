"""Ingest — records the closed set of truths a run may draw from (never judges).

`facts.build_ledger` turns the run input into the ledger snapshot. In fresh-build the
ledger is derived from the stored profile's cv_json; a run may also carry an explicit
`ledger` (the independent truth source used by fixtures and, later, by uploads/answers).
Section-alias canonicalization for parsing uploaded CVs lands with PDF ingest (Slice 3).
"""

from app.cv_engine.ingest.facts import build_ledger

__all__ = ["build_ledger"]
