"""The single user-facing score — computed on the REAL compiled + re-extracted artifact.

This is the concrete fix Slice 1 promises. The existing checker scores naive text with
the gate always ``unevaluated`` and never compiles a PDF; even generation scores the
cv_json *draft*, not the artifact. Here we rebuild a cv_json from the text re-extracted
from the compiled PDF and run the unmodified, test-locked `ats.score` against it, gated
by the real `format_gate` result — so a failed compile yields no number, and content
silently dropped in rendering actually lowers the score.

We deliberately do NOT introduce a competing weighted-rule score in this slice: the rule
violations gate/annotate, and `ats.score`'s locked model stays the number (its 7 invariant
tests must keep passing). A blended rule-weight score is a later slice.
"""

from __future__ import annotations

from app.pipelines.apply import ats
from app.pipelines.apply.cv_parse import cv_json_from_text


def score_artifact(
    *, extracted_text: str, jd_text: str, role_title: str | None, gate: dict
) -> dict:
    """Return the `ats.score` breakdown computed on the artifact's re-extracted text.

    `gate` is the `format_gate.evaluate` result for the same artifact — a ``fail`` gate
    yields ``score=None`` (the honesty rule), ``unevaluated`` leaves the content number
    intact but unblessed.
    """
    artifact_cv = cv_json_from_text(extracted_text)
    return ats.score(
        cv_json=artifact_cv, jd_text=jd_text, role_title=role_title, gate=gate
    )
