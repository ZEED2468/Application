"""Deterministic PATCH-phase fixes — date/text normalization + grounding safety.

The fixes only reformat existing strings, so a patched cv_json must still ground against
the original-input ledger (no invented numbers/entities), and the machine must record a
`patching` step whose delta reports what went fail→pass.
"""

import pytest
from sqlalchemy import select

from app.core.enums import RunState
from app.cv_engine.fixes.deterministic import (
    normalize_date_string,
    normalize_dates,
    tidy_links,
    tidy_text,
    tidy_value,
)
from app.cv_engine.rules import default_registry
from app.cv_engine.rules.base import Phase, RuleContext
from app.cv_engine.runs.machine import run_pipeline
from app.cv_engine.runs.models import CvRunStep
from tests.helpers import seed_hunter


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Jan 2020 - present", "Jan 2020 -- Present"),
        ("January 2020 – Present", "Jan 2020 -- Present"),
        ("2021/2024", "2021 -- 2024"),
        ("2020-2024", "2020 -- 2024"),
        ("01/2020", "Jan 2020"),
        ("2020-01", "Jan 2020"),
        ("Sept 2019 to Dec 2021", "Sep 2019 -- Dec 2021"),
        ("Present", "Present"),
    ],
)
def test_normalize_date_string_table(raw, expected):
    assert normalize_date_string(raw) == expected


@pytest.mark.parametrize(
    "raw", ["2021 -- 2024", "garbage text", ""]
)
def test_normalize_date_string_leaves_canonical_or_unparseable(raw):
    # Already-canonical or unrecognized inputs → None (left untouched by the fix).
    assert normalize_date_string(raw) is None


def test_tidy_value_strips_bullets_and_collapses_whitespace():
    assert tidy_value("  •  Built   Go  microservices ") == "Built Go microservices"


def test_tidy_links_adds_scheme_and_lowercases_host():
    cv, fixes = tidy_links({"links": {"github": "GitHub.com/AdaHunter"}})
    assert cv["links"]["github"] == "https://github.com/AdaHunter"  # host lowercased, path kept
    assert fixes and fixes[0]["rule_id"] == "structure.clean_text"


def test_fixes_are_grounding_safe():
    """Applying the deterministic fixes must not introduce a grounding violation."""
    cv = {
        "summary": "  Backend engineer in Go. ",
        "skills": ["Go"],
        "experience": [{"title": "Backend Engineer", "company": "Streamline",
                        "dates": "Jan 2020 - present",
                        "bullets": ["• Built Go microservices", "  Reduced latency by 40%  "]}],
        "links": {"github": "github.com/adahunter"},
        "education": [], "projects": [],
    }
    ledger = [{"text": "Backend engineer in Go. Backend Engineer at Streamline Jan 2020 present. "
                       "Built Go microservices. Reduced latency by 40%."},
              {"text": "github.com/adahunter"}]
    for fn in (normalize_dates, tidy_text, tidy_links):
        cv, _ = fn(cv)
    reg = default_registry()
    violations = reg.run(RuleContext(cv_json=cv, ledger=ledger, name="Ada Hunter"), Phase.draft)
    grounding = [v.rule_id for v in violations if v.rule_id.startswith("grounding.")]
    assert grounding == [], f"fixes broke grounding: {grounding}"


async def test_machine_patch_records_step_and_delta(session):
    user, _ = await seed_hunter(session)
    cv = {
        "headline": "Backend Engineer",
        "summary": "  Backend engineer in Go and Kubernetes. ",
        "skills": ["Go", "Kubernetes", "Postgres"],
        "experience": [{"title": "Backend Engineer", "company": "Streamline",
                        "dates": "Jan 2020 - present",
                        "bullets": ["• Built Go microservices", "  Reduced latency by 40%  "]}],
        "links": {"github": "github.com/adahunter"},
        "education": [{"degree": "BSc Computer Science", "school": "Unilag", "dates": "2016/2020"}],
        "projects": [],
    }
    ledger = [
        {"text": "Backend engineer in Go and Kubernetes. Backend Engineer at Streamline "
                 "Jan 2020 present. Built Go microservices. Reduced latency by 40%."},
        {"text": "BSc Computer Science Unilag 2016 2020"},
        {"text": "Go Kubernetes Postgres"}, {"text": "github.com/adahunter"},
    ]
    run = await run_pipeline(session, user_id=user.id, input={
        "cv_json": cv, "ledger": ledger, "jd_text": "Go Kubernetes backend",
        "role_title": "Backend", "name": "Ada Hunter",
    })
    # The PATCH step was recorded.
    steps = (await session.execute(
        select(CvRunStep).where(CvRunStep.run_id == run.id, CvRunStep.state == RunState.patching)
    )).scalars().all()
    assert len(steps) == 1
    # The delta reports the deterministic fixes + which rules went fail→pass.
    assert len(run.delta["fixed"]) >= 3
    assert {"structure.date_format", "structure.clean_text"} <= set(run.delta["resolved"])
    # No blocking issues remain — the fixes were minor and grounding still holds.
    assert run.delta["blocking"] == []
